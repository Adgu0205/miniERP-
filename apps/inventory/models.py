from django.conf import settings
from django.db import models


class MovementType(models.TextChoices):
    PURCHASE = "purchase", "Purchase Receipt"        # +
    SALE = "sale", "Sales Delivery"                  # -
    MFG_CONSUME = "mfg_consume", "MFG Consume"       # -
    MFG_PRODUCE = "mfg_produce", "MFG Produce"       # +
    ADJUST = "adjust", "Manual Adjustment"           # +/-


class StockLedger(models.Model):
    """Append-only record of every physical stock movement. Source of truth."""
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="ledger_entries"
    )
    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)  # signed
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.product.sku} {self.quantity:+} ({self.get_movement_type_display()})"
