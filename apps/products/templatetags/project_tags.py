import re

from django import template
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def log_body(entry):
    """An entry's text as safe HTML with each real @mention highlighted."""
    html = escape(entry.body)
    names = sorted((u.username for u in entry.mentions.all()), key=len, reverse=True)
    if names:
        pattern = re.compile(r"(?<![\w@.+-])@(" + "|".join(re.escape(escape(n)) for n in names) + r")(?![\w@+-])", re.I)
        html = pattern.sub(lambda m: f'<span class="pj-mention">@{m.group(1)}</span>', html)
    return mark_safe(html.replace("\n", "<br>"))


@register.filter
def day_label(day):
    today = timezone.localdate()
    if day == today:
        return "Today"
    if (today - day).days == 1:
        return "Yesterday"
    return day.strftime("%A, %-d %B %Y")


@register.filter
def initial(user):
    return (user.username[:1] if user else "?").upper()


@register.filter
def dictget(mapping, key):
    return mapping.get(key, key) if mapping else key
