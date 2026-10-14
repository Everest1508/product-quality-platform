from django import template
from django.utils.html import json_script

register = template.Library()

# `messages` is a lazy iterable of Message objects, which json.dumps cannot
# handle and which has no __dict__ contract worth depending on. Only the two
# fields the toast actually renders are carried across.
TOAST_TAGS = {"success", "error", "warning", "info"}


@register.simple_tag
def toast_payload(messages, element_id="toast-seed"):
    """The `messages` context processor's queue as a JSON payload for the toast.

    Escaped through Django's own `json_script`, which is the one helper that
    both emits valid JSON and neutralises `</script>` and `<!--` inside it. That
    is why this is a tag and not a filter: a filter's output gets HTML-escaped
    again by the template engine, turning every `"` into `&quot;` and leaving
    `JSON.parse` to choke.

    `element_id` is what the container's `x-init` looks the seed up by, so two
    toast containers on one page would otherwise both read the first seed and
    show every message twice.

    An unrecognised level is coerced to "info" rather than passed through. The
    value is interpolated into `:class`, and `message.tags` is Django's own
    mapping of its closed set of levels, but a level nobody has styled here
    (DEBUG) should not become a bare class name with no rules behind it.
    """
    payload = [
        {
            "text": str(message),
            "tags": message.tags if message.tags in TOAST_TAGS else "info",
        }
        for message in messages
    ]
    return json_script(payload, element_id)
