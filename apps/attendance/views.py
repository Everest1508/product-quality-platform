from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.attendance import service
from apps.attendance.models import AttendanceRecord, punch
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity

User = get_user_model()

PRIVILEGED_ROLES = ("owner", "admin")


def _is_privileged(request):
    return request.company_role in PRIVILEGED_ROLES


def _target_user(request, queryset_user=None):
    """Resolve the employee a view should act on.

    Non-privileged users are always pinned to themselves, so a user_id param can
    never surface another employee's attendance. Self-service views that should
    reject such a request outright call _requested_other_user() first.
    """
    if queryset_user is not None:
        return queryset_user

    if _is_privileged(request):
        target_id = request.GET.get("user_id") or request.POST.get("user_id")
        if target_id:
            return get_object_or_404(
                User, pk=target_id, memberships__company=request.company
            )
    return request.user


def _requested_other_user(request):
    """True when a non-admin explicitly asked for someone else's record.

    Rejected rather than silently ignored, so a hand-edited URL fails loudly
    instead of quietly returning the wrong person's data.
    """
    target_id = request.GET.get("user_id") or request.POST.get("user_id")
    if not target_id or _is_privileged(request):
        return False
    return str(target_id) != str(request.user.pk)


class MyAttendanceView(CompanyMemberRequiredMixin, View):
    """Self-service: punch the clock and review your own days."""

    def get(self, request):
        if _requested_other_user(request):
            return HttpResponseForbidden("You can only view your own attendance.")

        today = timezone.localdate()
        year, month = service.parse_month(request.GET.get("month"))
        user = _target_user(request)

        today_record = service.get_today_record(request.company, user)

        # Scope the table to the selected month, otherwise the arrows move the
        # header label without moving the data.
        first, last = service.month_bounds(year, month)
        month_records = AttendanceRecord.objects.filter(
            company=request.company, user=user, date__gte=first, date__lte=last
        ).order_by("-date")

        prev_year, prev_month = service.month_shift(year, month, -1)
        next_year, next_month = service.month_shift(year, month, 1)

        focus_user = user if user.pk != request.user.pk else None

        return render(request, "attendance/my_attendance.html", {
            "today": today,
            "today_record": today_record,
            "is_open": bool(today_record and today_record.is_open),
            "can_punch": not today_record or today_record.check_in is None or today_record.check_out is None,
            "records": month_records,
            "focus_user": focus_user,
            "month_label": service.month_label(year, month),
            "prev_month": f"{prev_year:04d}-{prev_month:02d}",
            "next_month": f"{next_year:04d}-{next_month:02d}",
            "current_month": f"{year:04d}-{month:02d}",
            "today_month": timezone.localdate().strftime("%Y-%m"),
        })


class AttendancePunchView(CompanyMemberRequiredMixin, View):
    """POST to toggle check-in / check-out for the signed-in employee."""

    def post(self, request):
        record, action = punch(
            company=request.company,
            user=request.user,
            notes=request.POST.get("notes", "")[:255],
        )

        if action == "checked_in":
            log_activity(
                request.company,
                "attendance_checked_in",
                f"{request.user.get_full_name() or request.user.username} checked in",
                description=record.check_in.strftime("%I:%M %p") if record.check_in else "",
                actor=request.user,
                target_content_type="attendance_record",
                target_object_id=record.pk,
                metadata={"date": record.date.isoformat()},
            )
            message = f"Checked in at {record.check_in.strftime('%I:%M %p')}."
        elif action == "checked_out":
            log_activity(
                request.company,
                "attendance_checked_out",
                f"{request.user.get_full_name() or request.user.username} checked out",
                description=f"{record.worked_formatted} worked",
                actor=request.user,
                target_content_type="attendance_record",
                target_object_id=record.pk,
                metadata={
                    "date": record.date.isoformat(),
                    "worked_minutes": record.worked_minutes,
                },
            )
            message = f"Checked out. {record.worked_formatted} logged today."
        else:
            message = "You have already checked in and out for today."

        if request.headers.get("HX-Request") == "true":
            today_record = service.get_today_record(request.company, request.user)
            return render(request, "attendance/partials/_punch_button.html", {
                "today_record": today_record,
                "is_open": bool(today_record and today_record.is_open),
                "can_punch": not today_record
                or today_record.check_in is None
                or today_record.check_out is None,
                "message": message,
            })

        messages.success(request, message)
        return redirect("attendance:my_attendance")


class TeamAttendanceView(CompanyAdminRequiredMixin, View):
    """Admin: who is on the clock right now, and the whole team's today."""

    def get(self, request):
        on_clock = service.get_who_is_in(request.company)
        team = service.get_team_today(request.company)

        context = {
            "on_clock": on_clock,
            "on_clock_count": len(on_clock),
            "stale_count": sum(1 for r in on_clock if r["is_stale"]),
            "team": team,
            "present_count": sum(1 for row in team if row["record"] and row["record"].check_in),
            # Someone on approved leave is not absent, so they are counted
            # separately instead of dragging the absent total up.
            "leave_count": sum(1 for row in team if row["on_leave"]),
            "absent_count": sum(
                1 for row in team
                if not row["on_leave"] and not (row["record"] and row["record"].check_in)
            ),
            "today": timezone.localdate(),
        }

        if request.headers.get("HX-Request") == "true":
            return render(request, "attendance/partials/_team_body.html", context)

        return render(request, "attendance/team_attendance.html", context)


class TimesheetView(CompanyAdminRequiredMixin, View):
    """Admin: per-month totals for every employee."""

    def get(self, request):
        year, month = service.parse_month(request.GET.get("month"))
        user = _target_user(request)
        rows = service.get_monthly_rows(request.company, year, month)

        prev_year, prev_month = service.month_shift(year, month, -1)
        next_year, next_month = service.month_shift(year, month, 1)

        company_total = sum(r["total_minutes"] for r in rows)

        return render(request, "attendance/timesheet.html", {
            "rows": rows,
            "year": year,
            "month": month,
            "month_label": service.month_label(year, month),
            "current_month": f"{year:04d}-{month:02d}",
            "today_month": timezone.localdate().strftime("%Y-%m"),
            "prev_month": f"{prev_year:04d}-{prev_month:02d}",
            "next_month": f"{next_year:04d}-{next_month:02d}",
            "company_total_minutes": company_total,
            "company_total_formatted": service.format_minutes(company_total),
            "focus_user": user if user.pk != request.user.pk else None,
        })


class TimesheetDetailView(CompanyAdminRequiredMixin, View):
    """Admin: one employee's day-by-day grid for a month."""

    def get(self, request, user_id):
        year, month = service.parse_month(request.GET.get("month"))
        user = get_object_or_404(User, pk=user_id, memberships__company=request.company)
        grid = service.get_month_grid(request.company, year, month, user)

        prev_year, prev_month = service.month_shift(year, month, -1)
        next_year, next_month = service.month_shift(year, month, 1)

        context = {
            "target_user": user,
            "year": year,
            "month": month,
            "month_label": service.month_label(year, month),
            "current_month": f"{year:04d}-{month:02d}",
            "today_month": timezone.localdate().strftime("%Y-%m"),
            "prev_month": f"{prev_year:04d}-{prev_month:02d}",
            "next_month": f"{next_year:04d}-{next_month:02d}",
            **grid,
        }

        if request.headers.get("HX-Request") == "true":
            return render(request, "attendance/partials/_month_grid.html", context)

        return render(request, "attendance/timesheet_detail.html", context)


class AttendanceEditView(CompanyAdminRequiredMixin, View):
    """Admin: correct a record's timestamps (forgotten check-outs, bad entry)."""

    def post(self, request, pk):
        record = get_object_or_404(
            AttendanceRecord, pk=pk, company=request.company
        )

        check_in = request.POST.get("check_in") or ""
        check_out = request.POST.get("check_out") or ""

        parsed_in = _parse_dt(check_in)
        parsed_out = _parse_dt(check_out)

        if parsed_in and parsed_out and parsed_out < parsed_in:
            messages.error(request, "Check-out cannot be before check-in.")
            return redirect("attendance:team_attendance")

        record.check_in = parsed_in
        record.check_out = parsed_out
        record.notes = request.POST.get("notes", "")[:255]
        record.is_edited = True
        record.save()

        log_activity(
            request.company,
            "attendance_edited",
            f"Attendance for {record.user.get_full_name() or record.user.username} on "
            f"{record.date.strftime('%b %d, %Y')} edited",
            description=f"{record.worked_formatted}",
            actor=request.user,
            target_content_type="attendance_record",
            target_object_id=record.pk,
            metadata={
                "date": record.date.isoformat(),
                "check_in": record.check_in.isoformat() if record.check_in else None,
                "check_out": record.check_out.isoformat() if record.check_out else None,
            },
        )

        messages.success(
            request,
            f"Updated {record.user.get_full_name() or record.user.username}'s "
            f"{record.date.strftime('%b %d')} record.",
        )
        return redirect("attendance:team_attendance")


def _parse_dt(raw):
    """Parse a datetime-local input value into an aware datetime.

    Returns None for empty input, which is how a record is cleared back to
    "not punched".
    """
    raw = raw.strip()
    if not raw:
        return None
    try:
        naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        try:
            naive = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    return timezone.make_aware(naive, timezone.get_current_timezone())
