from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, date
import csv

from core.utils import get_current_role, get_current_user, get_role_permissions, record_audit, recalculate_stock_quantity, has_page_access
from products.models import Product
from inventory.models import StockLedgerEntry


def inventory_valuation(request):
    role = get_current_role(request)
    if not has_page_access(role, "inventory_valuation"):
        return render(request, "no_access.html", {'page_name': 'Inventory'})

    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    products = Product.objects.all()

    # Calculations
    total_valuation = sum(p.on_hand * p.cost_price for p in products)
    low_stock = [p for p in products if p.free_to_use < p.reorder_threshold]
    reserved_stock = [p for p in products if p.reserved > 0]
    overstocked = [p for p in products if p.reorder_threshold > 0 and p.free_to_use > (p.reorder_threshold * 4)]

    # P7: Recently changed — products that have ledger entries in the last 7 days
    from django.utils import timezone as tz
    recent_cutoff = tz.now() - timezone.timedelta(days=7)
    recently_changed_ids = (
        StockLedgerEntry.objects
        .filter(timestamp__gte=recent_cutoff)
        .values_list('product_id', flat=True)
        .distinct()
    )
    recently_changed = Product.objects.filter(id__in=recently_changed_ids)

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'products': products,
        'total_valuation': float(total_valuation),
        'low_stock': low_stock,
        'reserved_stock': reserved_stock,
        'overstocked': overstocked,
        'recently_changed': recently_changed,
    }
    return render(request, "inventory_valuation.html", context)


@csrf_exempt
def post_stock_adjustment(request):
    role = get_current_role(request)
    permissions = get_role_permissions(role)
    if not permissions['can_adjust_inventory'] or permissions['is_read_only']:
        return JsonResponse({'status': 'error', 'message': 'Permission Denied'}, status=403)

    if request.method == 'POST':
        product_id = request.POST.get('productId')
        new_qty = int(request.POST.get('quantity', 0))
        reason = request.POST.get('reason', 'Correction')

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Product not found.'}, status=404)

        old_on_hand = product.on_hand
        diff = new_qty - old_on_hand

        # Apply change
        product.on_hand = new_qty
        product.save()

        # Log movement ledger
        StockLedgerEntry.objects.create(
            product=product,
            movement_type="Manual Adjustment",
            quantity_change=diff,
            source_document="Manual Adjustment",
            user=get_current_user(request)['name']
        )

        recalculate_stock_quantity(product.id)
        record_audit(request, "Inventory", "Stock Movement", f"Manual stock adjustment for {product.name}: {old_on_hand} -> {new_qty} (Reason: {reason})")

        return JsonResponse({'status': 'success', 'message': 'Inventory correction posted.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


def stock_ledger(request):
    role = get_current_role(request)
    if not has_page_access(role, "stock_ledger"):
        return render(request, "no_access.html", {'page_name': 'Stock Ledger'})

    user_info = get_current_user(request)
    ledger_qs = StockLedgerEntry.objects.all().order_by('-timestamp')

    # P8: Date range filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    movement_type = request.GET.get('movement_type', '')

    if date_from:
        try:
            ledger_qs = ledger_qs.filter(timestamp__date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            ledger_qs = ledger_qs.filter(timestamp__date__lte=date_to)
        except Exception:
            pass
    if movement_type:
        ledger_qs = ledger_qs.filter(movement_type=movement_type)

    # P8: Pagination
    paginator = Paginator(ledger_qs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'role': role,
        'user_info': user_info,
        'ledger': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'date_from': date_from,
        'date_to': date_to,
        'movement_type': movement_type,
        'total_count': ledger_qs.count(),
    }
    return render(request, "stock_ledger.html", context)


def export_ledger_csv(request):
    """P8: Export stock ledger as CSV."""
    role = get_current_role(request)
    if not has_page_access(role, "stock_ledger"):
        return JsonResponse({'status': 'error', 'message': 'Access Denied'}, status=403)

    ledger_qs = StockLedgerEntry.objects.all().order_by('-timestamp')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    movement_type = request.GET.get('movement_type', '')
    if date_from:
        ledger_qs = ledger_qs.filter(timestamp__date__gte=date_from)
    if date_to:
        ledger_qs = ledger_qs.filter(timestamp__date__lte=date_to)
    if movement_type:
        ledger_qs = ledger_qs.filter(movement_type=movement_type)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_ledger.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Product', 'SKU', 'Movement Type', 'Quantity Change', 'Source Document', 'User'])
    for entry in ledger_qs:
        writer.writerow([
            entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            entry.product.name,
            entry.product.sku,
            entry.movement_type,
            entry.quantity_change,
            entry.source_document,
            entry.user,
        ])
    return response


def inventory_movements(request):
    """P3: Dedicated Inventory Movements screen — reuses StockLedgerEntry."""
    role = get_current_role(request)
    if not has_page_access(role, "inventory_valuation"):
        return render(request, "no_access.html", {'page_name': 'Inventory Movements'})

    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    movements_qs = StockLedgerEntry.objects.select_related('product').order_by('-timestamp')

    # Filters
    product_id = request.GET.get('product', '')
    movement_type = request.GET.get('movement_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')

    if product_id:
        movements_qs = movements_qs.filter(product_id=product_id)
    if movement_type:
        movements_qs = movements_qs.filter(movement_type=movement_type)
    if date_from:
        try:
            movements_qs = movements_qs.filter(timestamp__date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            movements_qs = movements_qs.filter(timestamp__date__lte=date_to)
        except Exception:
            pass
    if search:
        movements_qs = movements_qs.filter(
            source_document__icontains=search
        ) | StockLedgerEntry.objects.filter(product__name__icontains=search).order_by('-timestamp')

    paginator = Paginator(movements_qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    products = Product.objects.all().order_by('name')
    movement_types = StockLedgerEntry.MOVEMENT_CHOICES

    context = {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'movements': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'products': products,
        'movement_types': movement_types,
        'selected_product': product_id,
        'selected_type': movement_type,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
        'total_count': movements_qs.count(),
    }
    return render(request, "inventory_movements.html", context)


def export_movements_csv(request):
    """P3: Export inventory movements as CSV."""
    role = get_current_role(request)
    if not has_page_access(role, "inventory_valuation"):
        return JsonResponse({'status': 'error', 'message': 'Access Denied'}, status=403)

    movements_qs = StockLedgerEntry.objects.select_related('product').order_by('-timestamp')
    product_id = request.GET.get('product', '')
    movement_type = request.GET.get('movement_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if product_id:
        movements_qs = movements_qs.filter(product_id=product_id)
    if movement_type:
        movements_qs = movements_qs.filter(movement_type=movement_type)
    if date_from:
        movements_qs = movements_qs.filter(timestamp__date__gte=date_from)
    if date_to:
        movements_qs = movements_qs.filter(timestamp__date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_movements.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Product', 'SKU', 'Movement Type', 'Quantity Change', 'Source Document', 'User'])
    for entry in movements_qs:
        writer.writerow([
            entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            entry.product.name,
            entry.product.sku,
            entry.movement_type,
            entry.quantity_change,
            entry.source_document,
            entry.user,
        ])
    return response
