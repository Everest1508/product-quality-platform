from django import template

from apps.costing import service

register = template.Library()


@register.filter
def inr(value):
    return service.inr(value)
