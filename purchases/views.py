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

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'purchase_orders': purchase_orders,
        'products': products
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
        items_json = request.POST.get('items')
        
        try:
            items_data = json.loads(items_json)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid items lines data.'}, status=400)

        if not items_data:
            return JsonResponse({'status': 'error', 'message': 'Order lines cannot be empty.'}, status=400)

        po = PurchaseOrder.objects.create(
            vendor_name=vendor_name,
            status='draft'
        )

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

        record_audit(request, "Purchase", "Order Creation", f"Purchase Order PO-{po.id:03d} created for vendor {vendor_name}")
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

    record_audit(request, "Purchase", "Status Change", f"Purchase Order PO-{po.id:03d} confirmed")
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
            qty_to_receive = int(receipt_data.get(str(product.id), 0))

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

        record_audit(request, "Purchase", "Receipt Validation", f"PO-{po.id:03d} received items. Status: {po.status.replace('_', ' ')}")
        create_notification("purchase_received", f"PO-{po.id:03d} materials received: status is now {po.status.replace('_', ' ')}")

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

    if po.status not in ['draft', 'confirmed']:
        return JsonResponse({'status': 'error', 'message': f'Cannot cancel PO in "{po.status}" state.'}, status=400)

    po.status = 'cancelled'
    po.save()

    record_audit(request, "Purchase", "Order Cancelled", f"Purchase Order {po.ref} cancelled. No stock changes applied.")
    create_notification("purchase_received", f"{po.ref} has been cancelled by {get_current_user(request)['name']}.")

    return JsonResponse({'status': 'success', 'message': f'{po.ref} cancelled successfully.'})
