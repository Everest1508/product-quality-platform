from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.ingestion.models import ErrorGroup, ErrorOccurrence
from apps.products.models import Product

User = get_user_model()


class ErrorListTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

        self.error1 = ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc123", title="TypeError: foo", severity="high", status="open",
        )
        self.error2 = ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="def456", title="NullError: bar", severity="critical", status="resolved",
        )

    def test_list_shows_all_errors(self):
        response = self.client.get(reverse("errors:error_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page"].object_list), 2)

    def test_filter_by_status(self):
        response = self.client.get(reverse("errors:error_list") + "?status=open")
        self.assertEqual(len(response.context["page"].object_list), 1)
        self.assertEqual(response.context["page"].object_list[0].status, "open")

    def test_filter_by_severity(self):
        response = self.client.get(reverse("errors:error_list") + "?severity=critical")
        self.assertEqual(len(response.context["page"].object_list), 1)
        self.assertEqual(response.context["page"].object_list[0].severity, "critical")

    def test_search(self):
        response = self.client.get(reverse("errors:error_list") + "?q=TypeError")
        self.assertEqual(len(response.context["page"].object_list), 1)
        self.assertIn("TypeError", response.context["page"].object_list[0].title)

    def test_htmx_partial_response(self):
        response = self.client.get(
            reverse("errors:error_list"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("TypeError: foo", content)
        self.assertNotIn("<html", content)

    def test_empty_list(self):
        ErrorGroup.objects.all().delete()
        response = self.client.get(reverse("errors:error_list"))
        self.assertEqual(len(response.context["page"].object_list), 0)


class ErrorDetailTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.error = ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc123", title="Test error", severity="medium", status="open",
        )
        self.client.login(username="alice", password="pass1234")

    def test_detail_page(self):
        response = self.client.get(reverse("errors:error_detail", kwargs={"pk": self.error.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["error_group"], self.error)

    def test_detail_not_found_other_tenant(self):
        other_company = Company.objects.create(name="Other", slug="other")
        other_product = Product.objects.create(name="B", slug="b", company=other_company)
        other_error = ErrorGroup.objects.create(
            product=other_product, company=other_company,
            fingerprint="xyz", title="Other error", severity="low", status="open",
        )
        response = self.client.get(reverse("errors:error_detail", kwargs={"pk": other_error.pk}))
        self.assertEqual(response.status_code, 404)


class ErrorStatusChangeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.error = ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc123", title="Test", severity="medium", status="open",
        )
        self.client.login(username="alice", password="pass1234")

    def test_change_status(self):
        response = self.client.post(
            reverse("errors:error_status", kwargs={"pk": self.error.pk}),
            {"status": "investigating"},
        )
        self.error.refresh_from_db()
        self.assertEqual(self.error.status, "investigating")

    def test_resolve(self):
        response = self.client.post(
            reverse("errors:error_resolve", kwargs={"pk": self.error.pk}),
        )
        self.error.refresh_from_db()
        self.assertEqual(self.error.status, "resolved")

    def test_ignore(self):
        response = self.client.post(
            reverse("errors:error_ignore", kwargs={"pk": self.error.pk}),
        )
        self.error.refresh_from_db()
        self.assertEqual(self.error.status, "ignored")

    def test_htmx_status_change(self):
        response = self.client.post(
            reverse("errors:error_status", kwargs={"pk": self.error.pk}),
            {"status": "resolved"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.error.refresh_from_db()
        self.assertEqual(self.error.status, "resolved")
