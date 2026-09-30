from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.leave.models import LeavePolicy, LeaveRequest

HALF_DAY = Decimal("0.5")


def format_days(value):
    """Render a day count for humans, without Decimal's scientific notation.

    ``Decimal("12.0").normalize()`` is ``Decimal('1.2E+1')``, so a naive
    normalize() in a template prints "1.2E+1" (and "1E+1" for ten whole days).
    """
    if value is None:
        return "—"
    value = value.normalize()
    if value == value.to_integral_value():
        value = value.quantize(Decimal("1"))
    return format(value, "f")


def working_days(start_date, end_date):
    """Mon-Fri days in an inclusive range.

    Leave is charged in working days, so a Friday-to-Monday spell costs 2, not
    4. Returns 0 for a range that contains only weekends, which the form
    rejects separately with a clearer message.
    """
    if not (start_date and end_date) or end_date < start_date:
        return 0
    count = 0
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


def charge_days(start_date, end_date, is_half_day):
    """Days this request costs: 0.5 for a half day, else working days."""
    if is_half_day:
        return HALF_DAY
    return Decimal(working_days(start_date, end_date))


def policies_for(company):
    return list(LeavePolicy.objects.filter(company=company))


def get_policy(company, pk):
    """Fetch a policy scoped to the company, or None."""
    return LeavePolicy.objects.filter(company=company, pk=pk).first()


def year_of(date):
    return date.year


def consumed_days(company, user, policy, year, include_pending=True):
    """Days already charged to a user for one policy in one year.

    Approved leave counts always; pending leave also counts by default so two
    applications cannot both claim the last remaining days.
    """
    statuses = ["approved"]
    if include_pending:
        statuses.append("pending")

    qs = LeaveRequest.objects.filter(
        company=company,
        user=user,
        policy=policy,
        status__in=statuses,
        start_date__year=year,
    )
    total = sum((r.days for r in qs), Decimal("0.0"))
    return total


def balance_for(company, user, policy, year=None):
    """Remaining allowance for one policy, as a dict for templates."""
    year = year or timezone.localdate().year
    limit = policy.max_days_per_year
    approved = consumed_days(company, user, policy, year, include_pending=False)
    pending = consumed_days(company, user, policy, year) - approved
    remaining = None if limit is None else max(Decimal("0.0"), limit - approved - pending)
    return {
        "policy": policy,
        "limit": limit,
        "approved": approved,
        "pending": pending,
        "remaining": remaining,
        "limit_label": format_days(limit),
        "approved_label": format_days(approved),
        "pending_label": format_days(pending),
        "remaining_label": format_days(remaining),
        "is_unlimited": limit is None,
        "has_pending": pending > 0,
    }


def balances_for(company, user, year=None):
    return [balance_for(company, user, p, year) for p in policies_for(company)]


def is_on_leave(company, user, date):
    """True when an approved request covers this exact date."""
    if not date:
        return False
    return LeaveRequest.objects.filter(
        company=company,
        user=user,
        status="approved",
        start_date__lte=date,
        end_date__gte=date,
    ).exists()


def leave_dates(company, user, start_date, end_date):
    """Set of dates covered by approved leave in an inclusive range."""
    return {
        r.start_date + timedelta(days=i)
        for r in LeaveRequest.objects.filter(
            company=company,
            user=user,
            status="approved",
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        for i in range((r.end_date - r.start_date).days + 1)
    }


def approved_leave_map(company, start_date, end_date):
    """{user_id: {dates covered by approved leave}} for a whole company.

    One query for every employee, so attendance reports annotate without
    N+1 lookups. Dates are clipped to the requested range so a long leave
    request spanning the boundary does not leak days outside it.
    """
    approved = {}
    for request in LeaveRequest.objects.filter(
        company=company,
        status="approved",
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).only("user_id", "start_date", "end_date"):
        first = max(request.start_date, start_date)
        last = min(request.end_date, end_date)
        days = approved.setdefault(request.user_id, set())
        days.update(
            first + timedelta(days=i) for i in range((last - first).days + 1)
        )
    return approved


def consecutive_run_days(company, user, start_date, end_date, exclude_pk=None):
    """Working days in the unbroken run of leave covering `start_date`.

    The run spans every open request that touches the range, on **any** policy,
    plus the proposed dates themselves (which are not in the database yet).

    Counted in *working* days, not calendar days, to match the unit leave is
    actually charged in. A Friday spell followed by a Monday spell is a
    two-working-day run, not a four-day one -- booking across a weekend is
    normal and must not trip the spell cap.
    """
    occupied = set()
    open_leave = LeaveRequest.objects.filter(
        company=company, user=user, status__in=LeaveRequest.OPEN_STATUSES
    )
    if exclude_pk:
        open_leave = open_leave.exclude(pk=exclude_pk)
    for request in open_leave.only("start_date", "end_date"):
        occupied.update(
            d
            for d in (
                request.start_date + timedelta(days=i)
                for i in range((request.end_date - request.start_date).days + 1)
            )
        )
    occupied.update(
        start_date + timedelta(days=i)
        for i in range((end_date - start_date).days + 1)
    )

    day = start_date
    while day - timedelta(days=1) in occupied:
        day -= timedelta(days=1)
    span_start = day
    day = end_date
    while day + timedelta(days=1) in occupied:
        day += timedelta(days=1)
    span_end = day

    # Decimal, like every other day count here, so `format_days` accepts it.
    return Decimal(working_days(span_start, span_end))


def validate_request(
    company, user, policy, start_date, end_date, is_half_day, exclude_pk=None
):
    """Return the charge in days, or raise ValidationError with the reason.

    Checks, in the order a person would care about them: the range makes sense,
    it is not in the past, it is not a lone weekend, it does not clash with
    leave already booked, and it fits both the policy's spell limit and the
    remaining balance.
    """
    if not (start_date and end_date):
        raise ValidationError("Choose a start and end date.")
    if end_date < start_date:
        raise ValidationError("End date cannot be before the start date.")

    today = timezone.localdate()
    if start_date < today:
        raise ValidationError("Leave cannot start in the past.")

    if is_half_day:
        if start_date != end_date:
            raise ValidationError("A half day can only be taken on a single date.")
        days = HALF_DAY
    else:
        working = working_days(start_date, end_date)
        if working == 0:
            raise ValidationError("That range is a weekend only.")
        days = Decimal(working)

    clash = LeaveRequest.objects.filter(
        company=company,
        user=user,
        status__in=LeaveRequest.OPEN_STATUSES,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if exclude_pk:
        clash = clash.exclude(pk=exclude_pk)
    if clash.exists():
        raise ValidationError("You already have leave booked across those dates.")

    # The spell cap is checked on the *combined* run, not just this request's
    # own days: 2 casual followed by 2 sick is four days away, and the office
    # rule caps the run rather than the type. The per-policy
    # `max_consecutive_days` supplies the limit; every other type contributes
    # its already-booked days to the same run.
    spell_cap = policy.max_consecutive_days
    if spell_cap is not None:
        if days > spell_cap:
            raise ValidationError(
                f"{policy.name} leave is capped at "
                f"{format_days(spell_cap)} days at a time."
            )
        run = consecutive_run_days(company, user, start_date, end_date, exclude_pk)
        if run > spell_cap:
            raise ValidationError(
                f"That would be {format_days(run)} consecutive days away, and "
                f"{policy.name} leave is capped at {format_days(spell_cap)} "
                f"days at a time."
            )

    balance = balance_for(company, user, policy, start_date.year)
    if balance["remaining"] is not None and days > balance["remaining"]:
        raise ValidationError(
            f"That would use {format_days(days)} of your {format_days(balance['remaining'])} "
            f"remaining {policy.name} days."
        )

    return days
