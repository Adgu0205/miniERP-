from django.db import models
from django.utils import timezone
from products.models import Product


class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('partially_delivered', 'Partially Delivered'),
        ('fully_delivered', 'Fully Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    # Added: stored order_number field (Odoo-style document reference)
    order_number = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        verbose_name='Order Number'
    )
    customer_name = models.CharField(max_length=150)
    customer_address = models.TextField(blank=True, default='', verbose_name='Customer Address')
    sales_person = models.CharField(max_length=100, blank=True, default='', verbose_name='Sales Person')
    date = models.DateTimeField(auto_now_add=True)
    expected_delivery_date = models.DateField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total Amount in INR (₹)")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    procurement_group_id = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, default='')

    # Added: created_by and updated_at (Odoo standard audit fields)
    created_by = models.CharField(max_length=100, default='System', verbose_name='Created By')
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def ref(self):
        return f"SO-{self.id:03d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-populate order_number after first save (uses PK)
        if not self.order_number:
            self.order_number = f"SO-{self.id:03d}"
            SalesOrder.objects.filter(pk=self.pk).update(order_number=self.order_number)

    def __str__(self):
        return f"{self.ref} ({self.customer_name})"


class SalesOrderItem(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Unit Price in INR (₹)")
    delivered_quantity = models.IntegerField(default=0)

    @property
    def line_total(self):
        """Computed line total: quantity × unit_price (Odoo standard field)."""
        return self.quantity * self.unit_price

    @property
    def remaining_quantity(self):
        return self.quantity - self.delivered_quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.name} @ {self.unit_price}"
