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
