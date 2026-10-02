from django import template
from django.utils.html import json_script

from apps.leave.service import format_days

register = template.Library()


@register.simple_tag
def leave_decision_payload(items, element_id="leave-decision-data"):
    """The approver dialog's rows, as JSON for the page to read.

    The view stringifies every day count on the way out, so nothing here has to
    serialise a `Decimal` into a JS number -- `json.dumps` has no answer for
    one, and silently coercing it to a float is how a 0.5 day split turns into
    0.5 fine and an 11.5 into 11.5 fine too, right up until a value like
    `1E+4` lands in the dialog as scientific notation.

    `json_script` is doing the real work: it is the one helper that emits valid
    JSON *and* neutralises `</script>` and `<!--`, so a leave reason containing
    either cannot close the block early.
    """
    return json_script(list(items), element_id)


@register.filter
def leave_days(value):
    """Render a day count the way `service.format_days` does.

    A template filter rather than a property on the model because the split is a
    `Decimal` and `str()` on one emits exponent notation whenever the exponent
    is positive -- `Decimal("1E+4")` renders as `1E+4`. `format_days` is the one
    helper that strips trailing zeros and never does that, and routing the
    templates through it keeps `|floatformat:"-2"` out of the leave screens,
    where it was producing "12.00" next to a "12 paid" pill.
    """
    if value is None:
        return ""
    return format_days(value)