from decimal import Decimal

from django.conf import settings
from django.db import models


class WorkCenter(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=20, blank=True)
    cost_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class BoM(models.Model):
    """Bill of Materials: how to build one finished product."""
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="boms"
    )
    name = models.CharField(max_length=120, blank=True)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=1,
        help_text="Output quantity this BoM produces.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"BoM: {self.product.name}"

    @property
    def component_cost(self):
        return sum((l.line_cost for l in self.lines.all()), Decimal("0"))


class BoMLine(models.Model):
    bom = models.ForeignKey(BoM, on_delete=models.CASCADE, related_name="lines")
    component = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="used_in_boms"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)

    def __str__(self):
        return f"{self.quantity} x {self.component.name}"

    @property
    def line_cost(self):
        return self.quantity * self.component.cost_price


class BoMOperation(models.Model):
    bom = models.ForeignKey(BoM, on_delete=models.CASCADE, related_name="operations")
    name = models.CharField(max_length=80)
    work_center = models.ForeignKey(
        WorkCenter, null=True, blank=True, on_delete=models.SET_NULL
    )
    duration_mins = models.PositiveIntegerField(default=0)
    sequence = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ("sequence",)

    def __str__(self):
        return f"{self.name} ({self.duration_mins}m)"


class MOStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    IN_PROGRESS = "in_progress", "In Progress"
    DONE = "done", "Done"
    CANCELLED = "cancelled", "Cancelled"


class ManufacturingOrder(models.Model):
    reference = models.CharField(max_length=20, unique=True, blank=True)
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="manufacturing_orders"
    )
    bom = models.ForeignKey(BoM, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    status = models.CharField(max_length=12, choices=MOStatus.choices,
                              default=MOStatus.DRAFT, db_index=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    deadline = models.DateField(null=True, blank=True)
    components_reserved = models.BooleanField(default=False)
    origin = models.CharField(max_length=60, blank=True,
                              help_text="e.g. auto-procurement from SO00007")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.reference or f"MO#{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            type(self).objects.filter(pk=self.pk).update(
                reference=f"MO{self.pk:05d}")
            self.reference = f"MO{self.pk:05d}"

    @property
    def is_delayed(self):
        from django.utils import timezone
        return bool(self.deadline and self.status != MOStatus.DONE
                    and self.deadline < timezone.localdate())


class WorkOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    mo = models.ForeignKey(ManufacturingOrder, on_delete=models.CASCADE,
                           related_name="work_orders")
    name = models.CharField(max_length=80)
    work_center = models.ForeignKey(WorkCenter, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    duration_mins = models.PositiveIntegerField(default=0)
    sequence = models.PositiveIntegerField(default=10)
    status = models.CharField(max_length=12, choices=Status.choices,
                              default=Status.PENDING)

    class Meta:
        ordering = ("sequence",)

    def __str__(self):
        return f"{self.name} [{self.mo.reference}]"
