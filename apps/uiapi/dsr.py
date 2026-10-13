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


def _moment(value, day):
    """A local clock time, with the date in front when it is not the entry's own day ("2 Oct 09:15")."""
    if not value:
        return ""
    local = timezone.localtime(value)
    return local.strftime("%H:%M") if local.date() == day else local.strftime("%-d %b %H:%M")


def entry_json(e):
    return {
        "id": e.pk, "task_name": e.task_name, "category": e.category, "category_label": e.get_category_display(),
        "status": e.status, "status_label": e.get_status_display(), "hours": format_hm(e.hours_spent),
        "hours_value": str(e.hours_spent), "notes": e.notes, "auto": e.is_auto_logged,
        "source": e.source, "source_id": e.source_id,
        "from_time": _moment(e.created_time, e.date),
        "to_time": _moment(e.completed_time, e.date),
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


class DsrLogAPIView(CompanyAPIView):
    """Submitted work over a date range as one list: today and history in the same table.

    `range` is today, yesterday, 7d (default) or 30d, or pass `from` and `to` (at most 92 days). Owners and admins can
    pass `user_id=all` for everyone or one member's id; everybody else only ever sees their own rows."""

    MAX_DAYS = 92
    MAX_ROWS = 500

    def get(self, request):
        today = timezone.localdate()
        params = request.query_params
        rng = params.get("range", "7d")
        start, end = {"today": (today, today), "yesterday": (today - timedelta(days=1),) * 2, "30d": (today - timedelta(days=29), today)}.get(rng, (today - timedelta(days=6), today))
        first, last = _day(params.get("from"), None), _day(params.get("to"), None)
        if first and last:
            start, end = sorted((first, last))
            start = max(start, end - timedelta(days=self.MAX_DAYS - 1))
            rng = "custom"
        end = min(end, today)
        privileged = _privileged(request)
        who = params.get("user_id", "")
        everyone = privileged and who == "all"
        target = request.user if everyone else _target(request)

        qs = DSREntry.objects.filter(company=request.company, date__gte=start, date__lte=end).select_related("user", "product", "ticket", "ticket__product")
        if not everyone:
            qs = qs.filter(user=target)
        q = (params.get("q") or "").strip()
        if q:
            from django.db.models import Q

            qs = qs.filter(Q(task_name__icontains=q) | Q(notes__icontains=q) | Q(product__name__icontains=q))
        entries = list(qs.order_by("-date", "user__username", "-created_at")[: self.MAX_ROWS])

        days, rows, lines = {}, [], []
        for e in entries:
            editable = (e.user_id == request.user.pk or privileged) and service.submission_window(e.date, privileged)[0]
            d = days.setdefault(e.date, {"date": e.date.isoformat(), "label": e.date.strftime("%a, %-d %b"), "hours": Decimal("0.00"), "count": 0, "completed": 0})
            d["hours"] += e.hours_spent
            d["count"] += 1
            d["completed"] += e.status == "completed"
            rows.append({
                **entry_json(e), "date": e.date.isoformat(), "editable": editable,
                "person": {"id": e.user_id, "name": _name(e.user), "username": e.user.username, "is_me": e.user_id == request.user.pk},
            })
        total = sum((d["hours"] for d in days.values()), Decimal("0.00"))
        for d in days.values():
            lines.append(f"📅 {d['label']}: {format_hm(d['hours'])}, {d['count']} task{'s' if d['count'] != 1 else ''}")
        for e in entries:
            lines.append(f"- {e.date.strftime('%-d %b')} {_name(e.user) + ': ' if everyone else ''}{e.task_name} ({e.get_category_display()}) - {format_hm(e.hours_spent)} [{e.get_status_display()}]")
        can_log, locked = service.submission_window(today, privileged)
        return Response({
            "range": rng, "from": start.isoformat(), "to": end.isoformat(), "today": today.isoformat(),
            "scope": "all" if everyone else ("me" if target.pk == request.user.pk else str(target.pk)),
            "target": {"id": target.pk, "name": _name(target), "is_me": target.pk == request.user.pk},
            "is_privileged": privileged, "members": [{"id": m.pk, "name": _name(m)} for m in User.objects.filter(memberships__company=request.company).order_by("username")] if privileged else [],
            "rows": rows, "days": [{**d, "hours": format_hm(d["hours"]) if d["hours"] else "0m"} for d in days.values()],
            "total": format_hm(total) if total else "0m", "count": len(entries), "completed": sum(d["completed"] for d in days.values()),
            "truncated": qs.count() > self.MAX_ROWS, "summary_text": "\n".join(lines) if entries else "No tasks recorded for this period.",
            "can_log": can_log, "locked_reason": locked,
            "products": [{"id": p.pk, "name": p.name} for p in accessible_products(target, request.company).order_by("name")],
            "categories": [list(c) for c in DSREntry.Category.choices], "statuses": [list(c) for c in DSREntry.Status.choices],
            "work_suggestions": [
                {"number": r["number"], "key": r["key"], "title": r["title"], "product": r["product"], "did": r["did"], "touched": r["touched"], "hours": format_hm(r["hours"]), "hours_value": str(r["hours"])}
                for r in service.suggestions(request.company, target, today)
            ] if can_log else [],
        })
