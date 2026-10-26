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
