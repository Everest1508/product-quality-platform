from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.attendance import service
from apps.attendance.models import AttendanceRecord, format_minutes, punch
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.core.redirects import safe_next
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


def annotate_effective(record, shift):
    """Attach the capped hours a day counts for, for a template.

    `effective_formatted` is not a model property on purpose: the cap needs the
    company's `WorkShift`, and looking that up per record would be a query per
    row in a list. It is attached to the instance so the partials can keep
    iterating plain records.
    """
    record.effective_minutes = service.effective_span_for(record, shift)
    record.effective_formatted = format_minutes(record.effective_minutes)
    return record


def _punch_context(request, record, message="", person=None):
    """Everything the punch panel renders, derived once.

    The panel is rendered from two places -- `MyAttendanceView` on a page load
    and `AttendancePunchView` on an htmx punch -- and if they each derived the
    state separately they would eventually disagree about whether somebody is on
    the clock.

    Lateness is shown here because the alternative is finding out you were 45
    minutes late on your payslip weeks later. It comes from `late_penalty_for`,
    the same call the payslip uses, so the panel and the payslip cannot quote
    different numbers.
    """
    shift = service.shift_for(request.company)
    # `person` is passed in rather than inferred from `record`, because the two
    # are not interchangeable: an admin reading a colleague's page gets
    # `person=that colleague` together with `record=None` on any day the
    # colleague has not punched yet. Inferring from the record then reported the
    # *admin's* forgotten days on somebody else's page -- a warning about the
    # wrong person, which is worse than no warning at all.
    owner = person or (record.user if record is not None else request.user)
    penalty = service.late_penalty_for(record, shift) if record else None
    now = timezone.localtime()

    # "Starts in 42m" is what makes the check-in button's meaning obvious
    # before it is pressed, which matters because arriving late is priced.
    starts_in = (
        shift.start_time.hour * 60 + shift.start_time.minute
        - (now.hour * 60 + now.minute)
    )

    # Numbers the live counter needs, as plain integers. The old template pasted
    # an unquoted ISO string into Alpine's x-data, which is a syntax error, so
    # the counter never ticked.
    today = timezone.localdate()
    shift_start = timezone.make_aware(datetime.combine(today, shift.start_time))
    shift_end = timezone.make_aware(datetime.combine(today, shift.end_time))
    span_minutes = max(1, int((shift_end - shift_start).total_seconds() // 60))
    since_ms = int(record.check_in.timestamp() * 1000) if record and record.check_in else None
    out_ms = int(record.check_out.timestamp() * 1000) if record and record.check_out else None
    worked = record.worked_minutes if record and record.is_complete else 0
    target = shift.worked_minutes_per_day

    return {
        "since_ms": since_ms,
        "end_ms": int(shift_end.timestamp() * 1000),
        "span_minutes": span_minutes,
        "shift_end_label": f"{shift.end_time:%I:%M %p}".lstrip("0"),
        "target_minutes": target,
        "target_formatted": format_minutes(target),
        "worked_delta": worked - target if worked else 0,
        "worked_delta_formatted": format_minutes(abs(worked - target)) if worked else "",
        "now_label": f"{now:%I:%M %p}".lstrip("0"),
        "week": _week_strip(request, owner, shift),
        "today_record": record,
        "shift": shift,
        "is_open": bool(record and record.is_open),
        "can_punch": not record
        or record.check_in is None
        or record.check_out is None,
        "late_minutes": service.lateness_for(record, shift) if record else 0,
        "late_band": penalty["band"] if penalty else None,
        "shift_label": f"{shift.start_time:%H:%M}–{shift.end_time:%H:%M}",
        "starts_in_minutes": starts_in if starts_in > 0 else None,
        # Every month, not the one on screen: an unclosed day from last month
        # still needs correcting and still stands between the employee and a
        # full day's pay.
        "missing_checkouts": list(service.unclosed_days(request.company, owner)),
        "message": message,
        # Set when the panel belongs to somebody else: the button would punch the
        # viewer, so the state row is suppressed and only the warning remains.
        "punch_readonly": False,
    }


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
        month_records = list(
            AttendanceRecord.objects.filter(
                company=request.company, user=user, date__gte=first, date__lte=last
            ).order_by("-date")
        )

        shift = service.shift_for(request.company)
        for record in month_records:
            annotate_effective(record, shift)
        # The "Today" stat reads `effective_formatted`, which was never set on
        # today's record, so it showed nothing while someone was on the clock.
        if today_record is not None:
            annotate_effective(today_record, shift)

        prev_year, prev_month = service.month_shift(year, month, -1)
        next_year, next_month = service.month_shift(year, month, 1)

        focus_user = user if user.pk != request.user.pk else None

        panel = _punch_context(request, today_record, person=user)
        panel["punch_readonly"] = focus_user is not None

        return render(request, "attendance/my_attendance.html", {
            "today": today,
            "today_record": today_record,
            "is_open": bool(today_record and today_record.is_open),
            "can_punch": not today_record
            or today_record.check_in is None
            or today_record.check_out is None,
            "records": month_records,
            "shift": shift,
            # Days in the month being viewed that were never closed out. The
            # stat strip is otherwise about today only, so this is the one place
            # an employee's own page admits a forgotten punch exists.
            "unclosed_days": sum(1 for r in month_records if r.is_stale),
            # The punch panel is hidden when an admin is reading a colleague's
            # record, but the correction form is what they came for -- so the
            # inline Edit is gated on privilege, not on who the record belongs to.
            "can_edit": _is_privileged(request),
            "next": request.get_full_path(),
            "focus_user": focus_user,
            "month_label": service.month_label(year, month),
            "prev_month": f"{prev_year:04d}-{prev_month:02d}",
            "next_month": f"{next_year:04d}-{next_month:02d}",
            "current_month": f"{year:04d}-{month:02d}",
            "today_month": timezone.localdate().strftime("%Y-%m"),
            **panel,
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
        elif action == "too_soon":
            message = "You just checked in. Give it a minute before checking out."
        else:
            message = "You have already checked in and out for today."

        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "attendance/partials/_punch_button.html",
                _punch_context(
                    request,
                    service.get_today_record(request.company, request.user),
                    message=message,
                ),
            )

        messages.success(request, message)
        return redirect("attendance:my_attendance")


def _week_strip(request, owner, shift):
    """Monday to Sunday for the current week: hours worked per day, for the bars
    under the punch panel."""
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    records = {
        r.date: r
        for r in AttendanceRecord.objects.filter(
            company=request.company, user=owner, date__gte=monday, date__lte=sunday
        )
    }
    on_leave = service.approved_leave_map(request.company, monday, sunday).get(owner.pk, set())
    target = max(1, shift.worked_minutes_per_day)
    days = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        record = records.get(day)
        minutes = service.net_minutes_for(record, shift) if record and record.check_in else 0
        if day in on_leave:
            state = "leave"
        elif minutes:
            state = "worked"
        elif day > today:
            state = "future"
        elif day.weekday() >= 5:
            state = "weekend"
        else:
            state = "none"
        days.append({
            "label": f"{day:%a}",
            "date": day,
            "minutes": minutes,
            "formatted": format_minutes(minutes),
            "pct": min(100, round(minutes / target * 100)),
            "is_today": day == today,
            "state": state,
        })
    return {
        "days": days,
        "total_formatted": format_minutes(sum(d["minutes"] for d in days)),
    }


def _last_week(company, user_ids, shift):
    """For each user, the last seven days as small state dots (worked, leave,
    none, weekend) and the minutes worked, from one query."""
    today = timezone.localdate()
    first = today - timedelta(days=6)
    records = {}
    for r in AttendanceRecord.objects.filter(
        company=company, user_id__in=user_ids, date__gte=first, date__lte=today
    ):
        records[(r.user_id, r.date)] = r
    on_leave = service.approved_leave_map(company, first, today)
    out = {}
    for uid in user_ids:
        days = []
        for offset in range(7):
            day = first + timedelta(days=offset)
            record = records.get((uid, day))
            minutes = service.net_minutes_for(record, shift) if record and record.check_in else 0
            if day in on_leave.get(uid, ()):
                state = "leave"
            elif record and record.check_in and record.is_stale:
                state = "open"
            elif minutes:
                state = "worked"
            elif day.weekday() >= 5:
                state = "weekend"
            else:
                state = "none"
            days.append({"date": day, "state": state, "formatted": format_minutes(minutes)})
        out[uid] = days
    return out


class TeamAttendanceView(CompanyAdminRequiredMixin, View):
    """Admin: who is on the clock right now, and the whole team's today."""

    def get(self, request):
        on_clock = service.get_who_is_in(request.company)
        team = service.get_team_today(request.company)
        shift = service.shift_for(request.company)

        # Your own row first, marked, then everyone else. It used to be buried
        # alphabetically, which read as "my attendance is not here".
        weeks = _last_week(request.company, [row["user"].pk for row in team], shift)
        for row in team:
            row["is_me"] = row["user"].pk == request.user.pk
            row["week"] = weeks[row["user"].pk]
            record = row["record"]
            if row["on_leave"]:
                row["state"] = "leave"
            elif record and record.is_stale:
                row["state"] = "stale"
            elif record and record.is_open_today:
                row["state"] = "clock"
            elif record and record.is_complete:
                row["state"] = "done"
            else:
                row["state"] = "absent"
            row["net_formatted"] = (
                format_minutes(service.net_minutes_for(record, shift))
                if record and record.check_in else ""
            )
            row["progress"] = (
                min(100, round(service.net_minutes_for(record, shift) / max(1, shift.worked_minutes_per_day) * 100))
                if record and record.check_in else 0
            )
        team.sort(key=lambda row: (not row["is_me"], row["user"].username.lower()))
        me = next((row for row in team if row["is_me"]), None)

        context = {
            "on_clock": on_clock,
            "on_clock_count": len(on_clock),
            "stale_count": sum(1 for r in on_clock if r["is_stale"]),
            "team": team,
            "me": me,
            "team_count": len(team),
            "present_count": sum(1 for row in team if row["record"] and row["record"].check_in),
            # Someone on approved leave is not absent, so they are counted
            # separately instead of dragging the absent total up.
            "leave_count": sum(1 for row in team if row["on_leave"]),
            "shift": shift,
            "next": request.get_full_path(),
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


def _safe_next(raw):
    """A same-site path to return to after an edit, or None.

    Delegates to `apps.core.redirects.safe_next`, which owns the rule: `next` is
    an attacker-supplied string that becomes a redirect target, so it is
    validated rather than trusted. Kept as a local name because it is called
    from a dozen places in this module.
    """
    return safe_next(raw)


class AttendanceEditView(CompanyAdminRequiredMixin, View):
    """Admin: correct a record's timestamps (forgotten check-outs, bad entry).

    GET renders the form so the correction is reachable as a plain link from
    anywhere a day is displayed -- the calendar grid has no room for an inline
    form, but it has room for a link.
    """

    def get(self, request, pk):
        record = get_object_or_404(
            AttendanceRecord, pk=pk, company=request.company
        )
        shift = service.shift_for(request.company)
        # The page explains the cap in hours, so it needs the number the cap
        # produced -- otherwise the sentence explains a rule and quotes no
        # consequence, which is the part the admin is actually weighing.
        annotate_effective(record, shift)

        return render(request, "attendance/edit_record.html", {
            "record": record,
            "shift": shift,
            "next": _safe_next(request.GET.get("next")),
        })

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
            return redirect(
                _safe_next(request.POST.get("next")) or "attendance:team_attendance"
            )

        if not parsed_in and record.check_in is None and request.POST:
            # A form submitted with both boxes empty would silently wipe a day
            # that never existed. Say so instead of storing an empty row.
            messages.error(request, "Enter at least a check-in time.")
            return redirect(
                _safe_next(request.POST.get("next")) or "attendance:team_attendance"
            )

        problem = _punch_problem(record, parsed_in, parsed_out)
        if problem:
            messages.error(request, problem)
            return redirect(
                _safe_next(request.POST.get("next")) or "attendance:team_attendance"
            )

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

        if record.is_open:
            messages.warning(
                request,
                f"{record.user.get_full_name() or record.user.username} still has no "
                f"check-out for {record.date.strftime('%b %d')}.",
            )
        else:
            messages.success(
                request,
                f"Updated {record.user.get_full_name() or record.user.username}'s "
                f"{record.date.strftime('%b %d')} record.",
            )
        return redirect(
            _safe_next(request.POST.get("next")) or "attendance:team_attendance"
        )


def _punch_problem(record, check_in, check_out):
    """Why an edited punch cannot be saved, or None when it is fine.

    A punch has to belong to the record's own day (a night shift may close the
    next morning) and cannot be in the future, otherwise a typo moves hours into
    a different day or invents time that has not happened yet.
    """
    now = timezone.now()
    for label, value in (("Check-in", check_in), ("Check-out", check_out)):
        if value is None:
            continue
        if value > now + timedelta(minutes=5):
            return f"{label} cannot be in the future."
        offset = (timezone.localtime(value).date() - record.date).days
        limit = (0, 1) if label == "Check-out" else (0, 0)
        if not limit[0] <= offset <= limit[1]:
            return f"{label} has to fall on {record.date:%b %d}" + (
                " or the morning after." if label == "Check-out" else "."
            )
    return None


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
