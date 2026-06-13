from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Product
from apps.users.permissions import module_required

from . import engine, forecast
from .models import ProcurementLog


@module_required("procurement")
def procurement_list(request):
    logs = ProcurementLog.objects.select_related("product").all()[:200]
    shortages = []
    for p in Product.objects.all():
        s = engine.shortage_for(p)
        if s > 0:
            shortages.append({"product": p, "shortage": s})
    return render(request, "procurement/list.html", {
        "logs": logs,
        "shortages": shortages,
        "forecasts": forecast.forecasts(only_actionable=True),
    })


@module_required("procurement")
def run_scan(request):
    results = engine.scan_all(user=request.user)
    messages.success(request, f"Procurement scan complete: {len(results)} order(s) raised.")
    return redirect("procurement:list")


@module_required("procurement")
def replenish_one(request, pk):
    """Act on a single forecast suggestion → raise the suggested PO/MO."""
    product = get_object_or_404(Product, pk=pk)
    from .forecast import forecast_product, _sold_map
    f = forecast_product(product, _sold_map().get(product.pk, 0))
    res = engine.replenish_to_quantity(product, f["suggested"],
                                       trigger="manual forecast", user=request.user)
    if res:
        messages.success(request, f"Raised {res.get_action_display()} {res.result_ref} for {product.name}.")
    else:
        messages.info(request, f"No replenishment needed for {product.name} (already covered).")
    return redirect("procurement:list")
