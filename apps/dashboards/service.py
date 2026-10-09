from datetime import timedelta

from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone


def get_admin_dashboard_data(company):
    from apps.accounts.models import Membership
    from apps.dashboards.models import ActivityLog
    from apps.ingestion.models import ErrorGroup
    from apps.tickets.models import Ticket

    member_count = Membership.objects.filter(company=company).count()
    role_breakdown = (
        Membership.objects.filter(company=company)
        .values("role")
        .annotate(count=Count("id"))
        .order_by("role")
    )

    open_errors = ErrorGroup.objects.filter(company=company).exclude(status__in=["resolved", "ignored"]).count()
    open_tickets = Ticket.objects.filter(company=company).exclude(status__in=["resolved", "closed"]).count()

    activity = ActivityLog.objects.filter(company=company).select_related("actor")[:20]

    now = timezone.now()
    errors_last_7d = ErrorGroup.objects.filter(
        company=company,
        first_seen__gte=now - timedelta(days=7),
    ).count()
    errors_last_30d = ErrorGroup.objects.filter(
        company=company,
        first_seen__gte=now - timedelta(days=30),
    ).count()
    tickets_last_7d = Ticket.objects.filter(
        company=company,
        created_at__gte=now - timedelta(days=7),
    ).count()
    tickets_last_30d = Ticket.objects.filter(
        company=company,
        created_at__gte=now - timedelta(days=30),
    ).count()

    return {
        "member_count": member_count,
        "role_breakdown": list(role_breakdown),
        "open_errors": open_errors,
        "open_tickets": open_tickets,
        "activity": activity,
        "errors_last_7d": errors_last_7d,
        "errors_last_30d": errors_last_30d,
        "tickets_last_7d": tickets_last_7d,
        "tickets_last_30d": tickets_last_30d,
    }


def get_product_dashboard_data(company, product):
    from apps.dashboards.models import ActivityLog
    from apps.feedback.models import Survey, SurveyResponse
    from apps.ingestion.models import ErrorGroup, ErrorOccurrence
    from apps.tickets.models import Ticket

    now = timezone.now()

    error_groups = ErrorGroup.objects.filter(company=company, product=product)
    total_errors = error_groups.count()
    open_errors = error_groups.exclude(status__in=["resolved", "ignored"]).count()
    resolved_errors = error_groups.filter(status="resolved").count()

    errors_by_severity = list(
        error_groups.values("severity")
        .annotate(count=Count("id"))
        .order_by("severity")
    )

    errors_by_day = []
    for days_ago in range(29, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        count = ErrorOccurrence.objects.filter(
            company=company,
            error_group__product=product,
            created_at__date=day,
        ).count()
        errors_by_day.append({"date": day.isoformat(), "count": count})

    error_status_breakdown = list(
        error_groups.values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )

    tickets = Ticket.objects.filter(company=company, product=product)
    total_tickets = tickets.count()
    open_tickets = tickets.exclude(status__in=["resolved", "closed"]).count()

    tickets_by_status = list(
        tickets.values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )

    ticket_burndown = []
    for days_ago in range(29, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        created_by_day = Ticket.objects.filter(
            company=company, product=product,
            created_at__date__lte=day,
        ).count()
        resolved_by_day = Ticket.objects.filter(
            company=company, product=product,
            status__in=["resolved", "closed"],
            updated_at__date__lte=day,
        ).count()
        ticket_burndown.append({
            "date": day.isoformat(),
            "open": created_by_day - resolved_by_day,
        })

    surveys = Survey.objects.filter(company=company, product=product)
    survey_responses = SurveyResponse.objects.filter(survey__product=product, company=company)
    total_responses = survey_responses.count()
    avg_score = survey_responses.aggregate(avg=Avg("score"))["avg"]

    csat_by_day = []
    for days_ago in range(29, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        day_avg = survey_responses.filter(
            created_at__date=day,
        ).aggregate(avg=Avg("score"))["avg"]
        csat_by_day.append({
            "date": day.isoformat(),
            "avg": round(day_avg, 1) if day_avg else None,
        })

    uptime_percentage = None
    if total_errors > 0:
        total_occurrences = ErrorOccurrence.objects.filter(
            company=company, error_group__product=product,
        ).count()
        critical_errors = error_groups.filter(severity="critical").count()
        if total_occurrences == 0:
            uptime_percentage = 100.0
        else:
            uptime_percentage = round(
                ((total_occurrences - critical_errors) / total_occurrences) * 100, 2
            ) if total_occurrences > 0 else 100.0

    recent_activity = ActivityLog.objects.filter(
        company=company,
        target_content_type__contains="product",
    ).select_related("actor")[:10]

    return {
        "product": product,
        "total_errors": total_errors,
        "open_errors": open_errors,
        "resolved_errors": resolved_errors,
        "errors_by_severity": errors_by_severity,
        "errors_by_severity_max": max(1, max((r["count"] for r in errors_by_severity), default=0)),
        "errors_by_day": errors_by_day,
        "errors_by_day_max": max(1, max((d["count"] for d in errors_by_day), default=0)),
        "error_status_breakdown": error_status_breakdown,
        "total_tickets": total_tickets,
        "open_tickets": open_tickets,
        "tickets_by_status": tickets_by_status,
        "tickets_by_status_max": max(1, max((r["count"] for r in tickets_by_status), default=0)),
        "ticket_burndown": ticket_burndown,
        "ticket_burndown_max": max(1, max((d["open"] for d in ticket_burndown), default=0)),
        "survey_count": surveys.count(),
        "total_responses": total_responses,
        "avg_score": round(avg_score, 1) if avg_score else None,
        "csat_by_day": csat_by_day,
        "uptime_percentage": uptime_percentage,
        "recent_activity": recent_activity,
    }


def log_activity(company, event_type, title, description="", actor=None,
                 target_content_type="", target_object_id=None, metadata=None):
    from apps.dashboards.models import ActivityLog
    return ActivityLog.objects.create(
        company=company,
        event_type=event_type,
        title=title,
        description=description,
        actor=actor,
        target_content_type=target_content_type,
        target_object_id=target_object_id,
        metadata=metadata,
    )


def _agg_by_product(queryset, key):
    return {row[key]: row for row in queryset}


def _build_product_cards(company, product_ids):
    from apps.feedback.models import SurveyResponse
    from apps.ingestion.models import ErrorGroup
    from apps.products.models import Product
    from apps.tickets.models import Ticket

    if not product_ids:
        return []

    error_map = _agg_by_product(
        ErrorGroup.objects.filter(company=company, product_id__in=product_ids)
        .exclude(status__in=["resolved", "ignored"])
        .values("product_id")
        .annotate(open_errors=Count("id")),
        "product_id",
    )
    critical_map = _agg_by_product(
        ErrorGroup.objects.filter(
            company=company,
            product_id__in=product_ids,
            severity__in=["critical", "high"],
        )
        .exclude(status__in=["resolved", "ignored"])
        .values("product_id")
        .annotate(critical_count=Count("id")),
        "product_id",
    )
    ticket_map = _agg_by_product(
        Ticket.objects.filter(company=company, product_id__in=product_ids)
        .exclude(status__in=["resolved", "closed"])
        .values("product_id")
        .annotate(open_tickets=Count("id")),
        "product_id",
    )
    score_map = _agg_by_product(
        SurveyResponse.objects.filter(company=company, survey__product_id__in=product_ids)
        .values("survey__product_id")
        .annotate(avg_score=Avg("score")),
        "survey__product_id",
    )
    stale_cutoff = timezone.now() - timedelta(days=7)
    stale_map = _agg_by_product(
        Ticket.objects.filter(
            company=company,
            product_id__in=product_ids,
            updated_at__lt=stale_cutoff,
        )
        .exclude(status__in=["resolved", "closed"])
        .values("product_id")
        .annotate(stale_count=Count("id")),
        "product_id",
    )

    cards = []
    for product in Product.objects.filter(id__in=product_ids).order_by("name"):
        open_errors = error_map.get(product.id, {}).get("open_errors", 0)
        critical = critical_map.get(product.id, {}).get("critical_count", 0)
        open_tickets = ticket_map.get(product.id, {}).get("open_tickets", 0)
        raw_score = score_map.get(product.id, {}).get("avg_score")
        avg_score = round(raw_score, 1) if raw_score is not None else None
        stale_count = stale_map.get(product.id, {}).get("stale_count", 0)

        if critical > 0 or (avg_score is not None and avg_score <= 2):
            health = "critical"
        elif open_errors > 0 or open_tickets > 0 or stale_count > 0 or (avg_score is not None and avg_score <= 3):
            health = "warning"
        else:
            health = "healthy"

        cards.append({
            "product": product,
            "open_errors": open_errors,
            "open_tickets": open_tickets,
            "avg_score": avg_score,
            "stale_count": stale_count,
            "health": health,
        })
    return cards


def _build_attention(company, product_ids, is_privileged):
    from apps.ingestion.models import ErrorGroup
    from apps.tickets.models import Ticket

    if is_privileged:
        error_qs = ErrorGroup.objects.filter(company=company)
        ticket_qs = Ticket.objects.filter(company=company)
    else:
        error_qs = ErrorGroup.objects.filter(company=company, product_id__in=product_ids)
        ticket_qs = Ticket.objects.filter(company=company, product_id__in=product_ids)

    stale_cutoff = timezone.now() - timedelta(days=7)

    return {
        "critical_errors": list(
            error_qs.filter(severity__in=["critical", "high"])
            .exclude(status__in=["resolved", "ignored"])
            .select_related("product")
            .order_by("-occurrence_count")[:5]
        ),
        "stale_tickets": list(
            ticket_qs.filter(updated_at__lt=stale_cutoff)
            .exclude(status__in=["resolved", "closed"])
            .select_related("product")
            .order_by("updated_at")[:5]
        ),
        "unassigned_tickets": list(
            ticket_qs.filter(assignees__isnull=True)
            .exclude(status__in=["resolved", "closed"])
            .select_related("product")
            .order_by("-updated_at")[:5]
        ),
    }


def get_user_dashboard_data(user, company):
    """Personalized dashboard scoped to the products the user can access.

    Owners and admins see company-wide data; other roles only see the
    products they are explicitly allocated to.
    """
    from apps.accounts.models import Membership
    from apps.products.access import accessible_products
    from apps.ingestion.models import ErrorGroup
    from apps.tickets.models import Ticket

    membership = Membership.objects.filter(user=user, company=company).first()
    is_privileged = bool(
        membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)
    )

    products = accessible_products(user, company)
    product_ids = list(products.values_list("id", flat=True))

    if is_privileged:
        error_scope = ErrorGroup.objects.filter(company=company)
        ticket_scope = Ticket.objects.filter(company=company)
    else:
        error_scope = ErrorGroup.objects.filter(company=company, product_id__in=product_ids)
        ticket_scope = Ticket.objects.filter(company=company, product_id__in=product_ids)

    open_errors = error_scope.exclude(status__in=["resolved", "ignored"]).count()
    open_tickets = ticket_scope.exclude(status__in=["resolved", "closed"]).count()
    resolved_errors = error_scope.filter(status="resolved").count()

    my_work = list(
        ticket_scope.filter(assignees=user)
        .exclude(status__in=["resolved", "closed"])
        .select_related("product")
        .order_by("-updated_at")[:10]
    )
    my_work_count = (
        ticket_scope.filter(assignees=user)
        .exclude(status__in=["resolved", "closed"])
        .count()
    )

    attention = _build_attention(company, product_ids, is_privileged)

    now = timezone.now()
    week = now - timedelta(days=7)
    two_weeks = now - timedelta(days=14)

    errors_7d = error_scope.filter(first_seen__gte=week).count()
    errors_prev_7d = error_scope.filter(first_seen__gte=two_weeks, first_seen__lt=week).count()
    tickets_7d = ticket_scope.filter(created_at__gte=week).count()
    tickets_prev_7d = ticket_scope.filter(created_at__gte=two_weeks, created_at__lt=week).count()
    resolved_7d = ticket_scope.filter(
        status__in=["resolved", "closed"], updated_at__gte=week
    ).count()

    data = {
        "is_privileged": is_privileged,
        "role": membership.role if membership else None,
        "product_cards": _build_product_cards(company, product_ids),
        "open_errors": open_errors,
        "open_tickets": open_tickets,
        "resolved_errors": resolved_errors,
        "errors_last_7d": errors_7d,
        "errors_delta": errors_7d - errors_prev_7d,
        "tickets_last_7d": tickets_7d,
        "tickets_delta": tickets_7d - tickets_prev_7d,
        "resolved_last_7d": resolved_7d,
        "my_work": my_work,
        "my_work_count": my_work_count,
        "attention": attention,
        "attention_count": sum(len(items) for items in attention.values()),
    }

    if is_privileged:
        data.update(get_admin_dashboard_data(company))

    return data


def get_summary_report(company, start_date, end_date, user=None):
    """Aggregate audit-log activity into a summary report for a date range.

    Both dates are inclusive. Counts come from ActivityLog entries so the
    report reflects actual events (ticket status changes, resolutions,
    captured/investigated errors, feedback, etc.).

    When ``user`` is a non-privileged member, the report is scoped to their
    own activity (events they acted on, across the products they can access).
    Owners and admins always get company-wide reports.
    """
    from datetime import datetime, time

    from apps.accounts.models import Membership
    from apps.dashboards.models import ActivityLog
    from apps.products.access import accessible_products
    from apps.products.models import Product

    day_start = datetime.combine(start_date, time.min)
    day_end = datetime.combine(end_date, time.max)

    logs = ActivityLog.objects.filter(
        company=company,
        created_at__range=(day_start, day_end),
    )

    scope = "company"
    product_ids = None
    if user is not None:
        membership = Membership.objects.filter(user=user, company=company).first()
        privileged = bool(
            membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)
        )
        if not privileged:
            scope = "mine"
            logs = logs.filter(actor=user)
            product_ids = list(
                accessible_products(user, company).values_list("id", flat=True)
            )

    by_type = dict(
        logs.values_list("event_type")
        .annotate(count=Count("id"))
        .order_by("event_type")
    )

    ticket_status_events = logs.filter(event_type="ticket_status_changed")
    error_status_events = logs.filter(event_type="error_status_changed")

    def transitions_to(qs, to_status):
        return qs.filter(metadata__to=to_status).count()

    errors_resolved = by_type.get("error_resolved", 0) + transitions_to(error_status_events, "resolved")
    errors_ignored = by_type.get("error_ignored", 0) + transitions_to(error_status_events, "ignored")

    products = list(
        Product.objects.filter(company=company)
        .filter(id__in=product_ids) if product_ids is not None else Product.objects.filter(company=company)
    )
    products.sort(key=lambda p: p.name)
    product_rows = []
    for product in products:
        p_logs = logs.filter(metadata__product_id=product.id)
        p_status = p_logs.filter(event_type="ticket_status_changed")
        product_rows.append({
            "product": product,
            "tickets_created": p_logs.filter(event_type="ticket_created").count(),
            "tickets_resolved": p_status.filter(metadata__to="resolved").count(),
            "errors_captured": p_logs.filter(event_type__in=["error_captured", "error_created"]).count(),
            "errors_resolved": p_logs.filter(event_type__in=["error_resolved"]).count()
                + p_logs.filter(event_type="error_status_changed", metadata__to="resolved").count(),
            "feedback": p_logs.filter(event_type__in=["feedback_received", "survey_response"]).count(),
        })

    daily = []
    span_days = (end_date - start_date).days + 1
    if span_days <= 92:
        current = start_date
        while current <= end_date:
            d_start = datetime.combine(current, time.min)
            d_end = datetime.combine(current, time.max)
            day_logs = logs.filter(created_at__range=(d_start, d_end))
            d_status = day_logs.filter(event_type="ticket_status_changed")
            daily.append({
                "date": current,
                "tickets_created": day_logs.filter(event_type="ticket_created").count(),
                "tickets_resolved": d_status.filter(metadata__to="resolved").count(),
                "tickets_closed": d_status.filter(metadata__to="closed").count(),
                "errors_captured": day_logs.filter(event_type__in=["error_captured", "error_created"]).count(),
                "errors_resolved": day_logs.filter(event_type__in=["error_resolved"]).count()
                    + day_logs.filter(event_type="error_status_changed", metadata__to="resolved").count(),
                "feedback": day_logs.filter(event_type__in=["feedback_received", "survey_response"]).count(),
                "total": day_logs.count(),
            })
            current += timedelta(days=1)

    total_events = logs.count()
    summary = {
        "tickets_created": by_type.get("ticket_created", 0),
        "tickets_resolved": transitions_to(ticket_status_events, "resolved"),
        "errors_captured": by_type.get("error_captured", 0) + by_type.get("error_created", 0),
        "errors_resolved": errors_resolved,
        "total_events": total_events,
    }

    return {
        "scope": scope,
        "start_date": start_date,
        "end_date": end_date,
        "total_events": total_events,
        "kpis": _report_kpis(company, start_date, end_date, user if scope == "mine" else None, summary),
        "daily_bars": _daily_bars(daily),
        "product_bars": _product_bars(product_rows),
        "event_mix": _event_mix(by_type),
        "resolution_rate": _rate(summary["tickets_resolved"], summary["tickets_created"]),
        "error_fix_rate": _rate(summary["errors_resolved"], summary["errors_captured"]),
        "by_type": by_type,
        "tickets_created": by_type.get("ticket_created", 0),
        "tickets_status_changed": ticket_status_events.count(),
        "tickets_resolved": transitions_to(ticket_status_events, "resolved"),
        "tickets_closed": transitions_to(ticket_status_events, "closed"),
        "tickets_in_progress": transitions_to(ticket_status_events, "in_progress"),
        "tickets_assigned": transitions_to(ticket_status_events, "assigned") + by_type.get("ticket_assigned", 0),
        "errors_captured": by_type.get("error_captured", 0) + by_type.get("error_created", 0),
        "errors_resolved": errors_resolved,
        "errors_ignored": errors_ignored,
        "errors_investigated": errors_resolved + errors_ignored,
        "feedback_received": by_type.get("feedback_received", 0),
        "survey_responses": by_type.get("survey_response", 0),
        "members_joined": by_type.get("member_joined", 0),
        "members_removed": by_type.get("member_removed", 0),
        "products_created": by_type.get("product_created", 0),
        "rules_created": by_type.get("rule_created", 0),
        "api_keys_created": by_type.get("api_key_created", 0),
        "product_rows": product_rows,
        "daily": daily,
        "recent": list(
            logs.select_related("actor")
            .order_by("-created_at")[:25]
        ),
    }


def _rate(done, total):
    """Whole-number percentage, or None when there is nothing to divide by."""
    return round(100 * done / total) if total else None


def _change(now, before):
    """How a number moved against the previous period, for the KPI tiles."""
    if before == 0:
        return {"before": 0, "pct": None, "dir": "up" if now else "flat"}
    pct = round(100 * (now - before) / before)
    return {"before": before, "pct": abs(pct), "dir": "up" if pct > 0 else ("down" if pct < 0 else "flat")}


def _report_kpis(company, start_date, end_date, mine_user, summary):
    """The five headline numbers, each with its change against the period just
    before this one (same length, ending the day before ``start_date``)."""
    from datetime import datetime, time

    from apps.dashboards.models import ActivityLog

    days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    prev = ActivityLog.objects.filter(
        company=company,
        created_at__range=(datetime.combine(prev_start, time.min), datetime.combine(prev_end, time.max)),
    )
    if mine_user is not None:
        prev = prev.filter(actor=mine_user)
    by_type = dict(prev.values_list("event_type").annotate(c=Count("id")).order_by("event_type"))
    status = prev.filter(event_type="ticket_status_changed")
    estatus = prev.filter(event_type="error_status_changed")
    before = {
        "tickets_created": by_type.get("ticket_created", 0),
        "tickets_resolved": status.filter(metadata__to="resolved").count(),
        "errors_captured": by_type.get("error_captured", 0) + by_type.get("error_created", 0),
        "errors_resolved": by_type.get("error_resolved", 0) + estatus.filter(metadata__to="resolved").count(),
        "total_events": prev.count(),
    }
    labels = [
        ("tickets_created", "Tickets created", "blue"),
        ("tickets_resolved", "Tickets resolved", "green"),
        ("errors_captured", "Errors captured", "red"),
        ("errors_resolved", "Errors resolved", "green"),
        ("total_events", "All activity", "gray"),
    ]
    return [
        {"key": key, "label": label, "tone": tone, "value": summary[key], **_change(summary[key], before[key])}
        for key, label, tone in labels
    ]


def _daily_bars(daily):
    """Bar heights as percentages of the busiest day, so the template needs no maths."""
    if not daily:
        return []
    peak = max(max(d["tickets_created"], d["tickets_resolved"], d["errors_captured"], d["errors_resolved"]) for d in daily) or 1
    step = max(1, len(daily) // 8)
    bars = []
    for i, d in enumerate(daily):
        bars.append({
            "date": d["date"],
            "label": i % step == 0,
            "created": round(100 * d["tickets_created"] / peak),
            "resolved": round(100 * d["tickets_resolved"] / peak),
            "captured": round(100 * d["errors_captured"] / peak),
            "fixed": round(100 * d["errors_resolved"] / peak),
            "row": d,
        })
    return bars


def _product_bars(rows):
    scored = []
    for r in rows:
        total = r["tickets_created"] + r["tickets_resolved"] + r["errors_captured"] + r["errors_resolved"] + r["feedback"]
        if total:
            scored.append({**r, "total": total})
    scored.sort(key=lambda r: -r["total"])
    peak = scored[0]["total"] if scored else 1
    for r in scored:
        r["pct"] = max(4, round(100 * r["total"] / peak))
    return scored[:8]


def _event_mix(by_type):
    from apps.dashboards.models import ActivityLog

    names = dict(ActivityLog.EventType.choices)
    ranked = sorted(by_type.items(), key=lambda kv: -kv[1])[:7]
    peak = ranked[0][1] if ranked else 1
    return [
        {"label": names.get(k, k.replace("_", " ").title()), "count": v, "pct": max(4, round(100 * v / peak))}
        for k, v in ranked
    ]


def _personal_attendance(company, user, today):
    """Today's punch state plus the month-to-date picture.

    An unclosed day (punched in, never out) is counted by
    `service.effective_span_for`, which uses elapsed time capped at the
    scheduled day. It used to contribute 0 -- better to under-report than invent
    an end time -- but 0 is not neutral: the employee loses the day's pay until
    an admin notices, which is exactly the case nobody noticed.
    """
    from apps.attendance.models import AttendanceRecord
    from apps.attendance.service import net_minutes_for, shift_for
    from apps.leave.service import is_on_leave

    record = AttendanceRecord.objects.filter(
        company=company, user=user, date=today
    ).first()

    month_first = today.replace(day=1)
    month_records = AttendanceRecord.objects.filter(
        company=company, user=user, date__gte=month_first, date__lte=today
    ).exclude(check_in__isnull=True)
    present_days = month_records.count()
    shift = shift_for(company)
    minutes = sum(net_minutes_for(r, shift) for r in month_records)

    return {
        "record": record,
        "on_leave_today": is_on_leave(company, user, today),
        "present_days": present_days,
        "worked_minutes": minutes,
        "month_label": today.strftime("%B"),
    }


def _personal_payroll(company, user):
    """Latest issued payslip, or an explicit 'not on payroll' state.

    Returns None fields rather than a fake zero when the user has never been
    on a run -- a 0.00 payslip would read as "you were paid nothing".
    """
    from apps.payroll.models import Payslip, PayrollProfile

    payslip = (
        Payslip.objects.filter(company=company, user=user)
        .select_related("run")
        .order_by("-run__period_end", "-pk")
        .first()
    )

    # "On payroll" is a profile fact, not a payslip fact. Reading it off the
    # payslip alone would tell someone whose admin simply hasn't run payroll
    # yet that they are not on payroll at all.
    latest = (
        PayrollProfile.objects.filter(company=company, user=user, is_on_payroll=True)
        .order_by("-effective_from")
        .first()
    )
    monthly = latest.monthly_salary if latest else None

    if not payslip:
        return {
            "payslip": None,
            "on_payroll": False,
            "has_profile": bool(latest),
            "monthly_salary": monthly,
        }

    profile = payslip.profile
    return {
        "payslip": payslip,
        "on_payroll": True,
        "has_profile": True,
        "monthly_salary": profile.monthly_salary if profile else monthly,
    }


def _personal_dsr(company, user, today):
    """This week's DSR logging, so an empty sheet is visible as a prompt."""
    from apps.dsr.models import DSREntry

    week_start = today - timedelta(days=today.weekday())
    week = DSREntry.objects.filter(
        company=company, user=user, date__gte=week_start, date__lte=today
    )
    recent = (
        DSREntry.objects.filter(company=company, user=user)
        .order_by("-date", "-pk")
        .select_related("ticket")[:5]
    )
    # Work still open on the sheet (not completed), so it is visible without opening it.
    open_tasks = DSREntry.objects.filter(
        company=company,
        user=user,
        status__in=[DSREntry.Status.IN_PROGRESS, DSREntry.Status.BLOCKED],
        date__gte=today - timedelta(days=14),
    ).order_by("-date", "-pk")
    return {
        "dsr_open": list(open_tasks[:4]),
        "dsr_open_count": open_tasks.count(),
        "dsr_week_start": week_start,
        "dsr_entries": week.count(),
        "dsr_hours": week.aggregate(total=Sum("hours_spent"))["total"] or Decimal("0"),
        "dsr_recent": list(recent),
    }



def _dashboard_charts(user, company, today):
    """The three small graphs on the home page, all scoped like the lists they summarise."""
    from apps.attendance import service as att
    from apps.attendance.models import AttendanceRecord
    from apps.ingestion.models import ErrorOccurrence
    from apps.products.access import accessible_error_groups, accessible_tickets
    from apps.tickets.models import Ticket

    # Hours this week, Monday to Sunday.
    monday = today - timedelta(days=today.weekday())
    shift = att.shift_for(company)
    records = {
        r.date: r
        for r in AttendanceRecord.objects.filter(
            company=company, user=user, date__gte=monday, date__lte=monday + timedelta(days=6)
        )
    }
    target = max(1, shift.worked_minutes_per_day)
    mins = [
        att.net_minutes_for(records[d], shift) if d in records and records[d].check_in else 0
        for d in (monday + timedelta(days=i) for i in range(7))
    ]
    scale = max(target, max(mins))
    week = [
        {
            "label": (monday + timedelta(days=i)).strftime("%a"),
            "hours": f"{m // 60}h {m % 60:02d}m" if m else "–",
            "pct": round(m * 100 / scale),
            "met": m >= target,
            "today": (monday + timedelta(days=i)) == today,
            "future": (monday + timedelta(days=i)) > today,
        }
        for i, m in enumerate(mins)
    ]
    week_total = sum(mins)

    # Tickets by status across everything this person can open.
    palette = {
        "open": "#1C75BC", "in_progress": "#75BAE6", "in_review": "#7c3aed",
        "resolved": "#177a4c", "closed": "#9aa3b2",
    }
    counts = dict(
        accessible_tickets(user, company).values_list("status").annotate(n=Count("pk")).order_by()
    )
    total = sum(counts.values())
    statuses, stops, at = [], [], 0.0
    for value, label in Ticket.Status.choices:
        n = counts.get(value, 0)
        if not n:
            continue
        color = palette.get(value, "#9aa3b2")
        pct = n * 100 / total
        stops.append(f"{color} {at:.2f}% {at + pct:.2f}%")
        at += pct
        statuses.append({"label": label, "n": n, "color": color})
    donut = f"conic-gradient({', '.join(stops)})" if stops else "none"

    # Error occurrences per day, last 14 days.
    since = today - timedelta(days=13)
    per_day = dict(
        ErrorOccurrence.objects.filter(
            company=company,
            error_group__in=accessible_error_groups(user, company),
            created_at__date__gte=since,
        )
        .values_list("created_at__date")
        .annotate(n=Count("pk"))
        .order_by()
    )
    series = [per_day.get(since + timedelta(days=i), 0) for i in range(14)]
    peak = max(series) or 1
    errors = [
        {"n": n, "pct": max(4, round(n * 100 / peak)) if n else 2, "label": (since + timedelta(days=i)).strftime("%b %d")}
        for i, n in enumerate(series)
    ]
    return {
        "chart_week": week,
        "chart_week_total": f"{week_total // 60}h {week_total % 60:02d}m",
        "chart_week_target": f"{target // 60}h {target % 60:02d}m",
        "chart_status": statuses,
        "chart_status_total": total,
        "chart_donut": donut,
        "chart_errors": errors,
        "chart_errors_total": sum(series),
    }



DSR_NUDGE_TITLE = "Log your DSR for today"


def _dsr_nudge(company, user, today, attendance):
    """True when the working day is over and nothing was logged on the DSR.

    Weekends, leave and days with no punch never nudge: nobody owes a DSR for a
    day they did not work. The first time it is true each day it also leaves one
    line in the bell, so the reminder survives closing the page.
    """
    from apps.attendance.service import shift_for
    from apps.dsr.models import DSREntry
    from apps.notifications import service as notifications
    from apps.notifications.models import Notification

    record = attendance["record"]
    if today.weekday() >= 5 or attendance["on_leave_today"] or not (record and record.check_in):
        return False
    shift = shift_for(company)
    if timezone.localtime().time() < shift.end_time and not record.check_out:
        return False
    if DSREntry.objects.filter(company=company, user=user, date=today).exists():
        return False
    if not Notification.objects.filter(
        company=company, user=user, title=DSR_NUDGE_TITLE, created_at__date=today
    ).exists():
        notifications.notify(
            user=user, company=company, kind=Notification.Kind.SYSTEM,
            title=DSR_NUDGE_TITLE, body="Nothing is logged for today yet.", url="/dsr/",
        )
    return True


def get_personal_dashboard_data(user, company):
    """Home page data: the member's own month, with company totals for admins.

    This is deliberately personal-first. The old dashboard opened on company
    error and ticket counts, which told an employee nothing about their own
    week. Everything here is either "mine" or, for owner/admin, a company
    number they are actually responsible for.
    """
    from apps.accounts.models import Membership
    from apps.leave.models import LeaveRequest
    from apps.leave.service import balances_for
    from apps.products.access import accessible_tickets

    today = timezone.localdate()
    membership = Membership.objects.filter(user=user, company=company).first()
    is_privileged = bool(
        membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)
    )

    attendance = _personal_attendance(company, user, today)

    my_leave = (
        LeaveRequest.objects.filter(company=company, user=user)
        .select_related("policy")
        .order_by("-start_date")[:4]
    )
    pending_leave = LeaveRequest.objects.filter(
        company=company, user=user, status="pending"
    ).count()

    # `accessible_tickets`, not `company=company`: a ticket is product-owned,
    # and a developer assigned a ticket in a product they cannot otherwise see
    # must not have it surface here.
    ticket_scope = accessible_tickets(user, company).filter(assignees=user)
    open_mine = ticket_scope.exclude(status__in=["resolved", "closed"])
    my_tickets = open_mine.select_related("product").order_by("-updated_at")[:5]
    my_ticket_count = open_mine.count()
    # Overdue first, then the next seven days: what the person should look at today.
    due_soon = list(
        open_mine.filter(deadline__isnull=False, deadline__lte=timezone.now() + timedelta(days=7))
        .select_related("product").order_by("deadline")[:4]
    )

    data = {
        "is_privileged": is_privileged,
        "role": membership.role if membership else None,
        "today": today,
        "attendance": attendance,
        "leave_balances": balances_for(company, user, today.year),
        "my_leave_requests": list(my_leave),
        "pending_leave": pending_leave,
        "payroll": _personal_payroll(company, user),
        "dsr": _personal_dsr(company, user, today),
        "my_tickets": list(my_tickets),
        "my_ticket_count": my_ticket_count,
        "due_soon": due_soon,
        **_dashboard_charts(user, company, today),
        "dsr_nudge": _dsr_nudge(company, user, today, attendance),
    }

    if is_privileged:
        data["team"] = get_admin_dashboard_data(company)
        data["leave_approvals"] = LeaveRequest.objects.filter(
            company=company, status="pending"
        ).select_related("user", "policy").order_by("start_date")[:5]
        data["leave_approval_count"] = LeaveRequest.objects.filter(
            company=company, status="pending"
        ).count()

    return data
