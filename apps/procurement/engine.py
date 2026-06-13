"""Smart Procurement Engine (USP).

When demand is committed beyond physical stock, automatically raise the right
replenishment order: a Manufacturing Order (if the product is built in-house)
or a Purchase Order (if bought from a vendor).
"""
from decimal import Decimal

from django.db import transaction

from apps.audit.models import Action
from apps.audit.services import log
from apps.products.models import ProcurementType

from .models import ProcurementAction, ProcurementLog


def shortage_for(product):
    """Committed demand not covered by physical stock = reserved - on_hand."""
    gap = product.reserved - product.on_hand
    return gap if gap > Decimal("0") else Decimal("0")


def open_replenishment_qty(product):
    """Quantity already on the way via open MOs / POs (so we don't double-order)."""
    from django.db.models import F, Sum
    from apps.manufacturing.models import ManufacturingOrder, MOStatus
    from apps.purchase.models import POStatus, PurchaseOrderLine

    if product.procurement_type == ProcurementType.MANUFACTURE:
        agg = (ManufacturingOrder.objects
               .filter(product=product,
                       status__in=[MOStatus.DRAFT, MOStatus.CONFIRMED,
                                   MOStatus.IN_PROGRESS])
               .aggregate(t=Sum("quantity"))["t"])
        return agg or Decimal("0")
    agg = (PurchaseOrderLine.objects
           .filter(product=product,
                   order__status__in=[POStatus.DRAFT, POStatus.CONFIRMED,
                                      POStatus.PARTIAL])
           .aggregate(t=Sum(F("quantity") - F("received_qty")))["t"])
    return agg or Decimal("0")


@transaction.atomic
def replenish_product(product, *, trigger="", user=None):
    """Create a PO or MO to cover the product's *uncovered* shortage. Idempotent:
    skips if open orders already cover it. Returns ProcurementLog or None."""
    shortage = shortage_for(product)
    if not product.procure_on_demand or shortage <= 0:
        return None

    # Net out what's already on order — keeps repeated scans from stacking duplicates.
    needed = shortage - open_replenishment_qty(product)
    if needed <= 0:
        return None

    if product.procurement_type == ProcurementType.MANUFACTURE:
        from apps.manufacturing import services as mfg
        mo = mfg.create_mo(product, needed, user=user, origin=f"auto:{trigger}")
        action, ref = ProcurementAction.MANUFACTURE, mo.reference
    else:
        from apps.purchase import services as pur
        po = pur.create_po_for_product(product, needed, user=user,
                                       origin=f"auto:{trigger}")
        action, ref = ProcurementAction.PURCHASE, po.reference

    entry = ProcurementLog.objects.create(
        product=product, trigger=trigger,
        required_qty=product.reserved, free_qty=product.free_to_use,
        shortage=needed, action=action, result_ref=ref,
    )
    log("procurement", Action.PROCUREMENT, product, user=user,
        description=f"Shortage {shortage} on {product.name} -> {action} {ref} ({trigger})")
    return entry


@transaction.atomic
def replenish_to_quantity(product, qty, *, trigger="", user=None):
    """Raise a PO/MO for `qty` (netting open orders). Used by forecast-driven
    proactive replenishment (reorder point / predicted demand)."""
    qty = qty if isinstance(qty, Decimal) else Decimal(str(qty))
    if not product.procure_on_demand or qty <= 0:
        return None
    needed = qty - open_replenishment_qty(product)
    if needed <= 0:
        return None
    if product.procurement_type == ProcurementType.MANUFACTURE:
        from apps.manufacturing import services as mfg
        mo = mfg.create_mo(product, needed, user=user, origin=f"auto:{trigger}")
        action, ref = ProcurementAction.MANUFACTURE, mo.reference
    else:
        from apps.purchase import services as pur
        po = pur.create_po_for_product(product, needed, user=user,
                                       origin=f"auto:{trigger}")
        action, ref = ProcurementAction.PURCHASE, po.reference
    entry = ProcurementLog.objects.create(
        product=product, trigger=trigger,
        required_qty=product.reserved, free_qty=product.free_to_use,
        shortage=needed, action=action, result_ref=ref,
    )
    log("procurement", Action.PROCUREMENT, product, user=user,
        description=f"Forecast replenish {needed} of {product.name} -> {action} {ref} ({trigger})")
    return entry


def run_for_order(order, user=None):
    """Evaluate every product on a confirmed sales order."""
    results = []
    seen = set()
    for line in order.lines.select_related("product"):
        p = line.product
        if p.pk in seen:
            continue
        seen.add(p.pk)
        p.refresh_from_db()
        res = replenish_product(p, trigger=f"{order.reference} confirmed", user=user)
        if res:
            results.append(res)
    return results


def scan_all(user=None):
    """Periodic safety net + predictive replenishment across the catalog.

    1) Cover hard shortages (reserved > on_hand).
    2) Proactively cover forecast demand-over-lead-time + reorder point.
    """
    from apps.products.models import Product
    from .forecast import forecast_product, _sold_map

    sold = _sold_map()
    results = []
    for p in Product.objects.filter(procure_on_demand=True).select_related("vendor"):
        res = replenish_product(p, trigger="scheduled scan", user=user)
        if res:
            results.append(res)
            continue
        p.refresh_from_db()
        f = forecast_product(p, sold.get(p.pk, Decimal("0")))
        if f["suggested"] > 0:
            res = replenish_to_quantity(p, f["suggested"],
                                        trigger="forecast scan", user=user)
            if res:
                results.append(res)
    return results
