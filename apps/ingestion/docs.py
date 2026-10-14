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


# --- SDK how-to, framework by framework ------------------------------------
# Code uses {url} for the site address; the key is always read from the
# environment so nobody pastes it into source.

_PY_ENV = 'export PQ_API_KEY="YOUR_API_KEY"\nexport PQ_BASE_URL="{url}"'
_JS_ENV = _PY_ENV
_PY_CLIENT = (
    "import os\nfrom pq_sdk import PQClient\n\n"
    'pq = PQClient(api_key=os.environ["PQ_API_KEY"], base_url=os.environ["PQ_BASE_URL"])'
)
_JS_CLIENT = (
    'const { PQClient } = require("pq-befu");\n\n'
    "const pq = new PQClient({\n  apiKey: process.env.PQ_API_KEY,\n  baseUrl: process.env.PQ_BASE_URL,\n});"
)

SDK_FRAMEWORKS = [
    {
        "key": "python", "label": "Python (plain)", "lang": "Python",
        "install": "pip install pq-befu",
        "steps": [
            ("Set the key and address", "bash", _PY_ENV),
            ("Create one client at startup", "python", _PY_CLIENT),
            ("Report a caught error", "python",
             "try:\n    risky()\nexcept Exception as exc:\n    pq.capture_exception(exc)\n    raise"),
            ("Or catch everything in a block or function", "python",
             "from pq_sdk.hooks import capture_exceptions, auto_capture\n\n"
            "with capture_exceptions(pq):\n    risky()\n\n@auto_capture(pq)\ndef nightly_job():\n    ..."),
            ("Feedback and tickets", "python",
             'pq.send_feedback(rating=5, comment="Great product!")\n'
             'pq.create_ticket(title="Invoice PDF is blank", description="From billing", ticket_type="bug")'),
        ],
    },
    {
        "key": "django", "label": "Django", "lang": "Python",
        "install": 'pip install "pq-befu[django]"',
        "steps": [
            ("Set the key and address", "bash", _PY_ENV),
            ("Add the middleware, last in the list", "python",
             'MIDDLEWARE = [\n    # ...\n    "pq_sdk.integrations.django.DjangoMiddleware",\n]'),
            ("Add the settings", "python",
             'import os\n\nPQ_SDK = {\n    "api_key": os.environ["PQ_API_KEY"],\n    "base_url": os.environ["PQ_BASE_URL"],\n    "environment": "production",\n}'),
            ("Anywhere else in your code", "python",
             "from pq_sdk import PQClient\nfrom django.conf import settings\n\n"
             'pq = PQClient(settings.PQ_SDK["api_key"], settings.PQ_SDK["base_url"])\npq.send_feedback(rating=4, comment="Nice")'),
        ],
    },
    {
        "key": "flask", "label": "Flask", "lang": "Python",
        "install": 'pip install "pq-befu[flask]"',
        "steps": [
            ("Set the key and address", "bash", _PY_ENV),
            ("Attach it to the app", "python",
             "from flask import Flask\nfrom pq_sdk.integrations.flask import FlaskIntegration\n\n"
             "app = Flask(__name__)\n" + _PY_CLIENT + "\nFlaskIntegration(app, pq)"),
        ],
    },
    {
        "key": "fastapi", "label": "FastAPI", "lang": "Python",
        "install": 'pip install "pq-befu[fastapi]"',
        "steps": [
            ("Set the key and address", "bash", _PY_ENV),
            ("Add the middleware", "python",
             "from fastapi import FastAPI\nfrom pq_sdk.integrations.fastapi import FastAPIMiddleware\n\n"
             "app = FastAPI()\n" + _PY_CLIENT + "\napp.add_middleware(FastAPIMiddleware, client=pq)"),
        ],
    },
    {
        "key": "express", "label": "Express", "lang": "Node",
        "install": "npm install pq-befu",
        "steps": [
            ("Set the key and address", "bash", _JS_ENV),
            ("Register it around your routes", "javascript",
             _JS_CLIENT + '\nconst { pqExpress } = require("pq-befu/integrations/express");\n\n'
             'const { middleware, errorHandler } = pqExpress({ client: pq, environment: process.env.NODE_ENV });\n\n'
             "app.use(middleware);      // before every route\n// ... your routes ...\napp.use(errorHandler);   // after every route"),
            ("Flush before exit", "javascript", "await pq.flush();"),
        ],
    },
    {
        "key": "fastify", "label": "Fastify", "lang": "Node",
        "install": "npm install pq-befu",
        "steps": [
            ("Set the key and address", "bash", _JS_ENV),
            ("Register the plugin once", "javascript",
             _JS_CLIENT + '\nconst { pqFastify } = require("pq-befu/integrations/fastify");\n\n'
             "await app.register(pqFastify, { client: pq, environment: process.env.NODE_ENV });"),
        ],
    },
    {
        "key": "koa", "label": "Koa", "lang": "Node",
        "install": "npm install pq-befu",
        "steps": [
            ("Set the key and address", "bash", _JS_ENV),
            ("Add it before your routes", "javascript",
             _JS_CLIENT + '\nconst { pqKoa } = require("pq-befu/integrations/koa");\n\n'
             "app.use(pqKoa(pq, { environment: process.env.NODE_ENV }));\n// routes go after this line"),
        ],
    },
    {
        "key": "nestjs", "label": "NestJS", "lang": "Node",
        "install": "npm install pq-befu @nestjs/common rxjs",
        "steps": [
            ("Set the key and address", "bash", _JS_ENV),
            ("Import the module in AppModule", "typescript",
             'import { Module } from "@nestjs/common";\nimport { PqSdkModule } from "pq-befu/integrations/nestjs";\n\n'
             "@Module({\n  imports: [\n    PqSdkModule.forRoot({\n      apiKey: process.env.PQ_API_KEY,\n"
             "      baseUrl: process.env.PQ_BASE_URL,\n      environment: process.env.NODE_ENV,\n    }),\n  ],\n})\nexport class AppModule {}"),
        ],
    },
    {
        "key": "electron", "label": "Electron", "lang": "Node",
        "install": "npm install pq-befu",
        "steps": [
            ("Set the key in the main process only", "bash", _JS_ENV),
            ("Main process", "javascript",
             _JS_CLIENT + '\nconst { pqElectronMain } = require("pq-befu/integrations/electron");\n\n'
             "pqElectronMain(pq, { environment: process.env.NODE_ENV });\n\n"
             'new BrowserWindow({ webPreferences: { preload: require.resolve("pq-befu/preload") } });'),
            ("Renderer (the key never reaches it)", "javascript",
             "try { await runAction(); } catch (err) { await window.pq.captureException(err); throw err; }"),
        ],
    },
    {
        "key": "browser", "label": "Browser / worker", "lang": "Node",
        "install": "npm install pq-befu",
        "steps": [
            ("Use a key you are happy to make public", "text",
             "Anything in browser code can be read by visitors. Prefer sending from your server."),
            ("Report from the page", "javascript",
             'import { PQBrowserClient } from "pq-befu/browser";\n\n'
             'const pq = new PQBrowserClient({ apiKey: PUBLIC_KEY, baseUrl: "{url}" });\n\n'
             "try { await runAction(); } catch (err) { await pq.captureException(err); throw err; }"),
        ],
    },
]

SDK_CHECK = (
    "Trigger a test error, then open Errors for this product. It shows up within a second. "
    "Nothing there? Check that the key is active (a wrong key answers 403) and that the base URL is reachable from your server."
)


def sdk_guide(base_url):
    """Framework-by-framework setup, with the site address filled in."""
    url = base_url.rstrip("/")
    out = []
    for f in SDK_FRAMEWORKS:
        out.append(
            {
                "key": f["key"],
                "label": f["label"],
                "lang": f["lang"],
                "install": f["install"],
                "steps": [
                    {"title": t, "lang": lang, "code": code.replace("{url}", url)}
                    for t, lang, code in f["steps"]
                ],
            }
        )
    return out
