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
