"""Parse and show the time a task took.

A bare number is hours (what the field has always meant); `45m`, `1h 30m`,
`1h30` and `1:30` are understood too. Pure functions, no Django, so they are
easy to test and reuse from the API, the forms and the template filter.
"""
import re
from decimal import ROUND_HALF_UP, Decimal

MESSAGE = "Use a time like 1h 30m, 45m or 1.5"

_NUM = r"(\d+(?:[.,]\d+)?)"
_H = _NUM + r"\s*(?:hours?|hrs?|h)"
_M = _NUM + r"\s*(?:minutes?|mins?|m)"
_BARE = re.compile(r"^" + _NUM + r"$")
_CLOCK = re.compile(r"^(\d+):(\d{1,2})$")
_UNITS = re.compile(r"^(?:" + _H + r")?\s*(?:" + _M + r")?$")
_H_THEN_MINUTES = re.compile(r"^" + _H + r"\s*(\d{1,2})$")


def _d(s):
    return Decimal(s.replace(",", "."))


def parse_hours(text):
    """Hours as a Decimal (0.01 steps), None for blank, ValueError for garbage."""
    s = str(text).strip().lower()
    if not s:
        return None
    if m := _BARE.match(s):
        hours = _d(m.group(1))
    elif m := _CLOCK.match(s):
        hours = Decimal(m.group(1)) + Decimal(m.group(2)) / 60
    elif m := _H_THEN_MINUTES.match(s):
        hours = _d(m.group(1)) + Decimal(m.group(2)) / 60
    elif (m := _UNITS.match(s)) and any(m.groups()):
        hours = (_d(m.group(1)) if m.group(1) else 0) + (_d(m.group(2)) / 60 if m.group(2) else 0)
    else:
        raise ValueError(MESSAGE)
    return Decimal(hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_hm(hours):
    """1.5 -> '1h 30m', 0.75 -> '45m', 2 -> '2h'. Anything unreadable -> ''."""
    try:
        minutes = int((Decimal(str(hours)) * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return ""
    h, m = divmod(minutes, 60)
    return " ".join(p for p in (f"{h}h" if h else "", f"{m}m" if m else "") if p) or "0m"
