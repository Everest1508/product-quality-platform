from django import template

from apps.dsr.duration import format_hm

register = template.Library()


@register.filter
def hm(hours):
    """Hours as "1h 30m" (0 as "0m")."""
    try:
        return format_hm(hours) if hours else "0m"
    except (TypeError, ValueError):
        return ""
