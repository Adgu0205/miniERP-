from decimal import Decimal

from django.db import transaction

from apps.audit.models import Action
from apps.audit.services import log
from apps.inventory import services as stock

from .models import POStatus, PurchaseOrder, PurchaseOrderLine


def _dec(v):
    return v if isinstance(v, Decimal) else Decimal(str(v))


@transaction.atomic
def confirm(po, user=None):
    if po.status != POStatus.DRAFT:
        return po
    po.status = POStatus.CONFIRMED
    po.save()
    log("purchase", Action.STATUS, po, user=user, field="status", new="confirmed")
    return po


@transaction.atomic
def receive_line(line, qty, user=None):
    """Receive `qty` of a line → stock in, update status."""
    qty = min(_dec(qty), line.remaining)
    if qty <= 0:
        return line
    line.received_qty += qty
    line.save()
    stock.stock_in_purchase(line.product, qty, user=user,
                            reference=line.order.reference, note="purchase receipt")
    log("purchase", Action.DELIVERY, line.order, user=user,
        description=f"Received {qty} x {line.product.name}")
    _refresh_status(line.order, user)
    return line


@transaction.atomic
def receive_all(po, user=None):
    if po.status not in (POStatus.CONFIRMED, POStatus.PARTIAL):
        return po
    for line in po.lines.select_related("product"):
        if line.remaining > 0:
            receive_line(line, line.remaining, user=user)
    return po


def _refresh_status(po, user=None):
    lines = list(po.lines.all())
    if lines and all(l.remaining <= 0 for l in lines):
        po.status = POStatus.RECEIVED
    elif any(l.received_qty > 0 for l in lines):
        po.status = POStatus.PARTIAL
    po.save()


@transaction.atomic
def create_po_for_product(product, quantity, *, user=None, origin=""):
    po = PurchaseOrder.objects.create(vendor=product.vendor, origin=origin)
    PurchaseOrderLine.objects.create(
        order=po, product=product, quantity=_dec(quantity),
        unit_price=product.cost_price,
    )
    log("purchase", Action.CREATE, po, user=user,
        description=f"PO created for {quantity} x {product.name} {origin}")
    return po
