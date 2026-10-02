from django import template

register = template.Library()


@register.filter
def opts(spec):
    """"value:Label|value:Label" -> [(value, Label), ...].

    Lets a template spell out a choice list inline, which a Django template
    otherwise cannot do — it has no literal tuple. Only for hardcoded lists;
    anything that already has a Python definition (model `.choices`, a service)
    should be passed to `{% dropdown %}` directly instead of retyped here.
    """
    pairs = []
    for chunk in spec.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        value, sep, text = chunk.partition(":")
        pairs.append((value.strip(), (text.strip() if sep else value.strip())))
    return pairs


@register.filter
def obj_pairs(items, spec):
    """[(value_attr, label_attr)] -> [(value, label), ...] for a queryset.

    A blank label falls back to `username` and then to `str(item)`, which is
    what a member list wants: people have no `get_full_name` until they set one.

    `label_attr` is usually a *method* -- `get_full_name`, `full_name` -- so it
    has to be called. Plain `str(getattr(item, ...))` renders the repr of a
    bound method instead ("<bound method User.get_full_name of <User: bob>>"),
    which puts a Python repr in front of every person in every dropdown.
    """
    value_attr, _, label_attr = spec.partition(":")
    pairs = []
    for item in items:
        raw = getattr(item, label_attr, "")
        if callable(raw):
            raw = raw()
        label = str(raw or "").strip()
        if not label:
            label = (str(getattr(item, "username", "") or "").strip()
                     or str(getattr(item, "name", "") or "").strip()
                     or str(item))
        pairs.append((str(getattr(item, value_attr, "")), label))
    return pairs


def _current_label(options, selected, placeholder):
    """The label to show while the menu is closed.

    Rendered server-side on purpose: with JavaScript off the control must still
    say what is currently chosen rather than reverting to the placeholder.
    """
    if len(selected) == 1:
        for value, text in options:
            if value in selected:
                return text
    return placeholder


@register.inclusion_tag("core/partials/_dropdown.html")
def dropdown(name, choices, current="", placeholder="All", label="", multiple=False, empty_value=None, navigate=False, submit=False, trigger_class="", extra_choices=None):
    """Render one choice control in the house `<details>` idiom.

    Replaces a native `<select>` while keeping the two things a hand-rolled
    dropdown has to work hardest to preserve: the value still posts with the
    form when JavaScript is off, and a change still fires a native `change`
    event, so `hx-trigger="change"` filtering keeps working untouched.

    `choices` is any iterable of `(value, label)` pairs. `current` is the
    selected value for a single dropdown, or an iterable of values for a
    multiple one. Pass `empty_value` for filters that have an "everything"
    state: it becomes a real first option, so the key is always submitted
    instead of vanishing when nothing is picked. Pass `navigate=True` for a
    filter that lives outside a form and reloads the page on change, or
    `submit=True` for one that posts its form on change.

    `extra_choices` appends a second pair list *after* `choices`, for the
    filters that mix hand-written sentinels with a real queryset -- "Assigned
    to me" / "Unassigned" followed by the company's members. A template cannot
    concatenate two iterables into one `choices` argument, and duplicating a
    context block per view to achieve it is worse than one parameter.
    """
    options = [(str(v), str(text)) for v, text in choices]
    if extra_choices:
        options.extend((str(v), str(text)) for v, text in extra_choices)
    if not multiple and empty_value is not None:
        empty_value = str(empty_value)
        options.insert(0, (empty_value, placeholder))

    selected = {str(v) for v in current} if multiple else {str(current if current is not None else "")}
    return {
        "name": name,
        "options": options,
        "selected": selected,
        "multiple": multiple,
        "input_type": "checkbox" if multiple else "radio",
        "placeholder": placeholder,
        "field_label": label or placeholder,
        "closed_label": _current_label(options, selected, placeholder),
        "navigate": navigate,
        "submit": submit,
        "trigger_class": trigger_class,
    }