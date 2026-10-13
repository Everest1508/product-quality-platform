"""What the attendance pages show, derived once from the service rules.

The punch panel, the month strip and the team week dots all read the same
`service` calls the payslip uses, so a page can never quote a different number.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from apps.attendance import service
from apps.attendance.models import AttendanceRecord, format_minutes
from apps.core.timefmt import t12

CURRENCY_SYMBOLS = service.CURRENCY_SYMBOLS


def annotate_effective(record, shift):
    """Attach the capped hours a day counts for, for a template.

    `effective_formatted` is not a model property on purpose: the cap needs the
    company's `WorkShift`, and looking that up per record would be a query per
    row in a list. It is attached to the instance so the partials can keep
    iterating plain records.
    """
    record.effective_minutes = service.effective_span_for(record, shift)
    record.effective_formatted = format_minutes(record.effective_minutes)
    return record


def punch_panel(company, viewer, record, message="", person=None):
    """Everything the punch panel renders, derived once.

    The panel is rendered from two places -- `MyAttendanceView` on a page load
    and `AttendancePunchView` on an htmx punch -- and if they each derived the
    state separately they would eventually disagree about whether somebody is on
    the clock.

    Lateness is shown here because the alternative is finding out you were 45
    minutes late on your payslip weeks later. It comes from `late_penalty_for`,
    the same call the payslip uses, so the panel and the payslip cannot quote
    different numbers.
    """
    shift = service.shift_for(company)
    # `person` is passed in rather than inferred from `record`, because the two
    # are not interchangeable: an admin reading a colleague's page gets
    # `person=that colleague` together with `record=None` on any day the
    # colleague has not punched yet. Inferring from the record then reported the
    # *admin's* forgotten days on somebody else's page -- a warning about the
    # wrong person, which is worse than no warning at all.
    owner = person or (record.user if record is not None else viewer)
    penalty = service.late_penalty_for(record, shift) if record else None
    now = timezone.localtime()

    # "Starts in 42m" is what makes the check-in button's meaning obvious
    # before it is pressed, which matters because arriving late is priced.
    starts_in = (
        shift.start_time.hour * 60 + shift.start_time.minute
        - (now.hour * 60 + now.minute)
    )

    # Numbers the live counter needs, as plain integers. The old template pasted
    # an unquoted ISO string into Alpine's x-data, which is a syntax error, so
    # the counter never ticked.
    today = timezone.localdate()
    shift_start = timezone.make_aware(datetime.combine(today, shift.start_time))
    shift_end = timezone.make_aware(datetime.combine(today, shift.end_time))
    span_minutes = max(1, int((shift_end - shift_start).total_seconds() // 60))
    since_ms = int(record.check_in.timestamp() * 1000) if record and record.check_in else None
    out_ms = int(record.check_out.timestamp() * 1000) if record and record.check_out else None
    worked = record.worked_minutes if record and record.is_complete else 0
    target = shift.worked_minutes_per_day

    # A full day is `worked_minutes_per_day` of work plus the unpaid break, which is
    # exactly the span `service.net_minutes_for` needs before it counts a day as
    # complete. The countdown runs to that moment, measured from the actual check-in.
    day_total = timedelta(minutes=target + shift.break_minutes)
    day_end = record.check_in + day_total if record and record.check_in else None
    remaining = max(0, int((day_end - timezone.now()).total_seconds())) if day_end else 0

    return {
        "since_ms": since_ms,
        "end_ms": int(shift_end.timestamp() * 1000),
        "span_minutes": span_minutes,
        "day_end_ms": int(day_end.timestamp() * 1000) if day_end else None,
        "day_end_label": f"{timezone.localtime(day_end):%I:%M %p}".lstrip("0") if day_end else "",
        "remaining_formatted": f"{remaining // 3600}h {remaining % 3600 // 60:02d}m {remaining % 60:02d}s",
        "shift_end_label": f"{shift.end_time:%I:%M %p}".lstrip("0"),
        "target_minutes": target,
        "target_formatted": format_minutes(target),
        "worked_delta": worked - target if worked else 0,
        "worked_delta_formatted": format_minutes(abs(worked - target)) if worked else "",
        "now_label": f"{now:%I:%M %p}".lstrip("0"),
        "week": week_strip(company, owner, shift),
        "today_record": record,
        "shift": shift,
        "is_open": bool(record and record.is_open),
        "can_punch": not record
        or record.check_in is None
        or record.check_out is None,
        "late_minutes": service.lateness_for(record, shift) if record else 0,
        "late_band": penalty["band"] if penalty else None,
        "shift_label": f"{t12(shift.start_time)}–{t12(shift.end_time)}",
        # What checking in *now* would cost, ticked in the browser from these numbers.
        # They are the same bands `late_penalty_for` applies, never a second copy of the rule.
        "late_rules": {
            "startMs": int(shift_start.timestamp() * 1000),
            "grace": shift.grace_minutes,
            "minorEnd": shift.minor_band_end_minutes,
            "majorEnd": shift.major_band_end_minutes,
            "minorAmt": f"{shift.minor_penalty:,.0f}",
            "majorAmt": f"{shift.major_penalty:,.0f}",
            "symbol": CURRENCY_SYMBOLS.get(shift.penalty_currency, shift.penalty_currency + " "),
            "onTimeBy": f"{(shift_start + timedelta(minutes=shift.grace_minutes)):%I:%M %p}".lstrip("0"),
        },
        "starts_in_minutes": starts_in if starts_in > 0 else None,
        # Every month, not the one on screen: an unclosed day from last month
        # still needs correcting and still stands between the employee and a
        # full day's pay.
        "missing_checkouts": list(service.unclosed_days(company, owner)),
        "message": message,
        # Set when the panel belongs to somebody else: the button would punch the
        # viewer, so the state row is suppressed and only the warning remains.
        "punch_readonly": False,
    }


def month_summary(records, shift, first, last, today):
    """Numbers and a day-by-day strip for the month being viewed.

    Hours come from `effective_minutes` (set by `annotate_effective`), so an
    unclosed day counts the same capped amount here as on the timesheet.
    """
    scheduled = max(1, shift.worked_minutes_per_day)
    by_day = {r.date: r for r in records}
    total = 0
    present = 0
    for r in records:
        mins = getattr(r, "effective_minutes", 0)
        r.day_pct = min(100, round(100 * mins / scheduled))
        if r.check_in:
            present += 1
            total += mins

    cells = []
    day = first
    while day <= last:
        rec = by_day.get(day)
        if rec is not None and rec.check_in:
            mins = getattr(rec, "effective_minutes", 0)
            if rec.is_stale:
                state, note = "stale", "no check-out"
            elif rec.is_open and day == today:
                state, note = "open", "on the clock"
            elif mins >= 0.9 * scheduled:
                state, note = "full", format_minutes(mins)
            else:
                state, note = "part", format_minutes(mins)
            pct = min(100, round(100 * mins / scheduled))
        elif day > today:
            state, note, pct = "future", "", 0
        elif day.weekday() >= 5:
            state, note, pct = "rest", "weekend", 0
        else:
            state, note, pct = "none", "no punch", 0
        cells.append({
            "day": day.day, "state": state, "pct": pct, "is_today": day == today,
            "title": f"{day:%a, %b} {day.day}" + (f": {note}" if note else ""),
        })
        day += timedelta(days=1)

    return {
        "month_total_formatted": format_minutes(total),
        "month_average_formatted": format_minutes(total // present) if present else "–",
        "month_present_days": present,
        "month_cells": cells,
        "month_counts": {
            state: sum(1 for c in cells if c["state"] == state)
            for state in ("full", "part", "open", "stale", "none")
        },
        "month_leading_blanks": first.weekday(),
    }


def week_strip(company, owner, shift):
    """Monday to Sunday for the current week: hours worked per day, for the bars
    under the punch panel."""
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    records = {
        r.date: r
        for r in AttendanceRecord.objects.filter(
            company=company, user=owner, date__gte=monday, date__lte=sunday
        )
    }
    on_leave = service.approved_leave_map(company, monday, sunday).get(owner.pk, set())
    target = max(1, shift.worked_minutes_per_day)
    days = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        record = records.get(day)
        minutes = service.net_minutes_for(record, shift) if record and record.check_in else 0
        if day in on_leave:
            state = "leave"
        elif minutes:
            state = "worked"
        elif day > today:
            state = "future"
        elif day.weekday() >= 5:
            state = "weekend"
        else:
            state = "none"
        days.append({
            "label": f"{day:%a}",
            "date": day,
            "minutes": minutes,
            "formatted": format_minutes(minutes),
            # Compact for the small label under each bar: "8h 49", or a dash.
            "short": f"{minutes // 60}h {minutes % 60:02d}" if minutes else "–",
            "pct": min(100, round(minutes / target * 100)),
            "is_today": day == today,
            "state": state,
        })
    return {
        "days": days,
        "total_formatted": format_minutes(sum(d["minutes"] for d in days)),
    }


def last_week(company, user_ids, shift):
    """For each user, the last seven days as small state dots (worked, leave,
    none, weekend) and the minutes worked, from one query."""
    today = timezone.localdate()
    first = today - timedelta(days=6)
    records = {}
    for r in AttendanceRecord.objects.filter(
        company=company, user_id__in=user_ids, date__gte=first, date__lte=today
    ):
        records[(r.user_id, r.date)] = r
    on_leave = service.approved_leave_map(company, first, today)
    out = {}
    for uid in user_ids:
        days = []
        for offset in range(7):
            day = first + timedelta(days=offset)
            record = records.get((uid, day))
            minutes = service.net_minutes_for(record, shift) if record and record.check_in else 0
            if day in on_leave.get(uid, ()):
                state = "leave"
            elif record and record.check_in and record.is_stale:
                state = "open"
            elif minutes:
                state = "worked"
            elif day.weekday() >= 5:
                state = "weekend"
            else:
                state = "none"
            days.append({"date": day, "state": state, "formatted": format_minutes(minutes)})
        out[uid] = days
    return out


