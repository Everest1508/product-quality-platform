from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.ingestion.models import ErrorGroup, ErrorOccurrence
from apps.products.models import Product, ProductAccess

User = get_user_model()


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

    def test_dashboard_button_gets_the_badge_back(self):
        response = self.client.post(
            reverse("errors:error_resolve", kwargs={"pk": self.error.pk}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resolved")


class ErrorProductAccessTest(TestCase):
    """A member restricted to certain products must not see or touch error
    groups belonging to products they have no access to."""

    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")

        self.allowed = Product.objects.create(name="Allowed", slug="allowed", company=self.company)
        self.secret = Product.objects.create(name="Secret", slug="secret", company=self.company)
        ProductAccess.objects.create(user=self.dev, product=self.allowed, company=self.company)

        self.allowed_error = ErrorGroup.objects.create(
            product=self.allowed, company=self.company,
            fingerprint="a1", title="Allowed error", severity="high", status="open",
        )
        self.secret_error = ErrorGroup.objects.create(
            product=self.secret, company=self.company,
            fingerprint="s1", title="Secret error", severity="high", status="open",
        )
        self.client.login(username="dev", password="pass1234")

    def test_cannot_open_inaccessible_error(self):
        response = self.client.get(
            reverse("errors:error_detail", kwargs={"pk": self.secret_error.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_resolve_inaccessible_error(self):
        response = self.client.post(
            reverse("errors:error_resolve", kwargs={"pk": self.secret_error.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.secret_error.refresh_from_db()
        self.assertEqual(self.secret_error.status, "open")

    def test_can_resolve_accessible_error(self):
        response = self.client.post(
            reverse("errors:error_resolve", kwargs={"pk": self.allowed_error.pk})
        )
        self.assertIn(response.status_code, (200, 302))
        self.allowed_error.refresh_from_db()
        self.assertEqual(self.allowed_error.status, "resolved")
