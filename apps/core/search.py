"""Global search for the Ctrl+K palette.

Every query goes through the same access helpers as the list pages
(`accessible_tickets`, `accessible_error_groups`, `accessible_products`), so
search can never show a title the person could not open. People are searched
only for owners and admins, who can open an attendance page for them; everyone
else would get a name with nowhere to go.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.products.access import accessible_error_groups, accessible_products, accessible_tickets

LIMITS = {"tickets": 6, "errors": 5, "products": 4, "people": 5, "pages": 6}
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
    ticket_filter = Q(title__icontains=query)
    if number.isdigit():
        ticket_filter |= Q(pk=int(number))
    tickets = (
        accessible_tickets(user, company)
        .filter(ticket_filter)
        .select_related("product")
        .order_by("-updated_at")[: LIMITS["tickets"]]
    )
    ticket_items = [
        {
            "title": f"#{t.pk} {t.title}",
            "subtitle": " · ".join(x for x in (t.product.name if t.product else "", t.get_status_display()) if x),
            "url": reverse("tickets:ticket_detail", args=[t.pk]),
        }
        for t in tickets
    ]

    errors = (
        accessible_error_groups(user, company)
        .filter(Q(title__icontains=query) | Q(error_type__icontains=query))
        .select_related("product")
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

    products = accessible_products(user, company).filter(name__icontains=query).order_by("name")[: LIMITS["products"]]
    product_items = [
        {"title": p.name, "subtitle": "Product", "url": reverse("products:product_board", args=[p.pk])}
        for p in products
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
        ("Go to", pages),
    ):
        if items:
            groups.append({"label": label, "items": items})
    return groups


class SearchView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"groups": search(request, request.GET.get("q", ""))})
