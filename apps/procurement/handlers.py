from django.dispatch import receiver

from apps.sales.signals import sales_order_confirmed

from . import engine


@receiver(sales_order_confirmed)
def on_sales_order_confirmed(sender, order, user=None, **kwargs):
    """Auto-procurement: fired synchronously when an SO is confirmed."""
    engine.run_for_order(order, user=user)
