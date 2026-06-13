from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("new/", views.product_form, name="new"),
    path("<int:pk>/", views.product_form, name="edit"),
]
