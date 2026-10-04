from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from rest_framework.test import APIClient

from apps.accounts.models import Company, Membership
from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback, IngestedTicket
from apps.products.models import APIKey, Product

User = get_user_model()


class IngestionAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.api_key, self.raw_key = APIKey.create_key(product=self.product, name="test")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.raw_key}")

    def test_error_capture(self):
        response = self.client.post("/api/v1/errors/capture/", {
            "message": "TypeError: foo",
            "error_type": "TypeError",
            "stacktrace": "at foo (main.js:10)",
            "page": "/home",
            "version": "1.0.0",
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn("error_group_id", response.data)
        self.assertEqual(ErrorGroup.objects.count(), 1)
        self.assertEqual(ErrorOccurrence.objects.count(), 1)

    def test_error_deduplication(self):
        payload = {"message": "NullError", "error_type": "Error", "stacktrace": "line 5"}
        self.client.post("/api/v1/errors/capture/", payload)
        response = self.client.post("/api/v1/errors/capture/", payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ErrorGroup.objects.count(), 1)
        self.assertEqual(ErrorGroup.objects.first().occurrence_count, 2)
        self.assertEqual(ErrorOccurrence.objects.count(), 2)

    def test_feedback_submission(self):
        response = self.client.post("/api/v1/feedback/", {
            "rating": 4,
            "comment": "Nice app",
            "user_ref": "u-99",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Feedback.objects.count(), 1)

    def test_ticket_ingestion(self):
        response = self.client.post("/api/v1/tickets/", {
            "title": "Login broken",
            "description": "Cannot login",
            "ticket_type": "bug",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(IngestedTicket.objects.count(), 1)

    def test_ticket_status(self):
        ticket_resp = self.client.post("/api/v1/tickets/", {"title": "Test"})
        ticket_id = ticket_resp.data["ticket_id"]
        response = self.client.get(f"/api/v1/tickets/{ticket_id}/status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Test")

    def test_missing_auth(self):
        client = APIClient()
        response = client.post("/api/v1/errors/capture/", {"message": "x"})
        self.assertEqual(response.status_code, 403)

    def test_invalid_key(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer fakekey123")
        response = client.post("/api/v1/errors/capture/", {"message": "x"})
        self.assertEqual(response.status_code, 403)

    def test_revoked_key(self):
        self.api_key.is_active = False
        self.api_key.revoked_at = "2025-01-01T00:00:00Z"
        self.api_key.save()
        response = self.client.post("/api/v1/errors/capture/", {"message": "x"})
        self.assertEqual(response.status_code, 403)


class CrossTenantIngestionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user("alice", "a@test.com", "pass1234")
        self.user_b = User.objects.create_user("bob", "b@test.com", "pass1234")
        self.company_a = Company.objects.create(name="A", slug="a")
        self.company_b = Company.objects.create(name="B", slug="b")
        Membership.objects.create(user=self.user_a, company=self.company_a, role="owner")
        Membership.objects.create(user=self.user_b, company=self.company_b, role="owner")
        self.product_a = Product.objects.create(name="A-App", slug="a-app", company=self.company_a)
        self.product_b = Product.objects.create(name="B-App", slug="b-app", company=self.company_b)
        self.key_a, raw_a = APIKey.create_key(product=self.product_a)
        self.key_b, raw_b = APIKey.create_key(product=self.product_b)
        self.raw_a = raw_a
        self.raw_b = raw_b

    def test_api_key_scoped_to_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.raw_a}")
        self.client.post("/api/v1/errors/capture/", {"message": "Error from A"})
        self.assertEqual(ErrorGroup.objects.filter(product=self.product_a).count(), 1)
        self.assertEqual(ErrorGroup.objects.filter(product=self.product_b).count(), 0)

    def test_key_a_cannot_write_to_product_b(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.raw_a}")
        response = self.client.post("/api/v1/feedback/", {
            "rating": 3,
            "product_id": self.product_b.pk,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Feedback.objects.filter(product=self.product_a).count(), 1)
        self.assertEqual(Feedback.objects.filter(product=self.product_b).count(), 0)


class IngestionHardeningTest(IngestionAPITest):
    """Counting, reopening, scrubbing and rate limiting for the capture API."""

    def capture(self, **extra):
        payload = {"message": "Boom", "error_type": "Error", "stacktrace": "line 1"}
        payload.update(extra)
        return self.client.post("/api/v1/errors/capture/", payload, format="json")

    def test_a_resolved_error_that_fires_again_reopens(self):
        self.capture()
        group = ErrorGroup.objects.get()
        group.status = "resolved"
        group.save(update_fields=["status"])
        response = self.capture()
        group.refresh_from_db()
        self.assertEqual(group.status, "open")
        self.assertEqual(group.occurrence_count, 2)
        self.assertEqual(response.status_code, 201)

    def test_an_ignored_error_stays_ignored(self):
        self.capture()
        group = ErrorGroup.objects.get()
        group.status = "ignored"
        group.save(update_fields=["status"])
        self.capture()
        group.refresh_from_db()
        self.assertEqual(group.status, "ignored")
        self.assertEqual(group.occurrence_count, 2)

    def test_the_count_is_the_databases_not_a_stale_copy(self):
        """A second writer between our read and our write used to be lost."""
        self.capture()
        ErrorGroup.objects.update(occurrence_count=10)
        response = self.capture()
        self.assertEqual(response.data["occurrence_count"], 11)

    def test_secrets_in_a_payload_are_redacted_before_storage(self):
        self.capture(
            request_payload={"user": "ann", "password": "hunter2", "nested": {"api_key": "k", "ok": 1}},
            extra={"Authorization": "Bearer abc", "note": "fine"},
        )
        occurrence = ErrorOccurrence.objects.get()
        self.assertEqual(occurrence.request_payload["password"], "[redacted]")
        self.assertEqual(occurrence.request_payload["nested"]["api_key"], "[redacted]")
        self.assertEqual(occurrence.request_payload["nested"]["ok"], 1)
        self.assertEqual(occurrence.request_payload["user"], "ann")
        self.assertEqual(occurrence.raw_data["Authorization"], "[redacted]")
        self.assertEqual(occurrence.raw_data["note"], "fine")

    def test_the_limit_is_per_key_not_per_ip(self):
        from django.core.cache import cache
        from django.test import override_settings
        from rest_framework.throttling import SimpleRateThrottle

        cache.clear()
        rates = {"apikey": "3/minute"}
        with override_settings():
            with self.settings(REST_FRAMEWORK={
                **__import__("django.conf").conf.settings.REST_FRAMEWORK,
                "DEFAULT_THROTTLE_RATES": rates,
            }):
                SimpleRateThrottle.THROTTLE_RATES = rates
                try:
                    statuses = [self.capture(message=f"m{i}").status_code for i in range(4)]
                    self.assertEqual(statuses, [201, 201, 201, 429])
                    # A different key from the same address has its own budget.
                    other_key, other_raw = APIKey.create_key(product=self.product, name="second")
                    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_raw}")
                    self.assertEqual(self.capture(message="fresh").status_code, 201)
                finally:
                    SimpleRateThrottle.THROTTLE_RATES = {"apikey": "600/minute"}
                    cache.clear()
