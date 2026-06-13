from decimal import Decimal

from django.db import transaction

from apps.audit.models import Action
from apps.audit.services import log
from apps.inventory import services as stock

from .models import SOStatus, SalesOrder
from .signals import sales_order_confirmed


def _dec(v):
    return v if isinstance(v, Decimal) else Decimal(str(v))


def availability(order):
    """Per-line stock availability snapshot for the form/detail view."""
    rows = []
    for line in order.lines.select_related("product"):
        rows.append({
            "line": line,
            "free": line.product.free_to_use,
            "shortage": line.shortage,
        })
    return rows


@transaction.atomic
def confirm(order, user=None):
    """Draft -> Confirmed: reserve stock, then trigger procurement."""
    if order.status != SOStatus.DRAFT:
        return order
    for line in order.lines.select_related("product"):
        stock.reserve(line.product, line.quantity, user=user,
                      reference=order.reference)
    order.status = SOStatus.CONFIRMED
    order.save()
    log("sales", Action.STATUS, order, user=user, field="status", new="confirmed",
        description=f"Confirmed; stock reserved for {order.lines.count()} line(s)")
    # Decoupled procurement automation (USP).
    sales_order_confirmed.send(sender=SalesOrder, order=order, user=user)
    return order


@transaction.atomic
def deliver(order, user=None):
    """Deliver everything currently available; partial if stock short."""
    if order.status not in (SOStatus.CONFIRMED, SOStatus.PARTIAL):
        return order
    for line in order.lines.select_related("product"):
        if line.remaining <= 0:
            continue
        # deliver up to what's physically on hand
        can = min(line.remaining, max(line.product.on_hand, Decimal("0")))
        if can <= 0:
            continue
        stock.unreserve(line.product, can, user=user, reference=order.reference)
        stock.stock_out_sale(line.product, can, user=user,
                             reference=order.reference, note="sales delivery")
        line.delivered_qty += can
        line.save()
        log("sales", Action.DELIVERY, order, user=user,
            description=f"Delivered {can} x {line.product.name}")
    _refresh_status(order, user)
    return order


def _refresh_status(order, user=None):
    lines = list(order.lines.all())
    if lines and all(l.remaining <= 0 for l in lines):
        order.status = SOStatus.DELIVERED
        log("sales", Action.STATUS, order, user=user, field="status", new="delivered")
    elif any(l.delivered_qty > 0 for l in lines):
        order.status = SOStatus.PARTIAL
    order.save()


@transaction.atomic
def cancel(order, user=None):
    if order.status in (SOStatus.DELIVERED, SOStatus.CANCELLED):
        return order
    if order.status in (SOStatus.CONFIRMED, SOStatus.PARTIAL):
        for line in order.lines.select_related("product"):
            if line.remaining > 0:
                stock.unreserve(line.product, line.remaining, user=user,
                                reference=order.reference)
    order.status = SOStatus.CANCELLED
    order.save()
    log("sales", Action.STATUS, order, user=user, field="status", new="cancelled")
    return order
