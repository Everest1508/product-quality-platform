from django import template

from apps.core.icons import ICON_CHOICES, render_icon

register = template.Library()


@register.simple_tag
def icon(name, css_class="ic"):
    """Inline one icon by name. Renders nothing for blank/unknown names."""
    return render_icon(name, css_class)


@register.simple_tag
def icon_choices():
    """`[(name, label, svg)]` for the leave-policy icon picker."""
    return [
        (name, label, render_icon(name, "lp-icon-glyph"))
        for name, label in ICON_CHOICES
    ]
