from django import template

from apps.core.icons import (
    ICON_CHOICES, PRODUCT_ICONS, product_icon_name, render_brand_mark, render_icon,
)

register = template.Library()


@register.simple_tag
def icon(name, css_class="ic"):
    """Inline one icon by name. Renders nothing for blank/unknown names."""
    return render_icon(name, css_class)


@register.simple_tag
def brand_mark(css_class="ic"):
    """Inline the PQ Platform mark."""
    return render_brand_mark(css_class)


@register.simple_tag
def icon_choices():
    """`[(name, label, svg)]` for the leave-policy icon picker."""
    return [
        (name, label, render_icon(name, "lp-icon-glyph"))
        for name, label in ICON_CHOICES
    ]


@register.simple_tag
def product_icon(product, css_class="ic"):
    """A product's own icon, or the default one when none was chosen."""
    name = product.get("icon") if isinstance(product, dict) else getattr(product, "icon", "")
    return render_icon(product_icon_name(name or ""), css_class)


@register.simple_tag
def product_icon_choices():
    """`[(name, svg)]` for the product form's icon picker."""
    return [(n, render_icon(n, "lp-icon-glyph")) for n in PRODUCT_ICONS]
