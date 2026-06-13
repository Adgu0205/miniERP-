from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.users.permissions import module_required

from . import services
from .forms import BoMForm, MOForm
from .models import BoM, ManufacturingOrder, MOStatus, WorkCenter


# ---- Manufacturing Orders ----
@module_required("manufacturing")
def mo_list(request):
    qs = ManufacturingOrder.objects.select_related("product", "assignee").all()
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    view = request.GET.get("view", "list")
    columns = {s: [] for s, _ in MOStatus.choices}
    if view == "kanban":
        for mo in qs:
            columns.setdefault(mo.status, []).append(mo)
    return render(request, "manufacturing/mo_list.html", {
        "orders": qs, "statuses": MOStatus.choices, "sel_status": status or "",
        "view": view, "columns": columns,
    })


@module_required("manufacturing")
def mo_form(request, pk=None):
    mo = get_object_or_404(ManufacturingOrder, pk=pk) if pk else None
    form = MOForm(request.POST or None, instance=mo)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, "Saved manufacturing order.")
        return redirect("manufacturing:detail", pk=obj.pk)
    return render(request, "manufacturing/mo_form.html", {"form": form, "mo": mo})


@module_required("manufacturing")
def mo_detail(request, pk):
    mo = get_object_or_404(
        ManufacturingOrder.objects.select_related("product", "bom"), pk=pk)
    reqs = list(services.component_requirements(mo))
    return render(request, "manufacturing/mo_detail.html", {
        "mo": mo, "requirements": reqs,
        "work_orders": mo.work_orders.all(),
    })


@module_required("manufacturing")
def mo_action(request, pk, action):
    mo = get_object_or_404(ManufacturingOrder, pk=pk)
    fn = {"confirm": services.confirm, "start": services.start,
          "done": services.done, "cancel": services.cancel}.get(action)
    if fn:
        fn(mo, user=request.user)
        messages.success(request, f"MO {action} done.")
    return redirect("manufacturing:detail", pk=pk)


# ---- Bill of Materials ----
@module_required("manufacturing")
def bom_list(request):
    boms = BoM.objects.select_related("product").prefetch_related("lines").all()
    return render(request, "manufacturing/bom_list.html", {"boms": boms})


@module_required("manufacturing")
def bom_detail(request, pk):
    bom = get_object_or_404(BoM, pk=pk)
    return render(request, "manufacturing/bom_detail.html", {"bom": bom})


@module_required("manufacturing")
def bom_form(request, pk=None):
    bom = get_object_or_404(BoM, pk=pk) if pk else None
    form = BoMForm(request.POST or None, instance=bom)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, "Saved BoM. Add components below.")
        return redirect("manufacturing:bom_detail", pk=obj.pk)
    return render(request, "manufacturing/bom_form.html", {"form": form, "bom": bom})
