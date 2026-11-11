from django import template

from apps.core import assets

register = template.Library()


@register.simple_tag
def app_css():
    return assets.css_url()


@register.simple_tag
def component_js(name):
    """URL of templates/core/js/<name>.js, cache-busted by content."""
    return assets.js_url(name)
