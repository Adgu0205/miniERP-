from django.db import models
from django.utils import timezone
from products.models import Product


class BoM(models.Model):
    """Bill of Materials — defines the recipe for manufacturing a product."""

    # Added: bom_code (unique identifier, Odoo-style)
    bom_code = models.CharField(
        max_length=50, unique=True, blank=True, null=True,
        verbose_name='BoM Code'
    )
    name = models.CharField(max_length=150)

    # Added: version field for BoM revision tracking
    version = models.CharField(max_length=10, default='1.0', verbose_name='Version')

    # NOTE: OneToOneField preserved to avoid breaking hasattr(product, 'bom') checks
    # throughout procurement logic. Phase A migration should change to ForeignKey
    # when full codebase refactor is done.
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="bom")

    # Added: quantity_produced — how many units this BoM produces per run
    quantity_produced = models.DecimalField(
        max_digits=10, decimal_places=2, default=1.00,
        verbose_name='Quantity Produced'
    )

    # Added: created_at timestamp
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-generate bom_code if not set
        if not self.bom_code:
            self.bom_code = f"BOM-{self.id:03d}"
            BoM.objects.filter(pk=self.pk).update(bom_code=self.bom_code)

    def __str__(self):
        return f"{self.bom_code or self.name} v{self.version}"


class BoMComponent(models.Model):
    """Component line within a Bill of Materials."""
    bom = models.ForeignKey(BoM, on_delete=models.CASCADE, related_name="components")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="bom_usages")

    # Converted to DecimalField for spec compliance (supports fractional quantities)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1.00,
        verbose_name='Quantity'
    )

    def __str__(self):
        return f"{self.quantity}x {self.product.name} for {self.bom.name}"


class BoMOperation(models.Model):
    """Operation step within a Bill of Materials."""
    bom = models.ForeignKey(BoM, on_delete=models.CASCADE, related_name="operations")

    # Renamed: name → operation_name (Odoo alignment)
    operation_name = models.CharField(max_length=100, default='', verbose_name='Operation Name')
    work_center = models.CharField(max_length=100, verbose_name='Work Center')

    # Renamed: duration → duration_minutes (Odoo alignment, explicit unit)
    duration_minutes = models.IntegerField(default=30, verbose_name='Duration (minutes)')

    @property
    def name(self):
        """Backwards-compatibility alias for operation_name."""
        return self.operation_name

    @property
    def duration(self):
        """Backwards-compatibility alias for duration_minutes."""
        return self.duration_minutes

    def __str__(self):
        return f"{self.operation_name} at {self.work_center} ({self.duration_minutes} mins)"


class ManufacturingOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('quality_check', 'Quality Check'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    # Added: stored mo_number (Odoo-style document reference)
    mo_number = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        verbose_name='MO Number'
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    # Converted to DecimalField for spec compliance
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=1.00,
        verbose_name='Quantity'
    )

    bom = models.ForeignKey(BoM, on_delete=models.CASCADE)
    assignee = models.CharField(max_length=100, default='John Operative')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    date = models.DateTimeField(auto_now_add=True)

    # Added: planned_date (spec requirement)
    planned_date = models.DateField(blank=True, null=True, verbose_name='Planned Date')

    source_document = models.CharField(max_length=100, blank=True, null=True)
    procurement_group_id = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, default='')

    # Added: updated_at
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def ref(self):
        return f"MO-{self.id:03d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-populate mo_number after first save
        if not self.mo_number:
            self.mo_number = f"MO-{self.id:03d}"
            ManufacturingOrder.objects.filter(pk=self.pk).update(mo_number=self.mo_number)

    def __str__(self):
        return f"{self.ref} ({self.product.name})"


class WorkOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]

    manufacturing_order = models.ForeignKey(
        ManufacturingOrder, on_delete=models.CASCADE, related_name="work_orders"
    )

    # Renamed: name → operation (Odoo alignment)
    operation = models.CharField(max_length=100, default='', verbose_name='Operation')
    work_center = models.CharField(max_length=100, verbose_name='Work Center')

    # Renamed: duration → duration_minutes (explicit unit)
    duration_minutes = models.IntegerField(default=30, verbose_name='Duration (minutes)')

    # Kept for backwards-compat with timer UI; kept alongside new timestamp fields
    elapsed_seconds = models.IntegerField(default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Added: started_at and completed_at (spec requirement, Odoo standard)
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Started At')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Completed At')

    @property
    def name(self):
        """Backwards-compatibility alias for operation."""
        return self.operation

    @property
    def duration(self):
        """Backwards-compatibility alias for duration_minutes."""
        return self.duration_minutes

    def __str__(self):
        return f"{self.operation} - MO-{self.manufacturing_order.id:03d} ({self.status})"
