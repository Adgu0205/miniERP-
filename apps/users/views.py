from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.models import Action
from apps.audit.services import log
from .forms import UserCreateForm, UserEditForm
from .models import Profile
from .permissions import module_required


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("dashboard:home")
    return render(request, "users/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("users:login")


@login_required
def profile_view(request):
    profiles = None
    if request.user.is_superuser:
        profiles = Profile.objects.select_related("user").all()
    return render(request, "users/profile.html", {
        "profile": getattr(request.user, "profile", None),
        "profiles": profiles,
    })


@module_required("users")
def user_list(request):
    profiles = Profile.objects.select_related("user").order_by("user__username")
    return render(request, "users/manage_list.html", {"profiles": profiles})


@module_required("users")
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log("users", Action.CREATE, user, user=request.user,
            description=f"User '{user.username}' created as {user.profile.get_role_display()}")
        messages.success(request, f"User {user.username} created.")
        return redirect("users:manage")
    return render(request, "users/manage_form.html", {"form": form, "creating": True})


@module_required("users")
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    profile = target.profile
    initial = {"role": profile.role, "position": profile.position,
               "phone": profile.phone, "is_active": target.is_active}
    form = UserEditForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        old_role = profile.role
        profile.role = d["role"]; profile.position = d["position"]; profile.phone = d["phone"]
        profile.save()
        target.is_active = d["is_active"]
        target.is_staff = target.is_superuser = (d["role"] == "admin")
        if d["new_password"]:
            target.set_password(d["new_password"])
        target.save()
        if old_role != d["role"]:
            log("users", Action.UPDATE, target, user=request.user,
                field="role", old=old_role, new=d["role"])
        messages.success(request, f"Updated {target.username}.")
        return redirect("users:manage")
    return render(request, "users/manage_form.html",
                  {"form": form, "target": target, "creating": False})
