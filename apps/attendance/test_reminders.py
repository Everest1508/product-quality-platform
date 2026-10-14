from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance import reminders
from apps.attendance.models import AttendanceRecord
from apps.notifications import service as notes
from apps.notifications.models import Notification

User = get_user_model()
TODAY = date(2026, 10, 13)  # a Tuesday; the default shift is 10:00 to 18:30 with 15 minutes' grace


def at(day, h, m=0):
    return timezone.make_aware(datetime(day.year, day.month, day.day, h, m), timezone.get_current_timezone())


class ReminderTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Co", slug="co")
        self.ann = User.objects.create_user("ann", password="x")
        Membership.objects.create(user=self.ann, company=self.co, role="developer")
        # Ann used attendance yesterday, so she is someone who gets nudged.
        AttendanceRecord.objects.create(company=self.co, user=self.ann, date=TODAY - timedelta(days=1), check_in=at(TODAY - timedelta(days=1), 10), check_out=at(TODAY - timedelta(days=1), 18))

    def kinds(self):
        return list(Notification.objects.filter(user=self.ann).values_list("kind", flat=True))

    def test_a_check_in_nudge_goes_out_once_after_the_shift_starts(self):
        self.assertEqual(reminders.send(self.co, at(TODAY, 10, 2)), 0)  # too early
        self.assertEqual(reminders.send(self.co, at(TODAY, 10, 10)), 1)
        self.assertEqual(reminders.send(self.co, at(TODAY, 10, 20)), 0)  # already told today
        self.assertEqual(self.kinds(), ["attendance_checkin"])

    def test_no_nudge_once_checked_in_but_a_check_out_nudge_after_the_shift_ends(self):
        AttendanceRecord.objects.create(company=self.co, user=self.ann, date=TODAY, check_in=at(TODAY, 10, 1))
        self.assertEqual(reminders.send(self.co, at(TODAY, 11)), 0)
        self.assertEqual(reminders.send(self.co, at(TODAY, 18, 45)), 1)
        self.assertEqual(self.kinds(), ["attendance_checkout"])

    def test_weekends_leave_and_people_who_never_punch_are_left_alone(self):
        self.assertEqual(reminders.send(self.co, at(date(2026, 10, 17), 10, 10)), 0)  # Saturday
        stranger = User.objects.create_user("zed", password="x")
        Membership.objects.create(user=stranger, company=self.co, role="developer")
        reminders.send(self.co, at(TODAY, 10, 10))
        self.assertFalse(Notification.objects.filter(user=stranger).exists())

    def test_a_muted_kind_sends_nothing_and_dry_run_only_counts(self):
        notes.set_enabled(self.ann, "attendance_checkin", False)
        reminders.send(self.co, at(TODAY, 10, 10))
        self.assertEqual(self.kinds(), [])
        notes.set_enabled(self.ann, "attendance_checkin", True)
        self.assertEqual(reminders.send(self.co, at(TODAY, 10, 10), dry_run=True), 1)
        self.assertEqual(self.kinds(), [])

    def test_the_command_runs(self):
        call_command("send_attendance_reminders", "--dry-run")
