from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("manage/", views.user_list, name="manage"),
    path("manage/new/", views.user_create, name="manage_new"),
    path("manage/<int:pk>/", views.user_edit, name="manage_edit"),
]
