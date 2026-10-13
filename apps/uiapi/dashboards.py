from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.templatetags.event_tags import event_pill, event_url
from apps.dashboards import quotes
from apps.uiapi import kudos
from apps.dashboards import todos as todo_service
from apps.dashboards.models import ActivityLog, Todo
from apps.dashboards.service import (
    get_personal_dashboard_data,
    get_product_dashboard_data,
    get_summary_report,
)
from apps.products.access import require_product_access
from apps.products.models import Product
from apps.uiapi.views import CompanyAPIView

User = get_user_model()
PER_PAGE = 25


def _day(value, default):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


def _hours(minutes):
    if not minutes:
        return "0"
    value = int(minutes) / 60
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def _days(value):
    number = float(value or 0)
    return str(int(number)) if number == int(number) else f"{number:g}"


def _name(u):
    return u.get_full_name() or u.username


def _ticket_url(t):
    return f"/products/{t.product_id}/tickets/{t.pk}/" if t.product_id else f"/tickets/{t.pk}/"


def event_json(e):
    return {
        "id": e.pk,
        "type": e.event_type,
        "label": e.get_event_type_display(),
        "pill": event_pill(e.event_type),
        "title": e.title,
        "description": e.description,
        "created_at": e.created_at.isoformat(),
        "url": event_url(e) or "",
        "actor": {"name": _name(e.actor), "initial": (e.actor.username[:1] or "?").upper()} if e.actor_id else None,
    }


def todos_json(user):
    todos = todo_service.sorted_todos(user)
    today = timezone.localdate()
    return {
        "todos": [
            {
                "id": t.pk, "text": t.text, "priority": t.priority, "priority_label": t.get_priority_display(),
                "done": t.done, "due": t.due.isoformat() if t.due else None,
                "late": bool(t.due and t.due < today and not t.done), "today": bool(t.due and t.due == today and not t.done),
            }
            for t in todos
        ],
        "total": len(todos),
        "done": sum(t.done for t in todos),
        "priorities": [[str(v), label] for v, label in Todo.Priority.choices],
    }


class HomeAPIView(CompanyAPIView):
    def get(self, request):
        d = get_personal_dashboard_data(request.user, request.company)
        todo_service.notify_overdue(request.user, request.company)
        att = d["attendance"]
        rec = att["record"]
        today = d["today"]
        if att["on_leave_today"]:
            state = "leave"
        elif rec and rec.is_open:
            state = "open"
        elif rec:
            state = "done"
        elif today.weekday() >= 5:
            state = "weekend"
        else:
            state = "todo"
        slip = d["payroll"]["payslip"]
        payroll = {
            "on_payroll": d["payroll"]["on_payroll"], "has_profile": d["payroll"]["has_profile"],
            "monthly_salary": f"{float(d['payroll']['monthly_salary']):,.2f}" if d["payroll"]["monthly_salary"] is not None else None,
            "payslip": {
                "id": slip.pk, "run_label": slip.run.label, "currency": slip.currency, "gross": f"{float(slip.gross):,.2f}",
                "deduction": f"{float(slip.deduction):,.2f}", "unpaid_leave_days": _days(slip.unpaid_leave_days),
                "url": reverse("payroll:my_payslip", kwargs={"pk": slip.pk}),
            } if slip else None,
        }
        balances = []
        for b in d["leave_balances"]:
            used = 0 if b["is_unlimited"] or not b["limit"] else min(100, round(float(b["approved"]) * 100 / float(b["limit"])))
            balances.append({
                "name": b["policy"].name, "unlimited": b["is_unlimited"], "approved_label": b["approved_label"],
                "remaining_label": b["remaining_label"], "used_pct": used, "has_pending": b["has_pending"], "pending_label": b["pending_label"],
            })
        team = d.get("team")
        return Response({
            "first_name": request.user.first_name,
            "company": request.company.name,
            "quote": quotes.pick(seed=today.toordinal() + request.user.pk),
            "server_greeting": "Good morning" if timezone.localtime().hour < 12 else "Good afternoon" if timezone.localtime().hour < 18 else "Good evening",
            "on_leave_today": att["on_leave_today"],
            "dsr_nudge": d["dsr_nudge"],
            "kpis": {"my_tickets": d["my_ticket_count"], "overdue": d["overdue_count"], "todos_left": d["todo_open"],
                     "week_total": d["chart_week_total"], "week_target": d["chart_week_target"]},
            "streak": kudos.on_time_streak(request.company, request.user),
            "milestones": kudos.milestones(request.company, request.user),
            "attendance": {
                "state": state,
                "check_in": rec.check_in.isoformat() if rec and rec.check_in else None,
                "check_out": rec.check_out.isoformat() if rec and rec.check_out else None,
                "worked_hours": f"{rec.worked_hours:.1f}" if rec and rec.check_out else None,
                "present_days": att["present_days"], "worked_label": _hours(att["worked_minutes"]), "month_label": att["month_label"],
            },
            "needs_attention": {
                "leave_to_approve": d.get("leave_approval_count", 0),
                "open_errors": team["open_errors"], "open_tickets": team["open_tickets"],
            } if team is not None else None,
            "week": d["chart_week"],
            "status": {"total": d["chart_status_total"], "items": d["chart_status"]},
            "errors": {"total": d["chart_errors_total"], "items": d["chart_errors"]},
            "payroll": payroll,
            "leave": {
                "balances": balances,
                "requests": [
                    {"id": r.pk, "start": r.start_date.isoformat(), "end": r.end_date.isoformat(), "policy": r.policy.name,
                     "days": _days(r.days), "status": r.status}
                    for r in d["my_leave_requests"][:2]
                ],
            },
            "dsr": {
                "week_start": d["dsr"]["dsr_week_start"].isoformat(), "hours": f"{float(d['dsr']['dsr_hours']):.1f}",
                "entries": d["dsr"]["dsr_entries"], "open_count": d["dsr"]["dsr_open_count"],
                "open": [{"id": e.pk, "task": e.task_name, "status": e.get_status_display(), "date": e.date.isoformat()} for e in d["dsr"]["dsr_open"]],
            },
            "due_soon": [
                {"id": t.pk, "key": t.key, "title": t.title, "overdue": t.is_overdue,
                 "deadline": t.deadline.isoformat() if t.deadline else None, "url": _ticket_url(t)}
                for t in d["due_soon"]
            ],
            "my_tickets": [
                {"id": t.pk, "title": t.title, "product": t.product.name if t.product_id else "", "status": t.get_status_display(), "url": _ticket_url(t)}
                for t in d["my_tickets"][:3]
            ],
            "activity": [{"id": a.pk, "title": a.title, "created_at": a.created_at.isoformat()} for a in d["my_activity"]],
        })


class QuoteAPIView(CompanyAPIView):
    def get(self, request):
        return Response({"quote": quotes.pick(exclude=request.query_params.get("current", ""))})


class PunchAPIView(CompanyAPIView):
    """Punch in or out from the home page; the same rules, log and receipt as the attendance page."""

    def post(self, request):
        from apps.attendance import service as attendance

        _, action, message = attendance.punch_user(request.company, request.user, (request.data.get("notes") or ""))
        return Response({"action": action, "message": message, "ok": action in ("checked_in", "checked_out")})


class TodoListAPIView(CompanyAPIView):
    def get(self, request):
        return Response(todos_json(request.user))

    def post(self, request):
        text = str(request.data.get("text") or "").strip()[:300]
        if not text:
            return Response({"detail": "To-do text can't be empty."}, status=400)
        priority = str(request.data.get("priority") or "")
        Todo.objects.create(
            user=request.user, company=request.company, text=text,
            due=_day(request.data.get("due"), None),
            priority=int(priority) if priority in ("1", "2", "3") else Todo.Priority.MEDIUM,
        )
        return Response({**todos_json(request.user), "message": f'Added "{text}".'}, status=201)


class TodoToggleAPIView(CompanyAPIView):
    def post(self, request, pk):
        todo = get_object_or_404(Todo, pk=pk, user=request.user)
        todo.done = not todo.done
        todo.completed_at = timezone.now() if todo.done else None
        todo.save(update_fields=["done", "completed_at"])
        todo_service.sync_dsr(todo, request.company)
        return Response({**todos_json(request.user), "message": f'Marked "{todo.text}" done.' if todo.done else f'Reopened "{todo.text}".'})


class TodoDeleteAPIView(CompanyAPIView):
    def delete(self, request, pk):
        todo = get_object_or_404(Todo, pk=pk, user=request.user)
        text = todo.text
        todo.delete()
        return Response({**todos_json(request.user), "message": f'Deleted "{text}".'})


class TodoClearDoneAPIView(CompanyAPIView):
    def post(self, request):
        removed, _ = Todo.objects.filter(user=request.user, done=True).delete()
        msg = f"Cleared {removed} completed to-do{'s' if removed != 1 else ''}." if removed else ""
        return Response({**todos_json(request.user), "message": msg})


class ProductDashboardAPIView(CompanyAPIView):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request._request, product)
        d = get_product_dashboard_data(request.company, product)
        return Response({
            "product": {"id": product.pk, "name": product.name},
            "errors": {"total": d["total_errors"], "open": d["open_errors"], "resolved": d["resolved_errors"]},
            "tickets": {"total": d["total_tickets"], "open": d["open_tickets"]},
            "survey": {"avg_score": d["avg_score"], "responses": d["total_responses"], "count": d["survey_count"]},
            "uptime": d["uptime_percentage"],
            "errors_by_day": d["errors_by_day"],
            "ticket_burndown": d["ticket_burndown"],
            "errors_by_severity": d["errors_by_severity"],
            "tickets_by_status": d["tickets_by_status"],
        })


class ReportAPIView(CompanyAPIView):
    def get(self, request):
        today = timezone.localdate()
        start = _day(request.query_params.get("start_date"), today)
        end = _day(request.query_params.get("end_date"), today)
        if start > end:
            start, end = end, start
        d = get_summary_report(request.company, start, end, user=request.user)
        return Response({
            "scope": d["scope"], "start_date": start.isoformat(), "end_date": end.isoformat(),
            "presets": [
                {"label": label, "start": s.isoformat(), "end": e.isoformat()}
                for label, s, e in [
                    ("Today", today, today), ("Yesterday", today - timedelta(days=1), today - timedelta(days=1)),
                    ("Last 7 days", today - timedelta(days=6), today), ("Last 30 days", today - timedelta(days=29), today),
                    ("This month", today.replace(day=1), today),
                ]
            ],
            "total_events": d["total_events"],
            "kpis": d["kpis"],
            "daily_bars": [
                {"date": b["date"].isoformat(), "label": b["label"], "created": b["created"], "resolved": b["resolved"],
                 "captured": b["captured"], "fixed": b["fixed"], "row": {k: v for k, v in b["row"].items() if k != "date"}}
                for b in d["daily_bars"]
            ],
            "resolution_rate": d["resolution_rate"], "error_fix_rate": d["error_fix_rate"],
            "tickets": {"created": d["tickets_created"], "resolved": d["tickets_resolved"], "in_progress": d["tickets_in_progress"], "assigned": d["tickets_assigned"]},
            "errors": {"captured": d["errors_captured"], "resolved": d["errors_resolved"], "ignored": d["errors_ignored"]},
            "feedback_received": d["feedback_received"], "survey_responses": d["survey_responses"],
            "product_bars": [{"name": r["product"].name, "total": r["total"], "pct": r["pct"]} for r in d["product_bars"]],
            "event_mix": d["event_mix"],
            "product_rows": [{**{k: v for k, v in r.items() if k != "product"}, "name": r["product"].name} for r in d["product_rows"]],
            "daily": [{**r, "date": r["date"].isoformat()} for r in d["daily"]],
            "recent": [event_json(e) for e in d["recent"]],
        })


class AuditLogAPIView(CompanyAPIView):
    def get(self, request):
        if request.company_role not in ("owner", "admin"):
            raise PermissionDenied("Only owners and admins can read the audit log.")
        q = request.query_params
        qs = ActivityLog.objects.filter(company=request.company).select_related("actor")
        if q.get("type"):
            qs = qs.filter(event_type=q["type"])
        if q.get("actor", "").isdecimal():
            qs = qs.filter(actor_id=int(q["actor"]))
        if _day(q.get("from"), None):
            qs = qs.filter(created_at__date__gte=_day(q["from"], None))
        if _day(q.get("to"), None):
            qs = qs.filter(created_at__date__lte=_day(q["to"], None))
        if q.get("q", "").strip():
            s = q["q"].strip()
            qs = qs.filter(Q(title__icontains=s) | Q(description__icontains=s))
        page = Paginator(qs, PER_PAGE).get_page(q.get("page", 1))
        members = User.objects.filter(memberships__company=request.company).order_by("username")
        return Response({
            "items": [event_json(e) for e in page],
            "page": {"number": page.number, "num_pages": page.paginator.num_pages, "count": page.paginator.count, "per_page": PER_PAGE},
            "event_types": [list(c) for c in ActivityLog.EventType.choices],
            "members": [{"id": u.pk, "name": _name(u)} for u in members],
        })
