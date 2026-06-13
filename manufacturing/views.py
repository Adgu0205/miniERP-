from django.shortcuts import render
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from core.utils import get_current_role, get_current_user, get_role_permissions, record_audit, create_notification, recalculate_stock_quantity, has_page_access
from products.models import Product
from manufacturing.models import BoM, BoMComponent, BoMOperation, ManufacturingOrder, WorkOrder
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

    # Get materials list for selected MO
    materials = []
    all_available = True
    if selected_mo:
        bom = selected_mo.bom
        for comp in bom.components.all():
            total_needed = comp.quantity * selected_mo.quantity
            comp_prod = comp.product
            
            is_reserved = selected_mo.status != 'draft'
            current_reserved = min(total_needed, comp_prod.reserved) if is_reserved else 0
            
            deficit = total_needed - comp_prod.free_to_use
            shortage = deficit > 0
            if shortage:
                all_available = False

            materials.append({
                'name': comp.product.name,
                'unit_needed': comp.quantity,
                'total_needed': total_needed,
                'reserved': current_reserved if is_reserved else min(total_needed, comp_prod.free_to_use),
                'on_hand': comp_prod.on_hand,
                'shortage': shortage
            })

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'mfg_orders': mfg_orders,
        'selected_mo': selected_mo,
        'materials': materials,
        'all_available': all_available,
        'products_with_boms': Product.objects.filter(bom__isnull=False),
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

        product = Product.objects.get(id=product_id)
        if not hasattr(product, 'bom'):
            return JsonResponse({'status': 'error', 'message': 'Product does not have a Bill of Materials recipe.'}, status=400)

        mo = ManufacturingOrder.objects.create(
            product=product,
            quantity=quantity,
            bom=product.bom,
            assignee=assignee,
            status='draft'
        )

        # Create Work Orders from BoM operations
        for idx, op in enumerate(product.bom.operations.all()):
            WorkOrder.objects.create(
                manufacturing_order=mo,
                operation=op.operation_name,
                work_center=op.work_center,
                duration_minutes=op.duration_minutes,
                elapsed_seconds=0,
                status='pending'
            )

        record_audit(request, "Manufacturing", "Order Creation", f"Manufacturing Order MO-{mo.id:03d} created for {product.name}")
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
    for comp in mo.bom.components.all():
        comp_needed = comp.quantity * mo.quantity
        comp.product.reserved += comp_needed
        comp.product.save()
        recalculate_stock_quantity(comp.product.id)

    record_audit(request, "Manufacturing", "Status Change", f"MO-{mo.id:03d} confirmed. Materials reserved.")
    return JsonResponse({'status': 'success', 'message': 'Manufacturing order confirmed.'})

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
    wo.save()

    # Check if all WOs for this MO are completed
    all_completed = mo.work_orders.filter(status='completed').count() == mo.work_orders.count()
    if all_completed:
        mo.status = 'quality_check'
        mo.save()
        create_notification("manufacturing_completion", f"MO-{mo.id:03d} completed assembly. Pending quality check.")

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

    # 1. Deduct component stocks
    for comp in mo.bom.components.all():
        product = comp.product
        consumed_qty = comp.quantity * mo.quantity
        product.on_hand -= consumed_qty
        # Release reserved component stock
        product.reserved = max(0, product.reserved - consumed_qty)
        product.save()

        StockLedgerEntry.objects.create(
            product=product,
            movement_type="Manufacturing Consumption",
            quantity_change=-consumed_qty,
            source_document=f"MO-{mo.id:03d}",
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
        source_document=f"MO-{mo.id:03d}",
        user=get_current_user(request)['name']
    )
    recalculate_stock_quantity(finished_prod.id)

    mo.status = 'completed'
    mo.save()

    # Complete all work orders
    mo.work_orders.update(status='completed')

    record_audit(request, "Manufacturing", "Status Change", f"MO-{mo.id:03d} status changed to completed. Produced {mo.quantity}x {finished_prod.name}")
    create_notification("manufacturing_completion", f"MO-{mo.id:03d} fully manufactured and verified. Added {mo.quantity}x {finished_prod.name} to finished stock.")

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

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'boms': boms,
        'products_without_boms': products_without_boms,
        'components': components
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
            product=product
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

        record_audit(request, "Manufacturing", "BoM Creation", f"Created Bill of Materials for {product.name}")
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

    if mo.status not in ['draft', 'confirmed']:
        return JsonResponse({'status': 'error', 'message': f'Cannot cancel MO in "{mo.status}" state.'}, status=400)

    # Release reserved component stock
    if mo.status == 'confirmed':
        for comp in mo.bom.components.all():
            comp_prod = comp.product
            released = comp.quantity * mo.quantity
            comp_prod.reserved = max(0, comp_prod.reserved - released)
            comp_prod.save()
            recalculate_stock_quantity(comp_prod.id)

    mo.status = 'cancelled'
    mo.save()

    record_audit(request, "Manufacturing", "Order Cancelled", f"Manufacturing Order {mo.ref} cancelled. Component reservations released.")
    create_notification("manufacturing_completion", f"{mo.ref} has been cancelled. Component stock reservations freed.")

    return JsonResponse({'status': 'success', 'message': f'{mo.ref} cancelled successfully.'})
