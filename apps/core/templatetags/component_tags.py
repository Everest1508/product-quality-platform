"""Reusable form components. The catalogue and the rules for adding one are in AGENTS.md ("Components").

Every component is a tag here plus a template in `templates/components/`, and its CSS lives in
`templates/core/css/_ui.css`. A component carries no inline <style> or <script>.
"""
from django import template
from django.template.loader import render_to_string

from .dropdown_tags import obj_pairs

register = template.Library()


@register.inclusion_tag("components/multiselect.html")
def multiselect(name, choices, current=(), placeholder="Select…", label="", auto_submit=False):
    """A chip-and-search picker for several values (assignees, tags).

    `choices` is `(value, label)` pairs, `current` the selected values. A hidden multiple
    `<select name=...>` carries the posted value, so a normal form submit and `auto_submit`
    (post the surrounding form on every change) both work.
    """
    chosen = {str(v) for v in current or ()}
    return {
        "name": name,
        "label": label or placeholder,
        "placeholder": placeholder,
        "auto_submit": bool(auto_submit),
        "options": [(str(v), str(t), str(v) in chosen) for v, t in choices],
    }


@register.simple_tag(takes_context=True)
def assignee_picker(context):
    """The ticket assignee picker. Pages hand the people and the current choice over under
    different names (ticket form, product form, quick-assign partial); this reads them all."""
    form = context.get("form")
    qs = context.get("assignees_qs")
    if not qs and form is not None:
        qs = form.fields["assignees"].queryset
    chosen = set(map(str, context.get("selected_ids") or ())) | set(map(str, context.get("assignee_selected_ids") or ()))
    if form is not None:
        value = form["assignees"].value() if "assignees" in form.fields else None
        chosen |= set(map(str, value or ()))
        if form.instance.pk:
            chosen |= {str(a.pk) for a in form.instance.assignees.all()}
    return render_to_string("components/multiselect.html", multiselect(
        "assignees", obj_pairs(qs or [], "pk:get_full_name"), chosen,
        placeholder="Select assignees…", label="Assignees", auto_submit=context.get("auto_submit", False)),
        request=context.get("request"))


@register.simple_block_tag
def field(content, label="", for_id="", hint="", error=""):
    """Label, control, hint and error message in the house spacing. `{% field "Title" for_id="title" %}…{% endfield %}`."""
    return render_to_string("components/field.html", {
        "content": content, "label": label, "for_id": for_id, "hint": hint, "error": error})
