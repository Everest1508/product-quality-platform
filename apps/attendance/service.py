from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.attendance.models import (
    AttendanceRecord,
    WorkShift,
    format_minutes,
    month_bounds,
)
from apps.leave.service import approved_leave_map


def unclosed_days(company, user):
    """Days checked in but never closed out, newest first.

    Query rather than a filter on `is_stale`, which is a property. This is the
    punch panel's warning list, so it deliberately spans **every** month, not
    the one currently being viewed: a punch from last month still costs the
    employee the days between check-in and closing time until it is fixed.
    """
    return AttendanceRecord.objects.filter(
        company=company,
        user=user,
        check_in__isnull=False,
        check_out__isnull=True,
        date__lt=timezone.localdate(),
    ).order_by("-date")


def get_today_record(company, user):
    return AttendanceRecord.objects.filter(
        company=company, user=user, date=timezone.localdate()
    ).first()


def get_who_is_in(company):
    """Members currently on the clock: check-in set, check-out still null.

    This can include yesterday's forgotten check-out, which is the point --
    an admin needs to see it, and the record stays editable.
    """
    records = (
        AttendanceRecord.objects.filter(
            company=company, check_in__isnull=False, check_out__isnull=True
        )
        .select_related("user")
        .order_by("check_in")
    )
    return [
        {
            "user": record.user,
            "record": record,
            "role": _role_for(record.user, company),
            "is_stale": record.is_stale,
        }
        for record in records
    ]


def _company_members(company):
    """Everyone with a membership in the company, ordered by username.

    Membership is unique per (user, company), so this cannot yield duplicates.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return list(User.objects.filter(memberships__company=company).order_by("username"))


def _blank_row(user, on_leave=None):
    """A timesheet row for an employee with no punches in the month."""
    return {
        "user": user,
        "days": [],
        "present_days": 0,
        "absent_days": 0,
        # Left-open days that were never closed out. Distinct from `open_days`
        # in a monthly row, which counted every unclosed day including today's.
        "open_days": 0,
        "total_minutes": 0,
        "late_days": 0,
        "leave_days": set() if on_leave is None else set(on_leave),
    }


def get_team_today(company):
    """Every member with their record for today, checked in or not."""
    today = timezone.localdate()
    records = {
        r.user_id: r
        for r in AttendanceRecord.objects.filter(company=company, date=today).select_related("user")
    }
    on_leave = approved_leave_map(company, today, today)
    return [
        {
            "user": member,
            "record": records.get(member.pk),
            "role": _role_for(member, company),
            "on_leave": today in on_leave.get(member.pk, ()),
        }
        for member in _company_members(company)
    ]


def _role_for(user, company):
    from apps.accounts.models import Membership

    membership = Membership.objects.filter(user=user, company=company).first()
    return membership.role if membership else ""


def get_monthly_rows(company, year, month, user=None):
    """Per-employee totals for one calendar month, for the timesheet grid.

    Every member is listed even when they have no punches in the month, so
    someone who never clocked in reads as 0h rather than silently vanishing
    from the report. Members with no rows at all would otherwise be
    indistinguishable from employees who do not belong to the company.
    """
    first, last = month_bounds(year, month)
    qs = AttendanceRecord.objects.filter(
        company=company, date__gte=first, date__lte=last
    )
    if user is not None:
        qs = qs.filter(user=user)

    on_leave = approved_leave_map(company, first, last)
    shift = shift_for(company)

    by_user = OrderedDict()
    for member in _company_members(company):
        if user is not None and member.pk != user.pk:
            continue
        by_user[member.pk] = _blank_row(member, on_leave.get(member.pk))

    for record in qs.select_related("user").order_by("user__username", "date"):
        row = by_user.get(record.user_id) or by_user.setdefault(
            record.user_id, _blank_row(record.user)
        )
        row["days"].append(record)
        if record.is_stale:
            row["open_days"] += 1

        if record.check_in is not None:
            row["present_days"] += 1
        else:
            row["absent_days"] += 1
        row["total_minutes"] += net_minutes_for(record, shift)
        if record.check_in is not None and late_label_for(record, shift):
            row["late_days"] += 1

    rows = list(by_user.values())
    for row in rows:
        row["leave_day_count"] = len(row.pop("leave_days"))
        row["total_formatted"] = format_minutes(row["total_minutes"])
        row["avg_per_day_formatted"] = (
            format_minutes(round(row["total_minutes"] / row["present_days"]))
            if row["present_days"] else "—"
        )
    return rows


def get_month_grid(company, year, month, user):
    """Calendar grid rows for one employee: day -> record, plus month totals."""
    first, last = month_bounds(year, month)
    records = {
        r.date: r
        for r in AttendanceRecord.objects.filter(
            company=company, user=user, date__gte=first, date__lte=last
        )
    }
    on_leave = approved_leave_map(company, first, last).get(user.pk, set())
    # One shift lookup for the whole month, not one per day.
    shift = shift_for(company)

    # Walk the month so leading/trailing blanks keep their weekday offset.
    days = []
    cursor = first
    while cursor <= last:
        record = records.get(cursor)
        days.append({
            "date": cursor,
            "day": cursor.day,
            "weekday": cursor.weekday(),
            "is_weekend": cursor.weekday() >= 5,
            "is_today": cursor == timezone.localdate(),
            "record": record,
            "on_leave": cursor in on_leave,
            "net_minutes": net_minutes_for(record, shift) if record else 0,
            "late_label": late_label_for(record, shift)
            if record and record.check_in
            else None,
            "is_unclosed": bool(record and record.is_stale),
        })
        cursor += timedelta(days=1)

    total_minutes = sum(d["net_minutes"] for d in days)
    return {
        "days": days,
        "total_minutes": total_minutes,
        "total_formatted": format_minutes(total_minutes),
        "present_days": sum(1 for d in days if d["record"] and d["record"].check_in),
        "absent_days": sum(
            1 for d in days
            if not d["on_leave"] and (not d["record"] or not d["record"].check_in)
        ),
        "leave_days": sum(1 for d in days if d["on_leave"]),
        "late_days": sum(1 for d in days if d["late_label"]),
        # Only days that are genuinely unclosed, not days still being worked.
        "open_days": sum(1 for d in days if d["is_unclosed"]),
    }


def parse_month(raw):
    """Parse ?month=YYYY-MM, falling back to the current month.

    Anything that is not exactly two numeric parts in range is rejected, so a
    stray value like "2026-1-5-x" cannot resolve to January.
    """
    today = timezone.localdate()
    if raw:
        parts = str(raw).strip().split("-")
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            year, month = int(parts[0]), int(parts[1])
            if 1 <= month <= 12 and 1900 <= year <= 2200:
                return year, month
    return today.year, today.month


def month_shift(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_label(year, month):
    return date(year, month, 1).strftime("%B %Y")


def shift_for(company):
    """The company's `WorkShift`, created with office-policy defaults.

    `get_or_create` rather than a required FK: a company with no shift row must
    still be able to run payroll, and the defaults are the real policy.
    """
    shift, _created = WorkShift.objects.get_or_create(company=company)
    return shift


def effective_span_for(record, shift=None):
    """The span a day is worth for reporting, even if nobody closed it out.

    An unclosed record is not zero hours: the employee demonstrably worked from
    check-in, and scoring the day 0 quietly costs them a day's pay until an admin
    happens to notice. So an open day counts elapsed time -- **capped at
    `shift.worked_minutes_per_day`**, i.e. assume they left at closing time.

    The cap is not optional. Elapsed time is measured from check-in to *now*, so
    without it a forgotten punch accrues hours forever and one unclosed record
    from last month reports 300h in a 22-working-day month.

    This cannot move anyone's pay: payslips price payable *days*
    (`payroll/service`), not hours, and `late_penalties_in_period` only reads
    `check_in`. It changes what the timesheet and the dashboard report.

    Falls back to 0 for a record with no check_in: nobody arrived, so there is
    nothing to count, and `lateness_for` already treats that as not-late.
    """
    if record.is_complete:
        return record.worked_minutes
    if not record.is_open:
        return 0
    shift = shift or shift_for(record.company)
    return min(record.elapsed_minutes, shift.worked_minutes_per_day)


def net_minutes_for(record, shift):
    """Worked minutes for one day, less the unpaid scheduled break.

    A 10:00-19:00 punch pair spans 9 hours but is 8 hours of work once the 60
    minute break comes off, and it is the 8 that office hours are measured
    against. `record.worked_minutes` stays the raw span -- that is what the
    punches say -- and this is the number the reports show.

    The break is only deducted from a day long enough to contain it. Someone
    who leaves at 11:00 has not sat out a 60 minute break, and taking one off
    anyway would under-report a short day that is already short.

    Note how `effective_span_for`'s cap lands *below* this threshold on
    purpose: `worked_minutes_per_day` is already net of the break, so a capped
    unclosed day passes through here un-deducted and reports exactly the day.
    Do not "simplify" the comparison to `<=`.
    """
    span = effective_span_for(record, shift)
    if span < shift.worked_minutes_per_day + shift.break_minutes:
        return span
    return max(0, span - shift.break_minutes)


def late_label_for(record, shift):
    """Short flag for the calendar grid, or None when the day was fine.

    Deliberately terse: the grid is dense, and the reason for any charge lives
    on the payslip, not squeezed into a 30px cell.
    """
    minutes = lateness_for(record, shift)
    band = shift.band_for_late_minutes(minutes)
    if band == "on_time":
        return None
    if band == "half_day":
        return f"late {minutes}m · half day"
    return f"late {minutes}m"


def lateness_for(record, shift=None):
    """Minutes late for one attendance row, or 0 when on time.

    Only `check_in` matters. A missing punch is not lateness -- someone who
    never clocked in has no arrival time to be late with, and guessing one
    would silently cost them money.
    """
    if record.check_in is None:
        return 0
    shift = shift or shift_for(record.company)
    scheduled = timezone.localtime(record.check_in).time()
    late = (
        scheduled.hour * 60 + scheduled.minute
        - (shift.start_time.hour * 60 + shift.start_time.minute)
    )
    return max(0, late)


def late_penalty_for(record, shift=None):
    """The money consequence of one late arrival.

    Returns `None` on time or with no punch, otherwise a dict carrying the
    band, the amount and enough detail for a payslip to explain itself. Kept as
    a plain dict (not a model) so it is recomputed from attendance every time
    rather than stored -- an admin editing a punch must never have to remember
    to also fix a penalty row.
    """
    shift = shift or shift_for(record.company)
    late_minutes = lateness_for(record, shift)
    band = shift.band_for_late_minutes(late_minutes)
    if band == "on_time":
        return None
    amount = {
        "minor": shift.minor_penalty,
        "major": shift.major_penalty,
        "half_day": Decimal("0"),  # costs a half day of pay, priced in payroll
    }[band]
    return {
        "date": record.date.isoformat(),
        "late_minutes": late_minutes,
        "band": band,
        "amount": str(amount),
        "currency": shift.penalty_currency,
        "reason": _penalty_reason(record, late_minutes, band, shift),
    }


def _penalty_reason(record, late_minutes, band, shift):
    # Date *and* time: a payslip line has to stand on its own as the record of
    # why someone was charged, months later.
    when = timezone.localtime(record.check_in).strftime("%Y-%m-%d %H:%M")
    if band == "half_day":
        return (
            f"Checked in at {when}, more than "
            f"{shift.major_band_end_minutes} min after the {shift.start_time:%H:%M} "
            f"shift start — half day."
        )
    return (
        f"Checked in at {when}, {late_minutes} min after the "
        f"{shift.start_time:%H:%M} shift start."
    )


def late_penalties_in_period(company, user, start_date, end_date):
    """Every late penalty for one person in a date range, cheapest query first.

    Only completed, dated records with a punch are considered, so a forgotten
    check-out cannot invent a penalty.
    """
    shift = shift_for(company)
    records = AttendanceRecord.objects.filter(
        company=company,
        user=user,
        check_in__isnull=False,
        date__gte=start_date,
        date__lte=end_date,
    ).order_by("date")
    return [p for p in (late_penalty_for(r, shift) for r in records) if p]
