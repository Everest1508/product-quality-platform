from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Company, ExternalAccessToken, Membership
from apps.dashboards.models import ActivityLog
from apps.dsr.models import DSREntry
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


def client_for(user):
    _, token = ExternalAccessToken.create_token(user, client_id="dsr-mcp")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c


class TicketApiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        self.admin = User.objects.create_user("adm", "a@t.local", "pass1234")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        Membership.objects.create(user=self.admin, company=self.company, role="admin")
        self.mine = Product.objects.create(company=self.company, name="Billing", slug="billing", key="BIL")
        self.secret = Product.objects.create(company=self.company, name="Vault", slug="vault", key="VLT")
        ProductAccess.objects.create(company=self.company, product=self.mine, user=self.dev)
        self.api = client_for(self.dev)
        self.url = reverse("dsr_api:tickets")

    def make(self, product, title, **kw):
        return Ticket.objects.create(company=self.company, product=product, title=title, created_by=self.admin, **kw)

    def create(self, **data):
        body = {"title": "Login broken", "product": self.mine.pk}
        body.update(data)
        return self.api.post(self.url, body, format="json")

    def test_auth_required(self):
        self.assertEqual(APIClient().get(self.url).status_code, 403)
        self.assertEqual(APIClient().post(self.url, {}, format="json").status_code, 403)

    def test_list_filters(self):
        a = self.make(self.mine, "Fix invoice PDF")
        self.make(self.mine, "Old thing", status="closed")
        self.make(self.secret, "Vault leak")
        self.assertEqual([t["id"] for t in self.api.get(self.url).json()], [a.pk])
        both = self.api.get(self.url, {"status": "all"}).json()
        self.assertEqual(len(both), 2)
        self.assertEqual([t["id"] for t in self.api.get(self.url, {"q": "INVOICE"}).json()], [a.pk])
        self.assertEqual([t["id"] for t in self.api.get(self.url, {"q": a.key}).json()], [a.pk])
        item = self.api.get(self.url, {"product": self.mine.pk}).json()[0]
        self.assertEqual(item["url"], f"/tickets/{a.pk}/")
        self.assertEqual((item["product_name"], item["assigned_to_me"]), ("Billing", False))
        self.assertEqual(self.api.get(self.url, {"product": self.secret.pk, "status": "all"}).json(), [])

    def test_create(self):
        res = self.create(description="boom")
        self.assertEqual(res.status_code, 201)
        item = res.json()
        self.assertEqual((item["key"], item["assigned_to_me"], item["status"]), ("BIL-001", True, "open"))
        t = Ticket.objects.get()
        self.assertEqual(t.assigned_to, self.dev)
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_created", target_object_id=t.pk).exists())

    def test_create_unassigned(self):
        self.assertFalse(self.create(assign_to_me=False).json()["assigned_to_me"])

    def test_inaccessible_product_and_bad_choices(self):
        for data in ({"product": self.secret.pk}, {"ticket_type": "x"}, {"priority": "x"}, {"status": "x"}, {"title": " "}):
            res = self.create(**data)
            self.assertEqual(res.status_code, 400, data)
            self.assertIn("fields", res.json())
        self.assertFalse(Ticket.objects.exists())

    def test_duplicate_open_title_is_409(self):
        first = self.create().json()
        res = self.create(title="LOGIN BROKEN")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["existing"]["id"], first["id"])
        self.assertEqual(Ticket.objects.count(), 1)

    def test_resolved_status_logs_the_dsr(self):
        res = self.create(status="resolved")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "resolved")
        self.assertEqual(DSREntry.objects.get(user=self.dev).ticket_id, res.json()["id"])


class ProjectApiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        self.admin = User.objects.create_user("adm", "a@t.local", "pass1234")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        Membership.objects.create(user=self.admin, company=self.company, role="admin")
        self.url = reverse("dsr_api:projects")

    def test_admin_creates_and_duplicates_conflict(self):
        api = client_for(self.admin)
        res = api.post(self.url, {"name": "AU Marketing"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual((res.json()["key"], res.json()["name"]), ("AUM", "AU Marketing"))
        self.assertTrue(ActivityLog.objects.filter(event_type="product_created").exists())
        by_name = api.post(self.url, {"name": "au marketing"}, format="json")
        by_key = api.post(self.url, {"name": "Other", "key": "aum"}, format="json")
        for r in (by_name, by_key):
            self.assertEqual(r.status_code, 409)
            self.assertEqual(r.json()["existing"]["id"], res.json()["id"])
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(api.post(self.url, {"name": "X", "key": "1"}, format="json").status_code, 400)

    def test_developer_is_refused(self):
        res = client_for(self.dev).post(self.url, {"name": "Nope"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertFalse(Product.objects.exists())

    def test_me_says_who_can_create_projects(self):
        me = lambda u: client_for(u).get(reverse("dsr_api:me")).json()["can_create_projects"]
        self.assertEqual((me(self.admin), me(self.dev)), (True, False))
