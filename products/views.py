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

    context = {
        'products': products,
        'bom_linked_product_ids': bom_linked_product_ids,
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
        reorder_threshold = int(request.POST.get('reorderThreshold', 5))

        if Product.objects.filter(sku=sku).exists():
            return JsonResponse({'status': 'error', 'message': f'SKU {sku} already exists.'}, status=400)

        product = Product.objects.create(
            name=name, sku=sku, category=category, cost_price=cost_price,
            sales_price=sales_price, procure_strategy=procure_strategy,
            procurement_type=procure_type, vendor=vendor, reorder_threshold=reorder_threshold
        )

        record_audit(request, "Product", "Product Creation", f"Created product {name} (SKU: {sku})")
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
        product.name = request.POST.get('name', product.name)
        product.category = request.POST.get('category', product.category)
        product.cost_price = float(request.POST.get('costPrice', product.cost_price))
        product.sales_price = float(request.POST.get('salesPrice', product.sales_price))
        product.procure_strategy = request.POST.get('procureStrategy', product.procure_strategy)
        product.procurement_type = request.POST.get('procureType', product.procurement_type)
        product.vendor = request.POST.get('vendor', product.vendor)
        product.reorder_threshold = int(request.POST.get('reorderThreshold', product.reorder_threshold))
        product.save()

        record_audit(request, "Product", "Price Changes", f"Product {product.sku} updated properties.")
        return JsonResponse({'status': 'success', 'message': 'Product modified successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
