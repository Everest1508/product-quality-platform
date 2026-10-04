from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
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
        """check_in recorded, check_out not yet recorded -- on *any* day.

        This is a property of the row, not of the clock: it is equally true for
        somebody working right now and for a punch somebody forgot to close three
        weeks ago. Use `is_open_today` / `is_stale` to tell those apart, because
        rendering both as "On clock" is how an unclosed day becomes invisible.
        """
        return self.check_in is not None and self.check_out is None

    @property
    def is_open_today(self):
        """Open on today's date: genuinely still on the clock."""
        return self.is_open and self.date == timezone.localdate()

    @property
    def is_stale(self):
        """Open but left unclosed on its own day: a forgotten check-out.

        Defined here, not in `service.get_who_is_in`, because it is a fact about
        the record. The team view used to compute it privately, so the four other
        places that render an open day had no way to ask.
        """
        return self.is_open and self.date < timezone.localdate()

    @property
    def is_complete(self):
        return self.check_in is not None and self.check_out is not None

    @property
    def open_days(self):
        """Whole days between the punch date and today (0 while it is today's).

        Days *since*, not days *open-for*: a punch from 3 days ago reads "3",
        which is what "checked in 3 days ago" has to say. Counting today's open
        day as well would report a 3-day-old punch as 4 days old.
        """
        if not self.is_open:
            return 0
        return max(0, (timezone.localdate() - self.date).days)

    @property
    def worked_minutes(self):
        """The raw punch span, and only when both punches exist.

        Deliberately 0 for an unclosed day: this is what the punches *say*, and
        they say nothing about when the person left. Anything that has to put a
        number on an unclosed day goes through
        `apps.attendance.service.effective_span_for`, which has the office
        hours needed to cap a guess.
        """
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
    def elapsed_minutes(self):
        """Minutes since check-in while the day is still open, else 0."""
        if not self.is_open:
            return 0
        return max(0, int((timezone.now() - self.check_in).total_seconds() // 60))

    @property
    def elapsed_formatted(self):
        """Time on the clock right now, for an open record."""
        if not self.is_open:
            return "N/A"
        return format_minutes(self.elapsed_minutes)

    @property
    def missing_checkout_label(self):
        """How long the day has been left open, for the flag beside the row."""
        if self.is_open_today:
            return "today"
        return f"{self.open_days}d"


def format_minutes(minutes):
    minutes = max(0, int(minutes or 0))
    return f"{minutes // 60}h {minutes % 60:02d}m"


def record_for_day(company, user, day):
    return AttendanceRecord.objects.filter(company=company, user=user, date=day).first()


# A check-out this soon after a check-in is a double tap, not a day's work.
# Without the guard the second tap closed the day at 0 minutes and the person
# could not check in again.
MIN_PUNCH_GAP = timedelta(seconds=45)


def punch(company, user, moment=None, notes=""):
    """Toggle the clock for `user` on today's date.

    Returns (record, action) where action is one of:
      "checked_in"  - a new day was started
      "checked_out" - the open day was closed
      "too_soon"    - a second tap right after checking in, ignored
      "unchanged"   - already closed for the day, no-op

    One transaction around a get_or_create, so two simultaneous first punches
    (a double tap, or a PWA retry) end up as one record instead of one of them
    failing on the unique constraint.
    """
    moment = moment or timezone.now()
    day = timezone.localdate(moment)

    with transaction.atomic():
        record, created = AttendanceRecord.objects.select_for_update().get_or_create(
            company=company,
            user=user,
            date=day,
            defaults={"check_in": moment, "notes": notes},
        )
        if created:
            return record, "checked_in"

        if record.check_in is None:
            record.check_in = moment
            if notes:
                record.notes = notes
            record.save()
            return record, "checked_in"

        if record.check_out is None:
            if timedelta(0) <= moment - record.check_in < MIN_PUNCH_GAP:
                return record, "too_soon"
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
        constraints = [
            models.UniqueConstraint(fields=["company"], name="one_work_shift_per_company"),
        ]
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
