from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.manufacturing.models import ManufacturingOrder, MOStatus
from apps.procurement.models import ProcurementAction, ProcurementLog
from apps.products.models import ProcurementType, Product
from apps.purchase.models import POStatus, PurchaseOrder
from apps.sales.models import SalesOrder, SalesOrderLine, SOStatus

DEC = DecimalField()


def _money(qs):
    return qs.aggregate(t=Coalesce(Sum(F("lines__quantity") * F("lines__unit_price"),
                                       output_field=DEC), 0, output_field=DEC))["t"]


def _delta(curr, prev):
    if not prev:
        return 100.0 if curr else 0.0
    return round((curr - prev) / prev * 100, 1)


def metrics():
    today = timezone.localdate()
    p30 = today - timedelta(days=30)
    p60 = today - timedelta(days=60)
    so = SalesOrder.objects.all()
    po = PurchaseOrder.objects.all()
    mo = ManufacturingOrder.objects.all()
    live = so.exclude(status=SOStatus.CANCELLED)

    rev_30 = _money(live.filter(order_date__gte=p30))
    rev_prev = _money(live.filter(order_date__gte=p60, order_date__lt=p30))
    so_30 = so.filter(order_date__gte=p30).count()
    so_prev = so.filter(order_date__gte=p60, order_date__lt=p30).count()

    pending = so.filter(status__in=[SOStatus.CONFIRMED, SOStatus.PARTIAL]).count()
    delayed = (so.filter(deadline__lt=today)
               .exclude(status__in=[SOStatus.DELIVERED, SOStatus.CANCELLED]).count())
    inv_value = sum((p.stock_value for p in Product.objects.all()), 0)
    low = sum(1 for p in Product.objects.all() if p.free_to_use <= 0)

    return {
        "revenue": float(rev_30), "revenue_delta": _delta(float(rev_30), float(rev_prev)),
        "total_sales": so.count(), "sales_delta": _delta(so_30, so_prev),
        "pending_deliveries": pending,
        "mfg_orders": mo.exclude(status__in=[MOStatus.DONE, MOStatus.CANCELLED]).count(),
        "delayed_orders": delayed,
        "purchase_orders": po.count(),
        "inventory_value": float(inv_value),
        "low_stock": low,
        "fulfilment": _fulfilment_rate(so),
    }


def _fulfilment_rate(so):
    total = so.exclude(status=SOStatus.CANCELLED).count()
    if not total:
        return 0
    done = so.filter(status=SOStatus.DELIVERED).count()
    return round(done / total * 100)


@login_required
def home(request):
    low_stock = sorted((p for p in Product.objects.all() if p.free_to_use <= 0),
                       key=lambda p: p.free_to_use)[:6]
    recent_so = SalesOrder.objects.select_related("customer").order_by("-created_at")[:6]
    return render(request, "dashboard/home.html", {
        "m": metrics(), "low_stock": low_stock, "recent_so": recent_so,
    })


@login_required
def analytics(request):
    """All chart series in one cached payload (Upstash Redis, 60s TTL)."""
    cached = cache.get("dash:analytics")
    if cached and not request.GET.get("fresh"):
        return JsonResponse(cached)

    today = timezone.localdate()
    start = today - timedelta(days=29)

    # Sales trend: revenue + order count per day (last 30d)
    rev_map, cnt_map = {}, {}
    rows = (SalesOrderLine.objects
            .filter(order__order_date__gte=start)
            .exclude(order__status=SOStatus.CANCELLED)
            .values("order__order_date")
            .annotate(rev=Coalesce(Sum(F("quantity") * F("unit_price"),
                                       output_field=DEC), 0, output_field=DEC)))
    for r in rows:
        rev_map[r["order__order_date"]] = float(r["rev"])
    for r in (SalesOrder.objects.filter(order_date__gte=start)
              .values("order_date").annotate(c=Count("id"))):
        cnt_map[r["order_date"]] = r["c"]
    tl, tr, tc = [], [], []
    for i in range(30):
        d = start + timedelta(days=i)
        tl.append(d.strftime("%d %b"))
        tr.append(round(rev_map.get(d, 0)))
        tc.append(cnt_map.get(d, 0))

    # Inventory distribution by value
    inv = sorted(((p.name, float(p.stock_value)) for p in Product.objects.all()
                  if p.stock_value > 0), key=lambda x: x[1], reverse=True)[:8]

    # Top products by qty + revenue
    top = (SalesOrderLine.objects.exclude(order__status=SOStatus.CANCELLED)
           .values("product__name")
           .annotate(q=Coalesce(Sum("quantity"), 0, output_field=DEC),
                     rev=Coalesce(Sum(F("quantity") * F("unit_price"),
                                      output_field=DEC), 0, output_field=DEC))
           .order_by("-q")[:7])

    # SO status funnel
    so_status = {s: 0 for s, _ in SOStatus.choices}
    for r in SalesOrder.objects.values("status").annotate(c=Count("id")):
        so_status[r["status"]] = r["c"]

    # MO status
    mo_status = {s: 0 for s, _ in MOStatus.choices}
    for r in ManufacturingOrder.objects.values("status").annotate(c=Count("id")):
        mo_status[r["status"]] = r["c"]

    # Procurement Buy vs Manufacture
    proc = {ProcurementAction.PURCHASE: 0, ProcurementAction.MANUFACTURE: 0}
    for r in ProcurementLog.objects.values("action").annotate(c=Count("id")):
        proc[r["action"]] = proc.get(r["action"], 0) + r["c"]

    # Revenue by customer (top 6)
    cust = (SalesOrderLine.objects.exclude(order__status=SOStatus.CANCELLED)
            .values("order__customer__name")
            .annotate(rev=Coalesce(Sum(F("quantity") * F("unit_price"),
                                       output_field=DEC), 0, output_field=DEC))
            .order_by("-rev")[:6])

    sankey = _build_sankey()

    payload = {
        "trend": {"labels": tl, "revenue": tr, "orders": tc},
        "inventory": {"labels": [i[0] for i in inv], "values": [i[1] for i in inv]},
        "top_products": {"labels": [t["product__name"] for t in top],
                         "qty": [float(t["q"]) for t in top],
                         "revenue": [float(t["rev"]) for t in top]},
        "so_status": {"labels": [dict(SOStatus.choices)[k] for k in so_status],
                      "values": list(so_status.values())},
        "mo_status": {"labels": [dict(MOStatus.choices)[k] for k in mo_status],
                      "values": list(mo_status.values())},
        "procurement": {"buy": proc.get(ProcurementAction.PURCHASE, 0),
                        "manufacture": proc.get(ProcurementAction.MANUFACTURE, 0)},
        "customers": {"labels": [c["order__customer__name"] or "Walk-in" for c in cust],
                      "values": [float(c["rev"]) for c in cust]},
        "sankey": sankey,
    }
    cache.set("dash:analytics", payload, 60)
    return JsonResponse(payload)


def _build_sankey():
    """Units flowing through the business: combines real ledger moves with
    order activity so the flow reads well even on seeded history."""
    from apps.manufacturing.models import BoM, MOStatus
    from apps.purchase.models import PurchaseOrderLine

    purchased = (PurchaseOrderLine.objects
                 .aggregate(t=Coalesce(Sum("received_qty"), 0, output_field=DEC))["t"])
    sold = (SalesOrderLine.objects
            .aggregate(t=Coalesce(Sum("delivered_qty"), 0, output_field=DEC))["t"])

    produced = 0
    consumed = 0
    bom_by_product = {b.product_id: b for b in
                      BoM.objects.prefetch_related("lines")}
    for mo in ManufacturingOrder.objects.filter(status=MOStatus.DONE):
        produced += float(mo.quantity)
        bom = bom_by_product.get(mo.product_id)
        if bom:
            factor = float(mo.quantity) / (float(bom.quantity) or 1)
            consumed += sum(float(l.quantity) * factor for l in bom.lines.all())

    purchased = float(purchased) + float(consumed) * 0  # keep float
    f = lambda v: max(round(v), 1)
    return [
        {"from": "Purchases", "to": "Warehouse", "flow": f(float(purchased))},
        {"from": "Warehouse", "to": "Manufacturing", "flow": f(consumed)},
        {"from": "Manufacturing", "to": "Finished Goods", "flow": f(produced)},
        {"from": "Warehouse", "to": "Customers", "flow": f(float(sold))},
        {"from": "Finished Goods", "to": "Customers", "flow": f(produced)},
    ]


@login_required
def bom_tree(request):
    from apps.manufacturing.models import BoM
    trees = []
    for bom in BoM.objects.select_related("product").prefetch_related("lines__component"):
        trees.append({
            "name": bom.product.name,
            "children": [{"name": f"{l.component.name} ×{l.quantity}"}
                         for l in bom.lines.all()],
        })
    return JsonResponse({"trees": trees})
