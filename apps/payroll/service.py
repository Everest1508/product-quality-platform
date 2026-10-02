"""Payroll calculations.

Pay cycle is the 27th of one month to the 26th of the next, because the 27th
of the following month would overlap a day and double-pay it.

Pay is entered as a **monthly salary** where possible, and the daily rate is
derived from it, because that is the number someone actually knows. Working
days already exclude Sat, Sun and company holidays, so the divisor is the real
one for that cycle and a person receives their full monthly salary in a normal
cycle. `effective_rate` is the single place that resolves a profile to a daily
rate; nothing else may divide a salary.

Pay rule, kept deliberately simple:

    daily rate    = monthly salary / working days   (or a rate set directly)
    payable days  = working days in the cycle - unpaid leave days
    gross         = payable days x daily rate

Paid leave (casual, sick) does not reduce it; only policies with
``is_paid = False`` do. There is no overtime logic.
"""

from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from apps.attendance.service import late_penalties_in_period
from apps.leave.models import LeaveRequest
from apps.payroll.models import Holiday, Payslip, PayrollProfile, PayrollRun

DAY = Decimal("1.00")
HALF_DAY = Decimal("0.5")
PERIOD_START_DAY = 27


def format_money(value, currency="INR"):
    """'₹22,200' style, without float rounding creeping in."""
    if value is None:
        return "—"
    quantized = Decimal(value).quantize(Decimal("0.01"))
    whole = f"{int(quantized):,}"
    return f"{currency} {whole}" if float(quantized) == quantized else (
        f"{currency} {quantized:,.2f}"
    )


def format_days(value):
    if value is None:
        return "—"
    value = Decimal(value)
    return str(value.normalize()) if value % 1 else str(int(value))


# --- Pay cycle -------------------------------------------------------------


def cycle_bounds(anchor):
    """The 27th-to-26th cycle containing `anchor`."""
    this_cycle_start = date(anchor.year, anchor.month, PERIOD_START_DAY)
    if anchor.day >= PERIOD_START_DAY:
        start = this_cycle_start
    else:
        start = _add_months(this_cycle_start, -1)
    return start, _add_months(start, 1) - timedelta(days=1)


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def shift_cycle(start, delta):
    """The cycle `delta` months after the one starting on `start`."""
    return cycle_bounds(_add_months(start, delta))


# --- Working days ----------------------------------------------------------


def holiday_dates(company, start, end):
    return set(
        Holiday.objects.filter(
            company=company, date__gte=start, date__lte=end
        ).values_list("date", flat=True)
    )


def working_days(company, start, end, holidays=None):
    """Working days between two dates, excluding weekends and holidays.

    Unlike the leave service (which counts plain Mon-Fri), payroll must skip
    company holidays: a person is not payable for a day the office was shut.
    """
    if end < start:
        return 0
    holidays = holiday_dates(company, start, end) if holidays is None else holidays
    total = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            total += 1
        cursor += timedelta(days=1)
    return total


def working_day_list(company, start, end):
    holidays = holiday_dates(company, start, end)
    days = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


# --- Leave inside a cycle --------------------------------------------------


def leave_days_in_period(company, user, start, end):
    """Paid and unpaid leave days clipped to one cycle.

    A leave request can straddle two cycles (25 Oct - 4 Nov), so the days are
    recomputed from the date range rather than read off
    ``LeaveRequest.days``, which charges the whole request at once.

    Only days the person would actually have been paid for are counted: a
    weekend or a company holiday inside the leave span is skipped, otherwise
    leave covering a holiday would deduct pay for a day that was already free.

    The paid/unpaid split is the request's own, not its policy's -- an approver
    can mark a spell unpaid that the type would normally pay for, and payroll
    has to price the decision that was actually made. A request with no stored
    split predates the field and falls back to its policy, which is the only
    record of the decision that existed then.

    **Paid days are billed from the start of the request**, which is the
    ordering `leave.service.auto_split` used when it decided the split. Given 3
    paid and 2 unpaid over a span crossing the cycle boundary, October's two
    working days are paid and November bills the remaining paid day then the
    unpaid ones. Both halves have to agree or the same request costs a different
    amount depending on which cycle is being run.
    """
    paid = Decimal("0.00")
    unpaid = Decimal("0.00")
    holidays = holiday_dates(company, start, end)
    for request in LeaveRequest.objects.filter(
        company=company,
        user=user,
        status="approved",
        start_date__lte=end,
        end_date__gte=start,
    ).select_related("policy"):
        # Walk the request's *whole* billable span, not just the part inside
        # this cycle, so each day's bucket is decided once and in order. Slicing
        # to the cycle first and then re-applying the full split to the slice
        # would hand every straddling cycle the request's entire paid allowance
        # again: a 3 paid + 2 unpaid spell crossing the boundary would be paid
        # 3 days in October *and* 3 in November, six paid days out of five.
        split = request.split
        # Half the span, so a half-day request inside the cycle stays 0.5.
        share = HALF_DAY if request.is_half_day else DAY
        paid_left = split["paid"]
        unpaid_left = split["unpaid"]
        # The request's holidays are fetched for its *own* span, not this
        # cycle's: a holiday sitting outside the cycle still removes a billable
        # day from the request, and skipping it here would hand its share to
        # whichever day follows.
        request_holidays = (
            holidays
            if request.start_date >= start and request.end_date <= end
            else holiday_dates(company, request.start_date, request.end_date)
        )
        for day in _weekdays(request.start_date, request.end_date):
            if day in request_holidays:
                continue
            # Consume the bucket for *every* day in the span, including the ones
            # belonging to an earlier cycle. Skipping them instead would restart
            # the allowance here and let each straddling cycle be paid the full
            # amount again.
            bucket = "paid" if paid_left > 0 else "unpaid"
            if bucket == "paid":
                paid_left -= share
            else:
                unpaid_left -= share
            if start <= day <= end:
                if bucket == "paid":
                    paid += share
                else:
                    unpaid += share
    return {"paid_days": paid, "unpaid_days": unpaid}


def _weekdays(start, end):
    days = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


# --- Rates -----------------------------------------------------------------


def active_profile(company, user, on_date):
    """The profile in force on `on_date` (most recent effective_from <= it)."""
    return (
        PayrollProfile.objects.filter(
            company=company, user=user, effective_from__lte=on_date
        )
        .order_by("-effective_from", "-created_at")
        .first()
    )


def payable_people(company, on_date):
    """Everyone on payroll as of `on_date`, with the rate that applies.

    Only the most recent profile per person matters, and its ``is_on_payroll``
    flag is the final word: an untick from November therefore stops someone
    appearing in later cycles, while their earlier cycles are unaffected
    because those runs were snapshotted. ``is_on_payroll`` is what keeps
    service accounts and bots out of a run.
    """
    latest = {}
    for profile in PayrollProfile.objects.filter(
        company=company, effective_from__lte=on_date
    ).select_related("user").order_by("user__username", "-effective_from", "-created_at"):
        latest.setdefault(profile.user_id, profile)
    return [
        latest[uid]
        for uid in sorted(latest, key=lambda uid: latest[uid].user.username)
        if latest[uid].is_on_payroll
    ]


# --- Generating a run ------------------------------------------------------


def effective_rate(company, profile, on_date):
    """The daily rate this profile pays on `on_date`.

    One rule: a monthly salary is divided by the working days in the cycle
    containing `on_date`. Sat, Sun and company holidays are already out of that
    count, so a person is paid their whole salary every cycle and adding a
    holiday raises the day rate rather than cutting the pay.

    A profile with no monthly salary is paid the daily rate as typed, which is
    both the per-day case and what keeps rows saved before monthly salary
    existed working.
    """
    if profile.monthly_salary is None or profile.monthly_salary <= 0:
        return profile.daily_rate

    start, end = cycle_bounds(on_date)
    divisor = working_days(company, start, end)
    if divisor < 1:
        return Decimal("0.00")
    return (profile.monthly_salary / Decimal(divisor)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def rate_breakdown(company, profile, on_date, days):
    """How this cycle's rate was arrived at, for the payslip and the screen.

    Plain quantized strings, not display text: this is stored data on a payslip
    that outlives any screen, and formatting belongs in the template.
    """
    rate = effective_rate(company, profile, on_date)
    if profile.monthly_salary is None or profile.monthly_salary <= 0:
        return {"daily_rate": str(rate)}
    return {
        "monthly_salary": str(profile.monthly_salary),
        "working_days": days,
        "daily_rate": str(rate),
    }


def preview(company, start, end):
    """Day counts per person, without writing anything.

    Returns (working_days, [rows]) so the screen can show what a run would pay
    before anyone commits to it.
    """
    days = working_days(company, start, end)
    rows = []
    for profile in payable_people(company, start):
        leave = leave_days_in_period(company, profile.user, start, end)
        rate = effective_rate(company, profile, start)
        late = late_pay_in_period(company, profile.user, start, end, rate)
        # A half day lost to lateness is a working day not paid, so it reduces
        # payable days the same way unpaid leave does; the cash bands are a flat
        # charge on top and cannot be expressed as days.
        payable = max(
            Decimal("0.00"),
            Decimal(days) - leave["unpaid_days"] - late["half_days"],
        )
        cash = late["cash_penalty"]
        # Deductions cannot exceed earnings. Someone on a low salary who is
        # Rs 100 late every single day of the cycle would otherwise be quoted a
        # *negative* gross -- a payslip telling them to hand money back, which
        # is not a thing payroll does. Cap the cash charge at what the payable
        # days can actually absorb and floor gross at zero. The uncapped figure
        # stays in the breakdown so the cap is auditable instead of silently
        # swallowing money.
        earned = (payable * rate).quantize(Decimal("0.01"))
        cash_applied = min(cash, earned) if cash > earned else cash
        rows.append(
            {
                "user": profile.user,
                "profile": profile,
                "daily_rate": rate,
                "currency": profile.currency,
                "working_days": days,
                "paid_leave_days": leave["paid_days"],
                "unpaid_leave_days": leave["unpaid_days"],
                "payable_days": payable,
                "late_half_days": late["half_days"],
                "late_penalty": cash_applied,
                "deduction": (
                    leave["unpaid_days"] * rate
                    + late["half_day_loss"]
                    + cash_applied
                ).quantize(Decimal("0.01")),
                "gross": (earned - cash_applied).quantize(Decimal("0.01")),
                "breakdown": {
                    **rate_breakdown(company, profile, start, days),
                    "late_penalty": format_money(cash_applied),
                    "late_half_days": format_days(late["half_days"]),
                    "late_half_day_loss": format_money(late["half_day_loss"]),
                    # Every event, so a payslip can say why and when.
                    "late_events": late["events"],
                    **(
                        {
                            "late_penalty_uncapped": format_money(cash),
                            "late_penalty_capped_at": format_money(earned),
                        }
                        if cash_applied != cash
                        else {}
                    ),
                },
            }
        )
    return days, rows


def late_pay_in_period(company, user, start, end, daily_rate):
    """What lateness costs one person over a cycle.

    Splits two different things that both reduce pay:
      * `cash_penalty` -- flat Rs 50 / Rs 100 bands, subtracted from gross
        directly because they are not a fraction of a day's pay.
      * `half_days` / `half_day_loss` -- arriving more than an hour late costs
        half a working day, so it is priced at half the daily rate and counted
        as a day the person was not paid for.

    `daily_rate` is passed in rather than recomputed so a payslip and its
    breakdown can never quote two different rates for the same person.
    """
    events = late_penalties_in_period(company, user, start, end)
    half_day_count = Decimal(sum(1 for e in events if e["band"] == "half_day"))
    cash = sum(
        (Decimal(e["amount"]) for e in events if e["band"] in ("minor", "major")),
        Decimal("0.00"),
    )
    return {
        "half_days": half_day_count,
        "half_day_loss": (half_day_count * daily_rate / Decimal("2")).quantize(
            Decimal("0.01")
        ),
        "cash_penalty": cash.quantize(Decimal("0.01")),
        "events": events,
    }


def generate_run(company, start, end, created_by=None):
    """Create (or refresh) the run for a cycle and snapshot a payslip per person.

    Refreshing an unlocked run is deliberate: fixing a missed holiday should
    let you re-run the cycle. A locked run is left alone.
    """
    existing = PayrollRun.objects.filter(
        company=company, period_start=start, period_end=end
    ).first()
    if existing and existing.is_locked:
        return existing, False

    days, rows = preview(company, start, end)
    run = existing or PayrollRun(company=company, period_start=start, period_end=end)
    run.working_days = days
    run.save()

    run.payslips.all().delete()
    for row in rows:
        Payslip.objects.create(
            company=company,
            run=run,
            user=row["user"],
            profile=row["profile"],
            currency=row["currency"],
            daily_rate=row["daily_rate"],
            working_days=row["working_days"],
            paid_leave_days=row["paid_leave_days"],
            unpaid_leave_days=row["unpaid_leave_days"],
            payable_days=row["payable_days"],
            late_half_days=row["late_half_days"],
            late_penalty=row["late_penalty"],
            deduction=row["deduction"],
            gross=row["gross"],
            breakdown={
                "paid_leave": format_days(row["paid_leave_days"]),
                "unpaid_leave": format_days(row["unpaid_leave_days"]),
                # How this daily rate was reached, so the slip explains itself.
                **row["breakdown"],
            },
        )
    if created_by is not None:
        from apps.dashboards.service import log_activity

        log_activity(
            company,
            "payroll_run",
            f"Payroll run for {run.label}",
            description=f"{len(rows)} payslip(s), {days} working days",
            actor=created_by,
            target_content_type="payroll_run",
            target_object_id=run.pk,
        )
    return run, True
