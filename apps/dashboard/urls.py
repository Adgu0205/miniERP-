from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("api/analytics/", views.analytics, name="analytics"),
    path("api/bom-tree/", views.bom_tree, name="bom_tree"),
]
