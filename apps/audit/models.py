from django.conf import settings
from django.db import models


class Action(models.TextChoices):
    CREATE = "create", "Created"
    UPDATE = "update", "Updated"
    STATUS = "status", "Status Change"
    STOCK = "stock", "Stock Change"
    PRICE = "price", "Price Update"
    DELIVERY = "delivery", "Delivery"
    PROCUREMENT = "procurement", "Procurement"


class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    module = models.CharField(max_length=30, db_index=True)
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    model = models.CharField(max_length=60)
    object_ref = models.CharField(max_length=120, blank=True)
    field = models.CharField(max_length=60, blank=True)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        return f"[{self.module}] {self.get_action_display()} {self.object_ref}"
