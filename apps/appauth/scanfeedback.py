"""Scan feedback intake: strict validation. Anything not on the allow-lists is dropped, never stored.

No user id is kept on the row; the person is only used for the rate limit in the view.
"""
import json
import math
import re

from apps.appauth.models import ScanFeedback
from apps.appauth.service import AuthError

MAX_BODY = 4 * 1024
VERSION = re.compile(r"^[0-9A-Za-z._+-]{1,20}$")


def bad(message="Send a small JSON object with app_version and fields."):
    return AuthError("invalid_request", message, 400)


def parse(raw: bytes):
    """The request body as the dict to store, or None when it holds nothing worth keeping."""
    if len(raw) > MAX_BODY:
        raise bad("That report is too large.")
    try:
        data = json.loads(raw or b"null")
    except ValueError:
        raise bad()
    if not isinstance(data, dict):
        raise bad()
    version = data.get("app_version")
    if not isinstance(version, str) or not VERSION.match(version):
        raise bad("app_version must be a short version string.")
    fields, conf = data.get("fields"), data.get("confidence")
    fields = fields if isinstance(fields, dict) else {}
    conf = conf if isinstance(conf, dict) else {}
    row = {"app_version": version,
           "scan_mode": data["scan_mode"] if data.get("scan_mode") in ScanFeedback.MODES else "",
           "parser": data["parser"] if data.get("parser") in ScanFeedback.PARSERS else ""}
    kept = 0
    for key in ScanFeedback.FIELD_KEYS:
        status = fields.get(key)
        if status not in ScanFeedback.STATUSES or (status == "fixed_format" and key != "phones"):
            continue  # unknown field, unknown value, or fixed_format outside phones: ignored
        row[f"{key}_status"] = status
        kept += 1
        c = conf.get(key)
        if isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) and 0 <= c <= 1:
            row[f"{key}_conf"] = float(c)
    return row if kept else None


def save(raw: bytes):
    row = parse(raw)
    if row:
        ScanFeedback.objects.create(**row)
