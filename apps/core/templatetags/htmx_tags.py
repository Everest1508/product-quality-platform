import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def csrf_token_header(context):
    token = context.get("csrf_token", "")
    return mark_safe(json.dumps({"X-CSRFToken": token}))


@register.simple_tag(takes_context=True)
def htmx_page(context, page_num, extra_class=""):
    current_page = context.get("page_obj")
    if not current_page:
        return ""
    params = context.get("request").GET.copy()
    params["page"] = page_num
    query = params.urlencode()
    active = "bg-blue-600 text-white" if page_num == current_page.number else "bg-white text-gray-700 hover:bg-gray-50"
    return mark_safe(
        f'<a href="?{query}" class="px-3 py-1 rounded text-sm font-medium {active} border border-gray-200 {extra_class}">'
        f"{page_num}</a>"
    )
