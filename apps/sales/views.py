from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.models import Action
from apps.audit.services import log
from apps.users.permissions import module_required

from . import services
from .forms import CustomerForm, SOForm, SOLineFormSet
from .models import Customer, SalesOrder, SOStatus


@module_required("sales")
def so_list(request):
    from django.db.models import Q
    qs = SalesOrder.objects.select_related("customer").prefetch_related("lines").all()
    status = request.GET.get("status")
    q = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(customer__name__icontains=q))
    if request.GET.get("export") == "csv":
        from config.utils import csv_response
        return csv_response("sales_orders.csv",
            ["Reference", "Customer", "Date", "Deadline", "Total", "Status"],
            [(o.reference, o.customer.name if o.customer else "", o.order_date,
              o.deadline or "", o.total, o.get_status_display()) for o in qs])
    view = request.GET.get("view", "list")
    columns = {s: [] for s, _ in SOStatus.choices}
    if view == "kanban":
        for so in qs:
            columns.setdefault(so.status, []).append(so)
    return render(request, "sales/list.html", {
        "orders": qs, "statuses": SOStatus.choices, "sel_status": status or "",
        "view": view, "columns": columns, "q": q,
    })


@module_required("sales")
def so_form(request, pk=None):
    so = get_object_or_404(SalesOrder, pk=pk) if pk else None
    form = SOForm(request.POST or None, instance=so)
    formset = SOLineFormSet(request.POST or None, instance=so)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        obj = form.save()
        formset.instance = obj
        formset.save()
        if so is None:
            log("sales", Action.CREATE, obj, user=request.user)
        messages.success(request, "Saved sales order.")
        return redirect("sales:detail", pk=obj.pk)
    return render(request, "sales/form.html",
                  {"form": form, "formset": formset, "so": so})


@module_required("sales")
def so_detail(request, pk):
    from config.utils import pipeline
    so = get_object_or_404(SalesOrder.objects.select_related("customer"), pk=pk)
    steps, cancelled = pipeline(so.status, [
        ("draft", "Draft"), ("confirmed", "Confirmed"),
        ("partial", "Partially Delivered"), ("delivered", "Fully Delivered")])
    return render(request, "sales/detail.html", {
        "so": so, "availability": services.availability(so),
        "steps": steps, "cancelled": cancelled})


@module_required("sales")
def so_action(request, pk, action):
    so = get_object_or_404(SalesOrder, pk=pk)
    fn = {"confirm": services.confirm, "deliver": services.deliver,
          "cancel": services.cancel}.get(action)
    if fn:
        fn(so, user=request.user)
        messages.success(request, f"SO {action} done.")
    return redirect("sales:detail", pk=pk)


@module_required("sales")
def customer_list(request):
    return render(request, "sales/customers.html",
                  {"customers": Customer.objects.all()})


@module_required("sales")
def customer_form(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk) if pk else None
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved customer.")
        return redirect("sales:customers")
    return render(request, "sales/customer_form.html", {"form": form})
