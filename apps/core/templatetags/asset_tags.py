from django import template

from apps.core import assets

register = template.Library()


@register.simple_tag
def app_css():
    return assets.css_url()
