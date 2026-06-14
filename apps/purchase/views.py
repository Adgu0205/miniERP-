from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.models import Action
from apps.audit.services import log
from apps.users.permissions import module_required

from . import services
from .forms import POForm, POLineFormSet, VendorForm
from .models import POStatus, PurchaseOrder, Vendor


@module_required("purchase")
def po_list(request):
    from django.db.models import Q
    qs = PurchaseOrder.objects.select_related("vendor").prefetch_related("lines").all()
    status = request.GET.get("status")
    q = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(vendor__name__icontains=q))
    if request.GET.get("export") == "csv":
        from config.utils import csv_response
        return csv_response("purchase_orders.csv",
            ["Reference", "Vendor", "Origin", "Date", "Total", "Status"],
            [(o.reference, o.vendor.name if o.vendor else "", o.origin,
              o.order_date, o.total, o.get_status_display()) for o in qs])
    view = request.GET.get("view", "list")
    columns = {s: [] for s, _ in POStatus.choices}
    if view == "kanban":
        for po in qs:
            columns.setdefault(po.status, []).append(po)
    return render(request, "purchase/list.html", {
        "orders": qs, "statuses": POStatus.choices, "sel_status": status or "",
        "view": view, "columns": columns, "q": q})


@module_required("purchase")
def po_form(request, pk=None):
    po = get_object_or_404(PurchaseOrder, pk=pk) if pk else None
    form = POForm(request.POST or None, instance=po)
    formset = POLineFormSet(request.POST or None, instance=po)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        obj = form.save()
        formset.instance = obj
        formset.save()
        if po is None:
            log("purchase", Action.CREATE, obj, user=request.user)
        messages.success(request, "Saved purchase order.")
        return redirect("purchase:detail", pk=obj.pk)
    return render(request, "purchase/form.html",
                  {"form": form, "formset": formset, "po": po})


@module_required("purchase")
def po_detail(request, pk):
    from config.utils import pipeline
    po = get_object_or_404(
        PurchaseOrder.objects.select_related("vendor"), pk=pk)
    steps, cancelled = pipeline(po.status, [
        ("draft", "Draft"), ("confirmed", "Confirmed"),
        ("partial", "Partially Received"), ("received", "Fully Received")])
    return render(request, "purchase/detail.html",
                  {"po": po, "lines": po.lines.select_related("product"),
                   "steps": steps, "cancelled": cancelled})


@module_required("purchase")
def po_action(request, pk, action):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if action == "confirm":
        services.confirm(po, user=request.user)
    elif action == "receive":
        services.receive_all(po, user=request.user)
    messages.success(request, f"PO {action} done.")
    return redirect("purchase:detail", pk=pk)


@module_required("purchase")
def vendor_list(request):
    return render(request, "purchase/vendors.html",
                  {"vendors": Vendor.objects.all()})


@module_required("purchase")
def vendor_form(request, pk=None):
    vendor = get_object_or_404(Vendor, pk=pk) if pk else None
    form = VendorForm(request.POST or None, instance=vendor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved vendor.")
        return redirect("purchase:vendors")
    return render(request, "purchase/vendor_form.html", {"form": form})
