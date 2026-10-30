from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User
from apps.leads.models import Lead, LeadWebhook

GOOD = {"full_name": "Test", "email": "t@example.com", "company": "Acme", "need": "CRM", "details": "hello"}


class LeadWebhookTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme")
        self.hook = LeadWebhook.objects.create(company=self.company)
        self.url = reverse("lead_webhook", args=[self.hook.token])

    def test_json_post_creates_lead(self):
        r = self.client.post(self.url, GOOD, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Lead.objects.get().company, self.company)

    def test_phone_is_stored_as_typed(self):
        r = self.client.post(self.url, {**GOOD, "phone": "+91 98765 43210"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Lead.objects.get().phone, "+91 98765 43210")

    def test_phone_is_optional_and_may_be_empty(self):
        self.assertEqual(self.client.post(self.url, {**GOOD, "phone": ""}, content_type="application/json").status_code, 201)
        self.assertEqual(self.client.post(self.url, GOOD, content_type="application/json").status_code, 201)
        self.assertEqual(set(Lead.objects.values_list("phone", flat=True)), {""})

    def test_form_post_creates_lead(self):
        self.assertEqual(self.client.post(self.url, GOOD).status_code, 201)

    def test_missing_required_fields_rejected(self):
        r = self.client.post(self.url, {"full_name": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Lead.objects.count(), 0)

    def test_bad_token_404(self):
        self.assertEqual(self.client.post(reverse("lead_webhook", args=["nope"]), GOOD).status_code, 404)

    def test_only_admins_see_list(self):
        for role, code in (("developer", 403), ("admin", 200)):
            u = User.objects.create_user(username=role, email=f"{role}@x.com", password="p")
            Membership.objects.create(user=u, company=self.company, role=role)
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("leads:lead_list")).status_code, code)

    def test_rotate_invalidates_old_url(self):
        u = User.objects.create_user(username="o", email="o@x.com", password="p")
        Membership.objects.create(user=u, company=self.company, role="owner")
        self.client.force_login(u)
        self.client.post(reverse("leads:webhook_rotate"))
        self.assertEqual(self.client.post(self.url, GOOD).status_code, 404)


class LeadNotifyTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme")
        self.hook = LeadWebhook.objects.create(company=self.company)
        self.owner = User.objects.create_user(username="o", email="o@x.com", password="p")
        self.dev = User.objects.create_user(username="d", email="d@x.com", password="p")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")

    def test_admins_notified_then_cleared_on_visit(self):
        from apps.notifications.models import Notification
        self.client.post(reverse("lead_webhook", args=[self.hook.token]), GOOD)
        self.assertEqual(Notification.objects.filter(user=self.owner, kind="lead").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.dev).count(), 0)
        self.client.force_login(self.owner)
        r = self.client.get(reverse("dashboards:index"), follow=True)
        self.assertEqual(r.context["nav_new_leads"], 1)
        r = self.client.get(reverse("leads:lead_list"))
        self.assertEqual(r.context["nav_new_leads"], 0)


class LeadFlowTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = User.objects.create_user(username="o", email="o@x.com", password="p")
        self.dev = User.objects.create_user(username="d", email="d@x.com", password="p")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.lead = Lead.objects.create(company=self.company, full_name="Asha Rao", email="a@x.com",
                                        company_name="Rao Textiles", details="Need an ERP")
        self.client.force_login(self.owner)
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()

    def url(self, name):
        return reverse(f"leads:{name}", args=[self.lead.pk])

    def test_log_status_and_convert(self):
        self.client.post(self.url("lead_log"), {"text": "Called, wants a demo"})
        self.client.post(self.url("lead_status"), {"status": "contacted"})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "contacted")
        self.assertEqual([l.kind for l in self.lead.logs.all()], ["status", "note"])

        self.client.post(self.url("lead_convert"))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "converted")
        self.assertEqual(self.lead.product.name, "Rao Textiles")
        self.assertEqual(self.lead.product.company, self.company)
        self.assertEqual(self.lead.logs.filter(kind="converted").count(), 1)
        self.assertContains(self.client.get(self.url("lead_detail")), "Open project")

    def test_converting_twice_makes_one_project(self):
        from apps.products.models import Product
        self.client.post(self.url("lead_convert"))
        self.client.post(self.url("lead_convert"))
        self.client.post(self.url("lead_status"), {"status": "converted"})
        self.assertEqual(Product.objects.filter(company=self.company).count(), 1)

    def test_name_clash_gets_a_number(self):
        from apps.products.models import Product
        Product.objects.create(company=self.company, name="Rao Textiles", slug="rao-textiles")
        self.client.post(self.url("lead_convert"))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.product.name, "Rao Textiles 2")

    def test_status_dropdown_can_convert(self):
        self.client.post(self.url("lead_status"), {"status": "converted"})
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.product_id)

    def test_admin_only(self):
        self.client.force_login(self.dev)
        for name in ("lead_detail",):
            self.assertEqual(self.client.get(self.url(name)).status_code, 403)
        for name in ("lead_log", "lead_status", "lead_convert"):
            self.assertEqual(self.client.post(self.url(name), {"text": "x", "status": "lost"}).status_code, 403)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "new")

    def test_other_companys_lead_is_404(self):
        theirs = Lead.objects.create(company=self.other, full_name="X", email="x@x.com", details="d")
        self.assertEqual(self.client.get(reverse("leads:lead_detail", args=[theirs.pk])).status_code, 404)
