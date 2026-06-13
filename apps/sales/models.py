from decimal import Decimal

from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class SOStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    PARTIAL = "partial", "Partially Delivered"
    DELIVERED = "delivered", "Fully Delivered"
    CANCELLED = "cancelled", "Cancelled"


class SalesOrder(models.Model):
    reference = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(Customer, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="orders")
    status = models.CharField(max_length=12, choices=SOStatus.choices,
                              default=SOStatus.DRAFT, db_index=True)
    order_date = models.DateField(auto_now_add=True)
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.reference or f"SO#{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            type(self).objects.filter(pk=self.pk).update(reference=f"SO{self.pk:05d}")
            self.reference = f"SO{self.pk:05d}"

    @property
    def total(self):
        return sum((l.subtotal for l in self.lines.all()), Decimal("0"))

    @property
    def is_delayed(self):
        from django.utils import timezone
        return bool(self.deadline and self.status not in
                    (SOStatus.DELIVERED, SOStatus.CANCELLED)
                    and self.deadline < timezone.localdate())


class SalesOrderLine(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE,
                              related_name="lines")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    delivered_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def remaining(self):
        return self.quantity - self.delivered_qty

    @property
    def shortage(self):
        """How much we can't currently fulfil from free stock."""
        gap = self.quantity - self.product.free_to_use
        return gap if gap > 0 else Decimal("0")
