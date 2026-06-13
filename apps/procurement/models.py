from django.db import models


class ProcurementAction(models.TextChoices):
    PURCHASE = "purchase", "Purchase Order"
    MANUFACTURE = "manufacture", "Manufacturing Order"
    NONE = "none", "No Action (in stock)"


class ProcurementLog(models.Model):
    """Record of every automated procurement decision (USP traceability)."""
    created_at = models.DateTimeField(auto_now_add=True)
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    trigger = models.CharField(max_length=60, help_text="e.g. SO00007 confirmed")
    required_qty = models.DecimalField(max_digits=12, decimal_places=2)
    free_qty = models.DecimalField(max_digits=12, decimal_places=2)
    shortage = models.DecimalField(max_digits=12, decimal_places=2)
    action = models.CharField(max_length=12, choices=ProcurementAction.choices)
    result_ref = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.product.name}: {self.get_action_display()} ({self.shortage})"
