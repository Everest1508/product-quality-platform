"""The costing maths. One place, used by the live preview, the saved list and the print page."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO = Decimal("0.01")
ZERO = Decimal("0")


def num(value, default=ZERO):
    """A typed number as a Decimal. Commas, a rupee sign and blanks are fine; junk is `default`."""
    if isinstance(value, Decimal):
        return value
    text = str(value if value is not None else "").replace(",", "").replace("₹", "").strip()
    if not text:
        return default
    try:
        d = Decimal(text)
    except InvalidOperation:
        return default
    return d if d.is_finite() else default


def pos(value, default=ZERO):
    return max(num(value, default), ZERO)


def money(value):
    return value.quantize(TWO, rounding=ROUND_HALF_UP)


def inr(value):
    """12345.5 -> '₹12,345.50', whole rupees without the paise: '₹12,346'. Indian grouping."""
    v = money(value)
    sign = "-" if v < 0 else ""
    whole, _, paise = f"{abs(v):.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    grouped = ",".join(parts + [tail])
    return f"{sign}₹{grouped}" + ("" if paise == "00" else f".{paise}")


def office_hours(company):
    """(hours per month, hours per day). A month is 30 days, as on the estimate sheet.

    Hours per day is the Attendance shift less the break (10:00-18:30 less 30 min = 8),
    so hours per month is 30 x 8 = 240. Weekly offs are deliberately not taken out.
    """
    from apps.attendance.service import shift_for

    per_day = Decimal(shift_for(company).worked_minutes_per_day) / 60
    return (per_day * 30).quantize(TWO), per_day.quantize(TWO)


def clean_rows(people, others):
    """Drop empty rows and coerce what is left, so saved JSON never holds junk."""
    p = [
        {
            "name": str(r.get("name", "")).strip()[:120],
            "role": str(r.get("role", "")).strip()[:120],
            "salary": str(pos(r.get("salary"))),
            "time": str(pos(r.get("time"))),
            "unit": "days" if r.get("unit") == "days" else "hours",
            "ai": bool(r.get("ai", True)),
        }
        for r in (people or []) if isinstance(r, dict)
    ]
    o = [
        {"name": str(r.get("name", "")).strip()[:120], "amount": str(pos(r.get("amount")))}
        for r in (others or []) if isinstance(r, dict)
    ]
    keep_p = [r for r in p if r["name"] or num(r["salary"]) or num(r["time"])]
    keep_o = [r for r in o if r["name"] or num(r["amount"])]
    return keep_p, keep_o


def compute(i):
    """Turn the typed inputs (a dict of strings and two row lists) into every figure shown.

    `hours_per_month` and `hours_per_day` are not typed; the views fill them from `office_hours`.
    Rate = salary / hours per month. A person's time in days is turned into hours
    with hours per day. Rent and AI scale with dedicated days / days per month.
    Margin mode "markup" prices at cost x (1 + p%); "margin" at cost / (1 - p%).
    A blank hours-per-month gives a zero rate rather than dividing by zero.
    """
    hpm, hpd = pos(i.get("hours_per_month")), pos(i.get("hours_per_day"))
    dpm = Decimal("30")
    days = pos(i.get("dedicated_days"))
    months = days / dpm

    people, others = clean_rows(i.get("people"), i.get("others"))
    rows, labour, ai_heads = [], ZERO, 0
    for r in people:
        rate = pos(r["salary"]) / hpm if hpm else ZERO
        hours = pos(r["time"]) * (hpd if r["unit"] == "days" else 1)
        cost = rate * hours
        labour += cost
        ai_heads += 1 if r["ai"] else 0
        rows.append({**r, "rate": money(rate), "hours": hours.normalize() if hours else ZERO, "cost": money(cost)})

    rent = pos(i.get("rent_monthly")) * months
    ai = pos(i.get("ai_per_person_month")) * ai_heads * months
    extra_rows = [{"name": r["name"], "amount": money(pos(r["amount"]))} for r in others]
    extra = sum((pos(r["amount"]) for r in others), ZERO)
    total = labour + rent + ai + extra

    pct = pos(i.get("margin_percent"))
    mode = "margin" if i.get("margin_mode") == "margin" else "markup"
    if mode == "margin":
        pct = min(pct, Decimal("99.99"))
        price = total / (1 - pct / 100)
    else:
        price = total * (1 + pct / 100)

    pitch_raw = str(i.get("pitch_price") or "").strip()
    pitch = pos(pitch_raw) if pitch_raw else None
    out = {
        "months": months.quantize(Decimal("0.01")).normalize(),
        "people": rows, "others": extra_rows, "ai_heads": ai_heads,
        "labour": money(labour), "rent": money(rent), "ai": money(ai), "extra": money(extra),
        "total": money(total), "price": money(price), "profit": money(price - total),
        "hpm": hpm.normalize(), "hpd": hpd.normalize(), "mode": mode, "has_pitch": pitch is not None,
    }
    shown = money(pitch) if pitch is not None else out["price"]
    out["shown_profit"] = money(shown - total)
    out["shown_margin"] = money((shown - total) / shown * 100) if shown else ZERO
    if pitch is not None:
        out["pitch"] = money(pitch)
        out["pitch_profit"] = money(pitch - total)
        out["pitch_margin"] = (money((pitch - total) / pitch * 100) if pitch else ZERO)
    return out


def quote_lines(r):
    """The client-facing lines: every cost line scaled so they add up to the quoted price.

    Each line shows only a label, a quantity and a price. The price is the line's cost times
    price / total cost, so the margin is spread evenly and no cost, salary or rate is shown.
    Lines are whole rupees; the rounding (and any paise) is settled on the last line so they add up to the total exactly.
    """
    price = r["pitch"] if r["has_pitch"] else r["price"]
    lines = [(p["role"] or p["name"] or "Team member", f"{p['hours']:f} hrs", p["cost"]) for p in r["people"] if p["cost"]]
    if r["rent"]:
        lines.append(("Office and infrastructure", "", r["rent"]))
    if r["ai"]:
        lines.append(("AI tools", "", r["ai"]))
    lines += [(o["name"] or "Other project expenses", "", o["amount"]) for o in r["others"] if o["amount"]]
    if not lines or not r["total"]:
        return [{"label": "Project package", "qty": "Fixed project price", "amount": price}], price
    factor = price / r["total"]
    out = [{"label": a, "qty": b, "amount": (c * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)} for a, b, c in lines]
    out[-1]["amount"] += price - sum((x["amount"] for x in out), Decimal("0"))
    return out, price
