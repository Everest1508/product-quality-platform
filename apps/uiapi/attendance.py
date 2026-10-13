from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.attendance import corrections, panel, service
from apps.attendance.models import AttendanceCorrection, AttendanceRecord, format_minutes
from apps.core.timefmt import t12
from apps.dashboards.service import log_activity
from apps.uiapi.tickets import local_input
from apps.uiapi.views import CompanyAPIView

User = get_user_model()


def _privileged(request):
    return request.company_role in ("owner", "admin")


def _admin(request):
    if not _privileged(request):
        raise PermissionDenied("Only company admins can perform this action.")


def _name(u):
    return u.get_full_name() or u.username


def _clock(dt):
    return t12(timezone.localtime(dt)) if dt else ""


def _ms(dt):
    return int(dt.timestamp() * 1000) if dt else None


def _month(raw):
    year, month = service.parse_month(raw)
    py, pm = service.month_shift(year, month, -1)
    ny, nm = service.month_shift(year, month, 1)
    return year, month, {
        "label": service.month_label(year, month), "current": f"{year:04d}-{month:02d}", "prev": f"{py:04d}-{pm:02d}",
        "next": f"{ny:04d}-{nm:02d}", "today": timezone.localdate().strftime("%Y-%m"),
    }


def _status(r):
    if r.is_stale:
        return "stale"
    if r.is_open_today:
        return "open"
    if r.is_complete:
        return "complete"
    return "none"


def record_json(r):
    return {
        "id": r.pk, "date": r.date.isoformat(), "date_label": f"{r.date:%a, %b %d}",
        "check_in": _clock(r.check_in), "check_out": _clock(r.check_out), "status": _status(r),
        "worked": r.worked_formatted if r.is_complete else "", "effective": getattr(r, "effective_formatted", ""),
        "elapsed": r.elapsed_formatted if r.is_open else "", "day_pct": getattr(r, "day_pct", 0),
        "is_edited": r.is_edited, "notes": r.notes, "open_days": r.open_days if r.is_stale else 0,
    }


def correction_json(c, **extra):
    return {
        "id": c.pk, "date": c.date.isoformat(), "date_label": f"{c.date:%A, %B %d}", "status": c.status, "status_label": c.get_status_display(),
        "reason": c.reason, "created_at": c.created_at.isoformat(),
        "original": {"check_in": _clock(c.original_check_in), "check_out": _clock(c.original_check_out)},
        "requested": {"check_in": _clock(c.requested_check_in), "check_out": _clock(c.requested_check_out),
                      "check_out_next_day": bool(c.requested_check_out and timezone.localtime(c.requested_check_out).date() != c.date)},
        "person": {"id": c.user_id, "name": _name(c.user), "initial": (_name(c.user)[:1] or "?").upper()},
        "decided_by": _name(c.decided_by) if c.decided_by_id else "", "decision_note": c.decision_note,
        "decided_at": c.decided_at.isoformat() if c.decided_at else None,
        **extra,
    }


class MyAttendanceAPIView(CompanyAPIView):
    """Self-service: punch the clock and review your own days. An owner or admin may read a colleague's month."""

    def get(self, request):
        raw = request.query_params.get("user_id")
        target = request.user
        if raw:
            if not _privileged(request):
                raise PermissionDenied("You can only view your own attendance.")
            if not raw.isdecimal():
                from django.http import Http404

                raise Http404
            target = get_object_or_404(User, pk=int(raw), memberships__company=request.company)
        company, today = request.company, timezone.localdate()
        year, month, m = _month(request.query_params.get("month"))
        today_record = service.get_today_record(company, target)
        first, last = service.month_bounds(year, month)
        records = list(AttendanceRecord.objects.filter(company=company, user=target, date__gte=first, date__lte=last).order_by("-date"))
        shift = service.shift_for(company)
        for r in records:
            panel.annotate_effective(r, shift)
        if today_record is not None:
            panel.annotate_effective(today_record, shift)
        summary = panel.month_summary(records, shift, first, last, today)
        p = panel.punch_panel(company, request.user, today_record, person=target)
        focus = target if target.pk != request.user.pk else None
        mine = AttendanceCorrection.objects.filter(company=company, user=request.user).select_related("user", "decided_by")[:5] if focus is None else []
        rec = p["today_record"]
        late = p["late_rules"]
        return Response({
            "focus_user": {"id": focus.pk, "name": _name(focus)} if focus else None,
            "can_edit": _privileged(request),
            "month": {**m, "total": summary["month_total_formatted"], "average": summary["month_average_formatted"],
                      "present_days": summary["month_present_days"], "cells": summary["month_cells"],
                      "counts": summary["month_counts"], "leading_blanks": summary["month_leading_blanks"],
                      "unclosed_days": sum(1 for r in records if r.is_stale)},
            "panel": {
                "readonly": focus is not None,
                "state": "done" if rec and rec.is_complete else "open" if rec and rec.is_open_today else "ready",
                "check_in": _clock(rec.check_in) if rec else "", "check_out": _clock(rec.check_out) if rec else "",
                "worked": rec.worked_formatted if rec and rec.is_complete else "",
                "elapsed": rec.elapsed_formatted if rec and rec.is_open_today else "",
                "since_ms": p["since_ms"], "end_ms": p["end_ms"], "day_end_ms": p["day_end_ms"], "span_minutes": p["span_minutes"],
                "day_end_label": p["day_end_label"], "shift_end_label": p["shift_end_label"], "shift_label": p["shift_label"],
                "target": p["target_formatted"], "worked_delta": p["worked_delta"], "worked_delta_label": p["worked_delta_formatted"],
                "now_label": p["now_label"], "starts_in_minutes": p["starts_in_minutes"], "late_minutes": p["late_minutes"], "late_band": p["late_band"],
                "late_rules": late, "can_punch": p["can_punch"],
                "week": {"total": p["week"]["total_formatted"], "days": [
                    {"label": d["label"], "date": d["date"].isoformat(), "formatted": d["formatted"], "short": d["short"], "pct": d["pct"], "is_today": d["is_today"], "state": d["state"]}
                    for d in p["week"]["days"]]},
                "missing_checkouts": [{"id": r.pk, "date": r.date.isoformat(), "date_label": f"{r.date:%a, %b %d}"} for r in p["missing_checkouts"]],
            },
            "records": [record_json(r) for r in records],
            "my_corrections": [correction_json(c) for c in mine],
        })


class TeamAttendanceAPIView(CompanyAPIView):
    """Admin: who is on the clock right now and the team's today, or the week matrix (`view=week`)."""

    def get(self, request):
        _admin(request)
        company, today = request.company, timezone.localdate()
        shift = service.shift_for(company)
        if request.query_params.get("view") == "week":
            try:
                anchor = date.fromisoformat(request.query_params.get("week", ""))
            except ValueError:
                anchor = today
            monday = anchor - timedelta(days=anchor.weekday())
            rows = service.get_team_week(company, monday, shift)
            rows.sort(key=lambda r: (r["user"].pk != request.user.pk, r["user"].username.lower()))
            return Response({
                "view": "week", "monday": monday.isoformat(), "sunday": (monday + timedelta(days=6)).isoformat(),
                "prev": (monday - timedelta(days=7)).isoformat(), "next": (monday + timedelta(days=7)).isoformat(),
                "is_this_week": monday == today - timedelta(days=today.weekday()),
                "days": [{"date": (monday + timedelta(days=i)).isoformat(), "label": f"{monday + timedelta(days=i):%a}", "day": (monday + timedelta(days=i)).day, "is_today": (monday + timedelta(days=i)) == today} for i in range(7)],
                "shift": {"label": f"{t12(shift.start_time)}–{t12(shift.end_time)}"},
                "rows": [
                    {"user": {"id": r["user"].pk, "name": _name(r["user"]), "username": r["user"].username, "is_me": r["user"].pk == request.user.pk}, "role": r["role"],
                     "total": format_minutes(r["total_minutes"]) if r["total_minutes"] else "–", "late_days": r["late_days"], "leave_days": r["leave_days"],
                     "days": [{"date": d["date"].isoformat(), "state": d["state"], "check_in": _clock(d["record"].check_in) if d["record"] else "",
                               "check_out": _clock(d["record"].check_out) if d["record"] else "", "formatted": format_minutes(d["minutes"]) if d["minutes"] else "",
                               "late_minutes": d["late_minutes"], "band": d["band"], "record_id": d["record"].pk if d["record"] else None} for d in r["days"]]}
                    for r in rows
                ],
            })
        on_clock = service.get_who_is_in(company)
        team = service.get_team_today(company)
        weeks = panel.last_week(company, [r["user"].pk for r in team], shift)
        rows = []
        for r in team:
            rec = r["record"]
            if r["on_leave"]:
                state = "leave"
            elif rec and rec.is_stale:
                state = "stale"
            elif rec and rec.is_open_today:
                state = "clock"
            elif rec and rec.is_complete:
                state = "done"
            else:
                state = "absent"
            net = service.net_minutes_for(rec, shift) if rec and rec.check_in else 0
            rows.append({
                "user": {"id": r["user"].pk, "name": _name(r["user"]), "username": r["user"].username, "is_me": r["user"].pk == request.user.pk}, "role": r["role"], "state": state,
                "check_in": _clock(rec.check_in) if rec and rec.check_in else "", "check_out": _clock(rec.check_out) if rec and rec.check_out else "",
                "net": format_minutes(net) if net else "", "progress": min(100, round(net / max(1, shift.worked_minutes_per_day) * 100)) if net else 0,
                "record_id": rec.pk if rec else None, "has_punch": bool(rec and rec.check_in),
                "week": [{"date": d["date"].isoformat(), "state": d["state"], "formatted": d["formatted"]} for d in weeks[r["user"].pk]],
            })
        rows.sort(key=lambda r: (not r["user"]["is_me"], r["user"]["username"].lower()))
        return Response({
            "view": "today", "today": today.isoformat(), "shift": {"label": f"{t12(shift.start_time)}–{t12(shift.end_time)}"},
            "on_clock": [{"user": {"id": o["user"].pk, "name": _name(o["user"])}, "role": o["role"], "is_stale": o["is_stale"], "check_in": _clock(o["record"].check_in),
                          "record_id": o["record"].pk, "date_label": f"{o['record'].date:%a, %b %d}"} for o in on_clock],
            "counts": {"team": len(rows), "present": sum(1 for r in rows if r["has_punch"]), "leave": sum(1 for r in rows if r["state"] == "leave"),
                       "absent": sum(1 for r in rows if r["state"] != "leave" and not r["has_punch"]), "on_clock": len(on_clock),
                       "stale": sum(1 for o in on_clock if o["is_stale"])},
            "rows": rows,
        })


class TimesheetAPIView(CompanyAPIView):
    """Admin: per-month totals for every employee."""

    def get(self, request):
        _admin(request)
        year, month, m = _month(request.query_params.get("month"))
        rows = service.get_monthly_rows(request.company, year, month)
        total = sum(r["total_minutes"] for r in rows)
        return Response({
            "month": m, "company_total": format_minutes(total),
            "rows": [{"user": {"id": r["user"].pk, "name": _name(r["user"]), "username": r["user"].username}, "present_days": r["present_days"],
                      "absent_days": r["absent_days"], "leave_days": r["leave_day_count"], "late_days": r["late_days"], "open_days": r["open_days"],
                      "total": r["total_formatted"], "average": r["avg_per_day_formatted"]} for r in rows],
        })


class TimesheetDetailAPIView(CompanyAPIView):
    def get(self, request, user_id):
        _admin(request)
        year, month, m = _month(request.query_params.get("month"))
        user = get_object_or_404(User, pk=user_id, memberships__company=request.company)
        grid = service.get_month_grid(request.company, year, month, user)
        return Response({
            "month": m, "user": {"id": user.pk, "name": _name(user)},
            "totals": {"total": grid["total_formatted"], "present": grid["present_days"], "absent": grid["absent_days"], "leave": grid["leave_days"], "late": grid["late_days"], "open": grid["open_days"]},
            "leading_blanks": grid["days"][0]["weekday"] if grid["days"] else 0,
            "days": [{"date": d["date"].isoformat(), "day": d["day"], "is_weekend": d["is_weekend"], "is_today": d["is_today"], "on_leave": d["on_leave"],
                      "net": format_minutes(d["net_minutes"]) if d["net_minutes"] else "", "late_label": d["late_label"] or "", "is_unclosed": d["is_unclosed"],
                      "check_in": _clock(d["record"].check_in) if d["record"] else "", "check_out": _clock(d["record"].check_out) if d["record"] else "",
                      "record_id": d["record"].pk if d["record"] else None} for d in grid["days"]],
        })


class RecordAPIView(CompanyAPIView):
    """Admin: correct a record's times (a forgotten check-out, a wrong entry)."""

    def _json(self, record):
        shift = service.shift_for(record.company)
        panel.annotate_effective(record, shift)
        return {
            "id": record.pk, "date": record.date.isoformat(), "date_label": f"{record.date:%A, %B %d, %Y}", "user": {"id": record.user_id, "name": _name(record.user)},
            "check_in": local_input(record.check_in), "check_out": local_input(record.check_out), "notes": record.notes, "status": _status(record),
            "effective": record.effective_formatted, "worked_hours_per_day": format_minutes(shift.worked_minutes_per_day),
            # For a day nobody closed: the end of the shift, the obvious value to offer.
            "suggested_check_out": f"{record.date.isoformat()}T{shift.end_time:%H:%M}",
        }

    def _record(self, request, pk):
        _admin(request)
        return get_object_or_404(AttendanceRecord.objects.select_related("user", "company"), pk=pk, company=request.company)

    def get(self, request, pk):
        return Response(self._json(self._record(request, pk)))

    def patch(self, request, pk):
        record = self._record(request, pk)
        d = request.data
        parsed_in, parsed_out = service.parse_local_dt(d.get("check_in") or ""), service.parse_local_dt(d.get("check_out") or "")
        if parsed_in and parsed_out and parsed_out < parsed_in:
            return Response({"detail": "Check-out cannot be before check-in."}, status=400)
        if not parsed_in and record.check_in is None:
            return Response({"detail": "Enter at least a check-in time."}, status=400)
        problem = service.punch_problem(record.date, parsed_in, parsed_out)
        if problem:
            return Response({"detail": problem}, status=400)
        record.check_in, record.check_out = parsed_in, parsed_out
        record.notes = (d.get("notes") or "")[:255]
        record.is_edited = True
        record.save()
        who = _name(record.user)
        log_activity(
            request.company, "attendance_edited", f"Attendance for {who} on {record.date.strftime('%b %d, %Y')} edited", description=f"{record.worked_formatted}",
            actor=request.user, target_content_type="attendance_record", target_object_id=record.pk,
            metadata={"date": record.date.isoformat(), "check_in": record.check_in.isoformat() if record.check_in else None,
                      "check_out": record.check_out.isoformat() if record.check_out else None},
        )
        warn = record.is_open
        message = f"{who} still has no check-out for {record.date.strftime('%b %d')}." if warn else f"Updated {who}'s {record.date.strftime('%b %d')} record."
        return Response({**self._json(record), "message": message, "warning": warn})


def _day(raw):
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return timezone.localdate()


class CorrectionRequestAPIView(CompanyAPIView):
    """An employee asks for new times on one day. Nothing changes until an owner or admin approves."""

    def get(self, request):
        day = _day(request.query_params.get("date"))
        today = timezone.localdate()
        rec = AttendanceRecord.objects.filter(company=request.company, user=request.user, date=day).first()
        recent = AttendanceCorrection.objects.filter(company=request.company, user=request.user).select_related("user", "decided_by")[:10]
        return Response({
            "date": day.isoformat(), "date_label": f"{day:%A, %B %d}", "min_date": (today - timedelta(days=corrections.MAX_AGE_DAYS)).isoformat(), "max_date": today.isoformat(),
            "max_age_days": corrections.MAX_AGE_DAYS,
            "record": {"check_in": _clock(rec.check_in), "check_out": _clock(rec.check_out)} if rec else None,
            "recent": [correction_json(c) for c in recent],
        })

    def post(self, request):
        d = request.data
        day = _day(d.get("date"))
        try:
            check_in = corrections.build_datetime(day, d.get("check_in"))
            check_out = corrections.build_datetime(day, d.get("check_out"), next_day=bool(d.get("out_next_day")))
            corrections.request_correction(request.user, request.company, day, check_in, check_out, d.get("reason"))
        except corrections.CorrectionError as exc:
            return Response({"detail": str(exc)}, status=400)
        sent = " · ".join(f"{label} {when:%-I:%M %p}" for label, when in (("In", check_in), ("Out", check_out)) if when)
        return Response({"message": f"Request sent for {day:%b %d}: {sent}. You will be told when it is decided."}, status=201)


class CorrectionCancelAPIView(CompanyAPIView):
    def post(self, request, pk):
        c = get_object_or_404(AttendanceCorrection, pk=pk, company=request.company, user=request.user)
        try:
            corrections.cancel(c.pk, request.user)
        except corrections.CorrectionError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"message": "Request cancelled."})


class CorrectionQueueAPIView(CompanyAPIView):
    def get(self, request):
        _admin(request)
        pending = list(AttendanceCorrection.objects.filter(company=request.company, status="pending").select_related("user", "decided_by"))
        decided = AttendanceCorrection.objects.filter(company=request.company).exclude(status="pending").select_related("user", "decided_by")[:30]
        return Response({
            "pending": [correction_json(c, can_decide=corrections.can_decide(request.user, c), is_mine=c.user_id == request.user.pk) for c in pending],
            "decided": [correction_json(c) for c in decided],
        })


class CorrectionDecisionAPIView(CompanyAPIView):
    def post(self, request, pk, action):
        _admin(request)
        if action not in ("approve", "reject"):
            raise PermissionDenied("Unknown action.")
        c = get_object_or_404(AttendanceCorrection, pk=pk, company=request.company)
        try:
            done = corrections.decide(c.pk, request.user, action == "approve", request.data.get("note", "") if hasattr(request.data, "get") else "")
        except corrections.CorrectionError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"message": f"{_name(done.user)}'s correction for {done.date:%b %d} {done.get_status_display().lower()}."})
