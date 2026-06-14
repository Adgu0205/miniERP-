from django import template
import json

register = template.Library()


@register.filter
def replace_underscore(value):
    """Replace underscores with spaces in a string."""
    if isinstance(value, str):
        return value.replace('_', ' ')
    return value


@register.filter
def mo_ref(value):
    """Format an integer as MO-XXX (zero-padded to 3 digits)."""
    try:
        return f"MO-{int(value):03d}"
    except (ValueError, TypeError):
        return value


@register.filter
def so_ref(value):
    """Format an integer as SO-XXX."""
    try:
        return f"SO-{int(value):03d}"
    except (ValueError, TypeError):
        return value


@register.filter
def po_ref(value):
    """Format an integer as PO-XXX."""
    try:
        return f"PO-{int(value):03d}"
    except (ValueError, TypeError):
        return value


@register.filter
def to_json(value):
    """Serialize a Python object to a JSON string for safe use in templates."""
    try:
        return json.dumps(value)
    except (ValueError, TypeError):
        return '{}'


@register.filter
def divide(value, arg):
    """Divide value by arg."""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

