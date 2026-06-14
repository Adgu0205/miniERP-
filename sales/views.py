from django.shortcuts import render
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from core.utils import get_current_role, get_current_user, get_role_permissions, record_audit, create_notification, recalculate_stock_quantity, has_page_access
from products.models import Product
from sales.models import SalesOrder, SalesOrderItem
from purchases.models import PurchaseOrder, PurchaseOrderItem
from manufacturing.models import ManufacturingOrder, WorkOrder, BoM
from inventory.models import StockLedgerEntry

def sales_pipeline(request):
    role = get_current_role(request)
    if not has_page_access(role, "sales_pipeline"):
        return render(request, "no_access.html", {'page_name': 'Sales Orders'})

    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    sales_orders = SalesOrder.objects.all().order_by('-date')
    products = Product.objects.filter(sales_price__gt=0)

    # Calculate next Sales Order ID for dialog box
    last_so = SalesOrder.objects.order_by('-id').first()
    next_so_id = (last_so.id + 1) if last_so else 1
    next_so_ref = f"SO-{next_so_id:03d}"

    # Group sales orders for Kanban columns
    kanban_orders = {
        'draft': sales_orders.filter(status='draft'),
        'confirmed': sales_orders.filter(status='confirmed'),
        'partially_delivered': sales_orders.filter(status='partially_delivered'),
        'fully_delivered': sales_orders.filter(status='fully_delivered'),
        'cancelled': sales_orders.filter(status='cancelled'),
    }

    # Gather trace documents for each sales order in view
    traces = {}
    mfg_orders = ManufacturingOrder.objects.all()
    po_orders = PurchaseOrder.objects.all()
    
    for so in sales_orders:
        linked_mos = list(mfg_orders.filter(source_document=f"SO-{so.id:03d}"))
        linked_pos = list(po_orders.filter(source_document=f"SO-{so.id:03d}"))
        
        # Include component POs linked to MOs
        for mo in linked_mos:
            comp_pos = po_orders.filter(source_document=f"MO-{mo.id:03d}")
            for po in comp_pos:
                if po not in linked_pos:
                    linked_pos.append(po)

        traces[so.id] = {
            'mos': [{'id': f"MO-{mo.id:03d}", 'status': mo.status} for mo in linked_mos],
            'pos': [{'id': f"PO-{po.id:03d}", 'status': po.status} for po in linked_pos],
            'has_chain': len(linked_mos) > 0 or len(linked_pos) > 0
        }

    from audit.models import AuditLog
    sales_logs = AuditLog.objects.filter(module__in=["Sales", "Procurement"]).order_by('-timestamp')[:50]

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'kanban_orders': kanban_orders,
        'products': products,
        'sales_orders': sales_orders,
        'traces': traces,
        'traces_json': json.dumps(traces),
        'next_so_ref': next_so_ref,
        'sales_logs': sales_logs,
    }
    return render(request, "sales_pipeline.html", context)

@csrf_exempt
def create_sales_order(request):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_sales'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    if request.method == 'POST':
        customer_name = request.POST.get('customerName')
        customer_address = request.POST.get('customerAddress', '')
        sales_person = request.POST.get('salesPerson', '')
        order_number = request.POST.get('orderNumber', '').strip()
        items_json = request.POST.get('items')
        
        if order_number:
            if SalesOrder.objects.filter(order_number=order_number).exists():
                return JsonResponse({'status': 'error', 'message': f'Sales Order ID "{order_number}" is already taken.'}, status=400)

        try:
            items_data = json.loads(items_json)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid items lines data.'}, status=400)

        if not items_data:
            return JsonResponse({'status': 'error', 'message': 'Order lines cannot be empty.'}, status=400)

        # Create SalesOrder header
        so = SalesOrder.objects.create(
            order_number=order_number if order_number else None,
            customer_name=customer_name,
            customer_address=customer_address,
            sales_person=sales_person,
            status='draft'
        )

        total_amount = 0
        for item in items_data:
            product = Product.objects.get(id=item['productId'])
            qty = int(item['quantity'])
            price = float(item['unitPrice'])
            
            SalesOrderItem.objects.create(
                sales_order=so,
                product=product,
                quantity=qty,
                unit_price=price,
                delivered_quantity=0
            )
            total_amount += qty * price

        so.total_amount = total_amount
        so.procurement_group_id = f"proc-grp-{so.id:03d}-{int(so.date.timestamp())}"
        so.created_by = get_current_user(request)['name']
        notes = request.POST.get('notes', '')
        expected_date = request.POST.get('expectedDeliveryDate', '')
        if notes:
            so.notes = notes
        if expected_date:
            so.expected_delivery_date = expected_date
        so.save()

        record_audit(
            request, 
            module="Sales", 
            action="Order Creation", 
            details=f"Sales Order SO-{so.id:03d} created for {customer_name}",
            record_id=f"SO-{so.id:03d}",
            record_type="Sales Order",
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Create"
        )
        return JsonResponse({'status': 'success', 'message': 'Sales order draft saved.', 'so_id': so.id})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def edit_sales_order(request, so_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_sales'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        so = SalesOrder.objects.get(id=so_id)
    except SalesOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sales Order not found.'}, status=404)

    if request.method == 'POST':
        customer_name = request.POST.get('customerName')
        customer_address = request.POST.get('customerAddress', '')
        sales_person = request.POST.get('salesPerson', '')
        expected_date = request.POST.get('expectedDeliveryDate', '')
        notes = request.POST.get('notes', '')
        items_json = request.POST.get('items', '[]')

        try:
            items_data = json.loads(items_json)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid items lines data.'}, status=400)

        # Release stock reservation if order was confirmed/partially delivered
        if so.status in ['confirmed', 'partially_delivered']:
            for item in so.items.all():
                prod = item.product
                to_deliver = item.quantity - item.delivered_quantity
                if to_deliver > 0:
                    prod.reserved = max(0, prod.reserved - to_deliver)
                    prod.save()
                    recalculate_stock_quantity(prod.id)

        # Update order header
        so.customer_name = customer_name
        so.customer_address = customer_address
        so.sales_person = sales_person
        so.notes = notes
        if expected_date:
            so.expected_delivery_date = expected_date
        else:
            so.expected_delivery_date = None

        # Update lines
        existing_items = {item.product_id: item for item in so.items.all()}
        new_product_ids = set()
        total_amount = 0

        for item in items_data:
            prod_id = int(item['productId'])
            qty = int(item['quantity'])
            price = float(item['unitPrice'])
            new_product_ids.add(prod_id)

            if prod_id in existing_items:
                line = existing_items[prod_id]
                line.quantity = qty
                line.unit_price = price
                # Ensure delivered_quantity is capped at new quantity
                if line.delivered_quantity > qty:
                    line.delivered_quantity = qty
                line.save()
            else:
                SalesOrderItem.objects.create(
                    sales_order=so,
                    product_id=prod_id,
                    quantity=qty,
                    unit_price=price,
                    delivered_quantity=0
                )
            total_amount += qty * price

        # Delete removed items
        for prod_id, line in existing_items.items():
            if prod_id not in new_product_ids:
                line.delete()

        # Re-apply reservation if order was confirmed/partially delivered
        if so.status in ['confirmed', 'partially_delivered']:
            for item in so.items.all():
                prod = item.product
                to_deliver = item.quantity - item.delivered_quantity
                if to_deliver > 0:
                    prod.reserved += to_deliver
                    prod.save()
                    recalculate_stock_quantity(prod.id)

        so.total_amount = total_amount
        so.save()

        # Update status if fully delivered or confirmed
        if so.status in ['confirmed', 'partially_delivered']:
            all_delivered = True
            for item in so.items.all():
                if item.delivered_quantity < item.quantity:
                    all_delivered = False
                    break
            so.status = 'fully_delivered' if all_delivered else 'partially_delivered'
            so.save()

        record_audit(
            request, 
            module="Sales", 
            action="Order Edit", 
            details=f"Sales Order {so.ref} updated.",
            record_id=so.ref,
            record_type="Sales Order",
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Update"
        )
        return JsonResponse({'status': 'success', 'message': 'Sales order updated successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

@csrf_exempt
def confirm_sales_order(request, so_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_sales'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        so = SalesOrder.objects.get(id=so_id)
    except SalesOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sales Order not found.'}, status=404)

    if so.status != 'draft':
        return JsonResponse({'status': 'error', 'message': 'Only draft orders can be confirmed.'}, status=400)

    # Perform stock check and reserve
    shortages = []
    items_to_reserve = []

    for item in so.items.all():
        product = item.product
        needed = item.quantity
        available = product.free_to_use

        if available >= needed:
            items_to_reserve.append((product, needed))
        else:
            if available > 0:
                items_to_reserve.append((product, available))
            
            shortage_qty = needed - available
            rec = get_python_recommendation(product, shortage_qty)
            shortages.append({
                'productId': product.id,
                'productName': product.name,
                'sku': product.sku,
                'needed': needed,
                'available': available,
                'shortage': shortage_qty,
                'procureStrategy': product.procure_strategy,
                'procureType': product.procurement_type,
                'bomId': product.bom.id if hasattr(product, 'bom') else None,
                'vendor': product.vendor,
                'recommendation': rec['recommendation'],
                'reason': rec['reason'],
                'action_code': rec['action_code'],
                'missing_components': rec['missing_components']
            })

    # If it is a dry-run checking shortages, return them
    is_dry_run = request.POST.get('dry_run', 'false') == 'true'
    trigger_procurement = request.POST.get('trigger_procurement', 'false') == 'true'

    if is_dry_run:
        return JsonResponse({
            'status': 'shortage' if shortages else 'success',
            'shortages': shortages
        })

    # Actually execute confirmation
    so.status = 'confirmed'
    so.save()

    # Reserve the available stock
    for product, qty in items_to_reserve:
        product.reserved += qty
        product.save()
        recalculate_stock_quantity(product.id)

    record_audit(
        request, 
        module="Sales", 
        action="Status Change", 
        details=f"Sales Order SO-{so.id:03d} confirmed",
        record_id=f"SO-{so.id:03d}",
        record_type="Sales Order",
        field_changed="Status",
        old_value="Draft",
        new_value="Confirmed",
        action_type="Update"
    )

    # If user confirmed auto-replenish, execute MTO
    if shortages and trigger_procurement:
        execute_python_mto(request, so, shortages)
        record_audit(request, "Procurement", "MTO Trigger", f"MTO replenishment executed for SO-{so.id:03d}")

    return JsonResponse({
        'status': 'success',
        'message': 'Sales Order confirmed.',
        'has_shortages': bool(shortages)
    })

@csrf_exempt
def deliver_sales_order(request, so_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_sales'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        so = SalesOrder.objects.get(id=so_id)
    except SalesOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sales Order not found.'}, status=404)

    if so.status not in ['confirmed', 'partially_delivered']:
        return JsonResponse({'status': 'error', 'message': 'Order is not in deliverable state.'}, status=400)

    if request.method == 'POST':
        ship_data_raw = request.POST.get('deliveries', '{}')
        try:
            ship_data = json.loads(ship_data_raw)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid delivery quantities data.'}, status=400)

        all_fully_delivered = True

        for item in so.items.all():
            product = item.product
            new_cumulative = int(ship_data.get(str(product.id), item.delivered_quantity))
            
            # Bound new_cumulative between item.delivered_quantity and item.quantity
            new_cumulative = max(item.delivered_quantity, min(item.quantity, new_cumulative))
            qty_to_deliver = new_cumulative - item.delivered_quantity

            if qty_to_deliver <= 0:
                if item.delivered_quantity < item.quantity:
                    all_fully_delivered = False
                continue

            # Cap delivery at available physical stock
            actual_delivery = min(qty_to_deliver, product.on_hand)
            if actual_delivery <= 0:
                all_fully_delivered = False
                continue

            # Decrement physical stock
            product.on_hand -= actual_delivery
            
            # Decrease reservation pool
            remaining_to_deliver = item.quantity - item.delivered_quantity
            reservation_deduction = min(actual_delivery, remaining_to_deliver)
            product.reserved = max(0, product.reserved - reservation_deduction)
            product.save()

            item.delivered_quantity += actual_delivery
            item.save()

            # Record Ledger entry
            StockLedgerEntry.objects.create(
                product=product,
                movement_type="Sales Delivery",
                quantity_change=-actual_delivery,
                source_document=f"SO-{so.id:03d}",
                user=get_current_user(request)['name']
            )

            recalculate_stock_quantity(product.id)

            if item.delivered_quantity < item.quantity:
                all_fully_delivered = False

        so.status = 'fully_delivered' if all_fully_delivered else 'partially_delivered'
        so.save()

        record_audit(
            request, 
            module="Sales", 
            action="Order Delivery", 
            details=f"Sales Order SO-{so.id:03d} delivery processed. Status is now {so.status.replace('_', ' ')}",
            record_id=f"SO-{so.id:03d}",
            record_type="Sales Order",
            field_changed="Status",
            old_value="Confirmed",
            new_value=so.status.replace('_', ' ').title(),
            action_type="Update"
        )
        create_notification("sales_delivered", f"SO-{so.id:03d} shipment dispatched. Status: {so.status.replace('_', ' ')}")

        return JsonResponse({'status': 'success', 'message': 'Delivery processed successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

# Python Procurement Recommendation implementation
def get_python_recommendation(product, quantity):
    if hasattr(product, 'bom'):
        bom = product.bom
        missing_components = []
        can_manufacture = True

        for comp in bom.components.all():
            total_needed = comp.quantity * quantity
            if comp.product.free_to_use < total_needed:
                can_manufacture = False
                missing_components.append({
                    'productId': comp.product.id,
                    'name': comp.product.name,
                    'sku': comp.product.sku,
                    'needed': total_needed,
                    'available': comp.product.free_to_use,
                    'deficit': total_needed - comp.product.free_to_use,
                    'vendor': comp.product.vendor
                })

        if can_manufacture:
            return {
                'recommendation': 'Manufacture',
                'reason': f"Recommended to <strong>Manufacture</strong> {quantity} units of {product.name}. All required raw materials are available in free inventory. Operations can begin immediately.",
                'action_code': 'mfg',
                'missing_components': []
            }
        else:
            missing_details = ", ".join(f"{c['name']} (Short by {c['deficit']} units)" for c in missing_components)
            return {
                'recommendation': 'Purchase Components & Manufacture',
                'reason': f"Shortage of raw materials detected: {missing_details}. Recommended action: <strong>Purchase components</strong> from their respective vendors, then proceed with Manufacturing.",
                'action_code': 'purchase_components',
                'missing_components': missing_components
            }

    return {
        'recommendation': 'Purchase',
        'reason': f"Recommended to <strong>Purchase</strong> {quantity} units of {product.name} from preferred vendor <strong>{product.vendor or 'Unknown Vendor'}</strong>.",
        'action_code': 'buy',
        'missing_components': []
    }

# Execute MTO automation
def execute_python_mto(request, sales_order, shortages):
    user_name = get_current_user(request)['name']
    
    for short in shortages:
        prod = Product.objects.get(id=short['productId'])
        shortage_qty = short['shortage']
        
        if short['procureType'] == 'Manufacturing' and short['bomId']:
            bom = BoM.objects.get(id=short['bomId'])
            # 1. Create MO
            mo = ManufacturingOrder.objects.create(
                product=prod,
                quantity=shortage_qty,
                bom=bom,
                assignee="Auto MTO Engine",
                status='confirmed', # Auto-confirm MO
                source_document=f"SO-{sales_order.id:03d}",
                procurement_group_id=sales_order.procurement_group_id
            )

            # Create Work Orders
            for idx, op in enumerate(bom.operations.all()):
                WorkOrder.objects.create(
                    manufacturing_order=mo,
                    name=op.name,
                    work_center=op.work_center,
                    duration=op.duration,
                    elapsed_seconds=0,
                    status='pending'
                )

            # Reserve component stock for the MO
            for comp in bom.components.all():
                comp_needed = comp.quantity * shortage_qty
                comp.product.reserved += comp_needed
                comp.product.save()
                recalculate_stock_quantity(comp.product.id)

            record_audit(request, "Procurement", "Auto Replenish", f"Automatically created and confirmed Manufacturing Order MO-{mo.id:03d} for {shortage_qty} units to satisfy SO-{sales_order.id:03d}")
            create_notification("procurement_created", f"MTO Automation: Created MO-{mo.id:03d} for {shortage_qty}x {prod.name} linked to SO-{sales_order.id:03d}")

            # If components are short, recursively create POs
            if short['action_code'] == 'purchase_components':
                for comp in short['missing_components']:
                    comp_prod = Product.objects.get(id=comp['productId'])
                    po = PurchaseOrder.objects.create(
                        vendor_name=comp['vendor'] or "Default Supplier",
                        total_amount=comp_prod.cost_price * comp['deficit'],
                        status='confirmed',
                        source_document=f"MO-{mo.id:03d}"
                    )
                    PurchaseOrderItem.objects.create(
                        purchase_order=po,
                        product=comp_prod,
                        quantity=comp['deficit'],
                        unit_cost=comp_prod.cost_price,
                        received_quantity=0
                    )
                    record_audit(request, "Procurement", "Component Auto PO", f"Automatically created confirmed Purchase Order PO-{po.id:03d} for component {comp['name']} (Qty: {comp['deficit']}) to satisfy MO-{mo.id:03d}")
                    create_notification("procurement_created", f"MTO Automation: Created PO-{po.id:03d} for raw component {comp['name']} linked to manufacturing queue.")

        elif short['procureType'] == 'Purchase':
            # Create PO
            po = PurchaseOrder.objects.create(
                vendor_name=short['vendor'] or "Default Supplier",
                total_amount=prod.cost_price * shortage_qty,
                status='confirmed',
                source_document=f"SO-{sales_order.id:03d}"
            )
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                product=prod,
                quantity=shortage_qty,
                unit_cost=prod.cost_price,
                received_quantity=0
            )
            record_audit(request, "Procurement", "Auto Replenish", f"Automatically created and confirmed Purchase Order PO-{po.id:03d} for {shortage_qty} units to satisfy SO-{sales_order.id:03d}")
            create_notification("procurement_created", f"MTO Automation: Created PO-{po.id:03d} for {shortage_qty}x {prod.name} linked to SO-{sales_order.id:03d}")

# ─── P1: Cancel Sales Order ────────────────────────────────────────────────
@csrf_exempt
def cancel_sales_order(request, so_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_sales'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        so = SalesOrder.objects.get(id=so_id)
    except SalesOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Sales Order not found.'}, status=404)

    if so.status not in ['draft', 'confirmed', 'partially_delivered']:
        return JsonResponse({'status': 'error', 'message': f'Cannot cancel order in "{so.status}" state.'}, status=400)

    # Release reserved stock for each item
    for item in so.items.all():
        product = item.product
        released = min(item.quantity - item.delivered_quantity, product.reserved)
        if released > 0:
            product.reserved = max(0, product.reserved - released)
            product.save()
            recalculate_stock_quantity(product.id)

    so.status = 'cancelled'
    so.save()

    record_audit(
        request, 
        module="Sales", 
        action="Order Cancelled", 
        details=f"Sales Order {so.ref} cancelled. Reserved stock released.",
        record_id=so.ref,
        record_type="Sales Order",
        field_changed="Status",
        old_value="Confirmed",
        new_value="Cancelled",
        action_type="Update"
    )
    create_notification("sales_delivered", f"{so.ref} has been cancelled. Reserved quantities released back to free stock.")

    return JsonResponse({'status': 'success', 'message': f'{so.ref} cancelled successfully.'})
