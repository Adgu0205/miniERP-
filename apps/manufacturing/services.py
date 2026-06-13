"""Manufacturing order lifecycle. Reserve components on confirm,
consume components + produce finished goods on done."""
from decimal import Decimal

from django.db import transaction

from apps.audit.models import Action
from apps.audit.services import log
from apps.inventory import services as stock

from .models import BoM, ManufacturingOrder, MOStatus, WorkOrder


def _dec(v):
    return v if isinstance(v, Decimal) else Decimal(str(v))


def resolve_bom(product):
    return product.bom or BoM.objects.filter(product=product, is_active=True).first()


def component_requirements(mo):
    """Yield (component, qty_needed) for the MO based on its BoM."""
    bom = mo.bom or resolve_bom(mo.product)
    if not bom:
        return
    factor = _dec(mo.quantity) / (_dec(bom.quantity) or Decimal("1"))
    for line in bom.lines.select_related("component"):
        yield line.component, line.quantity * factor


def build_work_orders(mo):
    bom = mo.bom or resolve_bom(mo.product)
    if not bom:
        return
    for op in bom.operations.select_related("work_center"):
        WorkOrder.objects.get_or_create(
            mo=mo, name=op.name,
            defaults={"work_center": op.work_center,
                      "duration_mins": op.duration_mins,
                      "sequence": op.sequence},
        )


@transaction.atomic
def confirm(mo, user=None):
    """Draft -> Confirmed. Reserve all components, generate work orders."""
    if mo.status != MOStatus.DRAFT:
        return mo
    if not mo.bom:
        mo.bom = resolve_bom(mo.product)
    for component, qty in component_requirements(mo):
        stock.reserve(component, qty, user=user, reference=mo.reference)
    build_work_orders(mo)
    mo.components_reserved = True
    mo.status = MOStatus.CONFIRMED
    mo.save()
    log("manufacturing", Action.STATUS, mo, user=user,
        field="status", new="confirmed",
        description=f"Confirmed MO for {mo.quantity} x {mo.product.name}; components reserved")
    return mo


@transaction.atomic
def start(mo, user=None):
    if mo.status != MOStatus.CONFIRMED:
        return mo
    mo.status = MOStatus.IN_PROGRESS
    mo.save()
    mo.work_orders.update(status=WorkOrder.Status.IN_PROGRESS)
    log("manufacturing", Action.STATUS, mo, user=user, field="status", new="in_progress")
    return mo


@transaction.atomic
def done(mo, user=None):
    """-> Done. Consume reserved components, produce finished goods."""
    if mo.status not in (MOStatus.CONFIRMED, MOStatus.IN_PROGRESS):
        return mo
    for component, qty in component_requirements(mo):
        if mo.components_reserved:
            stock.unreserve(component, qty, user=user, reference=mo.reference)
        stock.consume_for_mfg(component, qty, user=user,
                              reference=mo.reference, note="component consumed")
    stock.produce_from_mfg(mo.product, mo.quantity, user=user,
                           reference=mo.reference, note="finished goods")
    mo.components_reserved = False
    mo.status = MOStatus.DONE
    mo.save()
    mo.work_orders.update(status=WorkOrder.Status.DONE)
    log("manufacturing", Action.STATUS, mo, user=user, field="status", new="done",
        description=f"Produced {mo.quantity} x {mo.product.name}")
    return mo


@transaction.atomic
def cancel(mo, user=None):
    if mo.status in (MOStatus.DONE, MOStatus.CANCELLED):
        return mo
    if mo.components_reserved:
        for component, qty in component_requirements(mo):
            stock.unreserve(component, qty, user=user, reference=mo.reference)
        mo.components_reserved = False
    mo.status = MOStatus.CANCELLED
    mo.save()
    log("manufacturing", Action.STATUS, mo, user=user, field="status", new="cancelled")
    return mo


@transaction.atomic
def create_mo(product, quantity, *, user=None, origin="", bom=None):
    mo = ManufacturingOrder.objects.create(
        product=product, quantity=_dec(quantity),
        bom=bom or resolve_bom(product), origin=origin,
    )
    log("manufacturing", Action.CREATE, mo, user=user,
        description=f"MO created for {quantity} x {product.name} {origin}")
    return mo
