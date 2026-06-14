from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.utils import get_current_role, get_current_user, get_role_permissions, record_audit, has_page_access
from products.models import Product
from manufacturing.models import BoM

def products_list(request):
    role = get_current_role(request)
    if not has_page_access(role, "products_list"):
        return render(request, "no_access.html", {'page_name': 'Products'})

    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    products = Product.objects.all()
    boms = BoM.objects.all()
    
    # Simple check for BOM link
    bom_linked_product_ids = [b.product_id for b in boms]

    from audit.models import AuditLog
    product_logs = AuditLog.objects.filter(module__in=["Products", "Inventory"]).order_by('-timestamp')[:50]

    context = {
        'products': products,
        'bom_linked_product_ids': bom_linked_product_ids,
        'permissions': permissions,
        'product_logs': product_logs,
    }
    return render(request, "products_list.html", context)

@csrf_exempt
def create_product(request):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_products'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    if request.method == 'POST':
        name = request.POST.get('name')
        sku = request.POST.get('sku', '').upper()
        category = request.POST.get('category', 'Furniture')
        cost_price = float(request.POST.get('costPrice', 0.00))
        sales_price = float(request.POST.get('salesPrice', 0.00))
        procure_strategy = request.POST.get('procureStrategy', 'MTS')
        procure_type = request.POST.get('procureType', 'None')
        vendor = request.POST.get('vendor', '')
        # reorder_threshold intentionally not exposed in the UI — use model default (5.00)

        if Product.objects.filter(sku=sku).exists():
            return JsonResponse({'status': 'error', 'message': f'SKU {sku} already exists.'}, status=400)

        product = Product.objects.create(
            name=name, sku=sku, category=category, cost_price=cost_price,
            sales_price=sales_price, procure_strategy=procure_strategy,
            procurement_type=procure_type, vendor=vendor
        )

        record_type = "Item" if category == "Components" else "Product"
        record_audit(
            request, 
            module="Sales", 
            action="Product Creation", 
            details=f"Created product {name} (SKU: {sku})",
            record_id=sku,
            record_type=record_type,
            field_changed="-",
            old_value="-",
            new_value="-",
            action_type="Create"
        )
        return JsonResponse({'status': 'success', 'message': 'Product created successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def edit_product(request, product_id):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_edit_products'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    product = Product.objects.get(id=product_id)
    if request.method == 'POST':
        # Track old values
        old_name = product.name
        old_category = product.category
        old_cost = float(product.cost_price)
        old_sales = float(product.sales_price)

        new_name = request.POST.get('name', product.name)
        new_category = request.POST.get('category', product.category)
        new_cost = float(request.POST.get('costPrice', product.cost_price))
        new_sales = float(request.POST.get('salesPrice', product.sales_price))

        product.name = new_name
        product.category = new_category
        product.cost_price = new_cost
        product.sales_price = new_sales
        product.procure_strategy = request.POST.get('procureStrategy', product.procure_strategy)
        product.procurement_type = request.POST.get('procureType', product.procurement_type)
        product.vendor = request.POST.get('vendor', product.vendor)
        product.save()

        # Log individual field changes
        changes = []
        if old_sales != new_sales:
            changes.append(('Sales Price', f"₹{old_sales:.2f}", f"₹{new_sales:.2f}"))
        if old_cost != new_cost:
            changes.append(('Cost Price', f"₹{old_cost:.2f}", f"₹{new_cost:.2f}"))
        if old_name != new_name:
            changes.append(('Name', old_name, new_name))
        if old_category != new_category:
            changes.append(('Category', old_category, new_category))

        record_type = "Item" if product.category == "Components" else "Product"
        if changes:
            for field, old_val, new_val in changes:
                record_audit(
                    request,
                    module="Sales",
                    action="Price Changes",
                    details=f"Product {product.sku} field '{field}' updated from {old_val} to {new_val}",
                    record_id=product.sku,
                    record_type=record_type,
                    field_changed=field,
                    old_value=old_val,
                    new_value=new_val,
                    action_type="Update"
                )
        else:
            record_audit(
                request,
                module="Sales",
                action="Price Changes",
                details=f"Product {product.sku} updated properties.",
                record_id=product.sku,
                record_type=record_type,
                field_changed="-",
                old_value="-",
                new_value="-",
                action_type="Update"
            )

        return JsonResponse({'status': 'success', 'message': 'Product modified successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
