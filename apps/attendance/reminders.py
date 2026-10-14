"""Nudges to check in and out. Run from cron every few minutes (`manage.py send_attendance_reminders`).

Only people who actually use attendance (a punch in the last 30 days) are nudged, never on weekends, holidays or
approved leave, and each person gets each kind at most once a day. Switching the kind off in the profile mutes it,
because everything goes through `notifications.service.notify`.
"""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.attendance import service
from apps.attendance.models import AttendanceRecord
from apps.leave import service as leave
from apps.notifications import service as notes
from apps.notifications.models import Notification

CHECK_IN_AFTER = 5  # minutes after the shift starts, while the person is still on time


def _at(day, t):
    return timezone.make_aware(datetime.combine(day, t), timezone.get_current_timezone())


def send(company, now=None, dry_run=False):
    """Create the reminders that are due right now. Returns how many were (or would be) sent."""
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    if today.weekday() >= 5 or today in leave._holiday_dates(company, today, today):
        return 0
    shift = service.shift_for(company)
    start = _at(today, shift.start_time) + timedelta(minutes=min(CHECK_IN_AFTER, shift.grace_minutes))
    end = _at(today, shift.end_time)
    User = get_user_model()
    active = User.objects.filter(attendance_records__company=company, attendance_records__date__gte=today - timedelta(days=30)).distinct()
    sent = 0
    for user in active:
        if leave.is_on_leave(company, user, today):
            continue
        record = AttendanceRecord.objects.filter(company=company, user=user, date=today).first()
        kind = None
        if (record is None or record.check_in is None) and start <= now <= end:
            kind, title, body = Notification.Kind.ATTENDANCE_CHECKIN, "You haven’t checked in yet", f"Your shift started at {shift.start_time:%-I:%M %p}. Check in to stay on time."
        elif record is not None and record.check_in is not None and record.check_out is None and now >= end:
            kind, title, body = Notification.Kind.ATTENDANCE_CHECKOUT, "Don’t forget to check out", f"Your shift ended at {shift.end_time:%-I:%M %p}. Check out so your hours are right."
        if kind is None:
            continue
        if Notification.objects.filter(company=company, user=user, kind=kind, created_at__gte=_at(today, time.min)).exists():
            continue
        sent += 1
        if not dry_run:
            notes.notify(user=user, company=company, kind=kind, title=title, body=body, url="/attendance/")
    return sent
