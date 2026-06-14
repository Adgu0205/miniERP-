from django.shortcuts import render
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from core.utils import get_current_role, get_current_user, get_role_permissions, record_audit, create_notification, recalculate_stock_quantity, has_page_access
from products.models import Product
from purchases.models import PurchaseOrder, PurchaseOrderItem
from inventory.models import StockLedgerEntry

def purchase_list(request):
    role = get_current_role(request)
    if not has_page_access(role, "purchase_list"):
        return render(request, "no_access.html", {'page_name': 'Purchase Orders'})

    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    purchase_orders = PurchaseOrder.objects.all().order_by('-date')
    products = Product.objects.all()

    # Calculate next Purchase Order ID
    last_po = PurchaseOrder.objects.order_by('-id').first()
    next_po_id = (last_po.id + 1) if last_po else 1
    next_po_ref = f"PO-{next_po_id:03d}"

    # Group purchase orders for Kanban columns
    kanban_orders = {
        'draft': purchase_orders.filter(status='draft'),
        'confirmed': purchase_orders.filter(status='confirmed'),
        'partially_received': purchase_orders.filter(status='partially_received'),
        'fully_received': purchase_orders.filter(status='fully_received'),
        'cancelled': purchase_orders.filter(status='cancelled'),
    }

    from audit.models import AuditLog
    purchase_logs = AuditLog.objects.filter(module="Purchases").order_by('-timestamp')[:50]

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'purchase_orders': purchase_orders,
        'kanban_orders': kanban_orders,
        'products': products,
        'next_po_ref': next_po_ref,
        'purchase_logs': purchase_logs,
    }
    return render(request, "purchase_list.html", context)

@csrf_exempt
def create_purchase_order(request):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_purchases'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    if request.method == 'POST':
        vendor_name = request.POST.get('vendorName')
        vendor_address = request.POST.get('vendorAddress', '')
        responsible_person = request.POST.get('responsiblePerson', '')
        po_number = request.POST.get('orderNumber')
        expected_receipt_date = request.POST.get('expectedReceiptDate', '')
        notes = request.POST.get('notes', '')
        items_json = request.POST.get('items')
        
        try:
            items_data = json.loads(items_json)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid items lines data.'}, status=400)

        if not items_data:
            return JsonResponse({'status': 'error', 'message': 'Order lines cannot be empty.'}, status=400)

        if po_number:
            if PurchaseOrder.objects.filter(po_number=po_number).exists():
                return JsonResponse({'status': 'error', 'message': f'Purchase Order ID "{po_number}" is already taken.'}, status=400)

        po = PurchaseOrder.objects.create(
            po_number=po_number,
            vendor_name=vendor_name,
            vendor_address=vendor_address,
            responsible_person=responsible_person,
            notes=notes,
            status='draft'
        )

        if expected_receipt_date:
            po.expected_receipt_date = expected_receipt_date
            po.save()

        total_amount = 0
        for item in items_data:
            product = Product.objects.get(id=item['productId'])
            qty = int(item['quantity'])
            cost = float(item['unitPrice'])
            
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                product=product,
                quantity=qty,
                unit_cost=cost,
                received_quantity=0
            )
            total_amount += qty * cost

        po.total_amount = total_amount
        po.save()

        record_audit(
            request, 
            module="Purchase", 
            action="Order Creation", 
            details=f"Purchase Order {po.ref} created for vendor {vendor_name}",
            record_id=po.ref,
            record_type="Purchase Order",
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Create"
        )
        return JsonResponse({'status': 'success', 'message': 'Purchase RFQ draft saved.', 'po_id': po.id})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def confirm_purchase_order(request, po_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_purchases'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        po = PurchaseOrder.objects.get(id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Purchase Order not found.'}, status=404)

    if po.status != 'draft':
        return JsonResponse({'status': 'error', 'message': 'Only draft POs can be confirmed.'}, status=400)

    po.status = 'confirmed'
    po.save()

    record_audit(
        request, 
        module="Purchase", 
        action="Status Change", 
        details=f"Purchase Order {po.ref} confirmed",
        record_id=po.ref,
        record_type="Purchase Order",
        field_changed="Status",
        old_value="Draft",
        new_value="Confirmed",
        action_type="Update"
    )
    return JsonResponse({'status': 'success', 'message': 'Purchase Order confirmed.'})

@csrf_exempt
def receive_purchase_order(request, po_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_purchases'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        po = PurchaseOrder.objects.get(id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Purchase Order not found.'}, status=404)

    if po.status not in ['confirmed', 'partially_received']:
        return JsonResponse({'status': 'error', 'message': 'Order is not in receivable state.'}, status=400)

    if request.method == 'POST':
        receipt_data_raw = request.POST.get('receipts', '{}')
        try:
            receipt_data = json.loads(receipt_data_raw)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid receipt quantities.'}, status=400)

        all_fully_received = True

        for item in po.items.all():
            product = item.product
            new_cumulative = int(receipt_data.get(str(product.id), item.received_quantity))
            
            # Bound new_cumulative between item.received_quantity and item.quantity
            new_cumulative = max(item.received_quantity, min(item.quantity, new_cumulative))
            qty_to_receive = new_cumulative - item.received_quantity

            if qty_to_receive <= 0:
                if item.received_quantity < item.quantity:
                    all_fully_received = False
                continue

            # Increment physical inventory
            product.on_hand += qty_to_receive
            product.save()

            item.received_quantity += qty_to_receive
            item.save()

            # Record Ledger entry
            StockLedgerEntry.objects.create(
                product=product,
                movement_type="Purchase Receipt",
                quantity_change=qty_to_receive,
                source_document=f"PO-{po.id:03d}",
                user=get_current_user(request)['name']
            )

            recalculate_stock_quantity(product.id)

            if item.received_quantity < item.quantity:
                all_fully_received = False

        po.status = 'fully_received' if all_fully_received else 'partially_received'
        po.save()

        record_audit(
            request, 
            module="Purchase", 
            action="Receipt Validation", 
            details=f"{po.ref} received items. Status: {po.status.replace('_', ' ')}",
            record_id=po.ref,
            record_type="Purchase Order",
            field_changed="Status",
            old_value="Confirmed",
            new_value=po.status.replace('_', ' ').title(),
            action_type="Update"
        )
        create_notification("purchase_received", f"{po.ref} materials received: status is now {po.status.replace('_', ' ')}")

        return JsonResponse({'status': 'success', 'message': 'Receipt processed successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

# ─── P1: Cancel Purchase Order ────────────────────────────────────────────
@csrf_exempt
def cancel_purchase_order(request, po_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_purchases'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        po = PurchaseOrder.objects.get(id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Purchase Order not found.'}, status=404)

    if po.status not in ['draft', 'confirmed', 'partially_received']:
        return JsonResponse({'status': 'error', 'message': f'Cannot cancel PO in "{po.status}" state.'}, status=400)

    po.status = 'cancelled'
    po.save()

    record_audit(
        request, 
        module="Purchase", 
        action="Order Cancelled", 
        details=f"Purchase Order {po.ref} cancelled. No stock changes applied.",
        record_id=po.ref,
        record_type="Purchase Order",
        field_changed="Status",
        old_value="Confirmed",
        new_value="Cancelled",
        action_type="Update"
    )
    create_notification("purchase_received", f"{po.ref} has been cancelled by {get_current_user(request)['name']}.")

    return JsonResponse({'status': 'success', 'message': f'{po.ref} cancelled successfully.'})

@csrf_exempt
def edit_purchase_order(request, po_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_purchases'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    try:
        po = PurchaseOrder.objects.get(id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Purchase Order not found.'}, status=404)

    if request.method == 'POST':
        vendor_name = request.POST.get('vendorName')
        vendor_address = request.POST.get('vendorAddress', '')
        responsible_person = request.POST.get('responsiblePerson', '')
        expected_receipt_date = request.POST.get('expectedReceiptDate', '')
        notes = request.POST.get('notes', '')
        items_json = request.POST.get('items', '[]')

        try:
            items_data = json.loads(items_json)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid items lines data.'}, status=400)

        # Update headers allowed at any stage
        po.responsible_person = responsible_person
        po.notes = notes
        if expected_receipt_date:
            po.expected_receipt_date = expected_receipt_date
        else:
            po.expected_receipt_date = None

        # Vendor Name & Address are editable ONLY in draft
        if po.status == 'draft':
            if vendor_name:
                po.vendor_name = vendor_name
            po.vendor_address = vendor_address

        po.save()

        # Sync lines
        existing_items = {item.product_id: item for item in po.items.all()}
        new_product_ids = set()
        total_amount = 0

        for item in items_data:
            prod_id = int(item['productId'])
            qty = int(item['quantity'])
            cost = float(item['unitPrice'])
            new_product_ids.add(prod_id)

            if prod_id in existing_items:
                line = existing_items[prod_id]
                line.quantity = qty
                line.unit_cost = cost
                # Ensure received_quantity doesn't exceed quantity
                if line.received_quantity > qty:
                    line.received_quantity = qty
                line.save()
            else:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product_id=prod_id,
                    quantity=qty,
                    unit_cost=cost,
                    received_quantity=0
                )
            total_amount += qty * cost

        # Delete removed items
        for prod_id, line in existing_items.items():
            if prod_id not in new_product_ids:
                line.delete()

        po.total_amount = total_amount
        po.save()

        # Recalculate status if in receivable states
        if po.status in ['confirmed', 'partially_received', 'fully_received']:
            all_fully_received = True
            for item in po.items.all():
                if item.received_quantity < item.quantity:
                    all_fully_received = False
                    break
            po.status = 'fully_received' if all_fully_received else 'partially_received'
            po.save()

        record_audit(
            request, 
            module="Purchase", 
            action="Order Edit", 
            details=f"Purchase Order {po.ref} updated.",
            record_id=po.ref,
            record_type="Purchase Order",
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Update"
        )
        return JsonResponse({'status': 'success', 'message': 'Purchase Order updated successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
