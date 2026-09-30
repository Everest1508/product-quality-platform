from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel


class AttendanceRecord(TenantScopedModel):
    """One row per employee per day.

    Deliberately a single punch pair rather than a session log: check-out minus
    check-in is the day's worked time, and there is no break tracking. The
    unique_together below is what makes double-punching impossible.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField(default=timezone.localdate, db_index=True)

    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)

    notes = models.CharField(max_length=255, blank=True, default="")
    is_edited = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-date", "user__username"]
        unique_together = ("company", "user", "date")
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"

    def __str__(self):
        return f"{self.user.username} - {self.date}"

    @property
    def is_open(self):
        """True between check-in and check-out, i.e. the employee is on the clock."""
        return self.check_in is not None and self.check_out is None

    @property
    def is_complete(self):
        return self.check_in is not None and self.check_out is not None

    @property
    def worked_minutes(self):
        if not self.is_complete:
            return 0
        delta = self.check_out - self.check_in
        return max(0, int(delta.total_seconds() // 60))

    @property
    def worked_hours(self):
        return (Decimal(self.worked_minutes) / Decimal(60)).quantize(Decimal("0.01"))

    @property
    def worked_formatted(self):
        return format_minutes(self.worked_minutes)

    @property
    def elapsed_formatted(self):
        """Time on the clock right now, for an open record."""
        if not self.is_open:
            return "N/A"
        return format_minutes(self._elapsed_minutes())

    def _elapsed_minutes(self):
        return max(0, int((timezone.now() - self.check_in).total_seconds() // 60))


def format_minutes(minutes):
    minutes = max(0, int(minutes or 0))
    return f"{minutes // 60}h {minutes % 60:02d}m"


def record_for_day(company, user, day):
    return AttendanceRecord.objects.filter(company=company, user=user, date=day).first()


def punch(company, user, moment=None, notes=""):
    """Toggle the clock for `user` on today's date.

    Returns (record, action) where action is one of:
      "checked_in"  - a new day was started
      "checked_out" - the open day was closed
      "unchanged"   - already closed for the day, no-op
    """
    moment = moment or timezone.now()
    day = timezone.localdate(moment)

    record = AttendanceRecord.objects.filter(company=company, user=user, date=day).first()

    if record is None:
        record = AttendanceRecord.objects.create(
            company=company,
            user=user,
            date=day,
            check_in=moment,
            notes=notes,
        )
        return record, "checked_in"

    if record.check_in is None:
        record.check_in = moment
        if notes:
            record.notes = notes
        record.save()
        return record, "checked_in"

    if record.check_out is None:
        record.check_out = max(moment, record.check_in)
        if notes:
            record.notes = notes
        record.save()
        return record, "checked_out"

    return record, "unchanged"


def month_bounds(year, month):
    """First and last day of the given month, as dates."""
    first = timezone.datetime(year, month, 1).date()
    if month == 12:
        last = timezone.datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last = timezone.datetime(year, month + 1, 1).date() - timedelta(days=1)
    return first, last


class WorkShift(TenantScopedModel):
    """A company's office hours, and the lateness rules that hang off them.

    One row per company (`get_or_create` in `shift_for`), because these are the
    numbers every late penalty and every "hours worked" figure is derived from.
    Defaults are the office policy: 10:00-19:00 with a 60 minute break, which
    is 8 working hours a day.

    The bands are stored as *minutes after `start_time`* rather than as clock
    times, so the whole thing is one number to reason about:

    ==========  ==================  ==============
    late by     outcome             cost
    ==========  ==================  ==============
    <= 15 min   on time             nothing
    15-30 min   `minor_penalty`     Rs 50
    30-60 min   `major_penalty`     Rs 100
    > 60 min    half day            one day's pay
    ==========  ==================  ==============

    `late_minutes` is measured against `start_time`, so 10:30 is exactly 30
    minutes late and lands in the *major* band, not the minor one.
    """

    start_time = models.TimeField(default=time(10, 0))
    end_time = models.TimeField(default=time(19, 0))
    break_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Unpaid scheduled break, deducted from hours worked.",
    )

    grace_minutes = models.PositiveIntegerField(
        default=15, help_text="Arriving within this of start_time is on time."
    )
    minor_band_end_minutes = models.PositiveIntegerField(
        default=30, help_text="Up to this late: minor_penalty."
    )
    major_band_end_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Up to this late: major_penalty. Beyond it, a half day.",
    )
    minor_penalty = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("50.00")
    )
    major_penalty = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("100.00")
    )
    penalty_currency = models.CharField(max_length=8, default="INR")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        verbose_name = "Work Shift"
        verbose_name_plural = "Work Shifts"

    def __str__(self):
        return f"{self.company_id}: {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    @property
    def worked_minutes_per_day(self):
        """Scheduled working minutes, i.e. the span less the unpaid break."""
        span = datetime.combine(date.today(), self.end_time) - datetime.combine(
            date.today(), self.start_time
        )
        return max(0, int(span.total_seconds() // 60) - self.break_minutes)

    def band_for_late_minutes(self, late_minutes):
        """`"on_time" | "minor" | "major" | "half_day"` for a lateness.

        Boundaries are inclusive at the top of each band: exactly 30 minutes
        late is already the major penalty, exactly 60 is already a half day.
        """
        if late_minutes <= self.grace_minutes:
            return "on_time"
        if late_minutes <= self.minor_band_end_minutes:
            return "minor"
        if late_minutes <= self.major_band_end_minutes:
            return "major"
        return "half_day"
