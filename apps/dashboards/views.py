from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from apps.core.pagination import paginate
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards import quotes, todos as todo_service
from apps.dashboards.models import ActivityLog, Todo
from apps.dashboards.service import (
    get_personal_dashboard_data,
    get_product_dashboard_data,
    get_summary_report,
)
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
        data = get_personal_dashboard_data(request.user, request.company)
        todo_service.notify_overdue(request.user, request.company)
        hour = timezone.localtime().hour
        from apps.core import kudos

        from apps.dsr.views import _today_work

        todos = todo_service.sorted_todos(request.user)
        data["todos"] = todos
        data["todo_total"] = len(todos)
        data["todo_done"] = sum(t.done for t in todos)
        data["priority_choices"] = [(str(v), label) for v, label in Todo.Priority.choices]

        data["dsr_today"] = _today_work(request.company, request.user, timezone.localdate())
        data["now"] = timezone.localtime()
        data["streak"] = kudos.on_time_streak(request.company, request.user)
        data["milestones"] = kudos.milestones(request.company, request.user)
        data["greeting"] = (
            "Good morning" if hour < 12
            else "Good afternoon" if hour < 18
            else "Good evening"
        )

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_dashboard_content.html", data)

        # Same line all day for one person, so a reload does not reshuffle it.
        from apps.dashboards import greetings

        data["greetings"] = greetings.as_json_data()
        data["quote"] = quotes.pick(seed=timezone.localdate().toordinal() + request.user.pk)
        return render(request, "dashboards/dashboard.html", data)


class QuoteView(CompanyMemberRequiredMixin, View):
    """"Another one": swaps just the quote, without reloading the page."""

    def get(self, request):
        return render(request, "dashboards/partials/_quote.html", {
            "quote": quotes.pick(exclude=request.GET.get("current", "")),
        })


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
        base_qs = ActivityLog.objects.filter(company=request.company)
        qs = base_qs.select_related("actor")

        category = request.GET.get("category", "").strip().lower()
        if category == "security":
            qs = qs.filter(event_type__in=[
                "member_joined", "member_removed", "member_role_changed",
                "api_key_created", "api_key_revoked", "access_granted", "access_revoked",
            ])
        elif category == "issues":
            qs = qs.filter(Q(event_type__startswith="ticket_") | Q(event_type__startswith="error_") | Q(event_type="auto_ticket"))
        elif category == "finance":
            qs = qs.filter(Q(event_type__startswith="payroll_") | Q(event_type__startswith="expense_") | Q(event_type__startswith="holiday_"))
        elif category == "attendance":
            qs = qs.filter(Q(event_type__startswith="attendance_") | Q(event_type__startswith="leave_") | Q(event_type="weekly_off_changed"))
        elif category == "system":
            qs = qs.filter(Q(event_type__startswith="product_") | Q(event_type__startswith="version_") | Q(event_type__startswith="rule_") | Q(event_type__startswith="survey_") | Q(event_type__startswith="project_") | Q(event_type="feedback_received"))

        event_type = request.GET.get("type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        actor_id = request.GET.get("actor")
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        preset = request.GET.get("preset", "").strip().lower()
        today = timezone.localdate()
        date_from = request.GET.get("from")
        date_to = request.GET.get("to")

        if preset == "today":
            date_from = today.isoformat()
            date_to = today.isoformat()
        elif preset == "7d":
            date_from = (today - timedelta(days=7)).isoformat()
            date_to = today.isoformat()
        elif preset == "30d":
            date_from = (today - timedelta(days=30)).isoformat()
            date_to = today.isoformat()

        if date_from:
            d = _parse_date(date_from, None)
            if d:
                qs = qs.filter(created_at__date__gte=d)

        if date_to:
            d = _parse_date(date_to, None)
            if d:
                qs = qs.filter(created_at__date__lte=d)

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

        # Overall summary metrics for the workspace
        total_events = base_qs.count()
        today_events = base_qs.filter(created_at__date=today).count()
        active_actors = base_qs.exclude(actor=None).values("actor").distinct().count()
        security_events = base_qs.filter(event_type__in=[
            "member_joined", "member_removed", "member_role_changed",
            "api_key_created", "api_key_revoked", "access_granted", "access_revoked",
        ]).count()

        page = paginate(request, qs)

        members = User.objects.filter(memberships__company=request.company).order_by("username")
        event_types = ActivityLog.EventType.choices

        context = {
            "page": page,
            "members": members,
            "event_types": event_types,
            "current_type": event_type,
            "current_actor": actor_id,
            "current_from": date_from,
            "current_to": date_to,
            "current_category": category,
            "current_preset": preset,
            "search": search,
            "stats": {
                "total": total_events,
                "today": today_events,
                "actors": active_actors,
                "security": security_events,
            },
        }

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_audit_log_rows.html", context)

        return render(request, "dashboards/audit_log.html", context)


class ReportsView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        start_date = _parse_date(request.GET.get("start_date"), today)
        end_date = _parse_date(request.GET.get("end_date"), today)
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        data = get_summary_report(request.company, start_date, end_date, user=request.user)
        data.update({
            "today": today,
            "yesterday": today - timedelta(days=1),
            "week_ago": today - timedelta(days=6),
            "presets": [
                ("Today", today, today),
                ("Yesterday", today - timedelta(days=1), today - timedelta(days=1)),
                ("Last 7 days", today - timedelta(days=6), today),
                ("Last 30 days", today - timedelta(days=29), today),
                ("This month", today.replace(day=1), today),
            ],
        })

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_report_content.html", data)

        return render(request, "dashboards/reports.html", data)


class TodoMixin(CompanyMemberRequiredMixin):
    def render_list(self, request):
        todos = todo_service.sorted_todos(request.user)
        ctx = {
            "todos": todos,
            "todo_total": len(todos),
            "todo_done": sum(t.done for t in todos),
            "today": timezone.localdate(),
            "priority_choices": [(str(v), label) for v, label in Todo.Priority.choices],
        }
        return render(request, "dashboards/partials/_todos.html", ctx)


class TodoListView(TodoMixin, View):
    def get(self, request):
        if request.headers.get("HX-Request") != "true":
            if "text/html" in request.headers.get("Accept", "") or request.headers.get("Sec-Fetch-Mode") == "navigate":
                return redirect("dashboards:index")
        return self.render_list(request)

    def post(self, request):
        text = request.POST.get("text", "").strip()[:300]
        if text:
            priority = request.POST.get("priority")
            Todo.objects.create(
                user=request.user, company=request.company, text=text,
                due=_parse_date(request.POST.get("due"), None),
                priority=int(priority) if priority in ("1", "2", "3") else Todo.Priority.MEDIUM,
            )
            messages.success(request, f'Added "{text}".')
        else:
            messages.error(request, "To-do text can't be empty.")
        return self.render_list(request)


class TodoToggleView(TodoMixin, View):
    def post(self, request, pk):
        todo = get_object_or_404(Todo, pk=pk, user=request.user)
        todo.done = not todo.done
        todo.completed_at = timezone.now() if todo.done else None

        hours_raw = request.POST.get("hours", "").strip()
        if todo.done and hours_raw:
            from apps.dsr.duration import parse_hours
            parsed = parse_hours(hours_raw)
            if parsed is not None and parsed >= 0:
                todo.hours_spent = parsed
        elif not todo.done:
            todo.hours_spent = None

        todo.save(update_fields=["done", "completed_at", "hours_spent"])
        todo_service.sync_dsr(todo, request.company, hours=todo.hours_spent)
        time_msg = f" ({todo.hours_display} logged to DSR)" if (todo.done and todo.hours_spent) else ""
        messages.success(
            request,
            f'Marked "{todo.text}" done{time_msg}.' if todo.done else f'Reopened "{todo.text}".',
        )
        return self.render_list(request)


class TodoDeleteView(TodoMixin, View):
    def post(self, request, pk):
        todo = get_object_or_404(Todo, pk=pk, user=request.user)
        text = todo.text
        todo.delete()
        messages.success(request, f'Deleted "{text}".')
        return self.render_list(request)


class TodoClearDoneView(TodoMixin, View):
    def post(self, request):
        removed, _ = Todo.objects.filter(user=request.user, done=True).delete()
        if removed:
            messages.success(
                request,
                f"Cleared {removed} completed to-do{'s' if removed != 1 else ''}.",
            )
        return self.render_list(request)
