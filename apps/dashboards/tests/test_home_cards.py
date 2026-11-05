from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance.models import AttendanceRecord
from apps.dashboards import home_cards
from apps.dashboards.models import ActivityLog
from apps.ingestion.models import ErrorGroup, ErrorOccurrence
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.products.models import Product, ProductAccess

User = get_user_model()


class HomeCardsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.boss = User.objects.create_user("boss", "b@t.local", "pass1234")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        Membership.objects.create(user=self.boss, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.p1 = Product.objects.create(name="One", slug="one", company=self.company)
        self.p2 = Product.objects.create(name="Two", slug="two", company=self.company)
        ProductAccess.objects.create(company=self.company, product=self.p1, user=self.dev)

    def leave(self):
        policy = LeavePolicy.objects.create(company=self.company, name="Casual", max_days_per_year=12)
        start = timezone.localdate() + timedelta(days=3)
        while start.weekday() >= 5:
            start += timedelta(days=1)
        return LeaveRequest.objects.create(company=self.company, user=self.dev, policy=policy,
                                           start_date=start, end_date=start, days=1, status="pending")

    def test_approve_from_home_lands_back_on_home(self):
        lv = self.leave()
        self.client.login(username="boss", password="pass1234")
        res = self.client.post(reverse("leave:decision", args=[lv.pk, "approve"]), {
            "start_date": lv.start_date.isoformat(), "end_date": lv.end_date.isoformat(),
            "split_mode": "auto", "next": reverse("dashboards:index"),
        })
        self.assertRedirects(res, reverse("dashboards:index"), fetch_redirect_response=False)
        lv.refresh_from_db()
        self.assertEqual(lv.status, "approved")

    def test_next_cannot_leave_the_site(self):
        lv = self.leave()
        self.client.login(username="boss", password="pass1234")
        res = self.client.post(reverse("leave:decision", args=[lv.pk, "reject"]), {
            "start_date": lv.start_date.isoformat(), "split_mode": "auto", "next": "//evil.example",
        })
        self.assertEqual(res["Location"], reverse("leave:approvals"))

    def test_approvals_card_is_owner_only_content(self):
        self.leave()
        self.client.login(username="dev", password="pass1234")
        self.assertNotContains(self.client.get(reverse("dashboards:index")), "hm-approve")
        self.client.login(username="boss", password="pass1234")
        self.assertContains(self.client.get(reverse("dashboards:index")), "hm-approve")

    def test_team_board_states(self):
        today = timezone.localdate()
        now = timezone.now()
        AttendanceRecord.objects.create(company=self.company, user=self.dev, date=today, check_in=now)
        board = home_cards.team_board(self.company, today)
        states = {r["user"].username: r["state"] for r in board["rows"]}
        if board["weekly_off"]:
            self.assertEqual(states["boss"], "off")
        else:
            self.assertEqual(states["boss"], "not_in")
        self.assertEqual(states["dev"], "in")
        self.assertEqual(board["counts"]["in"], 1)

    def test_error_pulse_only_counts_what_the_person_can_open(self):
        mine = ErrorGroup.objects.create(company=self.company, product=self.p1, fingerprint="a", title="A")
        theirs = ErrorGroup.objects.create(company=self.company, product=self.p2, fingerprint="b", title="B")
        for g in (mine, theirs, theirs):
            ErrorOccurrence.objects.create(company=self.company, error_group=g)
        self.assertEqual(home_cards.error_pulse(self.dev, self.company)["week"], 1)
        self.assertEqual(home_cards.error_pulse(self.boss, self.company)["week"], 3)

    def test_activity_feed_links_live_tickets_only(self):
        ActivityLog.objects.create(company=self.company, event_type="ticket_created", title="Made one",
                                   target_content_type="ticket", target_object_id=5)
        ActivityLog.objects.create(company=self.company, event_type="ticket_deleted", title="Gone")
        feed = home_cards.activity_feed(self.company)
        self.assertEqual([e.title for e in feed], ["Made one"])
        self.assertTrue(feed[0].link.endswith("/5/"))
