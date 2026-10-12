from django.conf import settings
from django.contrib import messages as dj_messages
from django.middleware.csrf import get_token
from django.urls import reverse
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Membership
from apps.core.context_processors import nav_counts
from apps.notifications import service

LIMIT = 100


class CompanyAPIView(APIView):
    """Session-cookie JSON view. CSRF is enforced on writes by SessionAuthentication.
    Every subclass works on `request.company`, set by CurrentCompanyMiddleware."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.company:
            raise PermissionDenied("No active company.")


class NotificationListView(CompanyAPIView):
    def get(self, request):
        rows = service.mine(request.user, request.company)
        if request.query_params.get("filter") == "unread":
            rows = rows.filter(read_at__isnull=True)
        items = [{**n.as_json(), "kind_label": n.get_kind_display()} for n in rows[:LIMIT]]
        return Response({"unread": service.unread_count(request.user, request.company), "items": items})


class NotificationReadAllView(CompanyAPIView):
    def post(self, request):
        service.mark_read(request.user, request.company)
        return Response({"unread": 0})


_TAGS = {"success", "error", "info", "warning"}

_URL_NAMES = {
    "home": "dashboards:index", "products": "products:product_list", "tickets": "tickets:ticket_board",
    "errors": "errors:error_list", "reports": "dashboards:reports", "automation": "automation:rule_list",
    "cs_hub": "feedback:cs_hub", "feedback": "feedback:survey_list", "attendance": "attendance:my_attendance",
    "leave": "leave:my_leave", "leave_calendar": "leave:calendar", "dsr": "dsr:dsr_sheet",
    "payslips": "payroll:my_payslips", "team_attendance": "attendance:team_attendance",
    "timesheet": "attendance:timesheet", "corrections": "attendance:corrections",
    "leave_approvals": "leave:approvals", "payroll": "payroll:run_list", "payroll_setup": "payroll:profiles",
    "leave_policies": "leave:policies", "team": "accounts:team_list", "audit_log": "dashboards:audit_log",
    "profile": "accounts:profile", "logout": "accounts:logout", "notifications": "notifications:list",
    "ticket_create": "tickets:ticket_create", "leave_apply": "leave:apply",
    "correction_request": "attendance:correction_request", "product_create": "products:product_create",
    "bootstrap": "uiapi:bootstrap",
}


class BootstrapView(CompanyAPIView):
    """Everything the shell needs on first paint. Flash messages queued by a
    legacy view are returned once and cleared (iterating the queue marks them used)."""

    def get(self, request):
        user, company, role = request.user, request.company, request.company_role
        memberships = Membership.objects.filter(user=user).select_related("company").order_by("company__name")
        flash = [
            {"text": str(m.message), "tags": m.level_tag if m.level_tag in _TAGS else "info"}
            for m in dj_messages.get_messages(request._request)
        ]
        urls = {key: reverse(name) for key, name in _URL_NAMES.items()}
        urls["search"] = "/search/"
        urls["changelog"] = "/api/v1/changelog/"
        name = user.get_full_name() or user.username
        return Response({
            "user": {
                "id": user.pk, "name": name, "initial": name[:1].upper(), "role": role,
                "role_label": dict(Membership.Role.choices).get(role, role or "Member"),
            },
            "company": {"id": company.pk, "name": company.name},
            "workspaces": [
                {"company_id": m.company_id, "name": m.company.name, "role_label": m.get_role_display(),
                 "current": m.company_id == company.pk}
                for m in memberships
            ],
            "counts": nav_counts(user, company, role),
            "is_admin": role in ("owner", "admin"),
            "version": getattr(settings, "APP_VERSION", "0.0.0"),
            "csrf": get_token(request._request),
            "messages": flash,
            "urls": urls,
        })
