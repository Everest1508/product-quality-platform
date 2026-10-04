from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.attendance import corrections, service
from apps.attendance.models import AttendanceCorrection, AttendanceRecord, format_minutes, punch
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

    # A full day is `worked_minutes_per_day` of work plus the unpaid break, which is
    # exactly the span `service.net_minutes_for` needs before it counts a day as
    # complete. The countdown runs to that moment, measured from the actual check-in.
    day_total = timedelta(minutes=target + shift.break_minutes)
    day_end = record.check_in + day_total if record and record.check_in else None
    remaining = max(0, int((day_end - timezone.now()).total_seconds())) if day_end else 0

    return {
        "since_ms": since_ms,
        "end_ms": int(shift_end.timestamp() * 1000),
        "span_minutes": span_minutes,
        "day_end_ms": int(day_end.timestamp() * 1000) if day_end else None,
        "day_end_label": f"{timezone.localtime(day_end):%I:%M %p}".lstrip("0") if day_end else "",
        "remaining_formatted": f"{remaining // 3600}h {remaining % 3600 // 60:02d}m {remaining % 60:02d}s",
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


def _month_summary(records, shift, first, last, today):
    """Numbers and a day-by-day strip for the month being viewed.

    Hours come from `effective_minutes` (set by `annotate_effective`), so an
    unclosed day counts the same capped amount here as on the timesheet.
    """
    scheduled = max(1, shift.worked_minutes_per_day)
    by_day = {r.date: r for r in records}
    total = 0
    present = 0
    for r in records:
        mins = getattr(r, "effective_minutes", 0)
        r.day_pct = min(100, round(100 * mins / scheduled))
        if r.check_in:
            present += 1
            total += mins

    cells = []
    day = first
    while day <= last:
        rec = by_day.get(day)
        if rec is not None and rec.check_in:
            mins = getattr(rec, "effective_minutes", 0)
            if rec.is_stale:
                state, note = "stale", "no check-out"
            elif rec.is_open and day == today:
                state, note = "open", "on the clock"
            elif mins >= 0.9 * scheduled:
                state, note = "full", format_minutes(mins)
            else:
                state, note = "part", format_minutes(mins)
            pct = min(100, round(100 * mins / scheduled))
        elif day > today:
            state, note, pct = "future", "", 0
        elif day.weekday() >= 5:
            state, note, pct = "rest", "weekend", 0
        else:
            state, note, pct = "none", "no punch", 0
        cells.append({
            "day": day.day, "state": state, "pct": pct, "is_today": day == today,
            "title": f"{day:%a, %b} {day.day}" + (f": {note}" if note else ""),
        })
        day += timedelta(days=1)

    return {
        "month_total_formatted": format_minutes(total),
        "month_average_formatted": format_minutes(total // present) if present else "–",
        "month_present_days": present,
        "month_cells": cells,
        "month_counts": {
            state: sum(1 for c in cells if c["state"] == state)
            for state in ("full", "part", "open", "stale", "none")
        },
        "month_leading_blanks": first.weekday(),
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

        month_summary = _month_summary(month_records, shift, first, last, today)

        focus_user = user if user.pk != request.user.pk else None

        panel = _punch_context(request, today_record, person=user)
        panel["punch_readonly"] = focus_user is not None
        my_corrections = (
            AttendanceCorrection.objects.filter(company=request.company, user=request.user)[:5]
            if focus_user is None else []
        )

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
            **month_summary,
            "prev_month": f"{prev_year:04d}-{prev_month:02d}",
            "next_month": f"{next_year:04d}-{next_month:02d}",
            "current_month": f"{year:04d}-{month:02d}",
            "today_month": timezone.localdate().strftime("%Y-%m"),
            "my_corrections": my_corrections,
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
            # Compact for the small label under each bar: "8h 49", or a dash.
            "short": f"{minutes // 60}h {minutes % 60:02d}" if minutes else "–",
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

        problem = service.punch_problem(record.date, parsed_in, parsed_out)
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


def _parse_dt(raw):
    return service.parse_local_dt(raw)



def _day_param(raw):
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return timezone.localdate()


class CorrectionRequestView(CompanyMemberRequiredMixin, View):
    """An employee asks for new times on one day. Nothing changes until an owner
    or admin approves."""

    template_name = "attendance/correction_form.html"

    def _context(self, request, day, values=None):
        record = AttendanceRecord.objects.filter(company=request.company, user=request.user, date=day).first()
        today = timezone.localdate()
        return {
            "day": day,
            "record": record,
            "min_date": today - timedelta(days=corrections.MAX_AGE_DAYS),
            "max_date": today,
            "values": values or {},
            "max_age_days": corrections.MAX_AGE_DAYS,
            "recent": AttendanceCorrection.objects.filter(company=request.company, user=request.user)[:10],
        }

    def get(self, request):
        return render(request, self.template_name, self._context(request, _day_param(request.GET.get("date"))))

    def post(self, request):
        day = _day_param(request.POST.get("date"))
        values = {k: request.POST.get(k, "") for k in ("check_in", "check_out", "reason", "out_next_day")}
        try:
            check_in = corrections.build_datetime(day, values["check_in"])
            check_out = corrections.build_datetime(day, values["check_out"], next_day=bool(values["out_next_day"]))
            corrections.request_correction(request.user, request.company, day, check_in, check_out, values["reason"])
        except corrections.CorrectionError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, self._context(request, day, values), status=400)
        messages.success(request, f"Request sent for {day:%b %d}. You will be told when it is decided.")
        return redirect("attendance:my_attendance")


class CorrectionCancelView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        correction = get_object_or_404(AttendanceCorrection, pk=pk, company=request.company, user=request.user)
        try:
            corrections.cancel(correction.pk, request.user)
            messages.success(request, "Request cancelled.")
        except corrections.CorrectionError as exc:
            messages.error(request, str(exc))
        return redirect("attendance:my_attendance")


class CorrectionQueueView(CompanyAdminRequiredMixin, View):
    """Owners and admins: what is waiting, and what was decided lately."""

    def get(self, request):
        pending = list(
            AttendanceCorrection.objects.filter(company=request.company, status="pending").select_related("user")
        )
        for item in pending:
            item.can_decide = corrections.can_decide(request.user, item)
            item.is_mine = item.user_id == request.user.pk
        decided = (
            AttendanceCorrection.objects.filter(company=request.company)
            .exclude(status="pending")
            .select_related("user", "decided_by")[:30]
        )
        return render(request, "attendance/corrections.html", {"pending": pending, "decided": decided})


class CorrectionDecisionView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk, action):
        if action not in ("approve", "reject"):
            return HttpResponseForbidden("Unknown action.")
        correction = get_object_or_404(AttendanceCorrection, pk=pk, company=request.company)
        try:
            done = corrections.decide(correction.pk, request.user, action == "approve", request.POST.get("note", ""))
            who = done.user.get_full_name() or done.user.username
            messages.success(request, f"{who}'s correction for {done.date:%b %d} {done.get_status_display().lower()}.")
        except corrections.CorrectionError as exc:
            messages.error(request, str(exc))
        return redirect("attendance:corrections")
