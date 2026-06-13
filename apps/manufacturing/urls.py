from django.urls import path

from . import views

app_name = "manufacturing"

urlpatterns = [
    path("", views.mo_list, name="list"),
    path("new/", views.mo_form, name="new"),
    path("<int:pk>/", views.mo_detail, name="detail"),
    path("<int:pk>/edit/", views.mo_form, name="edit"),
    path("<int:pk>/<str:action>/", views.mo_action, name="action"),
    path("bom/", views.bom_list, name="bom_list"),
    path("bom/new/", views.bom_form, name="bom_new"),
    path("bom/<int:pk>/", views.bom_detail, name="bom_detail"),
    path("bom/<int:pk>/edit/", views.bom_form, name="bom_edit"),
]
