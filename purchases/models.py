from django.db import models
from products.models import Product


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('partially_received', 'Partially Received'),
        ('fully_received', 'Fully Received'),
        ('cancelled', 'Cancelled'),
    ]

    # Added: stored po_number (Odoo-style document reference)
    po_number = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        verbose_name='PO Number'
    )
    vendor_name = models.CharField(max_length=150)
    date = models.DateTimeField(auto_now_add=True)

    # Added: expected_receipt_date (spec requirement)
    expected_receipt_date = models.DateField(
        blank=True, null=True, verbose_name='Expected Receipt Date'
    )

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total Amount in INR (₹)")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    source_document = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, default='')

    # Added: created_by and updated_at (Odoo standard audit fields)
    created_by = models.CharField(max_length=100, default='System', verbose_name='Created By')
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def ref(self):
        return f"PO-{self.id:03d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-populate po_number after first save
        if not self.po_number:
            self.po_number = f"PO-{self.id:03d}"
            PurchaseOrder.objects.filter(pk=self.pk).update(po_number=self.po_number)

    def __str__(self):
        return f"{self.ref} ({self.vendor_name})"


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    # Renamed: unit_price → unit_cost (Odoo alignment — purchase context uses cost, not price)
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0.00,
        help_text="Unit Cost in INR (₹)",
        verbose_name='Unit Cost'
    )
    received_quantity = models.IntegerField(default=0)

    @property
    def unit_price(self):
        """Backwards-compatibility alias for unit_cost."""
        return self.unit_cost

    @property
    def line_total(self):
        """Computed line total: quantity × unit_cost (Odoo standard field)."""
        return self.quantity * self.unit_cost

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.name} @ {self.unit_cost}"
