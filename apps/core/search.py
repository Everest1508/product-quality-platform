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
LIMITS = {"tickets": 6, "errors": 5, "products": 4, "people": 5, "pages": 6, "feedback": 4, "surveys": 3, "rules": 3, "dsr": 4, "leave": 3, "expenses": 5, "corrections": 4, "log": 4, "notifications": 4}
MIN_QUERY = 2


def _pages(request):
    """(label, url, keywords, admin_only) for every place worth jumping to."""
    from apps.leave.views import is_approver

    is_admin = request.company_role in ("owner", "admin")
    approver = is_admin or is_approver(request.user, request.company)
    rows = [
        ("Home", reverse("dashboards:index"), "dashboard overview", False),
        ("Projects", reverse("products:project_board"), "apps products", False),
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
        ("Expenses", reverse("expenses:expense_list"), "spend money paid tea milk server subscription trip", True),
        ("Attendance corrections", reverse("attendance:corrections"), "fix punch requests", True),
    ]
    if approver:
        rows.append(("Leave approvals", reverse("leave:approvals"), "requests approve reject", False))
    return [r for r in rows if is_admin or not r[3]]


_FILTER = re.compile(r"\b(in|assignee|status):(\S+)", re.I)
# What `in:` accepts, mapped to the group it narrows to.
_IN_ALIASES = {
    "ticket": "tickets", "tickets": "tickets", "error": "errors", "errors": "errors",
    "product": "products", "products": "products", "people": "people", "person": "people",
    "user": "people", "users": "people", "feedback": "feedback", "survey": "surveys",
    "surveys": "surveys", "rule": "rules", "rules": "rules", "automation": "rules",
    "dsr": "dsr", "leave": "leave", "expense": "expenses", "expenses": "expenses",
    "correction": "corrections", "corrections": "corrections", "log": "log", "update": "log",
    "notification": "notifications", "notifications": "notifications", "page": "pages", "pages": "pages", "go": "pages",
}


def parse_query(raw):
    """Split `in:tickets assignee:me status:open some words` into filters and text."""
    raw = (raw or "")[:140]
    filters = {m.group(1).lower(): m.group(2).lower() for m in _FILTER.finditer(raw)}
    return filters, " ".join(_FILTER.sub(" ", raw).split())


def snippet(text, query, width=90):
    """A short stretch of `text` around the first match, or "" when it holds none."""
    text = " ".join((text or "").split())
    at = text.lower().find(query.lower()) if query else -1
    if at < 0:
        return ""
    start = max(0, at - width // 3)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def search(request, query):
    """Groups of results for `query`. Short queries return the page list only."""
    user, company = request.user, request.company
    filters, query = parse_query(query)
    only = _IN_ALIASES.get(filters.get("in", ""))
    if "assignee" in filters and not only:
        only = "tickets"
    groups = []

    def wanted(name):
        return only is None or only == name

    needle = query.lower()
    pages = [
        {"title": label, "subtitle": "Page", "url": url}
        for label, url, keywords, _ in _pages(request)
        if not needle or needle in label.lower() or needle in keywords
    ][: LIMITS["pages"]]

    if not filters and len(query) < MIN_QUERY and not query.lstrip("#").isdigit():
        return [{"label": "Go to", "items": pages}] if pages else []

    number = query.lstrip("#")
    ticket_filter = Q()
    if query:
        ticket_filter = (
            Q(title__icontains=query) | Q(description__icontains=query) | Q(comments__body__icontains=query)
        )
        if number.isdigit():
            ticket_filter |= Q(pk=int(number))
        # AUM-14, aum14 and "aum 14" find that product's ticket number 14. A bare key
        # such as AUM lists the product's newest tickets.
        keyed = _TICKET_KEY.match(query)
        if keyed:
            ticket_filter |= Q(product__key__iexact=keyed.group(1), number=int(keyed.group(2)))
        elif _BARE_KEY.match(query):
            ticket_filter |= Q(product__key__iexact=query)
    ticket_qs = accessible_tickets(user, company).filter(ticket_filter)
    if filters.get("assignee") in ("me", "@me"):
        ticket_qs = ticket_qs.filter(assignees=user)
    elif filters.get("assignee"):
        ticket_qs = ticket_qs.filter(assignees__username__iexact=filters["assignee"])
    if filters.get("status"):
        ticket_qs = ticket_qs.filter(status__iexact=filters["status"].replace("-", "_"))
    tickets = ticket_qs.select_related("product").distinct().order_by("-updated_at")[: LIMITS["tickets"]]
    ticket_items = []
    for t in tickets:
        why = ""
        if query and query.lower() not in t.title.lower():
            why = snippet(t.description, query)
            if not why:
                comment = t.comments.filter(body__icontains=query).values_list("body", flat=True).first()
                why = snippet(comment, query)
        ticket_items.append({
            "title": f"{t.key} {t.title}",
            "subtitle": " · ".join(x for x in (t.product.name if t.product else "", t.get_status_display()) if x),
            "snippet": why,
            "url": reverse("tickets:ticket_detail", args=[t.pk]),
        })

    error_qs = accessible_error_groups(user, company)
    if query:
        error_qs = error_qs.filter(
            Q(title__icontains=query)
            | Q(error_type__icontains=query)
            | Q(occurrences__page__icontains=query)
            | Q(occurrences__stacktrace__icontains=query)
        )
    if filters.get("status"):
        error_qs = error_qs.filter(status__iexact=filters["status"])
    error_items = []
    if "assignee" not in filters:
        for e in error_qs.select_related("product").distinct().order_by("-last_seen")[: LIMITS["errors"]]:
            why = ""
            if query and query.lower() not in e.title.lower():
                hit = e.occurrences.filter(Q(page__icontains=query) | Q(stacktrace__icontains=query)).first()
                if hit:
                    why = snippet(hit.page, query) or snippet(hit.stacktrace, query)
            error_items.append({
                "title": e.title[:120],
                "subtitle": f"{e.product.name} · {e.get_status_display()} · {e.occurrence_count} times",
                "snippet": why,
                "url": reverse("errors:error_detail", args=[e.pk]),
            })

    products = accessible_products(user, company).filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(key__iexact=query)).order_by("name")[: LIMITS["products"]]
    product_items = [
        {
            "title": p.name,
            "subtitle": "Product",
            "snippet": snippet(p.description, query) if query.lower() not in p.name.lower() else "",
            "url": reverse("products:product_board", args=[p.pk]),
        }
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

    is_admin = request.company_role in ("owner", "admin")
    log_items = []
    if query:
        from apps.products.models import ProjectLogEntry

        for entry in (
            ProjectLogEntry.objects.filter(company=company, product__in=scope, body__icontains=query)
            .select_related("product")
            .order_by("-created_at")[: LIMITS["log"]]
        ):
            log_items.append({
                "title": snippet(entry.body, query, 110) or entry.body[:110],
                "subtitle": f"{entry.product.name} · {entry.get_kind_display()} · {entry.created_at:%b %d}",
                "url": reverse("products:project_lifecycle", args=[entry.product_id]),
            })

    notification_items = []
    if query:
        from apps.notifications.models import Notification

        notification_items = [
            {"title": n.title[:110], "subtitle": f"Notification · {n.created_at:%b %d}", "url": n.url or reverse("notifications:list")}
            for n in Notification.objects.filter(user=user, company=company)
            .filter(Q(title__icontains=query) | Q(body__icontains=query))
            .order_by("-created_at")[: LIMITS["notifications"]]
        ]

    expense_items, correction_items = [], []
    if is_admin and query:
        from apps.attendance.models import AttendanceCorrection
        from apps.expenses.models import Expense
        from apps.expenses.service import format_paise

        text = Q(note__icontains=query) | Q(category_other__icontains=query) | Q(paid_by__username__icontains=query) | Q(
            paid_by__first_name__icontains=query
        ) | Q(paid_by__last_name__icontains=query)
        # "tea", "ai subscription", "server rent": match the category's own name too.
        text |= Q(category__in=[v for v, label in Expense.Category.choices if query.lower() in label.lower()])
        digits = query.replace(",", "").replace("₹", "").strip()
        if digits.replace(".", "", 1).isdigit():
            text |= Q(amount_paise=int(round(float(digits) * 100)))
        for e in Expense.objects.filter(company=company).filter(text).select_related("paid_by").order_by("-date", "-id")[: LIMITS["expenses"]]:
            expense_items.append({
                "title": f"{e.category_label} · {format_paise(e.amount_paise)}",
                "subtitle": f"Expense · {e.paid_by.get_full_name() or e.paid_by.username} paid · {e.date:%b %d}",
                "url": reverse("expenses:expense_edit", args=[e.pk]),
            })
        for c in (
            AttendanceCorrection.objects.filter(company=company)
            .filter(Q(reason__icontains=query) | Q(user__username__icontains=query) | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query))
            .select_related("user")
            .order_by("-date")[: LIMITS["corrections"]]
        ):
            correction_items.append({
                "title": f"{c.user.get_full_name() or c.user.username} · {c.date:%b %d}",
                "subtitle": f"Correction · {c.get_status_display()} · {c.reason[:60]}",
                "url": reverse("attendance:corrections"),
            })

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

    for name, label, items in (
        ("tickets", "Tickets", ticket_items),
        ("errors", "Errors", error_items),
        ("products", "Products", product_items),
        ("people", "People", people_items),
        ("feedback", "Feedback", feedback_items),
        ("surveys", "Surveys", survey_items),
        ("rules", "Automation", rule_items),
        ("dsr", "My DSR", dsr_items),
        ("leave", "My leave", leave_items),
        ("expenses", "Expenses", expense_items),
        ("corrections", "Corrections", correction_items),
        ("log", "Project updates", log_items),
        ("notifications", "Notifications", notification_items),
        ("pages", "Go to", pages),
    ):
        # With only filters typed (no words), listing every product or survey
        # would be noise; tickets and errors are the groups a filter makes sense for.
        if not wanted(name) or (not query and name not in ("tickets", "errors")):
            continue
        if items:
            groups.append({"label": label, "items": items})
    return groups


class SearchView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"groups": search(request, request.GET.get("q", ""))})
