from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
    path("", views.procurement_list, name="list"),
    path("scan/", views.run_scan, name="scan"),
    path("<int:pk>/replenish/", views.replenish_one, name="replenish"),
]
