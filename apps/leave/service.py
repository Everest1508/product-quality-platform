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

    Coerces to `Decimal` first because the callers are not all `Decimal`:
    `working_days` returns a plain `int`, and this helper is documented as the
    one place a day count is rendered. An `int` reached `.normalize()` and
    raised `AttributeError` -- inside a reason string, so the 500 was
    "AttributeError: 'int' object has no attribute 'normalize'" on a screen
    whose only job was to show a number.
    """
    if value is None:
        return "—"
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
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


def _paid_charge(request):
    """Days a request charges against its allowance.

    Only *paid* days consume an allowance -- an unpaid day is not a day of
    allowance spent, it is a day somebody chose (or was told) to go without pay
    for. Charging both would mean a single long request could exhaust the year's
    casual leave with days that were never paid in the first place, and the
    balance would fall without the payslip ever showing why.

    A row with no stored split predates the field; its policy's `is_paid` is the
    only record of the decision, so that is what it charges.
    """
    if request.paid_days is not None:
        return request.paid_days
    return request.days if request.policy.is_paid else Decimal("0.0")


def consumed_days(company, user, policy, year, include_pending=True):
    """Paid days already charged to a user for one policy in one year.

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
    ).select_related("policy")
    total = sum((_paid_charge(r) for r in qs), Decimal("0.0"))
    return total


def balance_for(company, user, policy, year=None):
    """Remaining *paid* allowance for one policy, as a dict for templates."""
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


def paid_allowance(company, user, policy, start_date, end_date, days, exclude_pk=None):
    """How many of `days` can be paid, and why not more.

    Two ceilings, and the lower one wins:

      * the remaining annual allowance, and
      * the spell cap, which now limits *paid* days in one unbroken run rather
        than blocking the run. The run already includes this request's own dates
        (`consecutive_run_days` adds them), so those are subtracted to get what
        is already booked -- otherwise a lone 5-day request under a 3-day cap
        would compute zero headroom and be charged entirely unpaid, which is the
        opposite of "the first 3 are paid".

    The subtraction is the span's working days, not `days`. The run is measured
    as a span, so a half day contributes one working day to it; subtracting the
    0.5 charge would leave 0.5 phantom days counted as already booked against
    the cap.

    Returns `None` for "unlimited", which is how an uncapped policy and a
    request smaller than both ceilings come back. `reasons` explains the binding
    constraint in words, because the apply screen and the approver's dialog both
    have to say *why* a request came out part-unpaid.
    """
    if not policy.is_paid:
        # An unpaid type is unpaid in full. It touches neither ceiling: there is
        # no allowance to spend and no paid spell to shorten.
        return Decimal("0.0"), ["This leave type is unpaid."]

    remaining = balance_for(company, user, policy, start_date.year)["remaining"]
    reasons = []
    headroom = None

    cap = policy.max_consecutive_days
    if cap is not None:
        run = consecutive_run_days(company, user, start_date, end_date, exclude_pk)
        already_booked = max(
            Decimal("0.0"), run - Decimal(working_days(start_date, end_date))
        )
        headroom = max(Decimal("0.0"), cap - already_booked)
        reasons.append(
            f"{policy.name} leave is capped at {format_days(cap)} paid days "
            f"at a time"
        )

    if remaining is None:
        allowance = headroom
    elif headroom is None:
        allowance = remaining
    else:
        allowance = min(remaining, headroom)

    if allowance is None:
        return None, reasons
    return min(allowance, days), reasons


def auto_split(company, user, policy, start_date, end_date, days, exclude_pk=None):
    """Paid up to the allowance, the rest unpaid.

    **Paid days come from the start of the request.** The allowance covers the
    earliest days and the overflow falls at the tail, which is also the order
    the applicant and the approver both read the split in.

    That ordering is what makes a request straddling two pay cycles priceable:
    payroll bills each cycle separately, so given 3 paid + 2 unpaid over a span
    crossing the boundary, the early cycle bills paid days first and only the
    days that spill past its own end date can land in the later one. If
    `payroll.service.leave_days_in_period` ever reverses this, the same request
    costs a different amount depending on which cycle is being run.
    """
    allowance, reasons = paid_allowance(
        company, user, policy, start_date, end_date, days, exclude_pk=exclude_pk
    )
    if allowance is None:
        return {"paid": days, "unpaid": Decimal("0.0"), "reasons": reasons}
    paid = max(Decimal("0.0"), min(days, allowance))
    unpaid = days - paid
    if unpaid > 0:
        reasons.append(
            f"{format_days(unpaid)} of the {format_days(days)} day(s) will be "
            f"charged as unpaid leave"
        )
    return {"paid": paid, "unpaid": unpaid, "reasons": reasons}


def resolve_split(company, user, policy, start_date, end_date, days, mode, paid,
                  unpaid, exclude_pk=None):
    """The split an approver's form means, checked against the request.

    AUTO recomputes it and ignores whatever the boxes said. MANUAL takes the
    approver's numbers, but never for more days than the request actually spans
    -- a form that can charge 9 paid days for a 3-day request is a form that can
    invent pay. Non-negative, and the two must add up, or the totals quietly stop
    describing the same span the dates do.
    """
    if mode == LeaveRequest.SplitMode.MANUAL:
        if paid is None or unpaid is None:
            raise ValidationError(
                "Enter both paid and unpaid days, or switch the split to automatic."
            )
        if paid < 0 or unpaid < 0:
            raise ValidationError("Paid and unpaid days cannot be negative.")
        total = paid + unpaid
        if total != days:
            raise ValidationError(
                f"Paid plus unpaid must equal the {format_days(days)} day(s) requested."
            )
        return {
            "paid": paid,
            "unpaid": unpaid,
            "reasons": ["Split set manually by the approver."],
        }
    return auto_split(
        company, user, policy, start_date, end_date, days, exclude_pk=exclude_pk
    )


def decision_preview(company, leave):
    """What the approver's dialog needs to show for one pending request.

    The automatic split is recomputed here rather than reusing the applicant's
    stored one: the allowance may have moved since they applied (somebody else
    booked the last paid day), and showing them a stale "3 paid" invites an
    approver to confirm a number the server will reject. A click on Approve
    re-validates regardless -- this is a preview, not the decision.
    """
    try:
        current = auto_split(
            company,
            leave.user,
            leave.policy,
            leave.start_date,
            leave.end_date,
            leave.days,
            exclude_pk=leave.pk,
        )
    except ValidationError:
        # A request that can no longer be split cleanly (its dates are now in
        # the past, say) still has to be reviewable, so the approver can reject
        # it or correct the dates rather than being met with an error page.
        current = {
            "paid": leave.split["paid"],
            "unpaid": leave.split["unpaid"],
            "reasons": [],
        }
    return {
        "paid": current["paid"],
        "unpaid": current["unpaid"],
        "reasons": current["reasons"],
        "paid_label": format_days(current["paid"]),
        "unpaid_label": format_days(current["unpaid"]),
    }


def validate_and_split(
    company, user, policy, start_date, end_date, is_half_day, exclude_pk=None
):
    """Validate a request and return its charge *and* its paid/unpaid split.

    The hard rejections are the ones no amount of goodwill fixes: no dates, an
    inverted range, a start in the past, a weekend-only range, a half day spread
    over two dates, and an overlap with leave already booked. The two policy
    ceilings are not rejections any more -- they decide how much of the request
    is paid, and the rest is unpaid. See `auto_split`.
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

    split = auto_split(
        company, user, policy, start_date, end_date, days, exclude_pk=exclude_pk
    )
    return {"days": days, **split}


def validate_request(
    company, user, policy, start_date, end_date, is_half_day, exclude_pk=None
):
    """The charge in days, or raise ValidationError with the reason.

    A thin wrapper over `validate_and_split` for callers that only need the
    number. The returned charge is the whole span: what is *paid* out of it is
    the split's business, and a caller that ignores the split is not wrong about
    how long the person is away.
    """
    return validate_and_split(
        company, user, policy, start_date, end_date, is_half_day, exclude_pk=exclude_pk
    )["days"]
