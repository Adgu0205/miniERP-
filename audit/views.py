from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import csv

from core.utils import get_current_role, get_current_user, has_page_access
from audit.models import AuditLog, Notification


def audit_logs(request):
    role = get_current_role(request)
    if not has_page_access(role, "audit_logs"):
        return render(request, "no_access.html", {'page_name': 'Audit Logs'})

    user_info = get_current_user(request)
    logs_qs = AuditLog.objects.all().order_by('-timestamp')

    # Date range + user + module + action type filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    user_filter = request.GET.get('user', '')
    module_filter = request.GET.get('module', '')
    action_filter = request.GET.get('action_type', '')
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
    if user_filter:
        logs_qs = logs_qs.filter(user=user_filter)
    if module_filter:
        logs_qs = logs_qs.filter(module=module_filter)
    if action_filter:
        logs_qs = logs_qs.filter(action_type=action_filter)
    if search:
        logs_qs = logs_qs.filter(
            models.Q(details__icontains=search) | 
            models.Q(record_id__icontains=search) | 
            models.Q(record_type__icontains=search)
        )

    # Dynamic counts for summary cards
    total_logs_count = AuditLog.objects.count()
    create_actions_count = AuditLog.objects.filter(action_type='Create').count()
    update_actions_count = AuditLog.objects.filter(action_type='Update').count()
    delete_actions_count = AuditLog.objects.filter(action_type='Delete').count()

    # P9: Pagination
    paginator = Paginator(logs_qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Get unique values for filter dropdowns
    users = AuditLog.objects.values_list('user', flat=True).distinct().order_by('user')
    modules = AuditLog.objects.values_list('module', flat=True).distinct().order_by('module')

    context = {
        'role': role,
        'user_info': user_info,
        'logs': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'date_from': date_from,
        'date_to': date_to,
        'user_filter': user_filter,
        'module_filter': module_filter,
        'action_filter': action_filter,
        'search': search,
        'users': users,
        'modules': modules,
        'total_logs': total_logs_count,
        'create_actions': create_actions_count,
        'update_actions': update_actions_count,
        'delete_actions': delete_actions_count,
        'total_count': logs_qs.count(),
    }
    return render(request, "audit_logs.html", context)


def export_audit_csv(request):
    """Export audit logs as CSV with the new columns."""
    role = get_current_role(request)
    if not has_page_access(role, "audit_logs"):
        return JsonResponse({'status': 'error', 'message': 'Access Denied'}, status=403)

    logs_qs = AuditLog.objects.all().order_by('-timestamp')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    user_filter = request.GET.get('user', '')
    module_filter = request.GET.get('module', '')
    action_filter = request.GET.get('action_type', '')

    if date_from:
        logs_qs = logs_qs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs_qs = logs_qs.filter(timestamp__date__lte=date_to)
    if user_filter:
        logs_qs = logs_qs.filter(user=user_filter)
    if module_filter:
        logs_qs = logs_qs.filter(module=module_filter)
    if action_filter:
        logs_qs = logs_qs.filter(action_type=action_filter)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'User', 'Module', 'Record Type', 'Record ID', 'Action', 'Field Changed', 'Old Value', 'New Value', 'Details'])
    for log in logs_qs:
        writer.writerow([
            timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            log.user,
            log.module,
            log.record_type,
            log.record_id,
            log.action_type,
            log.field_changed,
            log.old_value,
            log.new_value,
            log.details,
        ])
    return response


@csrf_exempt
def mark_notifications_read(request):
    Notification.objects.filter(read=False).update(read=True)
    return JsonResponse({'status': 'success'})
