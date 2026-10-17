"""Small, friendly facts about a person's work: an on-time streak and milestones worth a line of praise."""
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Membership
from apps.attendance import service as attendance
from apps.attendance.models import AttendanceRecord
from apps.leave import service as leave
from apps.tickets.models import Ticket

TICKET_MARKS = (1, 10, 25, 50, 100, 250, 500, 1000)


def on_time_streak(company, user, today=None):
    """Working days in a row, up to today, that the person checked in within the grace period.

    Weekly offs, company holidays and approved leave neither count nor break the run. A day today with no punch yet
    is skipped rather than counted against the streak.
    """
    today = today or timezone.localdate()
    shift = attendance.shift_for(company)
    start = today - timedelta(days=400)
    records = {r.date: r for r in AttendanceRecord.objects.filter(company=company, user=user, date__gte=start, check_in__isnull=False)}
    skip = leave.leave_dates(company, user, start, today) | set(leave._holiday_dates(company, start, today))
    n, day = 0, today
    while day >= start:
        if not shift.is_weekly_off(day) and day not in skip:
            rec = records.get(day)
            if rec is None:
                if day != today:
                    break
            elif attendance.lateness_for(rec, shift) > shift.grace_minutes:
                break
            else:
                n += 1
        day -= timedelta(days=1)
    return n


def milestones(company, user, today=None):
    """Short sentences for things worth marking this week: a work anniversary, a round number of resolved tickets."""
    today = today or timezone.localdate()
    out = []
    m = Membership.objects.filter(user=user, company=company).first()
    if m:
        joined = timezone.localtime(m.created_at).date()
        years = today.year - joined.year
        try:
            anniversary = joined.replace(year=today.year)
        except ValueError:  # 29 February
            anniversary = joined.replace(year=today.year, day=28)
        if years >= 1 and 0 <= (today - anniversary).days < 7:
            out.append(f"{years} year{'s' if years != 1 else ''} with {company.name} this week. Thank you!")
    done = Ticket.objects.filter(company=company, assignees=user, status__in=["resolved", "closed"]).count()
    if done in TICKET_MARKS:
        out.append("Your first resolved ticket. Great start!" if done == 1 else f"{done} tickets resolved. Keep it up!")
    return out
