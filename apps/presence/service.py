"""Who is online, and what they are doing.

Activity is derived on the server from the page path, never from text the
browser sends, so a client cannot label itself as something else. Labels name
the kind of page and (for tickets and errors) a number, never a title or a
product name: the people looking at this list may not have access to the
product, so a name would leak what they cannot open.
"""

import re
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Membership
from apps.presence.models import PresenceSession

# A heartbeat arrives every 25 seconds. Three missed beats and the tab is gone.
STALE_AFTER = timedelta(seconds=75)
PURGE_AFTER = timedelta(minutes=5)

_ACTIVITY = [
    (r"^/(dashboards)?/?$", "On the home dashboard"),
    (r"^/dashboards/reports", "Reading reports"),
    (r"^/dashboards/audit", "Reading the audit log"),
    (r"^/tickets/(\d+)/?$", "Viewing ticket #{0}"),
    (r"^/tickets/(create|new)", "Creating a ticket"),
    (r"^/tickets/", "Browsing tickets"),
    (r"^/errors/(\d+)/?$", "Looking at error group #{0}"),
    (r"^/errors/", "Browsing errors"),
    (r"^/products/\d+/tickets", "Browsing tickets"),
    (r"^/products/\d+/errors", "Browsing errors"),
    (r"^/products/", "Browsing products"),
    (r"^/dsr/", "Filling in the DSR"),
    (r"^/attendance/team", "Checking team attendance"),
    (r"^/attendance/timesheet", "Reviewing timesheets"),
    (r"^/attendance/", "On attendance"),
    (r"^/leave/approvals", "Reviewing leave requests"),
    (r"^/leave/", "On leave"),
    (r"^/payroll/me", "Reading their payslips"),
    (r"^/payroll/", "In an admin area"),
    (r"^/feedback/", "Reading feedback"),
    (r"^/automation/", "Editing automation rules"),
    (r"^/team/", "Managing the team"),
    (r"^/profile/", "On their profile"),
]
_COMPILED = [(re.compile(pattern), label) for pattern, label in _ACTIVITY]


def activity_for(path):
    path = (path or "")[:255]
    for pattern, label in _COMPILED:
        match = pattern.match(path)
        if match:
            return label.format(*match.groups())
    return "Using the app"


def snapshot(company):
    """The list the browser renders, as plain JSON-safe dicts."""
    from apps.attendance.models import AttendanceRecord
    from apps.tickets.models import Ticket

    now = timezone.now()
    PresenceSession.objects.filter(company=company, last_seen__lt=now - PURGE_AFTER).delete()

    sessions = (
        PresenceSession.objects.filter(company=company, last_seen__gte=now - STALE_AFTER)
        .select_related("user")
        .order_by("-last_seen")
    )
    by_user = {}
    for session in sessions:
        by_user.setdefault(session.user_id, []).append(session)
    if not by_user:
        return []

    roles = dict(
        Membership.objects.filter(company=company, user_id__in=by_user).values_list("user_id", "role")
    )
    clocked_in = {
        r.user_id: r.check_in
        for r in AttendanceRecord.objects.filter(
            company=company,
            user_id__in=by_user,
            date=timezone.localdate(),
            check_in__isnull=False,
            check_out__isnull=True,
        )
    }
    busy = {}
    for user_id in Ticket.assignees.through.objects.filter(
        ticket__company=company,
        ticket__status="in_progress",
        user_id__in=by_user,
    ).values_list("user_id", flat=True):
        busy[user_id] = busy.get(user_id, 0) + 1

    rows = []
    for user_id, user_sessions in by_user.items():
        active = [s for s in user_sessions if s.is_active]
        lead = (active or user_sessions)[0]
        user = lead.user
        rows.append(
            {
                "user_id": user_id,
                "name": user.get_full_name() or user.username,
                "username": user.username,
                "role": roles.get(user_id, ""),
                "status": "online" if active else "away",
                "activity": lead.activity if active else "Away from the keyboard",
                "tabs": len(user_sessions),
                "clocked_in_at": clocked_in[user_id].isoformat() if user_id in clocked_in else None,
                "tickets_in_progress": busy.get(user_id, 0),
                "since": min(s.connected_at for s in user_sessions).isoformat(),
            }
        )
    rows.sort(key=lambda r: (r["status"] != "online", r["name"].lower()))
    return rows


def snapshot_for_company_id(company_id):
    from apps.accounts.models import Company

    company = Company.objects.filter(pk=company_id).first()
    return snapshot(company) if company else []
