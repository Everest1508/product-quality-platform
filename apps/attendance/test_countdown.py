import re
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance import service
from apps.attendance.models import AttendanceRecord

User = get_user_model()


class PunchCountdownTest(TestCase):
    """No ring: plain time before check-in, a live countdown after it."""

    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.user = User.objects.create_user("emp", "e@t.local", "pass1234")
        Membership.objects.create(user=self.user, company=self.company, role="developer")
        self.client.login(username="emp", password="pass1234")
        self.shift = service.shift_for(self.company)

    def page(self):
        return self.client.get(reverse("attendance:my_attendance"))

    def hero(self):
        """Just the state card, so the page's logo and favicon do not count."""
        body = self.page().content.decode()
        return body.split('class="punch-hero', 1)[1].split('class="punch-week"', 1)[0]

    def punch_in(self, minutes_ago):
        check_in = timezone.now() - timedelta(minutes=minutes_ago)
        return AttendanceRecord.objects.create(
            company=self.company, user=self.user, date=timezone.localdate(), check_in=check_in
        )

    def test_before_check_in_it_shows_the_time_and_no_circle(self):
        body = self.hero()
        self.assertIn('x-text="clock"', body)
        self.assertIn("punch-big", body)
        self.assertNotIn("punch-ring", body)
        self.assertNotIn("<circle", body)

    def test_after_check_in_it_counts_down_to_the_end_of_the_full_day(self):
        record = self.punch_in(minutes_ago=60)
        res = self.page()
        total = timedelta(minutes=self.shift.worked_minutes_per_day + self.shift.break_minutes)
        self.assertEqual(res.context["day_end_ms"], int((record.check_in + total).timestamp() * 1000))
        body = self.hero()
        self.assertIn("left in your day", body)
        self.assertNotIn("punch-ring", body)
        self.assertNotIn("<circle", body)

    def test_the_countdown_has_a_value_before_javascript_runs(self):
        self.punch_in(minutes_ago=60)
        body = self.page().content.decode()
        match = re.search(r'x-text="dayDone \? extra : countdown">(\d+)h (\d{2})m (\d{2})s<', body)
        self.assertIsNotNone(match, "the server renders the first countdown value")
        left = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
        full_day = (self.shift.worked_minutes_per_day + self.shift.break_minutes) * 60
        self.assertAlmostEqual(left, full_day - 3600, delta=15)

    def test_the_finish_time_is_stated(self):
        record = self.punch_in(minutes_ago=30)
        total = timedelta(minutes=self.shift.worked_minutes_per_day + self.shift.break_minutes)
        label = f"{timezone.localtime(record.check_in + total):%I:%M %p}".lstrip("0")
        self.assertIn(f"Full day done at <b>{label}</b>", self.page().content.decode())

    def test_the_elapsed_time_is_still_there(self):
        self.punch_in(minutes_ago=75)
        self.assertRegex(self.page().content.decode(), r'x-text="elapsed">1h 1\dm<')

    def test_a_day_past_its_end_switches_to_time_over(self):
        self.punch_in(minutes_ago=self.shift.worked_minutes_per_day + self.shift.break_minutes + 30)
        res = self.page()
        self.assertEqual(res.context["remaining_formatted"], "0h 00m 00s")
        self.assertIn("past your full day", res.content.decode())

    def test_the_countdown_is_not_announced_as_it_ticks(self):
        self.punch_in(minutes_ago=10)
        self.assertNotIn("aria-live", self.page().content.decode())

    def test_after_check_out_it_shows_hours_worked_not_a_ring(self):
        start = timezone.now() - timedelta(hours=9)
        AttendanceRecord.objects.create(
            company=self.company, user=self.user, date=timezone.localdate(),
            check_in=start, check_out=start + timedelta(hours=9),
        )
        body = self.hero()
        self.assertIn("worked today", body)
        self.assertNotIn("punch-ring", body)
        self.assertNotIn("<circle", body)
