from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.so_list, name="list"),
    path("new/", views.so_form, name="new"),
    path("<int:pk>/", views.so_detail, name="detail"),
    path("<int:pk>/edit/", views.so_form, name="edit"),
    path("<int:pk>/<str:action>/", views.so_action, name="action"),
    path("customers/", views.customer_list, name="customers"),
    path("customers/new/", views.customer_form, name="customer_new"),
    path("customers/<int:pk>/", views.customer_form, name="customer_edit"),
]
