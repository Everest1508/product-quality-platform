from datetime import date, datetime, time, timedelta
from decimal import Decimal
import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.attendance import service
from apps.attendance.models import AttendanceRecord, month_bounds, punch
from apps.dashboards.models import ActivityLog

User = get_user_model()


def make_user(username, company, role):
    user = User.objects.create_user(username, f"{username}@test.local", "pass1234")
    from apps.accounts.models import Membership

    Membership.objects.create(user=user, company=company, role=role)
    return user


class AttendanceTestBase(TestCase):
    def setUp(self):
        from apps.accounts.models import Company

        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other_company = Company.objects.create(name="Other", slug="other")

        self.owner = make_user("owner", self.company, "owner")
        self.dev = make_user("dev", self.company, "developer")
        self.viewer = make_user("viewer", self.company, "viewer")
        self.outsider = make_user("outsider", self.other_company, "owner")

        self.client = Client()


class PunchToggleTest(AttendanceTestBase):
    def test_first_punch_creates_record_with_check_in_only(self):
        record, action = punch(self.company, self.dev)

        self.assertEqual(action, "checked_in")
        self.assertIsNotNone(record.check_in)
        self.assertIsNone(record.check_out)
        self.assertTrue(record.is_open)
        self.assertEqual(record.date, timezone.localdate())

    def test_second_punch_closes_the_day(self):
        punch(self.company, self.dev, moment=timezone.now() - timedelta(hours=4))
        record, action = punch(self.company, self.dev, moment=timezone.now())

        self.assertEqual(action, "checked_out")
        self.assertIsNotNone(record.check_out)
        self.assertTrue(record.is_complete)
        self.assertEqual(record.worked_minutes, 240)

    def test_third_punch_same_day_is_a_noop(self):
        punch(self.company, self.dev, moment=timezone.now() - timedelta(minutes=3))
        punch(self.company, self.dev)
        record, action = punch(self.company, self.dev)

        self.assertEqual(action, "unchanged")
        self.assertEqual(AttendanceRecord.objects.filter(company=self.company, user=self.dev).count(), 1)

    def test_check_out_never_precedes_check_in(self):
        now = timezone.now()
        record, action = punch(
            self.company, self.dev, moment=now, notes=""
        )
        # Simulate a clock skew: punching out with an earlier timestamp.
        record.check_out = record.check_in - timedelta(hours=1)
        record.save()
        self.assertEqual(record.worked_minutes, 0)


class PunchClampTest(AttendanceTestBase):
    def test_punch_clamps_checkout_to_checkin(self):
        now = timezone.now()
        record, _ = punch(self.company, self.dev, moment=now)
        record.check_out = now - timedelta(minutes=30)
        record.save()
        record.refresh_from_db()
        # worked_minutes floors at zero rather than going negative.
        self.assertEqual(record.worked_minutes, 0)


class DurationTest(AttendanceTestBase):
    def test_worked_minutes_and_hours(self):
        now = timezone.now()
        record, _ = punch(self.company, self.dev, moment=now - timedelta(hours=7, minutes=30))
        record.check_out = now
        record.save()

        self.assertEqual(record.worked_minutes, 450)
        self.assertEqual(record.worked_hours, Decimal("7.50"))
        self.assertEqual(record.worked_formatted, "7h 30m")

    def test_open_record_has_zero_worked_minutes(self):
        record, _ = punch(self.company, self.dev)
        self.assertEqual(record.worked_minutes, 0)
        self.assertEqual(record.worked_hours, Decimal("0.00"))

    def test_no_record_at_all(self):
        record = AttendanceRecord(company=self.company, user=self.dev)
        self.assertFalse(record.is_open)
        self.assertFalse(record.is_complete)
        self.assertEqual(record.worked_minutes, 0)
        self.assertEqual(record.elapsed_formatted, "N/A")


class OnePunchPerDayTest(AttendanceTestBase):
    def test_unique_constraint_blocks_duplicate_day(self):
        from django.db import IntegrityError, transaction

        now = timezone.now()
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=now.date(), check_in=now
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttendanceRecord.objects.create(
                    company=self.company, user=self.dev, date=now.date(), check_in=now
                )

    def test_same_user_different_day_allowed(self):
        now = timezone.now()
        punch(self.company, self.dev, moment=now - timedelta(days=1))
        punch(self.company, self.dev, moment=now)
        self.assertEqual(AttendanceRecord.objects.filter(user=self.dev).count(), 2)

    def test_same_day_different_company_allowed(self):
        now = timezone.now()
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=now.date(), check_in=now
        )
        AttendanceRecord.objects.create(
            company=self.other_company, user=self.outsider, date=now.date(), check_in=now
        )
        self.assertEqual(AttendanceRecord.objects.filter(date=now.date()).count(), 2)


class ReportTest(AttendanceTestBase):
    def test_who_is_in_lists_only_open_records(self):
        open_record, _ = punch(self.company, self.dev)
        punch(self.company, self.viewer, moment=timezone.now() - timedelta(minutes=3))
        punch(self.company, self.viewer)  # closes viewer's day

        on_clock = service.get_who_is_in(self.company)
        self.assertEqual([r["user"] for r in on_clock], [self.dev])
        self.assertFalse(on_clock[0]["is_stale"])

    def test_stale_flag_for_forgotten_checkout(self):
        yesterday = timezone.now() - timedelta(days=1)
        punch(self.company, self.dev, moment=yesterday)

        on_clock = service.get_who_is_in(self.company)
        self.assertTrue(on_clock[0]["is_stale"])

    def test_monthly_rows_totals(self):
        now = timezone.now()
        punch(self.company, self.dev, moment=now - timedelta(days=1))
        record = AttendanceRecord.objects.get(user=self.dev)
        record.check_out = record.check_in + timedelta(hours=6)
        record.save()

        rows = service.get_monthly_rows(self.company, now.year, now.month)
        row = next(r for r in rows if r["user"] == self.dev)
        self.assertEqual(row["present_days"], 1)
        self.assertEqual(row["total_minutes"], 360)
        self.assertEqual(row["total_formatted"], "6h 00m")
        self.assertEqual(row["avg_per_day_formatted"], "6h 00m")

    def test_monthly_rows_exclude_other_months(self):
        now = timezone.now()
        other = now.replace(month=1, day=15) if now.month != 1 else now.replace(month=2, day=15)
        punch(self.company, self.dev, moment=other)

        rows = service.get_monthly_rows(self.company, now.year, now.month)
        # Members are always listed, so assert on the minutes rather than on
        # the row count -- another month's punches must contribute nothing.
        self.assertEqual(
            {r["user"].pk for r in rows},
            {self.owner.pk, self.dev.pk, self.viewer.pk},
        )
        self.assertTrue(all(r["total_minutes"] == 0 for r in rows))

    def test_month_grid_covers_every_day(self):
        now = timezone.now()
        grid = service.get_month_grid(self.company, now.year, now.month, self.dev)
        self.assertEqual(len(grid["days"]), 31 if now.month in (1, 3, 5, 7, 8, 10, 12) else 30)
        self.assertEqual(grid["present_days"], 0)

    def test_month_grid_flags_weekends_and_today(self):
        now = timezone.now()
        grid = service.get_month_grid(self.company, now.year, now.month, self.dev)
        today_cells = [d for d in grid["days"] if d["is_today"]]
        self.assertEqual(len(today_cells), 1)
        self.assertTrue(any(d["is_weekend"] for d in grid["days"]))

    def test_empty_month_lists_members_with_zero(self):
        """Every employee appears even with no punches, so nobody vanishes."""
        now = timezone.now()
        rows = service.get_monthly_rows(self.company, now.year, now.month)
        self.assertEqual(
            {r["user"].pk for r in rows},
            {self.owner.pk, self.dev.pk, self.viewer.pk},
        )
        for row in rows:
            self.assertEqual(row["present_days"], 0)
            self.assertEqual(row["total_minutes"], 0)
            self.assertEqual(row["total_formatted"], "0h 00m")
            self.assertEqual(row["avg_per_day_formatted"], "—")

    def test_member_with_no_punches_does_not_change_other_totals(self):
        punch(self.company, self.dev)
        now = timezone.now()
        rows = service.get_monthly_rows(self.company, now.year, now.month)
        dev = next(r for r in rows if r["user"] == self.dev)
        viewer = next(r for r in rows if r["user"] == self.viewer)
        self.assertEqual(dev["present_days"], 1)
        self.assertEqual(viewer["present_days"], 0)


class MonthParsingTest(AttendanceTestBase):
    def test_valid_month_parses(self):
        self.assertEqual(service.parse_month("2026-03"), (2026, 3))

    def test_invalid_month_falls_back_to_today(self):
        today = timezone.localdate()
        for raw in ("garbage", "2026-13", "2026-00", "", None, "2026-1-5-x"):
            self.assertEqual(service.parse_month(raw), (today.year, today.month), raw)

    def test_month_shift_crosses_year_boundary(self):
        self.assertEqual(service.month_shift(2026, 1, -1), (2025, 12))
        self.assertEqual(service.month_shift(2026, 12, 1), (2027, 1))

    def test_month_bounds_are_inclusive(self):
        first, last = service.month_bounds(2026, 2)
        self.assertEqual(first.day, 1)
        self.assertEqual(last.day, 28)

    def test_month_bounds_december(self):
        first, last = service.month_bounds(2026, 12)
        self.assertEqual(first.month, 12)
        self.assertEqual(last.month, 12)
        self.assertEqual(last.day, 31)


class LatePenaltyTest(AttendanceTestBase):
    """The office rule: 10:00 start, 15 min grace, Rs 50 / Rs 100, half day after
    an hour. Bands are stored as minutes-after-start on `WorkShift`, not as
    clock times, so each boundary is a single number to test."""

    def punch_at(self, at, day=None):
        day = day or timezone.localdate()
        return AttendanceRecord.objects.create(
            company=self.company,
            user=self.dev,
            date=day,
            check_in=timezone.make_aware(datetime.combine(day, at)),
            check_out=timezone.make_aware(
                datetime.combine(day, datetime.strptime("19:00", "%H:%M").time())
            ),
        )

    def test_the_default_shift_is_the_office_hours(self):
        shift = service.shift_for(self.company)
        self.assertEqual(shift.start_time, time(10, 0))
        self.assertEqual(shift.end_time, time(18, 30))
        self.assertEqual(shift.break_minutes, 60)
        # 8.5 hours less a 60 minute break.
        self.assertEqual(shift.worked_minutes_per_day, 450)

    def test_a_company_with_no_shift_row_still_gets_one(self):
        from apps.attendance.models import WorkShift

        self.assertFalse(WorkShift.objects.filter(company=self.company).exists())
        self.assertEqual(service.shift_for(self.company).start_time, time(10, 0))

    def test_the_band_boundaries(self):
        shift = service.shift_for(self.company)
        cases = [
            (0, "on_time"),
            (10, "on_time"),
            (15, "on_time"),   # 10:15 is still on time
            (16, "minor"),     # 10:16 is late enough to cost Rs 50
            (30, "minor"),     # 10:30 is the top of the minor band
            (31, "major"),
            (60, "major"),     # 11:00 is still Rs 100
            (61, "half_day"),  # 11:01 costs half a day
        ]
        for minutes, expected in cases:
            with self.subTest(late=minutes):
                self.assertEqual(shift.band_for_late_minutes(minutes), expected)

    def test_early_arrival_is_not_late(self):
        record = self.punch_at(time(8, 15))
        self.assertEqual(service.lateness_for(record), 0)
        self.assertIsNone(service.late_penalty_for(record))

    def test_a_minor_arrival_costs_fifty_with_a_reason(self):
        penalty = service.late_penalty_for(self.punch_at(time(10, 20)))
        self.assertEqual(penalty["band"], "minor")
        self.assertEqual(Decimal(penalty["amount"]), Decimal("50.00"))
        self.assertEqual(penalty["late_minutes"], 20)
        self.assertIn("10:20 AM", penalty["reason"])
        # The date is part of the reason, not only a sibling field.
        self.assertIn(penalty["date"], penalty["reason"])

    def test_a_major_arrival_costs_a_hundred(self):
        penalty = service.late_penalty_for(self.punch_at(time(10, 45)))
        self.assertEqual(penalty["band"], "major")
        self.assertEqual(Decimal(penalty["amount"]), Decimal("100.00"))

    def test_more_than_an_hour_late_is_a_half_day(self):
        penalty = service.late_penalty_for(self.punch_at(time(11, 30)))
        self.assertEqual(penalty["band"], "half_day")
        # Priced in payroll, not here, so the amount is zero by design.
        self.assertEqual(Decimal(penalty["amount"]), Decimal("0"))
        self.assertIn("half day", penalty["reason"])

    def test_no_punch_is_not_lateness(self):
        """A missing arrival has no time to be late with; guessing costs money."""
        record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=timezone.localdate()
        )
        self.assertEqual(service.lateness_for(record), 0)
        self.assertIsNone(service.late_penalty_for(record))

    def test_penalties_in_a_period_are_ordered_and_scoped(self):
        from datetime import date as _date

        self.punch_at(time(10, 45), _date(2026, 3, 2))
        self.punch_at(time(10, 20), _date(2026, 3, 3))
        self.punch_at(time(10, 0), _date(2026, 3, 4))  # on time
        self.punch_at(time(11, 30), _date(2026, 3, 9))  # outside the window
        found = service.late_penalties_in_period(
            self.company, self.dev, _date(2026, 3, 1), _date(2026, 3, 5)
        )
        self.assertEqual([f["date"] for f in found], ["2026-03-02", "2026-03-03"])
        self.assertEqual(
            [f["band"] for f in found], ["major", "minor"]
        )

    def test_another_person_and_another_company_are_never_counted(self):
        from apps.attendance.models import WorkShift

        self.punch_at(time(10, 45))
        WorkShift.objects.create(company=self.other_company)  # must not leak
        self.assertEqual(
            service.late_penalties_in_period(
                self.other_company, self.dev, timezone.localdate(),
                timezone.localdate(),
            ),
            [],
        )
        self.assertEqual(
            service.late_penalties_in_period(
                self.company, self.owner, timezone.localdate(),
                timezone.localdate(),
            ),
            [],
        )


class WeekendWorkNotLateTest(TestCase):
    def test_weekend_punch_is_never_late(self):
        from datetime import date, time
        from types import SimpleNamespace
        from apps.attendance.service import lateness_for
        tz = timezone.get_current_timezone()
        for day, expected in ((date(2026, 10, 10), 0), (date(2026, 10, 11), 0), (date(2026, 10, 12), 240)):
            rec = SimpleNamespace(date=day, check_in=timezone.make_aware(datetime.combine(day, time(14, 0)), tz))
            shift = SimpleNamespace(start_time=time(10, 0))
            self.assertEqual(lateness_for(rec, shift), expected)


class PunchNotificationTest(AttendanceTestBase):
    """The receipt in the bell: what it says, and in whose time."""

    def at(self, hour, minute=0):
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(hour, minute)))

    def test_the_body_names_lateness_or_the_day(self):
        from apps.attendance.service import punch_notification_body
        from apps.notifications.models import Notification

        late = AttendanceRecord.objects.create(company=self.company, user=self.dev, date=timezone.localdate(), check_in=self.at(10, 45))
        body = punch_notification_body(late, "checked_in", self.company)
        self.assertIn("45 min late", body)
        self.assertIn("₹100", body)  # the number the payslip quotes
        self.assertIn("late fee", body)
        half = AttendanceRecord.objects.create(company=self.company, user=self.owner, date=timezone.localdate(), check_in=self.at(11, 20))
        self.assertIn("counts as a half day", punch_notification_body(half, "checked_in", self.company))
        on_time = AttendanceRecord.objects.create(company=self.company, user=self.viewer, date=timezone.localdate(), check_in=self.at(10, 2))
        self.assertEqual("On time for the 10:00 AM shift.", punch_notification_body(on_time, "checked_in", self.company))
        # And a real check-out writes that body onto the notification.
        extra = make_user("extra", self.company, "developer")
        AttendanceRecord.objects.create(company=self.company, user=extra, date=timezone.localdate(), check_in=timezone.now() - timedelta(hours=2))
        service.punch_user(self.company, extra)
        n = Notification.objects.filter(user=extra, kind="system").order_by("-id").first()
        self.assertIn("worked today", n.body)
        self.assertIn("short of a full", n.body)

    def test_the_message_and_notification_say_the_local_time_not_utc(self):
        """`check_in` is stored UTC; a raw strftime printed the UTC wall clock (a 10:02 IST punch read 04:32 AM)."""
        from apps.notifications.models import Notification

        _record, _action, message = service.punch_user(self.company, self.dev)
        record = AttendanceRecord.objects.get(company=self.company, user=self.dev, date=timezone.localdate())
        ist = timezone.localtime(record.check_in).strftime("%I:%M %p")
        utc = record.check_in.strftime("%I:%M %p")
        self.assertIn(f"Checked in at {ist}.", message)
        if ist != utc:
            self.assertNotIn(f"Checked in at {utc}.", message)
        note = Notification.objects.get(user=self.dev, kind="system")
        self.assertIn(f"Checked in at {ist}.", note.title)

    def test_a_second_tap_is_ignored_and_a_real_check_out_after_the_gap_works(self):
        record, action, _ = service.punch_user(self.company, self.dev)
        self.assertEqual(action, "checked_in")
        self.assertEqual(service.punch_user(self.company, self.dev)[1], "too_soon")
        record.check_in = timezone.now() - timedelta(hours=1)
        record.save()
        self.assertEqual(service.punch_user(self.company, self.dev)[1], "checked_out")

    def test_a_company_has_one_work_shift(self):
        from django.db import IntegrityError, transaction

        from apps.attendance.models import WorkShift

        service.shift_for(self.company)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkShift.objects.create(company=self.company)
        self.assertEqual(service.shift_for(self.company).pk, service.shift_for(self.company).pk)
