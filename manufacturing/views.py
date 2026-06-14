from django.shortcuts import render
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from core.utils import get_current_role, get_current_user, get_role_permissions, record_audit, create_notification, recalculate_stock_quantity, has_page_access
from products.models import Product
from manufacturing.models import BoM, BoMComponent, BoMOperation, ManufacturingOrder, WorkOrder, ManufacturingOrderComponent
from inventory.models import StockLedgerEntry

def manufacturing_cockpit(request):
    role = get_current_role(request)
    if not has_page_access(role, "manufacturing_cockpit"):
        return render(request, "no_access.html", {'page_name': 'Manufacturing'})

    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    mfg_orders = ManufacturingOrder.objects.all().order_by('-date')
    products = Product.objects.all()
    boms = BoM.objects.all()

    # Pre-select first MO if available
    selected_mo_id = request.GET.get('mo_id')
    selected_mo = None
    if selected_mo_id:
        selected_mo = ManufacturingOrder.objects.filter(id=selected_mo_id).first()
    elif mfg_orders.exists():
        selected_mo = mfg_orders.first()

    # Calculate next MO Reference ID
    last_mo = ManufacturingOrder.objects.order_by('-id').first()
    next_mo_id = (last_mo.id + 1) if last_mo else 1
    next_mo_ref = f"MO-{next_mo_id:04d}"

    # Get materials list for selected MO
    materials = []
    all_available = True
    if selected_mo:
        for comp in selected_mo.components.all():
            comp_prod = comp.product
            needed = comp.to_consume
            
            # For draft status, free stock check: free_to_use >= to_consume
            # For confirmed/in_progress status, we include its own reservation in available check:
            available_for_mo = comp_prod.free_to_use
            if selected_mo.status != 'draft':
                available_for_mo += needed
                
            shortage = available_for_mo < needed
            if shortage:
                all_available = False

            materials.append({
                'id': comp.id,
                'prod_id': comp_prod.id,
                'name': comp_prod.name,
                'unit_needed': comp.to_consume / selected_mo.quantity if selected_mo.quantity else comp.to_consume,
                'total_needed': needed,
                'consumed': comp.consumed,
                'reserved': min(needed, comp_prod.reserved) if selected_mo.status != 'draft' else min(needed, comp_prod.free_to_use),
                'on_hand': comp_prod.on_hand,
                'shortage': shortage
            })

    # Group manufacturing orders for Kanban columns
    kanban_orders = {
        'draft': mfg_orders.filter(status='draft'),
        'confirmed': mfg_orders.filter(status='confirmed'),
        'in_progress': mfg_orders.filter(status__in=['in_progress', 'quality_check']),
        'completed': mfg_orders.filter(status='completed'),
        'cancelled': mfg_orders.filter(status='cancelled'),
    }

    from audit.models import AuditLog
    mfg_logs = AuditLog.objects.filter(module="Manufacturing").exclude(action__icontains="BoM").order_by('-timestamp')[:50]

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'mfg_orders': mfg_orders,
        'kanban_orders': kanban_orders,
        'selected_mo': selected_mo,
        'materials': materials,
        'all_available': all_available,
        'products_with_boms': Product.objects.filter(bom__isnull=False),
        'products': products,
        'boms': boms,
        'next_mo_ref': next_mo_ref,
        'mfg_logs': mfg_logs,
    }
    return render(request, "manufacturing_cockpit.html", context)

@csrf_exempt
def create_mo(request):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    if request.method == 'POST':
        product_id = request.POST.get('productId')
        quantity = int(request.POST.get('quantity', 1))
        assignee = request.POST.get('assignee', 'John Operative')
        mo_number = request.POST.get('orderNumber')
        bom_id = request.POST.get('bomId')
        planned_date = request.POST.get('plannedDate', '')
        notes = request.POST.get('notes', '')
        components_json = request.POST.get('components', '[]')
        operations_json = request.POST.get('operations', '[]')

        product = Product.objects.get(id=product_id)
        
        if mo_number:
            if ManufacturingOrder.objects.filter(mo_number=mo_number).exists():
                return JsonResponse({'status': 'error', 'message': f'Manufacturing Order ID "{mo_number}" is already taken.'}, status=400)

        selected_bom = None
        if bom_id and bom_id != 'none':
            try:
                selected_bom = BoM.objects.get(id=bom_id)
            except BoM.DoesNotExist:
                pass
        elif hasattr(product, 'bom'):
            selected_bom = product.bom

        mo = ManufacturingOrder.objects.create(
            mo_number=mo_number,
            product=product,
            quantity=quantity,
            bom=selected_bom,
            assignee=assignee,
            status='draft',
            notes=notes
        )

        if planned_date:
            mo.planned_date = planned_date
            mo.save()

        # Populate components from selected BoM
        if selected_bom:
            for comp in selected_bom.components.all():
                ManufacturingOrderComponent.objects.create(
                    manufacturing_order=mo,
                    product=comp.product,
                    to_consume=comp.quantity * quantity,
                    consumed=0
                )
        
        # Add custom components if any provided
        try:
            comps_list = json.loads(components_json)
            for c in comps_list:
                comp_prod = Product.objects.get(id=c['productId'])
                comp_qty = float(c['quantity'])
                # avoid duplicates if already added from BOM
                if not mo.components.filter(product=comp_prod).exists():
                    ManufacturingOrderComponent.objects.create(
                        manufacturing_order=mo,
                        product=comp_prod,
                        to_consume=comp_qty,
                        consumed=0
                    )
        except Exception:
            pass

        # Populate work orders from BoM operations
        if selected_bom:
            for op in selected_bom.operations.all():
                scaled_dur = int(op.duration_minutes * (quantity / selected_bom.quantity_produced)) if selected_bom.quantity_produced else int(op.duration_minutes * quantity)
                WorkOrder.objects.create(
                    manufacturing_order=mo,
                    operation=op.operation_name,
                    work_center=op.work_center,
                    duration_minutes=scaled_dur,
                    elapsed_seconds=0,
                    status='pending'
                )

        # Add custom operations if any provided
        try:
            ops_list = json.loads(operations_json)
            for o in ops_list:
                WorkOrder.objects.create(
                    manufacturing_order=mo,
                    operation=o['name'],
                    work_center=o['workCenter'],
                    duration_minutes=int(o['duration']),
                    elapsed_seconds=0,
                    status='pending'
                )
        except Exception:
            pass

        record_audit(
            request, 
            module="Manufacturing", 
            action="Order Creation", 
            details=f"Manufacturing Order {mo.ref} created for {product.name}",
            record_id=mo.ref,
            record_type="Manufacturing Order",
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Create"
        )
        return JsonResponse({'status': 'success', 'message': 'Manufacturing order saved as draft.', 'mo_id': mo.id})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def confirm_mo(request, mo_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        mo = ManufacturingOrder.objects.get(id=mo_id)
    except ManufacturingOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'MO not found.'}, status=404)

    if mo.status != 'draft':
        return JsonResponse({'status': 'error', 'message': 'Only draft MOs can be confirmed.'}, status=400)

    mo.status = 'confirmed'
    mo.save()

    # Reserve raw materials
    for comp in mo.components.all():
        comp_prod = comp.product
        comp_prod.reserved += comp.to_consume
        comp_prod.save()
        recalculate_stock_quantity(comp_prod.id)

    record_audit(
        request, 
        module="Manufacturing", 
        action="Status Change", 
        details=f"{mo.ref} confirmed. Materials reserved.",
        record_id=mo.ref,
        record_type="Manufacturing Order",
        field_changed="Status",
        old_value="Draft",
        new_value="Confirmed",
        action_type="Update"
    )
    return JsonResponse({'status': 'success', 'message': 'Manufacturing order confirmed.'})

@csrf_exempt
def start_mo(request, mo_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        mo = ManufacturingOrder.objects.get(id=mo_id)
    except ManufacturingOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'MO not found.'}, status=404)

    if mo.status != 'confirmed':
        return JsonResponse({'status': 'error', 'message': 'Only confirmed MOs can be started.'}, status=400)

    mo.status = 'in_progress'
    mo.save()

    record_audit(
        request, 
        module="Manufacturing", 
        action="Status Change", 
        details=f"MO {mo.ref} started. Status is now In Progress.",
        record_id=mo.ref,
        record_type="Manufacturing Order",
        field_changed="Status",
        old_value="Confirmed",
        new_value="In Progress",
        action_type="Update"
    )
    return JsonResponse({'status': 'success', 'message': 'Manufacturing order started.'})

@csrf_exempt
def edit_mo(request, mo_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        mo = ManufacturingOrder.objects.get(id=mo_id)
    except ManufacturingOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'MO not found.'}, status=404)

    if request.method == 'POST':
        product_id = request.POST.get('productId')
        quantity_str = request.POST.get('quantity')
        bom_id = request.POST.get('bomId')
        assignee = request.POST.get('assignee')
        planned_date = request.POST.get('plannedDate')
        notes = request.POST.get('notes', '')

        components_json = request.POST.get('components', '[]')
        operations_json = request.POST.get('operations', '[]')

        # If in draft, we can update core fields (Finished Product, Quantity, BoM)
        if mo.status == 'draft':
            old_qty = int(mo.quantity)
            if product_id:
                mo.product_id = product_id
            if quantity_str:
                mo.quantity = int(quantity_str)
            if bom_id:
                mo.bom_id = bom_id if bom_id != 'none' else None
            if assignee:
                mo.assignee = assignee
            if planned_date:
                mo.planned_date = planned_date
            mo.notes = notes
            mo.save()

            if quantity_str and int(quantity_str) != old_qty:
                record_audit(
                    request,
                    module="Manufacturing",
                    action="Order Edit",
                    details=f"Manufacturing Order {mo.ref} quantity changed from {old_qty} to {mo.quantity}",
                    record_id=mo.ref,
                    record_type="Manufacturing Order",
                    field_changed="Demand",
                    old_value=str(old_qty),
                    new_value=str(int(mo.quantity)),
                    action_type="Update"
                )

            # Sync components
            try:
                comps_data = json.loads(components_json)
                if comps_data:
                    mo.components.all().delete()
                    for c in comps_data:
                        prod = Product.objects.get(id=c['productId'])
                        ManufacturingOrderComponent.objects.create(
                            manufacturing_order=mo,
                            product=prod,
                            to_consume=float(c['quantity']),
                            consumed=0
                        )
            except Exception:
                pass

            # Sync operations
            try:
                ops_data = json.loads(operations_json)
                if ops_data:
                    mo.work_orders.all().delete()
                    for o in ops_data:
                        WorkOrder.objects.create(
                            manufacturing_order=mo,
                            operation=o['name'],
                            work_center=o['workCenter'],
                            duration_minutes=int(o['duration']),
                            status='pending'
                        )
            except Exception:
                pass

        # If in Confirmed or In Progress, we cannot update product/bom/quantity.
        # But we can update assignee, planned date, components consumed, and operations real duration.
        if mo.status in ['confirmed', 'in_progress']:
            if assignee:
                mo.assignee = assignee
            if planned_date:
                mo.planned_date = planned_date
            mo.notes = notes
            mo.save()

            # Update consumed quantities
            try:
                comps_data = json.loads(components_json)
                for c in comps_data:
                    comp_id = c.get('id')
                    consumed_val = float(c.get('consumed', 0))
                    if comp_id:
                        comp_line = mo.components.get(id=comp_id)
                        old_consumed = float(comp_line.consumed)
                        if old_consumed != consumed_val:
                            comp_line.consumed = consumed_val
                            comp_line.save()
                            # Record audit log for consumed quantity change
                            record_audit(
                                request,
                                module="Manufacturing",
                                action="Material Consumption Update",
                                details=f"Updated consumed quantity for {comp_line.product.name} in {mo.ref} from {old_consumed} to {consumed_val}",
                                record_id=f"MC-2026-{comp_line.id:03d}",
                                record_type="Material Consumption",
                                field_changed="Consumed Qty",
                                old_value=str(int(old_consumed) if old_consumed.is_integer() else old_consumed),
                                new_value=str(int(consumed_val) if consumed_val.is_integer() else consumed_val),
                                action_type="Update"
                            )
                        else:
                            comp_line.consumed = consumed_val
                            comp_line.save()
            except Exception:
                pass

            # Update real durations
            try:
                ops_data = json.loads(operations_json)
                for o in ops_data:
                    wo_id = o.get('id')
                    real_dur = int(o.get('realDuration', 0))
                    if wo_id:
                        wo_line = mo.work_orders.get(id=wo_id)
                        wo_line.real_duration_minutes = real_dur
                        wo_line.save()
            except Exception:
                pass

        record_audit(
            request, 
            module="Manufacturing", 
            action="Order Edit", 
            details=f"Manufacturing Order {mo.ref} updated.",
            record_id=mo.ref,
            record_type="Manufacturing Order",
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Update"
        )
        return JsonResponse({'status': 'success', 'message': 'Manufacturing order updated successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def start_work_order(request, wo_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        wo = WorkOrder.objects.get(id=wo_id)
    except WorkOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Work Order not found.'}, status=404)

    mo = wo.manufacturing_order
    wo.status = 'active'
    from django.utils import timezone as tz
    if not wo.started_at:
        wo.started_at = tz.now()
    wo.save()

    if mo.status == 'confirmed':
        mo.status = 'in_progress'
        mo.save()

    return JsonResponse({'status': 'success', 'message': 'Work order started.'})

@csrf_exempt
def complete_work_order(request, wo_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        wo = WorkOrder.objects.get(id=wo_id)
    except WorkOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Work Order not found.'}, status=404)

    mo = wo.manufacturing_order
    wo.status = 'completed'

    # Save simulated timer duration and completion timestamp
    from django.utils import timezone as tz
    elapsed = int(request.POST.get('elapsed_seconds', wo.duration_minutes * 60))
    wo.elapsed_seconds = elapsed
    wo.completed_at = tz.now()
    if not wo.started_at:
        wo.started_at = tz.now()
    # Save real_duration_minutes from timer (elapsed seconds / 60)
    wo.real_duration_minutes = int(elapsed / 60)
    wo.save()

    # Check if all WOs for this MO are completed
    all_completed = mo.work_orders.filter(status='completed').count() == mo.work_orders.count()
    if all_completed:
        mo.status = 'quality_check'
        mo.save()
        create_notification("manufacturing_completion", f"{mo.ref} completed assembly. Pending quality check.")

    return JsonResponse({'status': 'success', 'message': 'Work order completed.', 'all_done': all_completed})

@csrf_exempt
def complete_mo(request, mo_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        mo = ManufacturingOrder.objects.get(id=mo_id)
    except ManufacturingOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'MO not found.'}, status=404)

    if mo.status not in ['quality_check', 'in_progress', 'confirmed']:
        return JsonResponse({'status': 'error', 'message': 'MO is not in finishable state.'}, status=400)

    # 1. Deduct component stocks based on actual consumed quantity
    for comp in mo.components.all():
        product = comp.product
        consumed_qty = comp.consumed
        product.on_hand -= consumed_qty
        
        # Release reserved component stock
        released_reserve = min(product.reserved, comp.to_consume)
        product.reserved = max(0, product.reserved - released_reserve)
        product.save()

        StockLedgerEntry.objects.create(
            product=product,
            movement_type="Manufacturing Consumption",
            quantity_change=-consumed_qty,
            source_document=mo.ref,
            user=get_current_user(request)['name']
        )
        recalculate_stock_quantity(product.id)

    # 2. Add finished goods to stock
    finished_prod = mo.product
    finished_prod.on_hand += mo.quantity
    finished_prod.save()

    StockLedgerEntry.objects.create(
        product=finished_prod,
        movement_type="Manufacturing Production",
        quantity_change=mo.quantity,
        source_document=mo.ref,
        user=get_current_user(request)['name']
    )
    recalculate_stock_quantity(finished_prod.id)

    mo.status = 'completed'
    mo.save()

    # Complete all work orders
    mo.work_orders.update(status='completed')

    record_audit(
        request, 
        module="Manufacturing", 
        action="Status Change", 
        details=f"{mo.ref} status changed to completed. Produced {mo.quantity}x {finished_prod.name}",
        record_id=mo.ref,
        record_type="Manufacturing Order",
        field_changed="Status",
        old_value="In Progress",
        new_value="Completed",
        action_type="Update"
    )
    create_notification("manufacturing_completion", f"{mo.ref} fully manufactured and verified. Added {mo.quantity}x {finished_prod.name} to finished stock.")

    return JsonResponse({'status': 'success', 'message': 'Manufacturing order completed successfully.'})

def bom_list(request):
    role = get_current_role(request)
    if not has_page_access(role, "bom_list"):
        return render(request, "no_access.html", {'page_name': 'Bills of Material'})

    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    boms = BoM.objects.all()
    products_without_boms = Product.objects.filter(category='Furniture', bom__isnull=True)
    components = Product.objects.filter(category='Components')

    # Calculate next BoM Reference ID
    last_bom = BoM.objects.order_by('-id').first()
    next_bom_id = (last_bom.id + 1) if last_bom else 1
    next_bom_ref = f"BOM-{next_bom_id:06d}"

    from audit.models import AuditLog
    bom_logs = AuditLog.objects.filter(module="Manufacturing", action__icontains="BoM").order_by('-timestamp')[:50]

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'boms': boms,
        'products_without_boms': products_without_boms,
        'components': components,
        'products': Product.objects.all(),
        'next_bom_ref': next_bom_ref,
        'bom_logs': bom_logs
    }
    return render(request, "bom_list.html", context)

@csrf_exempt
def create_bom(request):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_bom'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    if request.method == 'POST':
        product_id = request.POST.get('productId')
        comps_raw = request.POST.get('components', '[]')
        ops_raw = request.POST.get('operations', '[]')
        qty_produced = float(request.POST.get('quantityProduced', 1.00))
        reference = request.POST.get('reference', '')

        try:
            comps = json.loads(comps_raw)
            ops = json.loads(ops_raw)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data formats.'}, status=400)

        product = Product.objects.get(id=product_id)
        if hasattr(product, 'bom'):
            return JsonResponse({'status': 'error', 'message': 'Product already has a recipe.'}, status=400)

        bom = BoM.objects.create(
            name=f"Bill of Materials - {product.name}",
            product=product,
            quantity_produced=qty_produced,
            reference=reference
        )

        for c in comps:
            comp_prod = Product.objects.get(id=c['productId'])
            qty = int(c['quantity'])
            BoMComponent.objects.create(bom=bom, product=comp_prod, quantity=qty)

        for o in ops:
            BoMOperation.objects.create(
                bom=bom,
                operation_name=o['name'],
                work_center=o['workCenter'],
                duration_minutes=int(o['duration'])
            )

        record_audit(
            request, 
            module="Manufacturing", 
            action="BoM Creation", 
            details=f"Created Bill of Materials for {product.name}",
            record_id=bom.bom_code,
            record_type="BOM",
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Create"
        )
        return JsonResponse({'status': 'success', 'message': 'Bill of Materials recipe created.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

# ─── P1: Cancel Manufacturing Order ───────────────────────────────────────
@csrf_exempt
def cancel_mo(request, mo_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_manufacturing'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        mo = ManufacturingOrder.objects.get(id=mo_id)
    except ManufacturingOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Manufacturing Order not found.'}, status=404)

    if mo.status not in ['draft', 'confirmed', 'in_progress']:
        return JsonResponse({'status': 'error', 'message': f'Cannot cancel MO in "{mo.status}" state.'}, status=400)

    # Release reserved component stock
    if mo.status in ['confirmed', 'in_progress']:
        for comp in mo.components.all():
            comp_prod = comp.product
            released = comp.to_consume
            comp_prod.reserved = max(0, comp_prod.reserved - released)
            comp_prod.save()
            recalculate_stock_quantity(comp_prod.id)

    old_status = mo.status.title() if mo.status else "Draft"
    mo.status = 'cancelled'
    mo.save()

    record_audit(
        request, 
        module="Manufacturing", 
        action="Order Cancelled", 
        details=f"Manufacturing Order {mo.ref} cancelled. Component reservations released.",
        record_id=mo.ref,
        record_type="Manufacturing Order",
        field_changed="Status",
        old_value=old_status,
        new_value="Cancelled",
        action_type="Update"
    )
    create_notification("manufacturing_completion", f"{mo.ref} has been cancelled. Component stock reservations freed.")

    return JsonResponse({'status': 'success', 'message': f'{mo.ref} cancelled successfully.'})
