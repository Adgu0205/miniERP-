from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.stock_overview, name="overview"),
    path("ledger/", views.ledger, name="ledger"),
]
