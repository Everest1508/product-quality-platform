from datetime import timedelta

from django.db.models import Avg, Count, Q
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
        "errors_by_day": errors_by_day,
        "error_status_breakdown": error_status_breakdown,
        "total_tickets": total_tickets,
        "open_tickets": open_tickets,
        "tickets_by_status": tickets_by_status,
        "ticket_burndown": ticket_burndown,
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
            ticket_qs.filter(assigned_to__isnull=True)
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
        ticket_scope.filter(assigned_to=user)
        .exclude(status__in=["resolved", "closed"])
        .select_related("product")
        .order_by("-updated_at")[:10]
    )
    my_work_count = (
        ticket_scope.filter(assigned_to=user)
        .exclude(status__in=["resolved", "closed"])
        .count()
    )

    attention = _build_attention(company, product_ids, is_privileged)

    data = {
        "is_privileged": is_privileged,
        "role": membership.role if membership else None,
        "product_cards": _build_product_cards(company, product_ids),
        "open_errors": open_errors,
        "open_tickets": open_tickets,
        "resolved_errors": resolved_errors,
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

    return {
        "scope": scope,
        "start_date": start_date,
        "end_date": end_date,
        "total_events": logs.count(),
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
