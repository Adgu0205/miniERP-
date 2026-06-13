from django.core.paginator import Paginator
from django.shortcuts import render

from apps.products.models import Product
from apps.users.permissions import module_required

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
    products = Product.objects.all()
    return render(request, "inventory/overview.html", {"products": products})
