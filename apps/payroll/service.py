"""Payroll calculations.

Pay cycle is the 27th of one month to the 26th of the next, because the 27th
of the following month would overlap a day and double-pay it.

Pay is entered as a **monthly salary** where possible, and the daily rate is
derived from it, because that is the number someone actually knows. The rate is
the salary divided by every calendar day in the cycle (28 to 31), and weekly
offs and holidays are paid days, so a person who misses nothing receives their
full monthly salary and each unpaid day costs one day rate. `effective_rate` is
the single place that resolves a profile to a daily rate; nothing else may
divide a salary.

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

from django.db import transaction
from django.db.models import Q

from apps.attendance.models import WEEKEND, weekly_off_for
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


def cycle_key(end):
    """A cycle is named by the month it ends in: 27 Sep to 26 Oct is "2026-10"."""
    return f"{end:%Y-%m}"


def cycle_from_key(key):
    """The (start, end) a `cycle_key` names, or None for anything else."""
    try:
        year, month = (int(part) for part in key.split("-"))
        return cycle_bounds(date(year, month, 1))
    except (AttributeError, TypeError, ValueError):
        return None


def last_finished_cycle(today):
    """The newest cycle whose last day has passed: the one that is ready to pay."""
    start, _ = cycle_bounds(today)
    return cycle_bounds(start - timedelta(days=1))


def cycle_options(company, today, limit=24):
    """Cycles to choose from, newest first, from the first payroll record to the running one.

    Each says where it stands, so nobody has to remember which month was done:
    "In progress", "Not created", "Created" or "Locked".
    """
    firsts = [
        d for d in (
            PayrollProfile.objects.filter(company=company).order_by("effective_from").values_list("effective_from", flat=True).first(),
            PayrollRun.objects.filter(company=company).order_by("period_start").values_list("period_start", flat=True).first(),
        ) if d
    ]
    runs = {r.period_end: r for r in PayrollRun.objects.filter(company=company)}
    running = cycle_bounds(today)
    earliest = cycle_bounds(min(firsts))[0] if firsts else running[0]
    options, start = [], running[0]
    while len(options) < limit:
        s, e = cycle_bounds(start)
        run = runs.get(e)
        options.append({
            "key": cycle_key(e),
            "month": f"{e:%B %Y}",
            "range": f"{s.day} {s:%b} to {e.day} {e:%b}",
            "start": s,
            "end": e,
            "status": (
                "In progress" if e >= today
                else "Locked" if run and run.is_locked
                else "Created" if run
                else "Not created"
            ),
        })
        if s <= earliest:
            break
        start = s - timedelta(days=1)
    return options


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
    """Working days between two dates, excluding weekly offs and holidays.

    The weekly offs are the company's (`weekly_off_for`: Saturday and Sunday
    unless it changed them), the same days the leave service skips. Payroll
    also skips company holidays: a person is not payable for a day the office
    was shut. Work done on a weekly off never adds to or takes from this.
    """
    if end < start:
        return 0
    holidays = holiday_dates(company, start, end) if holidays is None else holidays
    off = weekly_off_for(company)
    total = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() not in off and cursor not in holidays:
            total += 1
        cursor += timedelta(days=1)
    return total


def working_day_list(company, start, end):
    holidays = holiday_dates(company, start, end)
    off = weekly_off_for(company)
    days = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() not in off and cursor not in holidays:
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
    weekly off or a company holiday inside the leave span is skipped, otherwise
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
    off = weekly_off_for(company)
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
        for day in _weekdays(request.start_date, request.end_date, off):
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


def _weekdays(start, end, off=WEEKEND):
    """The days in a range that are not weekly offs (what a leave request is charged on)."""
    days = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() not in off:
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


def payable_people(company, on_date, end=None):
    """Everyone on payroll as of `on_date`, with the rate that applies.

    Only the most recent profile per person matters, and its ``is_on_payroll``
    flag is the final word: an untick from November therefore stops someone
    appearing in later cycles, while their earlier cycles are unaffected
    because those runs were snapshotted. ``is_on_payroll`` is what keeps
    service accounts and bots out of a run.

    With `end` (the cycle's last day), a person whose very first profile starts
    inside the cycle is a joiner: they are listed too, on that first profile,
    with `joins_on` set to its date so the cycle pays from that day to the end.
    A raise for someone already paid never makes a joiner.
    """
    latest, first = {}, {}
    profiles = PayrollProfile.objects.filter(
        company=company, effective_from__lte=end or on_date
    ).select_related("user").order_by("user__username", "-effective_from", "-created_at")
    for profile in profiles:
        first[profile.user_id] = profile  # ends as the earliest profile
        if profile.effective_from <= on_date:
            latest.setdefault(profile.user_id, profile)
    people = [
        latest[uid]
        for uid in sorted(latest, key=lambda uid: latest[uid].user.username)
        if latest[uid].is_on_payroll
    ]
    for profile in people:
        profile.joins_on = None
    if end is not None:
        for uid, profile in sorted(first.items(), key=lambda kv: kv[1].user.username):
            if uid not in latest and on_date < profile.effective_from <= end and profile.is_on_payroll:
                profile.joins_on = profile.effective_from
                people.append(profile)
        people.sort(key=lambda p: p.user.username)
    return people


# --- Generating a run ------------------------------------------------------


def cycle_days(start, end):
    """Calendar days in a cycle: 30 for 27 Sep to 26 Oct, 28 or 29 for February's."""
    return (end - start).days + 1


def effective_rate(company, profile, on_date):
    """The daily rate this profile pays on `on_date`.

    One rule: a monthly salary is divided by the calendar days in the cycle
    containing `on_date` (8000 over 30 days is 266.67 a day). Weekly offs and
    company holidays are paid days, so a person is paid their whole salary every
    cycle and a holiday never changes the rate.

    A profile with no monthly salary is paid the daily rate as typed, which is
    both the per-day case and what keeps rows saved before monthly salary
    existed working.
    """
    if profile.monthly_salary is None or profile.monthly_salary <= 0:
        return profile.daily_rate

    start, end = cycle_bounds(on_date)
    return (profile.monthly_salary / Decimal(cycle_days(start, end))).quantize(
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
    start, end = cycle_bounds(on_date)
    return {
        "monthly_salary": str(profile.monthly_salary),
        "cycle_days": cycle_days(start, end),
        "working_days": days,
        "daily_rate": str(rate),
    }


def reimbursements(company, start, end):
    """{user_id: [Expense]} the cycle would repay through salary.

    Anything marked `to_salary` dated up to the cycle end that no other run has
    taken yet; this run's own earlier pick-ups count too, so regenerating an
    open run keeps them.
    """
    from apps.expenses.models import Expense

    run = PayrollRun.objects.filter(company=company, period_start=start, period_end=end).first()
    taken = Q(paid_in_run__isnull=True) | Q(paid_in_run=run) if run else Q(paid_in_run__isnull=True)
    out = {}
    for e in Expense.objects.filter(taken, company=company, to_salary=True, date__lte=end).order_by("date", "id"):
        out.setdefault(e.paid_by_id, []).append(e)
    return out


def preview(company, start, end):
    """Day counts per person, without writing anything.

    Returns (working_days, [rows]) so the screen can show what a run would pay
    before anyone commits to it.
    """
    days = working_days(company, start, end)
    repay = reimbursements(company, start, end)
    rows = []
    for profile in payable_people(company, start, end):
        # A joiner is paid from their first day; everyone else from the cycle start.
        paid_from = profile.joins_on or start
        row_days = working_days(company, paid_from, end) if profile.joins_on else days
        leave = leave_days_in_period(company, profile.user, paid_from, end)
        rate = effective_rate(company, profile, start)
        late = late_pay_in_period(company, profile.user, paid_from, end, rate)
        # A half day lost to lateness is a working day not paid, so it reduces
        # payable days the same way unpaid leave does; the cash bands are a flat
        # charge on top and cannot be expressed as days.
        # A monthly salary pays every calendar day of the cycle (weekly offs and
        # holidays included) minus the days lost; a per-day profile is paid for
        # working days only, as before.
        monthly = profile.monthly_salary is not None and profile.monthly_salary > 0
        pay_days = cycle_days(paid_from, end) if monthly else row_days
        payable = max(
            Decimal("0.00"),
            Decimal(pay_days) - leave["unpaid_days"] - late["half_days"],
        )
        cash = late["cash_penalty"]
        # Deductions cannot exceed earnings. Someone on a low salary who is
        # Rs 100 late every single day of the cycle would otherwise be quoted a
        # *negative* gross -- a payslip telling them to hand money back, which
        # is not a thing payroll does. Cap the cash charge at what the payable
        # days can actually absorb and floor gross at zero. The uncapped figure
        # stays in the breakdown so the cap is auditable instead of silently
        # swallowing money.
        if monthly:
            # Salary over days, rounded once: multiplying the rounded day rate
            # back up would leave a full cycle a few paise short of the salary.
            whole = cycle_days(start, end)
            earned = (profile.monthly_salary * payable / Decimal(whole)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            lost = (profile.monthly_salary * Decimal(pay_days) / Decimal(whole) - earned).quantize(Decimal("0.01"))
        else:
            earned = (payable * rate).quantize(Decimal("0.01"))
            lost = (leave["unpaid_days"] * rate + late["half_day_loss"]).quantize(Decimal("0.01"))
        owed = repay.get(profile.user_id, [])
        back = (Decimal(sum(e.amount_paise for e in owed)) / 100).quantize(Decimal("0.01"))
        cash_applied = min(cash, earned) if cash > earned else cash
        rows.append(
            {
                "user": profile.user,
                "profile": profile,
                "daily_rate": rate,
                "currency": profile.currency,
                "working_days": row_days,
                "pay_days": pay_days,
                "joined_on": profile.joins_on,
                "paid_leave_days": leave["paid_days"],
                "unpaid_leave_days": leave["unpaid_days"],
                "payable_days": payable,
                "late_half_days": late["half_days"],
                "late_penalty": cash_applied,
                "deduction": (lost + cash_applied).quantize(Decimal("0.01")),
                "reimbursement": back,
                "expense_ids": [e.pk for e in owed],
                "gross": (earned - cash_applied + back).quantize(Decimal("0.01")),
                "breakdown": {
                    "reimbursements": [
                        {"what": e.category_label, "date": f"{e.date:%d %b %Y}", "amount": format_money(Decimal(e.amount_paise) / 100)}
                        for e in owed
                    ],
                    **rate_breakdown(company, profile, start, row_days),
                    **(
                        {
                            "joined_on": f"{profile.joins_on:%d %b %Y}",
                            "paid_days_of": f"{pay_days} of {cycle_days(start, end)}",
                        }
                        if profile.joins_on
                        else {}
                    ),
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
    # One transaction: deleting the old payslips and writing the new ones either
    # all happens or none of it does, so a crash cannot leave a run half-empty.
    with transaction.atomic():
        run = _write_run(company, start, end, existing, days, rows)
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


def _write_run(company, start, end, existing, days, rows):
    run = existing or PayrollRun(company=company, period_start=start, period_end=end)
    run.working_days = days
    run.save()

    run.payslips.all().delete()
    run.expenses.update(paid_in_run=None)
    for row in rows:
        if row["expense_ids"]:
            run.expenses.model.objects.filter(pk__in=row["expense_ids"]).update(paid_in_run=run)
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
            reimbursement=row["reimbursement"],
            breakdown={
                "paid_leave": format_days(row["paid_leave_days"]),
                "unpaid_leave": format_days(row["unpaid_leave_days"]),
                # How this daily rate was reached, so the slip explains itself.
                **row["breakdown"],
            },
        )
    return run
