from .models import AuditLog


def log(module, action, instance=None, *, user=None, field="", old="", new="",
        description="", model="", object_ref=""):
    """Write an audit trail entry. `instance` auto-fills model + object_ref."""
    if instance is not None:
        model = model or instance.__class__.__name__
        object_ref = object_ref or str(instance)
    return AuditLog.objects.create(
        user=user if (user and getattr(user, "is_authenticated", False)) else None,
        module=module,
        action=action,
        model=model,
        object_ref=object_ref[:120],
        field=field,
        old_value=str(old)[:255],
        new_value=str(new)[:255],
        description=description[:255],
    )
