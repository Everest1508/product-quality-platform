from django import template
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def short_ago(value):
    """"2 days ago" instead of Django's "2 days, 3 hours ago".

    ``timesince`` joins the two biggest units, which is too wide for a table cell
    and wraps onto three lines. Only the first unit is kept.
    """
    if not value:
        return ""
    first = timesince(value).split(",")[0].replace("\xa0", " ")
    if first.startswith("0 "):
        return "just now"
    return f"{first} ago"
