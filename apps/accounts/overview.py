"""What a person's own page and a colleague's page show: numbers, recent activity, streak and milestones."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Membership
from apps.attendance.models import AttendanceRecord
from apps.core import kudos
from apps.dashboards.models import ActivityLog
from apps.dsr.duration import format_hm
from apps.dsr.models import DSREntry
from apps.products.access import accessible_products, accessible_tickets


def my_overview(user, company):
    """Since when, how busy, what they touched lately, plus the streak and any milestone worth a line."""
    today = timezone.localdate()
    membership = Membership.objects.filter(user=user, company=company).first()
    mine = accessible_tickets(user, company).filter(assignees=user)
    week_start = today - timedelta(days=today.weekday())
    hours = DSREntry.objects.filter(company=company, user=user, date__gte=week_start).aggregate(t=Sum("hours_spent"))["t"] or Decimal("0")
    return {
        "joined": membership.created_at if membership else None,
        "last_login": user.last_login,
        "stats": [
            ("Open tickets", mine.exclude(status__in=["resolved", "closed"]).count()),
            ("Resolved (30 days)", mine.filter(status__in=["resolved", "closed"], updated_at__gte=timezone.now() - timedelta(days=30)).count()),
            ("Logged this week", format_hm(hours) if hours else "0m"),
            ("Days present", AttendanceRecord.objects.filter(company=company, user=user, date__year=today.year, date__month=today.month, check_in__isnull=False).count()),
            ("Products", accessible_products(user, company).count()),
        ],
        "recent": ActivityLog.objects.filter(company=company, actor=user).order_by("-created_at")[:8],
        "streak": kudos.on_time_streak(company, user),
        "milestones": kudos.milestones(company, user),
    }


def member_overview(viewer, company, membership):
    """A colleague's page. Only tickets the viewer can open are counted or listed; the email is for owners and admins."""
    theirs = accessible_tickets(viewer, company).filter(assignees=membership.user).select_related("product")
    open_ = theirs.exclude(status__in=["resolved", "closed"]).order_by("-updated_at")
    viewer_role = Membership.objects.filter(user=viewer, company=company).values_list("role", flat=True).first()
    return {
        "streak": kudos.on_time_streak(company, membership.user),
        "milestones": kudos.milestones(company, membership.user),
        "open_count": open_.count(),
        "resolved_30d": theirs.filter(status__in=["resolved", "closed"], updated_at__gte=timezone.now() - timedelta(days=30)).count(),
        "tickets": list(open_[:10]),
        "show_email": viewer_role in ("owner", "admin"),
    }
