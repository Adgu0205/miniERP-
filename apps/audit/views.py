from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.users.permissions import module_required

from .models import Action, AuditLog


@module_required("audit")
def audit_list(request):
    logs = AuditLog.objects.select_related("user").all()
    module = request.GET.get("module", "")
    action = request.GET.get("action", "")
    ref = request.GET.get("ref", "")
    date_from = request.GET.get("from", "")
    date_to = request.GET.get("to", "")

    if module:
        logs = logs.filter(module=module)
    if action:
        logs = logs.filter(action=action)
    if ref:
        logs = logs.filter(object_ref__icontains=ref)
    if date_from:
        try:
            logs = logs.filter(timestamp__date__gte=datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            logs = logs.filter(timestamp__date__lte=datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass

    # Summary cards (respect current filters except pagination)
    counts = {row["action"]: row["c"] for row in logs.values("action").annotate(c=Count("id"))}
    today = timezone.localdate()
    cards = [
        {"label": "Total Logs", "value": logs.count(), "color": "violet"},
        {"label": "Status Changes", "value": counts.get(Action.STATUS, 0), "color": "sky"},
        {"label": "Stock Moves", "value": counts.get(Action.STOCK, 0), "color": "emerald"},
        {"label": "Today", "value": logs.filter(timestamp__date=today).count(), "color": "amber"},
    ]

    page = Paginator(logs, 40).get_page(request.GET.get("page"))
    return render(request, "audit/list.html", {
        "page": page,
        "cards": cards,
        "actions": Action.choices,
        "modules": ["sales", "purchase", "manufacturing", "inventory",
                    "products", "procurement", "users"],
        "sel_module": module, "sel_action": action, "ref": ref,
        "date_from": date_from, "date_to": date_to,
    })
