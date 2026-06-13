"""Predictive demand forecasting (USP).

Simple, explainable moving-average model over recent sales. For each product:
- avg daily demand  = qty sold in window / window days
- predicted 30-day  = avg daily * 30
- demand over lead  = avg daily * lead_time_days
- suggested reorder = (demand over lead + reorder_point) - free_to_use   (>=0)

No external ML deps — fast, deterministic, demo-friendly, and easy to defend.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.products.models import Product
from apps.sales.models import SalesOrderLine, SOStatus

WINDOW_DAYS = 30
DEC = DecimalField()


def _sold_map(window=WINDOW_DAYS):
    start = timezone.localdate() - timedelta(days=window)
    rows = (SalesOrderLine.objects
            .filter(order__order_date__gte=start)
            .exclude(order__status=SOStatus.CANCELLED)
            .values("product_id")
            .annotate(q=Coalesce(Sum("quantity"), 0, output_field=DEC)))
    return {r["product_id"]: r["q"] for r in rows}


def forecast_product(product, sold_qty, window=WINDOW_DAYS):
    avg_daily = (sold_qty or Decimal("0")) / Decimal(window)
    lead = product.lead_time_days
    predicted_30 = (avg_daily * 30).quantize(Decimal("0.1"))
    demand_lead = avg_daily * Decimal(lead)
    target = demand_lead + product.reorder_point
    suggested = target - product.free_to_use
    suggested = suggested.quantize(Decimal("1")) if suggested > 0 else Decimal("0")
    # Days of cover left at current pace
    days_cover = None
    if avg_daily > 0:
        days_cover = int((product.free_to_use / avg_daily)) if product.free_to_use > 0 else 0
    return {
        "product": product,
        "avg_daily": avg_daily.quantize(Decimal("0.01")),
        "predicted_30": predicted_30,
        "lead_days": lead,
        "free": product.free_to_use,
        "reorder_point": product.reorder_point,
        "suggested": suggested,
        "days_cover": days_cover,
        "action": ("manufacture" if product.procurement_type == "manufacture"
                   else "buy"),
    }


def forecasts(only_actionable=False, window=WINDOW_DAYS):
    sold = _sold_map(window)
    out = []
    for p in Product.objects.select_related("vendor").all():
        f = forecast_product(p, sold.get(p.pk, Decimal("0")), window)
        if only_actionable and f["suggested"] <= 0:
            continue
        out.append(f)
    out.sort(key=lambda f: f["suggested"], reverse=True)
    return out
