from decimal import Decimal

from django.db import models


class Vendor(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200, blank=True)
    lead_time_days = models.PositiveIntegerField(default=3)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class POStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    PARTIAL = "partial", "Partially Received"
    RECEIVED = "received", "Fully Received"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrder(models.Model):
    reference = models.CharField(max_length=20, unique=True, blank=True)
    vendor = models.ForeignKey(Vendor, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="orders")
    status = models.CharField(max_length=12, choices=POStatus.choices,
                              default=POStatus.DRAFT, db_index=True)
    order_date = models.DateField(auto_now_add=True)
    origin = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.reference or f"PO#{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            type(self).objects.filter(pk=self.pk).update(reference=f"PO{self.pk:05d}")
            self.reference = f"PO{self.pk:05d}"

    @property
    def total(self):
        return sum((l.subtotal for l in self.lines.all()), Decimal("0"))


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE,
                              related_name="lines")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    received_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def remaining(self):
        return self.quantity - self.received_qty
