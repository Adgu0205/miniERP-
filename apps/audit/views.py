from django.core.paginator import Paginator
from django.shortcuts import render

from apps.users.permissions import module_required

from .models import Action, AuditLog


@module_required("audit")
def audit_list(request):
    logs = AuditLog.objects.select_related("user").all()
    module = request.GET.get("module")
    action = request.GET.get("action")
    if module:
        logs = logs.filter(module=module)
    if action:
        logs = logs.filter(action=action)
    page = Paginator(logs, 50).get_page(request.GET.get("page"))
    return render(request, "audit/list.html", {
        "page": page,
        "actions": Action.choices,
        "modules": ["sales", "purchase", "manufacturing", "inventory",
                    "products", "procurement"],
        "sel_module": module or "",
        "sel_action": action or "",
    })
