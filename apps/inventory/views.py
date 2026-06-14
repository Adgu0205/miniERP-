from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Product
from apps.users.permissions import module_required

from . import services
from .models import MovementType, StockLedger


@module_required("inventory")
def ledger(request):
    qs = StockLedger.objects.select_related("product", "created_by").all()
    product_id = request.GET.get("product")
    mtype = request.GET.get("type")
    if product_id:
        qs = qs.filter(product_id=product_id)
    if mtype:
        qs = qs.filter(movement_type=mtype)
    if request.GET.get("export") == "csv":
        from config.utils import csv_response
        return csv_response("stock_ledger.csv",
            ["Date", "Product", "Movement", "Qty", "Balance", "Reference", "By"],
            [(e.created_at.strftime("%Y-%m-%d %H:%M"), e.product.name,
              e.get_movement_type_display(), e.quantity, e.balance_after,
              e.reference, e.created_by.username if e.created_by else "system")
             for e in qs[:5000]])
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "inventory/ledger.html", {
        "page": page,
        "products": Product.objects.all(),
        "types": MovementType.choices,
        "sel_product": product_id or "",
        "sel_type": mtype or "",
    })


@module_required("inventory")
def stock_overview(request):
    products = list(Product.objects.all())
    summary = {
        "skus": len(products),
        "value": sum((p.stock_value for p in products), Decimal("0")),
        "low": sum(1 for p in products if p.free_to_use <= 0),
        "reserved": sum((p.reserved for p in products), Decimal("0")),
    }
    return render(request, "inventory/overview.html",
                  {"products": products, "summary": summary})


@module_required("inventory")
def stock_adjust(request):
    """Manual stock adjustment (counts, damage, opening balance) → ledger move."""
    products = Product.objects.all()
    if request.method == "POST":
        product = get_object_or_404(Product, pk=request.POST.get("product"))
        try:
            qty = Decimal(request.POST.get("quantity", "0"))
        except (InvalidOperation, TypeError):
            qty = Decimal("0")
        note = request.POST.get("note", "").strip() or "manual adjustment"
        if qty == 0:
            messages.error(request, "Enter a non-zero quantity (use a minus sign to remove).")
        else:
            services.record_move(product, qty, MovementType.ADJUST,
                                 reference="adjustment", note=note, user=request.user)
            messages.success(request, f"Adjusted {product.name} by {qty:+}. New on-hand: {product.on_hand}.")
        return redirect("inventory:adjust")
    return render(request, "inventory/adjust.html", {"products": products})
