from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def has_module(user, module):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_access(module))


def module_required(module):
    """Gate a view behind a module the user's role can access."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not has_module(request.user, module):
                raise PermissionDenied(f"Your role cannot access '{module}'.")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
