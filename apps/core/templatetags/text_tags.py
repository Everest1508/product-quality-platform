import re

from django import template
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Only http and https are ever matched, so javascript: and data: stay plain text.
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_TRAIL = ".,;:!?)]}"


@register.filter
def linkify(value):
    """Plain text -> safe HTML: every piece is escaped, http(s) URLs become links, line breaks stay."""
    text, out, pos = str(value or ""), [], 0
    for m in _URL.finditer(text):
        url = m.group().rstrip(_TRAIL)
        out.append(conditional_escape(text[pos:m.start()]))
        out.append(format_html('<a href="{0}" target="_blank" rel="noopener noreferrer">{0}</a>', url))
        pos = m.start() + len(url)
    out.append(conditional_escape(text[pos:]))
    return mark_safe("".join(out).replace("\r\n", "\n").replace("\n", "<br>"))
