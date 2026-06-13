from django.urls import path

from . import views

app_name = "purchase"

urlpatterns = [
    path("", views.po_list, name="list"),
    path("new/", views.po_form, name="new"),
    path("<int:pk>/", views.po_detail, name="detail"),
    path("<int:pk>/edit/", views.po_form, name="edit"),
    path("<int:pk>/<str:action>/", views.po_action, name="action"),
    path("vendors/", views.vendor_list, name="vendors"),
    path("vendors/new/", views.vendor_form, name="vendor_new"),
    path("vendors/<int:pk>/", views.vendor_form, name="vendor_edit"),
]
