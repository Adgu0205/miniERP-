from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
import csv

from core.utils import get_current_role, get_current_user, has_page_access
from audit.models import AuditLog, Notification


def audit_logs(request):
    role = get_current_role(request)
    if not has_page_access(role, "audit_logs"):
        return render(request, "no_access.html", {'page_name': 'Audit Logs'})

    user_info = get_current_user(request)
    logs_qs = AuditLog.objects.all().order_by('-timestamp')

    # P9: Date range + module filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    module_filter = request.GET.get('module', '')
    search = request.GET.get('search', '')

    if date_from:
        try:
            logs_qs = logs_qs.filter(timestamp__date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            logs_qs = logs_qs.filter(timestamp__date__lte=date_to)
        except Exception:
            pass
    if module_filter:
        logs_qs = logs_qs.filter(module=module_filter)
    if search:
        logs_qs = logs_qs.filter(details__icontains=search)

    # P9: Pagination
    paginator = Paginator(logs_qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Get unique modules for filter dropdown
    modules = AuditLog.objects.values_list('module', flat=True).distinct().order_by('module')

    context = {
        'role': role,
        'user_info': user_info,
        'logs': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'date_from': date_from,
        'date_to': date_to,
        'module_filter': module_filter,
        'search': search,
        'modules': modules,
        'total_count': logs_qs.count(),
    }
    return render(request, "audit_logs.html", context)


def export_audit_csv(request):
    """P9: Export audit logs as CSV."""
    role = get_current_role(request)
    if not has_page_access(role, "audit_logs"):
        return JsonResponse({'status': 'error', 'message': 'Access Denied'}, status=403)

    logs_qs = AuditLog.objects.all().order_by('-timestamp')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    module_filter = request.GET.get('module', '')

    if date_from:
        logs_qs = logs_qs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs_qs = logs_qs.filter(timestamp__date__lte=date_to)
    if module_filter:
        logs_qs = logs_qs.filter(module=module_filter)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Module', 'Action', 'Details', 'User'])
    for log in logs_qs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.module,
            log.action,
            log.details,
            log.user,
        ])
    return response


@csrf_exempt
def mark_notifications_read(request):
    Notification.objects.filter(read=False).update(read=True)
    return JsonResponse({'status': 'success'})
