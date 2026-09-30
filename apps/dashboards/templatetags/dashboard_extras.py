"""Template filters for the personal dashboard.

Deliberately forgiving: every one of these renders a dashboard tile from a
value that may be None, and a filter that raises on empty data turns a missing
payroll slip into a 500 instead of an honest "not on payroll" state.
"""

from django import template

register = template.Library()


@register.filter
def abs_value(value):
    try:
        return abs(value)
    except TypeError:
        return value


@register.filter
def amount(value):
    """Money without the trailing noise: 42000 -> '42,000.00'."""
    if value is None:
        return ""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return value


@register.filter
def hours(minutes):
    """Worked minutes as hours: 450 -> '7.5', 0 -> '0'."""
    if not minutes:
        return "0"
    try:
        value = int(minutes) / 60
    except (TypeError, ValueError):
        return minutes
    return str(int(value)) if value == int(value) else f"{value:.1f}"


@register.filter
def days(value):
    """Decimal day count as '3' or '0.5' -- matches leave/payroll wording."""
    if value is None:
        return "0"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return str(int(number)) if number == int(number) else f"{number:g}"
