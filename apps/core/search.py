"""Global search for the top bar and Ctrl+K palette.

Every query goes through the same access helpers as the list pages
(`accessible_tickets`, `accessible_error_groups`, `accessible_products`), so
search can never show a title the person could not open. People are searched
only for owners and admins, who can open an attendance page for them; everyone
else would get a name with nowhere to go.
"""

import re

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.products.access import accessible_error_groups, accessible_products, accessible_tickets

_TICKET_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9]{1,5}?)[-\s]?0*(\d+)$")
_BARE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,5}$")
LIMITS = {"tickets": 6, "errors": 5, "products": 4, "people": 5, "pages": 6, "feedback": 4, "surveys": 3, "rules": 3, "dsr": 4, "leave": 3}
MIN_QUERY = 2


def _pages(request):
    """(label, url, keywords, admin_only) for every place worth jumping to."""
    from apps.leave.views import is_approver

    is_admin = request.company_role in ("owner", "admin")
    approver = is_admin or is_approver(request.user, request.company)
    rows = [
        ("Home", reverse("dashboards:index"), "dashboard overview", False),
        ("Products", reverse("products:product_list"), "apps projects", False),
        ("All tickets", reverse("tickets:ticket_board"), "kanban board issues bugs", False),
        ("All errors", reverse("errors:error_list"), "exceptions crashes", False),
        ("Reports", reverse("dashboards:reports"), "summary analytics", False),
        ("Automation rules", reverse("automation:rule_list"), "auto ticket", False),
        ("CS Hub", reverse("feedback:cs_hub"), "customer support feedback", False),
        ("Surveys", reverse("feedback:survey_list"), "feedback forms", False),
        ("My attendance", reverse("attendance:my_attendance"), "check in out punch clock", False),
        ("My leave", reverse("leave:my_leave"), "time off vacation holiday", False),
        ("Leave calendar", reverse("leave:calendar"), "who is off team holidays", False),
        ("DSR sheet", reverse("dsr:dsr_sheet"), "daily status report timesheet", False),
        ("My payslips", reverse("payroll:my_payslips"), "salary pay", False),
        ("My profile", reverse("accounts:profile"), "account password", False),
        ("Notifications", reverse("notifications:list"), "bell alerts", False),
        ("Team attendance", reverse("attendance:team_attendance"), "who is in clock", True),
        ("Timesheet", reverse("attendance:timesheet"), "monthly hours", True),
        ("Payroll runs", reverse("payroll:run_list"), "salary cycle", True),
        ("Payroll setup", reverse("payroll:profiles"), "salaries rates", True),
        ("Leave policies", reverse("leave:policies"), "types caps", True),
        ("Team", reverse("accounts:team_list"), "members invite roles", True),
        ("Audit log", reverse("dashboards:audit_log"), "activity history", True),
    ]
    if approver:
        rows.append(("Leave approvals", reverse("leave:approvals"), "requests approve reject", False))
    return [r for r in rows if is_admin or not r[3]]


def search(request, query):
    """Groups of results for `query`. Short queries return the page list only."""
    user, company = request.user, request.company
    query = (query or "").strip()[:100]
    groups = []

    needle = query.lower()
    pages = [
        {"title": label, "subtitle": "Page", "url": url}
        for label, url, keywords, _ in _pages(request)
        if not needle or needle in label.lower() or needle in keywords
    ][: LIMITS["pages"]]

    if len(query) < MIN_QUERY and not query.lstrip("#").isdigit():
        return [{"label": "Go to", "items": pages}] if pages else []

    number = query.lstrip("#")
    ticket_filter = Q(title__icontains=query) | Q(description__icontains=query) | Q(comments__body__icontains=query)
    if number.isdigit():
        ticket_filter |= Q(pk=int(number))
    # AUM-14, aum14 and "aum 14" find that product's ticket number 14. A bare key
    # such as AUM lists the product's newest tickets.
    keyed = _TICKET_KEY.match(query)
    if keyed:
        ticket_filter |= Q(product__key__iexact=keyed.group(1), number=int(keyed.group(2)))
    elif _BARE_KEY.match(query):
        ticket_filter |= Q(product__key__iexact=query)
    tickets = (
        accessible_tickets(user, company)
        .filter(ticket_filter)
        .select_related("product")
        .distinct()
        .order_by("-updated_at")[: LIMITS["tickets"]]
    )
    ticket_items = [
        {
            "title": f"{t.key} {t.title}",
            "subtitle": " · ".join(x for x in (t.product.name if t.product else "", t.get_status_display()) if x),
            "url": reverse("tickets:ticket_detail", args=[t.pk]),
        }
        for t in tickets
    ]

    errors = (
        accessible_error_groups(user, company)
        .filter(
            Q(title__icontains=query)
            | Q(error_type__icontains=query)
            | Q(occurrences__page__icontains=query)
            | Q(occurrences__stacktrace__icontains=query)
        )
        .select_related("product")
        .distinct()
        .order_by("-last_seen")[: LIMITS["errors"]]
    )
    error_items = [
        {
            "title": e.title[:120],
            "subtitle": f"{e.product.name} · {e.get_status_display()} · {e.occurrence_count} times",
            "url": reverse("errors:error_detail", args=[e.pk]),
        }
        for e in errors
    ]

    products = accessible_products(user, company).filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(key__iexact=query)).order_by("name")[: LIMITS["products"]]
    product_items = [
        {"title": p.name, "subtitle": "Product", "url": reverse("products:product_board", args=[p.pk])}
        for p in products
    ]

    scope = accessible_products(user, company)
    from apps.automation.models import AutoTicketRule
    from apps.dsr.models import DSREntry
    from apps.feedback.models import Survey
    from apps.ingestion.models import Feedback
    from apps.leave.models import LeaveRequest

    feedback_items = [
        {
            "title": (f.comment or "Feedback").strip()[:110],
            "subtitle": f"{f.product.name} · Feedback",
            "url": reverse("feedback:cs_hub"),
        }
        for f in Feedback.objects.filter(company=company, product__in=scope, comment__icontains=query)
        .select_related("product")
        .order_by("-pk")[: LIMITS["feedback"]]
    ]
    survey_items = [
        {"title": sv.name, "subtitle": "Survey", "url": reverse("feedback:survey_detail", args=[sv.pk])}
        for sv in Survey.objects.filter(company=company, product__in=scope)
        .filter(Q(name__icontains=query) | Q(description__icontains=query))[: LIMITS["surveys"]]
    ]
    rule_items = [
        {"title": r.name, "subtitle": "Automation rule", "url": reverse("automation:rule_edit", args=[r.pk])}
        for r in AutoTicketRule.objects.filter(company=company, product__in=scope, name__icontains=query)[: LIMITS["rules"]]
    ]
    # Your own work log and leave: nobody else's, whatever their role.
    dsr_items = [
        {
            "title": e.task_name[:110],
            "subtitle": f"DSR · {e.date:%b %d}",
            "url": reverse("dsr:dsr_sheet"),
        }
        for e in DSREntry.objects.filter(company=company, user=user)
        .filter(Q(task_name__icontains=query) | Q(notes__icontains=query))
        .order_by("-date")[: LIMITS["dsr"]]
    ]
    leave_items = [
        {
            "title": f"{r.start_date:%b %d} – {r.end_date:%b %d} · {r.get_status_display()}",
            "subtitle": "My leave",
            "url": reverse("leave:my_leave"),
        }
        for r in LeaveRequest.objects.filter(company=company, user=user, reason__icontains=query).order_by("-start_date")[
            : LIMITS["leave"]
        ]
    ]

    people_items = []
    if request.company_role in ("owner", "admin"):
        User = get_user_model()
        people = (
            User.objects.filter(memberships__company=company)
            .filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
            .distinct()
            .order_by("username")[: LIMITS["people"]]
        )
        people_items = [
            {
                "title": u.get_full_name() or u.username,
                "subtitle": f"@{u.username} · attendance",
                "url": f"{reverse('attendance:my_attendance')}?user_id={u.pk}",
            }
            for u in people
        ]

    for label, items in (
        ("Tickets", ticket_items),
        ("Errors", error_items),
        ("Products", product_items),
        ("People", people_items),
        ("Feedback", feedback_items),
        ("Surveys", survey_items),
        ("Automation", rule_items),
        ("My DSR", dsr_items),
        ("My leave", leave_items),
        ("Go to", pages),
    ):
        if items:
            groups.append({"label": label, "items": items})
    return groups


class SearchView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"groups": search(request, request.GET.get("q", ""))})
