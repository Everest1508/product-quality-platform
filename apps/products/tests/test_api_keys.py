from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.ingestion import docs
from apps.ingestion.serializers import ErrorCaptureSerializer, FeedbackSerializer, TicketIngestSerializer
from apps.products.models import APIKey, Product, ProductAccess

User = get_user_model()


def make(username, company, role):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = make("owner", self.company, "owner")
        self.dev = make("dev", self.company, "developer")
        self.support = make("support", self.company, "support")
        self.viewer = make("viewer", self.company, "viewer")
        self.nodev = make("nodev", self.company, "developer")  # no access to the product
        self.outsider = make("outsider", self.other, "owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.theirs = Product.objects.create(name="Theirs", slug="theirs", company=self.other)
        for u in (self.dev, self.support, self.viewer):
            ProductAccess.objects.create(company=self.company, product=self.product, user=u)

    def login(self, name):
        self.client.login(username=name, password="pass1234")


class KeyStateTest(Base):
    def test_a_new_key_is_active_and_validates(self):
        key, raw = APIKey.create_key(self.product, "k")
        self.assertEqual((key.state, key.is_usable), ("active", True))
        self.assertEqual(APIKey.validate_key(raw), key)

    def test_a_key_with_a_future_end_still_works(self):
        key, raw = APIKey.create_key(self.product, "k")
        APIKey.objects.filter(pk=key.pk).update(expires_at=timezone.now() + timedelta(hours=3))
        key.refresh_from_db()
        self.assertEqual(key.state, "expiring")
        self.assertIsNotNone(APIKey.validate_key(raw))

    def test_a_key_past_its_end_is_refused(self):
        key, raw = APIKey.create_key(self.product, "k")
        APIKey.objects.filter(pk=key.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        key.refresh_from_db()
        self.assertEqual((key.state, key.is_usable), ("expired", False))
        self.assertIsNone(APIKey.validate_key(raw))

    def test_an_expired_key_is_refused_by_the_api_and_is_not_marked_used(self):
        key, raw = APIKey.create_key(self.product, "k")
        APIKey.objects.filter(pk=key.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        self.assertEqual(api.post("/api/v1/errors/capture/", {"message": "x"}, format="json").status_code, 403)  # the API answers 403 for any bad key
        key.refresh_from_db()
        self.assertIsNone(key.last_used_at)

    def test_revoked_wins_over_everything(self):
        key, raw = APIKey.create_key(self.product, "k")
        APIKey.objects.filter(pk=key.pk).update(is_active=False, revoked_at=timezone.now())
        key.refresh_from_db()
        self.assertEqual(key.state, "revoked")
        self.assertIsNone(APIKey.validate_key(raw))
