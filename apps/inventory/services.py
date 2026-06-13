"""The single gateway for ALL stock mutation. Nothing else touches
Product.on_hand / Product.reserved. Keeps the StockLedger authoritative."""
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.audit.models import Action
from apps.audit.services import log
from apps.products.models import Product

from .models import MovementType, StockLedger


def _dec(v):
    return v if isinstance(v, Decimal) else Decimal(str(v))


@transaction.atomic
def record_move(product, qty, movement_type, *, reference="", note="", user=None):
    """Apply a signed physical stock movement and append a ledger row.

    qty > 0 increases on_hand, qty < 0 decreases it.
    Returns the created StockLedger entry.
    """
    qty = _dec(qty)
    # Lock the row to keep balance_after consistent under concurrency.
    locked = Product.objects.select_for_update().get(pk=product.pk)
    new_balance = locked.on_hand + qty
    Product.objects.filter(pk=locked.pk).update(on_hand=F("on_hand") + qty)

    entry = StockLedger.objects.create(
        product=locked,
        movement_type=movement_type,
        quantity=qty,
        balance_after=new_balance,
        reference=reference,
        note=note,
        created_by=user if (user and getattr(user, "is_authenticated", False)) else None,
    )
    log("inventory", Action.STOCK, locked, user=user,
        field="on_hand", old=locked.on_hand, new=new_balance,
        description=f"{movement_type} {qty:+} ({reference})")
    product.on_hand = new_balance
    return entry


@transaction.atomic
def reserve(product, qty, *, user=None, reference=""):
    """Commit stock to an order. Increases reserved (capped at on_hand-ish:
    we allow over-reserve to surface shortages, procurement covers the gap)."""
    qty = _dec(qty)
    Product.objects.filter(pk=product.pk).update(reserved=F("reserved") + qty)
    product.refresh_from_db(fields=["reserved", "on_hand"])
    log("inventory", Action.STOCK, product, user=user,
        field="reserved", new=product.reserved,
        description=f"Reserved {qty} ({reference})")
    return product.reserved


@transaction.atomic
def unreserve(product, qty, *, user=None, reference=""):
    qty = _dec(qty)
    Product.objects.filter(pk=product.pk).update(reserved=F("reserved") - qty)
    product.refresh_from_db(fields=["reserved", "on_hand"])
    if product.reserved < 0:
        Product.objects.filter(pk=product.pk).update(reserved=0)
        product.reserved = Decimal("0")
    log("inventory", Action.STOCK, product, user=user,
        field="reserved", new=product.reserved,
        description=f"Released {qty} ({reference})")
    return product.reserved


# Convenience wrappers used by the order modules ---------------------------

def stock_in_purchase(product, qty, **kw):
    return record_move(product, abs(_dec(qty)), MovementType.PURCHASE, **kw)


def stock_out_sale(product, qty, **kw):
    return record_move(product, -abs(_dec(qty)), MovementType.SALE, **kw)


def consume_for_mfg(product, qty, **kw):
    return record_move(product, -abs(_dec(qty)), MovementType.MFG_CONSUME, **kw)


def produce_from_mfg(product, qty, **kw):
    return record_move(product, abs(_dec(qty)), MovementType.MFG_PRODUCE, **kw)
