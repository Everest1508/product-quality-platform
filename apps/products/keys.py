"""Short product keys such as AUM, used to name tickets (AUM-001)."""

import re

KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,5}$")
MAX_LEN = 6


def suggest_key(name):
    """A key from a product name: the first letters of each part.

    "AU-Marketing" gives AUM, "AU-HRMS" gives AUH, "AU-Marketing-Staging" gives
    AUMS, "CRM" stays CRM. A long first word contributes two letters so
    "Aureole Websites" is AUW and not just AW.
    """
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", name or "") if p]
    if not parts:
        return "PRD"
    if len(parts) == 1:
        word = parts[0].upper()
        key = word if len(word) <= 4 else word[:3]
    else:
        first = parts[0].upper()
        head = first if len(first) <= 3 else first[:2]
        key = head + "".join(p[0].upper() for p in parts[1:])
    key = re.sub(r"^[0-9]+", "", key) or "P"
    key = key[:MAX_LEN]
    while len(key) < 2:
        key += "X"
    return key


def unique_key(name, taken):
    """`suggest_key`, with a number added if another product already has it."""
    base = suggest_key(name)
    if base not in taken:
        return base
    n = 2
    while True:
        suffix = str(n)
        candidate = base[: MAX_LEN - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1
