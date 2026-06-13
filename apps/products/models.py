from decimal import Decimal

from django.db import models


class ProductType(models.TextChoices):
    STOCKABLE = "stockable", "Stockable"
    CONSUMABLE = "consumable", "Consumable"


class ProcurementType(models.TextChoices):
    BUY = "buy", "Purchase"
    MANUFACTURE = "manufacture", "Manufacture"


class ProcurementStrategy(models.TextChoices):
    MTS = "mts", "Make To Stock"
    MTO = "mto", "Make To Order"


class Product(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=40, unique=True)
    product_type = models.CharField(
        max_length=12, choices=ProductType.choices, default=ProductType.STOCKABLE
    )

    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # --- Procurement config ---
    strategy = models.CharField(
        max_length=4, choices=ProcurementStrategy.choices,
        default=ProcurementStrategy.MTS,
        help_text="MTS: replenish before demand. MTO: replenish on customer order.",
    )
    procure_on_demand = models.BooleanField(default=True)
    procurement_type = models.CharField(
        max_length=12, choices=ProcurementType.choices, default=ProcurementType.BUY
    )
    reorder_point = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Min free stock to keep (MTS). Below this → replenish.",
    )
    manufacture_lead_days = models.PositiveIntegerField(
        default=5, help_text="Days to build this product (used for forecasting).",
    )
    vendor = models.ForeignKey(
        "purchase.Vendor", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="products",
    )
    bom = models.ForeignKey(
        "manufacturing.BoM", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text="Default BoM used when manufacturing this product.",
    )

    # --- Stock (mutated ONLY via apps.inventory.services) ---
    on_hand = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reserved = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} [{self.sku}]"

    @property
    def free_to_use(self):
        return self.on_hand - self.reserved

    @property
    def lead_time_days(self):
        if self.procurement_type == ProcurementType.MANUFACTURE:
            return self.manufacture_lead_days
        return self.vendor.lead_time_days if self.vendor else 7

    @property
    def stock_value(self):
        return self.on_hand * self.cost_price

    @property
    def is_low(self):
        return self.free_to_use <= Decimal("0")
