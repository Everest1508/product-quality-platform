from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership, User
from apps.notifications.models import Notification
from apps.products.models import Product
from apps.tickets.models import Ticket, TicketComment


class TopbarFeaturesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@t.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_punching_toasts_and_leaves_a_receipt_in_the_bell(self):
        resp = self.client.post(reverse("attendance:punch"), HTTP_HX_REQUEST="true")
        self.assertIn("HX-Trigger", resp.headers)
        self.assertIn("Checked in at", resp.headers["HX-Trigger"])
        self.assertTrue(Notification.objects.filter(user=self.user, title__startswith="Checked in at").exists())

    def test_correction_message_shows_the_times_that_were_filled_in(self):
        day = timezone.localdate() - timedelta(days=1)
        resp = self.client.post(
            reverse("attendance:correction_request"),
            {"date": day.isoformat(), "check_in": "09:45", "check_out": "18:30", "reason": "forgot"},
        )
        self.assertEqual(resp.status_code, 302)
        text = " ".join(str(m) for m in get_messages(resp.wsgi_request))
        self.assertIn("In 9:45 AM", text)
        self.assertIn("Out 6:30 PM", text)
        page = self.client.get(reverse("attendance:my_attendance")).content.decode()
        self.assertIn("9:45 AM", page)
        self.assertIn("6:30 PM", page)

    def test_search_reaches_ticket_descriptions_and_comments(self):
        t = Ticket.objects.create(
            company=self.company, product=self.product, title="Plain title",
            description="the zebrafish pipeline is slow", created_by=self.user,
        )
        c = Ticket.objects.create(company=self.company, product=self.product, title="Other", created_by=self.user)
        TicketComment.objects.create(company=self.company, ticket=c, author=self.user, body="narwhal sighting")
        for q, want in (("zebrafish", t), ("narwhal", c)):
            groups = self.client.get("/search/", {"q": q}).json()["groups"]
            urls = [i["url"] for g in groups for i in g["items"]]
            self.assertIn(reverse("tickets:ticket_detail", args=[want.pk]), urls)

    def test_home_has_the_charts(self):
        page = self.client.get(reverse("dashboards:index")).content.decode()
        for marker in ("Hours this week", "Tickets by status", "ch-spark"):
            self.assertIn(marker, page)

    def test_products_page_shows_summary_tiles(self):
        page = self.client.get(reverse("products:product_list")).content.decode()
        self.assertIn("pl-tiles", page)


class FeatureRoundTwoTest(TestCase):
    def setUp(self):
        from datetime import datetime

        self.datetime = datetime
        self.user = User.objects.create_user("alice", "a@t.com", "pass1234")
        self.dev = User.objects.create_user("bob", "b@t.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def _record(self, user, day, at_in, at_out=None):
        from apps.attendance.models import AttendanceRecord

        tz = timezone.get_current_timezone()
        aware = lambda t: timezone.make_aware(self.datetime.combine(day, t), tz)
        return AttendanceRecord.objects.create(
            company=self.company, user=user, date=day, check_in=aware(at_in),
            check_out=aware(at_out) if at_out else None,
        )

    def test_team_week_grid_shows_times_and_lateness(self):
        from datetime import time

        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        self._record(self.dev, monday, time(10, 40), time(18, 30))  # 40 min late: major band
        page = self.client.get(reverse("attendance:team_attendance"), {"view": "week"}).content.decode()
        self.assertIn("tw-table", page)
        self.assertIn("40m late", page)
        self.assertIn("10:40", page)

    def test_idle_punch_panel_carries_the_late_rules_for_the_preview(self):
        page = self.client.get(reverse("attendance:my_attendance")).content.decode()
        self.assertIn("punch-latenote", page)
        self.assertIn("&quot;majorAmt&quot;", page)

    def test_dsr_nudge_after_the_day_ends_and_only_one_bell_line(self):
        from datetime import time

        from apps.dashboards import service as dash

        today = timezone.localdate()
        if today.weekday() >= 5:
            self.skipTest("weekend: no DSR is owed")
        self._record(self.user, today, time(10, 0), time(18, 30))
        attendance = dash._personal_attendance(self.company, self.user, today)
        self.assertTrue(dash._dsr_nudge(self.company, self.user, today, attendance))
        self.assertTrue(dash._dsr_nudge(self.company, self.user, today, attendance))
        self.assertEqual(Notification.objects.filter(user=self.user, title=dash.DSR_NUDGE_TITLE).count(), 1)

    def test_following_a_ticket_notifies_the_follower_on_comments(self):
        ticket = Ticket.objects.create(company=self.company, product=self.product, title="T", created_by=self.user)
        self.client.login(username="bob", password="pass1234")
        self.client.post(reverse("tickets:ticket_follow", args=[ticket.pk]))
        self.assertTrue(ticket.watchers.filter(pk=self.dev.pk).exists())
        self.client.login(username="alice", password="pass1234")
        self.client.post(reverse("tickets:ticket_comment", args=[ticket.pk]), {"body": "hello"})
        self.assertTrue(Notification.objects.filter(user=self.dev, title__contains="commented").exists())
        self.client.login(username="bob", password="pass1234")
        self.client.post(reverse("tickets:ticket_follow", args=[ticket.pk]))
        self.assertFalse(ticket.watchers.filter(pk=self.dev.pk).exists())

    def test_regressed_tab_and_linked_tickets(self):
        from apps.ingestion.models import ErrorGroup

        now = timezone.now()
        common = dict(company=self.company, product=self.product, first_seen=now, last_seen=now)
        back = ErrorGroup.objects.create(title="Came back", fingerprint="a" * 64, regression_count=1, **common)
        ErrorGroup.objects.create(title="Never fixed once", fingerprint="b" * 64, **common)
        ticket = Ticket.objects.create(
            company=self.company, product=self.product, title="Fix it", created_by=self.user, linked_error_group=back
        )
        page = self.client.get(reverse("errors:error_list"), {"regressed": "1"}).content.decode()
        self.assertIn("Came back", page)
        self.assertNotIn("Never fixed once", page)
        detail = self.client.get(reverse("errors:error_detail", args=[back.pk])).content.decode()
        self.assertIn("Linked tickets", detail)
        self.assertIn(ticket.key, detail)

    def test_search_filters_and_snippets(self):
        from apps.core.search import parse_query, snippet

        self.assertEqual(parse_query("in:tickets assignee:me  login bug"), ({"in": "tickets", "assignee": "me"}, "login bug"))
        self.assertIn("lazy", snippet("the quick brown fox jumps over the lazy dog", "lazy"))
        mine = Ticket.objects.create(
            company=self.company, product=self.product, title="Mine", description="the zebrafish pipeline", created_by=self.user
        )
        mine.assignees.add(self.user)
        Ticket.objects.create(company=self.company, product=self.product, title="Not mine", created_by=self.user)
        groups = self.client.get("/search/", {"q": "assignee:me"}).json()["groups"]
        titles = [i["title"] for g in groups for i in g["items"]]
        self.assertTrue(any("Mine" in t for t in titles))
        self.assertFalse(any("Not mine" in t for t in titles))
        hit = self.client.get("/search/", {"q": "in:tickets zebrafish"}).json()["groups"][0]["items"][0]
        self.assertIn("zebrafish", hit["snippet"])
        self.assertEqual([g["label"] for g in self.client.get("/search/", {"q": "in:errors zebrafish"}).json()["groups"]], [])
