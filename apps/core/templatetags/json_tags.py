import json

from django import template

register = template.Library()


@register.filter
def json_dumps(value):
    """A Python value as a JS literal for an Alpine attribute.

    Returned as a plain string on purpose: autoescape then turns the `"` into
    `&quot;`, which is what keeps it inside a double-quoted attribute.
    """
    return json.dumps(value, ensure_ascii=False)
