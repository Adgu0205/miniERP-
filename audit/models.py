from django.db import models


class AuditLog(models.Model):
    # Added: created_at alias — spec requires created_at, timestamp kept for backwards compat
    timestamp = models.DateTimeField(auto_now_add=True)
    module = models.CharField(max_length=50)
    action = models.CharField(max_length=100)

    # Added: object_type and object_id for full Odoo-style traceability
    object_type = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='Object Type',
        help_text='The model/entity this log refers to (e.g. SalesOrder, Product)'
    )
    object_id = models.IntegerField(
        blank=True, null=True,
        verbose_name='Object ID',
        help_text='The primary key of the affected record'
    )

    details = models.TextField()
    user = models.CharField(max_length=100, default='System')

    # New fields for detailed Audit Logs view
    record_id = models.CharField(max_length=50, blank=True, default='', verbose_name='Record ID')
    record_type = models.CharField(max_length=50, blank=True, default='', verbose_name='Record Type')
    field_changed = models.CharField(max_length=50, blank=True, default='-', verbose_name='Field Changed')
    old_value = models.CharField(max_length=100, blank=True, default='-', verbose_name='Old Value')
    new_value = models.CharField(max_length=100, blank=True, default='-', verbose_name='New Value')
    action_type = models.CharField(
        max_length=20, default='Create',
        choices=[('Create', 'Create'), ('Update', 'Update'), ('Delete', 'Delete')],
        verbose_name='Action Type'
    )

    @property
    def created_at(self):
        """Odoo-aligned alias for timestamp."""
        return self.timestamp

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.module}] {self.action} by {self.user}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('low_stock', 'Low Stock Alert'),
        ('procurement_created', 'Procurement Triggered'),
        ('purchase_received', 'Purchase Shipment Received'),
        ('sales_delivered', 'Sales Delivery Dispatched'),
        ('manufacturing_completion', 'Manufacturing Completed'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    message = models.TextField()
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"[{self.type}] {self.message[:40]}"
