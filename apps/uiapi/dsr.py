from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.dsr import service
from apps.dsr.duration import format_hm
from apps.dsr.models import DSREntry
from apps.products.access import accessible_products, accessible_tickets
from apps.uiapi.tickets import form_errors
from apps.uiapi.views import CompanyAPIView

User = get_user_model()
GOAL = Decimal("8.0")


def _day(raw, default):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


def _name(u):
    return u.get_full_name() or u.username


def _privileged(request):
    return request.company_role in ("owner", "admin")


def _target(request):
    """Whose sheet: the signed-in person's, or (owners and admins only) a member's."""
    raw = request.query_params.get("user_id") or (request.data.get("user_id") if hasattr(request.data, "get") else None)
    if raw and _privileged(request):
        if not str(raw).isdecimal():
            from django.http import Http404

            raise Http404
        return get_object_or_404(User, pk=int(raw), memberships__company=request.company)
    return request.user


def entry_json(e):
    return {
        "id": e.pk, "task_name": e.task_name, "category": e.category, "category_label": e.get_category_display(),
        "status": e.status, "status_label": e.get_status_display(), "hours": format_hm(e.hours_spent),
        "hours_value": str(e.hours_spent), "notes": e.notes, "auto": e.is_auto_logged,
        "source": e.source, "source_id": e.source_id,
        "product": {"id": e.product_id, "name": e.product.name} if e.product_id else None,
        "ticket": {"id": e.ticket_id, "key": e.ticket.key,
                   "url": f"/products/{e.ticket.product_id}/tickets/{e.ticket_id}/" if e.ticket.product_id else f"/tickets/{e.ticket_id}/"} if e.ticket_id else None,
    }


def sheet_json(request, target, day, **extra):
    company = request.company
    privileged = _privileged(request)
    today = timezone.localdate()
    can_submit, locked = service.submission_window(day, privileged)
    entries = list(DSREntry.objects.filter(company=company, user=target, date=day).select_related("product", "ticket", "ticket__product"))
    total = sum((e.hours_spent for e in entries), Decimal("0.00"))
    completed = sum(1 for e in entries if e.status == "completed")
    lines = [
        f"📅 DSR: {_name(target)} — {day.strftime('%b %d, %Y')}",
        f"⏱ Total Time: {format_hm(total)} | Tasks Completed: {completed}",
        "--------------------------------------------------",
    ]
    for i, e in enumerate(entries, 1):
        where = f"[{e.product.name}] " if e.product and f"[{e.product.name}]" not in e.task_name else ""
        lines.append(f"{i}. {'[AUTO] ' if e.is_auto_logged else ''}{where}{e.task_name} ({e.get_category_display()}) - {format_hm(e.hours_spent)} [{e.get_status_display()}]")
        if e.notes:
            lines.append(f"   Note: {e.notes}")
    if not entries:
        lines.append("No tasks recorded for this date.")

    ticket_suggestions, work = [], []
    if can_submit:
        for t in (
            accessible_tickets(target, company).select_related("product")
            .filter(assignees=target, status__in=["open", "assigned", "in_progress", "testing"]).order_by("-id")[:6]
        ):
            ticket_suggestions.append({"id": t.pk, "key": t.key, "title": t.title, "label": f"{t.key} {t.title}"[:255]})
        work = [
            {"number": r["number"], "key": r["key"], "title": r["title"], "product": r["product"], "did": r["did"],
             "touched": r["touched"], "hours": format_hm(r["hours"]), "hours_value": str(r["hours"])}
            for r in service.suggestions(company, target, day)
        ]
    overview = []
    members = []
    if privileged:
        for m in User.objects.filter(memberships__company=company).order_by("username"):
            rows = DSREntry.objects.filter(company=company, user=m, date=day)
            raw = rows.aggregate(total=Sum("hours_spent"))["total"] or Decimal("0.00")
            members.append({"id": m.pk, "name": _name(m)})
            overview.append({
                "id": m.pk, "name": _name(m), "username": m.username, "hours": format_hm(raw) if raw else "0m",
                "progress": min(100, int(raw / GOAL * 100)), "completed": rows.filter(status="completed").count(), "entries": rows.count(),
            })
    return {
        "date": day.isoformat(), "today": today.isoformat(), "yesterday": (today - timedelta(days=1)).isoformat(),
        "prev": (day - timedelta(days=1)).isoformat(), "next": min(day + timedelta(days=1), today).isoformat(),
        "can_submit": can_submit, "locked_reason": locked,
        "target": {"id": target.pk, "name": _name(target), "is_me": target.pk == request.user.pk},
        "is_privileged": privileged,
        "entries": [entry_json(e) for e in entries],
        "total": format_hm(total) if total else "0m", "progress": min(100, int(total / GOAL * 100)),
        "completed": completed, "auto_logged": sum(1 for e in entries if e.is_auto_logged),
        "summary_text": "\n".join(lines), "ticket_suggestions": ticket_suggestions, "work_suggestions": work,
        "products": [{"id": p.pk, "name": p.name} for p in accessible_products(target, company).order_by("name")],
        "categories": [list(c) for c in DSREntry.Category.choices], "statuses": [list(c) for c in DSREntry.Status.choices],
        "members": members, "team_overview": overview,
        **extra,
    }


def _window(request, day):
    ok, reason = service.submission_window(day, _privileged(request))
    if not ok:
        raise PermissionDenied(reason)


def _entry(request, pk):
    entry = get_object_or_404(DSREntry.objects.select_related("user"), pk=pk, company=request.company)
    if entry.user_id != request.user.pk and not _privileged(request):
        raise PermissionDenied("Permission denied")
    return entry


class DsrSheetAPIView(CompanyAPIView):
    def get(self, request):
        day = _day(request.query_params.get("date"), timezone.localdate())
        return Response(sheet_json(request, _target(request), day))


class DsrEntriesAPIView(CompanyAPIView):
    def post(self, request):
        today = timezone.localdate()
        day = _day(request.query_params.get("date") or request.data.get("date"), today)
        target = _target(request)
        _window(request, day)
        products = accessible_products(target, request.company).order_by("name")
        entry, form = service.add_entry(request.company, request.user, target, day, request.data, products)
        if entry is None:
            return Response(form_errors(form), status=400)
        return Response(sheet_json(request, target, day, message=f'Added "{entry.task_name}".'), status=201)


class DsrEntryAPIView(CompanyAPIView):
    def patch(self, request, pk):
        entry = _entry(request, pk)
        _window(request, entry.date)
        products = accessible_products(entry.user, request.company)
        saved, form = service.update_entry(request.company, request.user, entry, request.data, products)
        if saved is None:
            return Response(form_errors(form), status=400)
        return Response(sheet_json(request, entry.user, entry.date))

    def delete(self, request, pk):
        entry = _entry(request, pk)
        _window(request, entry.date)
        day, owner = entry.date, entry.user
        name = service.delete_entry(request.company, request.user, entry)
        return Response(sheet_json(request, owner, day, message=f'Deleted "{name}".'))


class DsrSuggestionAPIView(CompanyAPIView):
    def post(self, request):
        day = _day(request.query_params.get("date") or request.data.get("date"), timezone.localdate())
        target = _target(request)
        _window(request, day)
        entry, message = service.add_suggested(request.company, request.user, target, day, request.data.get("ticket_id"), request.data.get("hours"))
        if entry is None:
            return Response({"detail": message}, status=400)
        return Response(sheet_json(request, target, day, message=message), status=201)
