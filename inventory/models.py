from django.db import models
from products.models import Product


class StockLedgerEntry(models.Model):
    MOVEMENT_CHOICES = [
        ('Sales Delivery', 'Sales Delivery'),
        ('Purchase Receipt', 'Purchase Receipt'),
        ('Manufacturing Consumption', 'Manufacturing Consumption'),
        ('Manufacturing Production', 'Manufacturing Production'),
        ('Manual Adjustment', 'Manual Adjustment'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ledger_entries")
    movement_type = models.CharField(max_length=50, choices=MOVEMENT_CHOICES)

    # Converted: IntegerField → DecimalField (spec requirement)
    quantity_change = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='Quantity Change'
    )

    # Added: balance_after — running stock balance after this movement (Odoo standard)
    balance_after = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Balance After'
    )

    source_document = models.CharField(max_length=100)
    user = models.CharField(max_length=100, default='System')

    def save(self, *args, **kwargs):
        # Auto-compute balance_after = current on_hand + quantity_change (before save)
        # on_hand is updated before ledger entry is created in views,
        # so balance_after = product's current on_hand at time of entry.
        if self.balance_after is None and self.product_id:
            try:
                from products.models import Product as P
                p = P.objects.get(id=self.product_id)
                self.balance_after = p.on_hand
            except Exception:
                self.balance_after = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name}: {self.quantity_change:+} → balance {self.balance_after} (Source: {self.source_document})"
