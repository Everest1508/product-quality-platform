from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance import corrections, service
from apps.attendance.models import AttendanceCorrection, AttendanceRecord
from apps.dashboards.models import ActivityLog
from apps.notifications.models import Notification

User = get_user_model()


def make(username, company, role):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = make("owner", self.company, "owner")
        self.admin = make("admin", self.company, "admin")
        self.dev = make("dev", self.company, "developer")
        self.outsider = make("outsider", self.other, "owner")
        self.day = timezone.localdate() - timedelta(days=2)

    def ask(self, user=None, day=None, check_in=None, check_out=None, reason="forgot to check out"):
        day = day or self.day
        return corrections.request_correction(user or self.dev, self.company, day, check_in, check_out, reason)

    def record(self, **kw):
        return AttendanceRecord.objects.create(company=self.company, user=kw.pop("user", self.dev), date=kw.pop("date", self.day), **kw)


class RequestRulesTest(Base):
    def test_a_check_out_for_a_day_with_a_check_in_is_accepted(self):
        self.record(check_in=at(self.day, 10))
        c = self.ask(check_out=at(self.day, 18, 30))
        self.assertEqual((c.status, c.original_check_in, c.original_check_out), ("pending", at(self.day, 10), None))

    def test_a_day_with_no_punch_needs_a_check_in(self):
        with self.assertRaisesMessage(corrections.CorrectionError, "check-in time is needed"):
            self.ask(check_out=at(self.day, 18))
        self.assertEqual(self.ask(check_in=at(self.day, 10), check_out=at(self.day, 18)).status, "pending")

    def test_it_needs_a_reason_and_a_time(self):
        self.record(check_in=at(self.day, 10))
        with self.assertRaisesMessage(corrections.CorrectionError, "Say why"):
            self.ask(check_out=at(self.day, 18), reason="  ")
        with self.assertRaisesMessage(corrections.CorrectionError, "check-in time, a check-out time"):
            self.ask()

    def test_today_is_allowed_tomorrow_is_not(self):
        today = timezone.localdate()
        self.record(date=today, check_in=at(today, 0, 1))
        self.assertEqual(self.ask(day=today, check_out=at(today, 0, 2)).status, "pending")
        with self.assertRaisesMessage(corrections.CorrectionError, "already started"):
            self.ask(day=today + timedelta(days=1), check_in=at(today, 9))

    def test_it_cannot_reach_back_past_the_limit(self):
        old = timezone.localdate() - timedelta(days=corrections.MAX_AGE_DAYS + 1)
        with self.assertRaisesMessage(corrections.CorrectionError, "go back"):
            self.ask(day=old, check_in=at(old, 10))

    def test_times_must_belong_to_that_day(self):
        self.record(check_in=at(self.day, 10))
        with self.assertRaisesMessage(corrections.CorrectionError, "has to fall on"):
            self.ask(check_out=at(self.day - timedelta(days=3), 9))

    def test_a_night_shift_may_end_the_next_morning(self):
        self.record(check_in=at(self.day, 22))
        self.assertEqual(self.ask(check_out=at(self.day + timedelta(days=1), 6)).status, "pending")

    def test_check_out_cannot_precede_check_in(self):
        self.record(check_in=at(self.day, 10))
        with self.assertRaisesMessage(corrections.CorrectionError, "before check-in"):
            self.ask(check_out=at(self.day, 9))

    def test_one_open_request_per_day(self):
        self.record(check_in=at(self.day, 10))
        self.ask(check_out=at(self.day, 18))
        with self.assertRaisesMessage(corrections.CorrectionError, "already have a request"):
            self.ask(check_out=at(self.day, 19))

    def test_the_database_enforces_it_too(self):
        self.record(check_in=at(self.day, 10))
        self.ask(check_out=at(self.day, 18))
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceCorrection.objects.create(company=self.company, user=self.dev, date=self.day, reason="x")

    def test_a_decided_request_does_not_block_a_new_one(self):
        self.record(check_in=at(self.day, 10))
        first = self.ask(check_out=at(self.day, 18))
        corrections.decide(first.pk, self.owner, False)
        self.assertEqual(self.ask(check_out=at(self.day, 19)).status, "pending")

    def test_admins_are_told_and_the_requester_is_not(self):
        self.record(check_in=at(self.day, 10))
        self.ask(check_out=at(self.day, 18))
        notified = {n.user.username for n in Notification.objects.filter(kind="correction_request")}
        self.assertEqual(notified, {"owner", "admin"})
        self.assertTrue(ActivityLog.objects.filter(event_type="attendance_correction_requested").exists())

    def test_an_admin_asking_does_not_notify_themselves(self):
        self.record(user=self.admin, check_in=at(self.day, 10))
        self.ask(user=self.admin, check_out=at(self.day, 18))
        self.assertEqual({n.user.username for n in Notification.objects.all()}, {"owner"})


class DecisionTest(Base):
    def setUp(self):
        super().setUp()
        self.rec = self.record(check_in=at(self.day, 10))
        self.c = self.ask(check_out=at(self.day, 18, 30))

    def test_approval_applies_only_the_times_given(self):
        corrections.decide(self.c.pk, self.owner, True, "ok")
        self.rec.refresh_from_db()
        self.assertEqual(self.rec.check_in, at(self.day, 10))  # untouched
        self.assertEqual(self.rec.check_out, at(self.day, 18, 30))
        self.assertTrue(self.rec.is_edited)
        self.assertFalse(self.rec.is_stale)  # the forgotten day is closed now

    def test_approval_records_who_when_and_why(self):
        done = corrections.decide(self.c.pk, self.owner, True, "thanks")
        self.assertEqual((done.status, done.decided_by, done.decision_note), ("approved", self.owner, "thanks"))
        self.assertIsNotNone(done.decided_at)
        self.assertTrue(ActivityLog.objects.filter(event_type="attendance_correction_approved", actor=self.owner).exists())

    def test_the_requester_is_told_the_result(self):
        corrections.decide(self.c.pk, self.owner, True)
        n = Notification.objects.get(user=self.dev, kind="correction_decision")
        self.assertIn("approved", n.title)
        self.assertEqual(n.url, f"/attendance/?month={self.day:%Y-%m}")

    def test_approval_creates_a_missing_day(self):
        day = self.day - timedelta(days=3)
        c = self.ask(day=day, check_in=at(day, 9, 30), check_out=at(day, 17, 30))
        corrections.decide(c.pk, self.owner, True)
        r = AttendanceRecord.objects.get(user=self.dev, date=day)
        self.assertEqual((r.check_in, r.check_out, r.is_edited), (at(day, 9, 30), at(day, 17, 30), True))

    def test_rejection_changes_nothing(self):
        corrections.decide(self.c.pk, self.owner, False, "not that late")
        self.rec.refresh_from_db()
        self.assertIsNone(self.rec.check_out)
        self.assertEqual(AttendanceCorrection.objects.get().status, "rejected")
        self.assertIn("rejected", Notification.objects.get(user=self.dev, kind="correction_decision").title)

    def test_a_developer_cannot_decide(self):
        with self.assertRaisesMessage(corrections.CorrectionError, "Only owners and admins"):
            corrections.decide(self.c.pk, self.dev, True)
        self.assertTrue(AttendanceCorrection.objects.get().is_pending)

    def test_it_cannot_be_decided_twice(self):
        corrections.decide(self.c.pk, self.owner, True)
        with self.assertRaisesMessage(corrections.CorrectionError, "already been dealt with"):
            corrections.decide(self.c.pk, self.admin, False)

    def test_an_admin_cannot_approve_their_own_request_when_another_admin_exists(self):
        self.record(user=self.admin, date=self.day, check_in=at(self.day, 10))
        mine = self.ask(user=self.admin, check_out=at(self.day, 18))
        with self.assertRaisesMessage(corrections.CorrectionError, "Another owner or admin"):
            corrections.decide(mine.pk, self.admin, True)
        self.assertEqual(corrections.decide(mine.pk, self.owner, True).status, "approved")

    def test_a_lone_owner_can_decide_their_own(self):
        solo = Company.objects.create(name="Solo", slug="solo")
        boss = make("boss", solo, "owner")
        AttendanceRecord.objects.create(company=solo, user=boss, date=self.day, check_in=at(self.day, 10))
        c = corrections.request_correction(boss, solo, self.day, None, at(self.day, 18), "forgot")
        self.assertEqual(corrections.decide(c.pk, boss, True).status, "approved")

    def test_approval_checks_again_against_the_record_as_it_is_now(self):
        AttendanceRecord.objects.filter(pk=self.rec.pk).update(check_in=at(self.day, 19))
        with self.assertRaisesMessage(corrections.CorrectionError, "before check-in"):
            corrections.decide(self.c.pk, self.owner, True)
        self.assertTrue(AttendanceCorrection.objects.get().is_pending)

    def test_the_requester_can_cancel_but_nobody_else(self):
        with self.assertRaisesMessage(corrections.CorrectionError, "your own"):
            corrections.cancel(self.c.pk, self.admin)
        corrections.cancel(self.c.pk, self.dev)
        self.assertEqual(AttendanceCorrection.objects.get().status, "cancelled")
        with self.assertRaisesMessage(corrections.CorrectionError, "already been dealt with"):
            corrections.cancel(self.c.pk, self.dev)


class ViewsTest(Base):
    def setUp(self):
        super().setUp()
        self.rec = self.record(check_in=at(self.day, 10))

    def post_request(self, user="dev", **extra):
        self.client.login(username=user, password="pass1234")
        data = {"date": self.day.isoformat(), "check_out": "18:30", "reason": "forgot"}
        data.update(extra)
        return self.client.post(reverse("attendance:correction_request"), data)

    def test_the_form_prefills_the_day_and_shows_what_is_recorded(self):
        self.client.login(username="dev", password="pass1234")
        page = self.client.get(reverse("attendance:correction_request"), {"date": self.day.isoformat()})
        self.assertContains(page, f'value="{self.day:%Y-%m-%d}"')
        self.assertContains(page, "10:00 AM")

    def test_a_valid_request_is_saved_and_the_person_is_sent_back(self):
        response = self.post_request()
        self.assertRedirects(response, reverse("attendance:my_attendance"))
        c = AttendanceCorrection.objects.get()
        self.assertEqual((c.user, c.company, c.requested_check_out), (self.dev, self.company, at(self.day, 18, 30)))

    def test_after_midnight_puts_the_check_out_on_the_next_day(self):
        self.record(date=self.day - timedelta(days=1), check_in=at(self.day - timedelta(days=1), 22))
        self.post_request(date=(self.day - timedelta(days=1)).isoformat(), check_out="06:00", out_next_day="1")
        self.assertEqual(AttendanceCorrection.objects.get().requested_check_out, at(self.day, 6))

    def test_a_bad_request_shows_the_message_and_keeps_what_was_typed(self):
        response = self.post_request(reason="")
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Say why", status_code=400)
        self.assertContains(response, 'value="18:30"', status_code=400)
        self.assertEqual(AttendanceCorrection.objects.count(), 0)

    def test_garbage_times_are_a_message_not_a_crash(self):
        self.assertEqual(self.post_request(check_out="soon").status_code, 400)

    def test_the_queue_is_for_owners_and_admins(self):
        self.post_request()
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(self.client.get(reverse("attendance:corrections")).status_code, 403)
        self.client.login(username="owner", password="pass1234")
        page = self.client.get(reverse("attendance:corrections"))
        self.assertContains(page, "forgot")
        self.assertContains(page, "6:30 PM")

    def test_an_owner_approves_through_the_queue(self):
        self.post_request()
        c = AttendanceCorrection.objects.get()
        self.client.login(username="owner", password="pass1234")
        self.client.post(reverse("attendance:correction_decision", args=[c.pk, "approve"]), {"note": "ok"})
        self.rec.refresh_from_db()
        self.assertEqual(self.rec.check_out, at(self.day, 18, 30))

    def test_a_developer_cannot_decide_through_the_url(self):
        self.post_request()
        c = AttendanceCorrection.objects.get()
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(self.client.post(reverse("attendance:correction_decision", args=[c.pk, "approve"])).status_code, 403)
        c.refresh_from_db()
        self.assertTrue(c.is_pending)

    def test_another_workspaces_request_is_a_404(self):
        c = AttendanceCorrection.objects.create(company=self.other, user=self.outsider, date=self.day, reason="x")
        self.client.login(username="owner", password="pass1234")
        self.assertEqual(self.client.post(reverse("attendance:correction_decision", args=[c.pk, "approve"])).status_code, 404)

    def test_an_unknown_action_is_refused(self):
        self.post_request()
        c = AttendanceCorrection.objects.get()
        self.client.login(username="owner", password="pass1234")
        self.assertEqual(self.client.post(reverse("attendance:correction_decision", args=[c.pk, "delete"])).status_code, 403)

    def test_cancelling_someone_elses_request_is_a_404(self):
        self.post_request()
        c = AttendanceCorrection.objects.get()
        self.client.login(username="admin", password="pass1234")
        self.assertEqual(self.client.post(reverse("attendance:correction_cancel", args=[c.pk])).status_code, 404)

    def test_the_sidebar_counts_what_is_waiting_for_admins_only(self):
        self.post_request()
        self.client.login(username="owner", password="pass1234")
        page = self.client.get(reverse("attendance:corrections")).content.decode()
        self.assertIn('data-label="Corrections"', page)
        self.assertRegex(page, r'Corrections</span>\s*<span class="side-badge">1</span>')
        self.client.login(username="dev", password="pass1234")
        self.assertNotIn('data-label="Corrections"', self.client.get(reverse("attendance:my_attendance")).content.decode())

    def test_my_attendance_lists_my_requests_and_offers_the_form(self):
        self.post_request()
        page = self.client.get(reverse("attendance:my_attendance")).content.decode()
        self.assertIn("Your correction requests", page)
        self.assertIn("Request a correction", page)

    def test_the_forgotten_day_warning_links_to_the_form_for_that_day(self):
        self.client.login(username="dev", password="pass1234")
        page = self.client.get(reverse("attendance:my_attendance")).content.decode()
        self.assertIn(f"?date={self.day:%Y-%m-%d}", page)

    def test_the_admin_edit_still_applies_the_same_rules(self):
        self.client.login(username="owner", password="pass1234")
        far = self.day + timedelta(days=1)
        self.client.post(reverse("attendance:attendance_edit", args=[self.rec.pk]), {
            "check_in": f"{far:%Y-%m-%d}T10:00", "check_out": "",
        })
        self.rec.refresh_from_db()
        self.assertEqual(timezone.localtime(self.rec.check_in).date(), self.day)
