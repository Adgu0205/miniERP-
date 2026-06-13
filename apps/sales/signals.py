import django.dispatch

# Fired when a Sales Order is confirmed. Procurement engine listens to this.
sales_order_confirmed = django.dispatch.Signal()  # providing kwargs: order, user
