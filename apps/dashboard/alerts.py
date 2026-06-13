"""Smart Alerts engine — surfaces things a manager must act on.
Used by the topbar bell (context processor) and the alerts page."""
from django.utils import timezone

from apps.users.permissions import has_module


def build_alerts(user):
    from apps.manufacturing.models import ManufacturingOrder, MOStatus
    from apps.products.models import Product
    from apps.sales.models import SalesOrder, SOStatus

    today = timezone.localdate()
    alerts = []

    if has_module(user, "inventory") or has_module(user, "procurement"):
        for p in Product.objects.all():
            if p.free_to_use <= 0:
                alerts.append({
                    "level": "danger", "icon": "📦",
                    "title": f"{p.name} out of free stock",
                    "detail": f"Free to use: {p.free_to_use}",
                    "url": "/procurement/",
                })

    if has_module(user, "sales"):
        for so in (SalesOrder.objects.filter(deadline__lt=today)
                   .exclude(status__in=[SOStatus.DELIVERED, SOStatus.CANCELLED])
                   .select_related("customer")[:10]):
            alerts.append({
                "level": "warning", "icon": "⏰",
                "title": f"{so.reference} is overdue",
                "detail": f"Due {so.deadline} · {so.get_status_display()}",
                "url": f"/sales/{so.pk}/",
            })

    if has_module(user, "manufacturing"):
        for mo in (ManufacturingOrder.objects.filter(deadline__lt=today)
                   .exclude(status__in=[MOStatus.DONE, MOStatus.CANCELLED])
                   .select_related("product")[:10]):
            alerts.append({
                "level": "warning", "icon": "🏭",
                "title": f"{mo.reference} behind schedule",
                "detail": f"Due {mo.deadline} · {mo.get_status_display()}",
                "url": f"/manufacturing/{mo.pk}/",
            })
        # MOs that can't be built — component shortage
        for mo in (ManufacturingOrder.objects.filter(status=MOStatus.DRAFT)
                   .select_related("product", "bom")[:20]):
            from apps.manufacturing.services import component_requirements
            short = [c.name for c, q in component_requirements(mo) if c.free_to_use < q]
            if short:
                alerts.append({
                    "level": "danger", "icon": "🧩",
                    "title": f"{mo.reference} blocked: low components",
                    "detail": "Short: " + ", ".join(short[:3]),
                    "url": f"/manufacturing/{mo.pk}/",
                })
    return alerts


def alerts_context(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {"alerts": [], "alert_count": 0}
    alerts = build_alerts(user)
    return {"alerts": alerts[:12], "alert_count": len(alerts)}
