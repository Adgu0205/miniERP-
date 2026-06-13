from audit.models import Notification
from core.utils import get_current_role, get_current_user, get_role_permissions


def global_context(request):
    """Injects role, user_info, notifications, and permissions into every template."""
    role = get_current_role(request)
    user_info = get_current_user(request)
    permissions = get_role_permissions(role)
    notifications_list = Notification.objects.all().order_by('-timestamp')[:10]
    unread_notifications = Notification.objects.filter(read=False).count()

    return {
        'role': role,
        'user_info': user_info,
        'permissions': permissions,
        'notifications_list': notifications_list,
        'unread_notifications': unread_notifications,
    }
