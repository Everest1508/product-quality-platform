"""The Today card on Home: punch in and out from the first page, on any day.

It used to hide Punch in on Saturday and Sunday, so someone opening Home on a
weekend found no way to start their day. The card now follows the company's
weekly off days instead, and a weekly off still lets you punch.
"""
from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance import service
from apps.attendance.models import AttendanceRecord

User = get_user_model()


class HomePunchTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.dev = User.objects.create_user("dev", "dev@test.local", "pass1234")
        Membership.objects.create(user=self.dev, company=self.co, role="developer")
        self.client.login(username="dev", password="pass1234")
        self.home = reverse("dashboards:index")

    # The command palette also says "Punch in or out", so look for the card's own buttons.
    PUNCH_IN, PUNCH_OUT = "Punch in</button>", "Punch out</button>"

    def today_off(self, off):
        service.set_weekly_off(self.co, [str(timezone.localdate().weekday())] if off else [])

    def test_a_working_day_offers_punch_in(self):
        self.today_off(False)
        page = self.client.get(self.home)
        self.assertContains(page, self.PUNCH_IN)
        self.assertContains(page, "Not punched in")
        self.assertContains(page, f'action="{reverse("attendance:punch")}"')

    def test_a_weekly_off_still_offers_punch_in(self):
        self.today_off(True)
        page = self.client.get(self.home)
        self.assertContains(page, self.PUNCH_IN)
        self.assertContains(page, "Weekly off · punch in only if you work")
        self.assertNotContains(page, "Not punched in")

    def test_the_card_says_when_you_started_and_offers_punch_out(self):
        AttendanceRecord.objects.create(
            company=self.co, user=self.dev, date=timezone.localdate(), check_in=timezone.now()
        )
        page = self.client.get(self.home)
        self.assertContains(page, "Working since")
        self.assertContains(page, self.PUNCH_OUT)
        self.assertNotContains(page, self.PUNCH_IN)

    def test_a_finished_day_shows_net_hours_not_the_raw_span(self):
        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        AttendanceRecord.objects.create(
            company=self.co, user=self.dev, date=today,
            check_in=timezone.make_aware(datetime.combine(today, time(10, 0)), tz),
            check_out=timezone.make_aware(datetime.combine(today, time(18, 30)), tz),
        )
        page = self.client.get(self.home)
        # 8h30 on the clock, less the 30 minute break; the raw span would read 8.5h.
        self.assertContains(page, "8h · 10:00 AM → 6:30 PM")
        self.assertNotContains(page, "8.5h")
        self.assertNotContains(page, self.PUNCH_IN)
        self.assertNotContains(page, self.PUNCH_OUT)

    def test_punching_from_home_comes_back_to_home_with_a_toast(self):
        res = self.client.post(reverse("attendance:punch"), {"next": self.home}, follow=True)
        self.assertEqual(res.redirect_chain[-1][0], self.home)
        self.assertTrue(AttendanceRecord.objects.filter(company=self.co, user=self.dev, check_in__isnull=False).exists())
        self.assertContains(res, 'id="toast-seed"')
        self.assertContains(res, "Checked in at")
        self.assertContains(res, "Working since")

    def test_a_next_that_leaves_the_site_is_ignored(self):
        for bad in ("//evil.example/", "https://evil.example/", "/\\evil.example"):
            with self.subTest(next=bad):
                AttendanceRecord.objects.all().delete()
                res = self.client.post(reverse("attendance:punch"), {"next": bad})
                self.assertRedirects(res, reverse("attendance:my_attendance"), fetch_redirect_response=False)

    def test_a_punch_without_next_still_lands_on_attendance(self):
        res = self.client.post(reverse("attendance:punch"))
        self.assertRedirects(res, reverse("attendance:my_attendance"), fetch_redirect_response=False)
