from django.db import models


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('Furniture', 'Furniture'),
        ('Components', 'Components'),
    ]

    STRATEGY_CHOICES = [
        ('MTS', 'Make To Stock (MTS)'),
        ('MTO', 'Make To Order (MTO)'),
    ]

    # Renamed from procure_type → procurement_type (Odoo alignment)
    PROCUREMENT_TYPE_CHOICES = [
        ('Manufacturing', 'Manufacturing'),
        ('Purchase', 'Purchase'),
        ('None', 'None'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Low Stock', 'Low Stock'),
        ('Inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Furniture')

    # Added: Unit of Measure (Odoo standard field)
    uom = models.CharField(max_length=50, default='Units', verbose_name='Unit of Measure')

    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Cost Price in INR (₹)")
    sales_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Sales Price in INR (₹)")

    # NOTE: on_hand and reserved kept as IntegerField to preserve all existing
    # arithmetic throughout views. A future Phase A migration should convert to
    # DecimalField once all template/view references are updated.
    on_hand = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)

    # Renamed: procure_type → procurement_type (Odoo alignment)
    procure_strategy = models.CharField(max_length=10, choices=STRATEGY_CHOICES, default='MTS')
    procurement_type = models.CharField(
        max_length=20,
        choices=PROCUREMENT_TYPE_CHOICES,
        default='None',
        verbose_name='Procurement Type'
    )

    vendor = models.CharField(max_length=150, blank=True, null=True)

    # Converted: reorder_threshold IntegerField → DecimalField (spec requirement)
    reorder_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=5.00,
        verbose_name='Reorder Point'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')

    # Added: audit timestamps (Odoo standard)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    @property
    def free_to_use(self):
        """Free-to-use quantity: on_hand minus reserved. Kept for backwards compatibility."""
        val = self.on_hand - self.reserved
        return val if val > 0 else 0

    @property
    def free_qty(self):
        """Odoo-aligned alias for free_to_use."""
        return self.free_to_use

    def save(self, *args, **kwargs):
        # Update status based on stock level before saving
        if self.status != 'Inactive':
            if self.free_to_use < self.reorder_threshold:
                self.status = "Low Stock"
            else:
                self.status = "Active"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"
