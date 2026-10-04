"""The ingestion API as data, for the docs page.

Field lists are read from the real serializers, so the page cannot describe a
field that does not exist or miss one that does. `FIELD_NOTES` only adds the
human words. A test fails if a serializer field has no note, so adding a field
means documenting it.
"""

import json

from apps.ingestion.serializers import ErrorCaptureSerializer, FeedbackSerializer, TicketIngestSerializer

FIELD_NOTES = {
    "errors": {
        "error_type": "The class or kind of error, such as TypeError. Part of how errors are grouped.",
        "message": "What went wrong. Part of how errors are grouped, so keep ids and timestamps out of it.",
        "stacktrace": "The stack trace. The first 500 characters help decide which group this belongs to.",
        "environment": "production, staging and so on.",
        "user_ref": "Your own id for the affected user. Counts distinct users, and is never matched to an account here.",
        "page": "The page or route where it happened.",
        "device": "Device name or model.",
        "os": "Operating system.",
        "browser": "Browser name and version.",
        "version": "Your app's release, such as 2.0.1. Add the same string as a version on the product to get release breakdowns.",
        "request_payload": "The request that failed, as JSON. Values under keys like password, token or secret are replaced before storage.",
        "extra": "Anything else worth keeping, as JSON. Secret-looking keys are replaced here too.",
    },
    "feedback": {
        "user_ref": "Your own id for the person giving feedback.",
        "rating": "A whole number from 1 to 5.",
        "comment": "What they said.",
        "screenshot_url": "A link to a screenshot you host.",
        "version": "Your app's release.",
    },
    "tickets": {
        "title": "A short summary.",
        "description": "The details.",
        "ticket_type": "bug, feature or question. Defaults to bug.",
        "user_ref": "Your own id for the person who reported it.",
        "external_id": "Your id for this ticket, so you can find it again.",
        "metadata": "Anything else, as JSON.",
    },
}


def _type_name(field):
    kind = type(field).__name__
    return {
        "CharField": "string", "URLField": "string", "ChoiceField": "string", "IntegerField": "integer",
        "JSONField": "any JSON", "BooleanField": "boolean",
    }.get(kind, kind.replace("Field", "").lower())


def _fields(key, serializer_class):
    out = []
    for name, field in serializer_class().fields.items():
        extra = []
        if getattr(field, "max_length", None):
            extra.append(f"up to {field.max_length} characters")
        if getattr(field, "min_value", None) is not None and getattr(field, "max_value", None) is not None:
            extra.append(f"{field.min_value} to {field.max_value}")
        out.append(
            {
                "name": name,
                "type": _type_name(field),
                "required": field.required,
                "limits": ", ".join(extra),
                "note": FIELD_NOTES[key].get(name, ""),
            }
        )
    return out


ENDPOINTS = [
    {
        "key": "errors",
        "title": "Report an error",
        "method": "POST",
        "path": "/api/v1/errors/capture/",
        "summary": "Send an error. Errors with the same type, message and start of stack trace are grouped, and each report counts as one occurrence.",
        "serializer": ErrorCaptureSerializer,
        "example": {
            "error_type": "TypeError",
            "message": "Cannot read properties of undefined (reading 'total')",
            "stacktrace": "at renderCart (cart.js:42)\n  at onClick (cart.js:90)",
            "environment": "production",
            "page": "/checkout",
            "version": "2.0.1",
            "user_ref": "user-123",
        },
        "response": {"error_group_id": 12, "occurrence_id": 340, "fingerprint": "9f2c...", "occurrence_count": 5, "created": False},
        "notes": [
            "A resolved error that is reported again reopens, and the owners and admins are told once.",
            "Ignored errors stay ignored but keep counting.",
        ],
    },
    {
        "key": "feedback",
        "title": "Send feedback",
        "method": "POST",
        "path": "/api/v1/feedback/",
        "summary": "Send a rating and an optional comment from a user.",
        "serializer": FeedbackSerializer,
        "example": {"rating": 4, "comment": "Checkout is much faster now", "user_ref": "user-123", "version": "2.0.1"},
        "response": {"feedback_id": 58},
        "notes": [],
    },
    {
        "key": "tickets",
        "title": "Create a ticket",
        "method": "POST",
        "path": "/api/v1/tickets/",
        "summary": "Open a ticket on the product, for example from a Report a problem button.",
        "serializer": TicketIngestSerializer,
        "example": {"title": "Invoice PDF is blank", "description": "Opened from the billing page", "ticket_type": "bug", "user_ref": "user-123"},
        "response": {"ticket_id": 31, "ui_ticket_id": 204, "ui_ticket_key": "AUM-014"},
        "notes": ["ticket_id is the id in the API. ui_ticket_key is the name your team sees in the app, such as AUM-014. ui_ticket_id is the database id behind it."],
    },
    {
        "key": "status",
        "title": "Check a ticket",
        "method": "GET",
        "path": "/api/v1/tickets/{ticket_id}/status/",
        "summary": "Look up a ticket you created through the API. Only tickets from the same product are visible.",
        "serializer": None,
        "example": None,
        "response": {"id": 31, "title": "Invoice PDF is blank", "status": "ingested", "created_at": "2030-06-03T10:15:00+05:30"},
        "notes": [],
    },
]

ERRORS = [
    ("400", "The body is not valid. The response names each field that failed."),
    ("403", "The key is missing, wrong, revoked or expired. Check the Authorization header and the key's status."),
    ("404", "The ticket does not exist for this product."),
    ("429", "Too many requests from this key. The limit is 600 a minute. Wait for the Retry-After seconds."),
]


def _snippets(endpoint, base_url):
    url = base_url.rstrip("/") + endpoint["path"].replace("{ticket_id}", "31")
    body = endpoint["example"]
    pretty = json.dumps(body, indent=2) if body else ""
    out = {}
    if endpoint["method"] == "GET":
        out["curl"] = f'curl {url} \\\n  -H "Authorization: Bearer YOUR_API_KEY"'
        out["python"] = (
            "import requests\n\n"
            f'r = requests.get("{url}", headers={{"Authorization": "Bearer YOUR_API_KEY"}}, timeout=5)\n'
            "print(r.status_code, r.json())"
        )
        out["javascript"] = (
            f'const res = await fetch("{url}", {{\n  headers: {{ Authorization: "Bearer YOUR_API_KEY" }},\n}});\nconsole.log(res.status, await res.json());'
        )
        out["php"] = (
            f'$ch = curl_init("{url}");\ncurl_setopt_array($ch, [\n  CURLOPT_HTTPHEADER => ["Authorization: Bearer YOUR_API_KEY"],\n  CURLOPT_RETURNTRANSFER => true,\n  CURLOPT_TIMEOUT => 5,\n]);\n$body = curl_exec($ch);'
        )
        return out
    out["curl"] = (
        f'curl -X POST {url} \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d \'{json.dumps(body)}\''
    )
    out["python"] = (
        "import requests\n\n"
        f"payload = {pretty}\n"
        f'r = requests.post("{url}", json=payload, headers={{"Authorization": "Bearer YOUR_API_KEY"}}, timeout=5)\n'
        "r.raise_for_status()"
    )
    out["javascript"] = (
        f'await fetch("{url}", {{\n  method: "POST",\n  headers: {{\n    Authorization: "Bearer YOUR_API_KEY",\n    "Content-Type": "application/json",\n  }},\n  body: JSON.stringify({pretty}),\n}});'
    )
    out["php"] = (
        f'$ch = curl_init("{url}");\ncurl_setopt_array($ch, [\n  CURLOPT_POST => true,\n  CURLOPT_HTTPHEADER => ["Authorization: Bearer YOUR_API_KEY", "Content-Type: application/json"],\n  CURLOPT_POSTFIELDS => json_encode({_php_array(body)}),\n  CURLOPT_RETURNTRANSFER => true,\n  CURLOPT_TIMEOUT => 5,\n]);\ncurl_exec($ch);'
    )
    return out


def _php_array(value):
    return "[" + ", ".join(f'"{k}" => {json.dumps(v)}' for k, v in value.items()) + "]"


def build(base_url):
    """Everything the docs page shows, with snippets pointing at `base_url`."""
    docs = []
    for e in ENDPOINTS:
        docs.append(
            {
                "key": e["key"],
                "title": e["title"],
                "method": e["method"],
                "path": e["path"],
                "summary": e["summary"],
                "notes": e["notes"],
                "fields": _fields(e["key"], e["serializer"]) if e["serializer"] else [],
                "response": json.dumps(e["response"], indent=2),
                "snippets": _snippets(e, base_url),
            }
        )
    return docs
