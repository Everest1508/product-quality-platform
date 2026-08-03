from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.models import ActivityLog
from apps.dashboards.service import get_product_dashboard_data, get_summary_report, get_user_dashboard_data
from apps.products.access import require_product_access
from apps.products.models import Product

User = get_user_model()


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default


class DashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        data = get_user_dashboard_data(request.user, request.company)

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_dashboard_content.html", data)

        return render(request, "dashboards/dashboard.html", data)


class ProductDashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request, product_pk):
        product = get_object_or_404(
            Product.objects.select_related("company"),
            pk=product_pk,
            company=request.company,
        )
        require_product_access(request, product)
        data = get_product_dashboard_data(request.company, product)

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_product_dashboard_content.html", data)

        return render(request, "dashboards/product_dashboard.html", data)


class AuditLogView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        qs = ActivityLog.objects.filter(company=request.company).select_related("actor")

        event_type = request.GET.get("type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        actor_id = request.GET.get("actor")
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        date_from = request.GET.get("from")
        if date_from:
            d = _parse_date(date_from, None)
            if d:
                qs = qs.filter(created_at__date__gte=d)

        date_to = request.GET.get("to")
        if date_to:
            d = _parse_date(date_to, None)
            if d:
                qs = qs.filter(created_at__date__lte=d)

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        members = User.objects.filter(memberships__company=request.company).order_by("username")
        event_types = ActivityLog.EventType.choices

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_audit_log_rows.html", {"page": page})

        return render(request, "dashboards/audit_log.html", {
            "page": page,
            "members": members,
            "event_types": event_types,
            "current_type": event_type,
            "current_actor": actor_id,
            "current_from": date_from,
            "current_to": date_to,
            "search": search,
        })


class ReportsView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        start_date = _parse_date(request.GET.get("start_date"), today)
        end_date = _parse_date(request.GET.get("end_date"), today)
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        data = get_summary_report(request.company, start_date, end_date)
        data.update({
            "today": today,
            "yesterday": today - timedelta(days=1),
            "week_ago": today - timedelta(days=6),
        })

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_report_content.html", data)

        return render(request, "dashboards/reports.html", data)
