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


class PermissionTest(Base):
    def create(self, name="k", product=None):
        return self.client.post(reverse("products:api_key_create", args=[(product or self.product).pk]), {"name": name})

    def test_owners_and_developers_can_create(self):
        for user in ("owner", "dev"):
            self.login(user)
            self.assertEqual(self.create(user).status_code, 200, user)
        self.assertEqual(self.product.api_keys.count(), 2)

    def test_viewers_and_support_cannot(self):
        for user in ("viewer", "support"):
            self.login(user)
            self.assertEqual(self.create().status_code, 403, user)
        self.assertEqual(self.product.api_keys.count(), 0)

    def test_a_developer_without_access_to_the_product_gets_a_404(self):
        self.login("nodev")
        self.assertEqual(self.create().status_code, 404)

    def test_another_workspaces_product_is_a_404(self):
        self.login("owner")
        self.assertEqual(self.create(product=self.theirs).status_code, 404)

    def test_the_name_is_trimmed_defaulted_and_capped(self):
        self.login("owner")
        self.create("   ")
        self.create("n" * 300)
        names = sorted(self.product.api_keys.values_list("name", flat=True), key=len)
        self.assertEqual(names[0], "default")
        self.assertEqual(len(names[1]), 100)

    def test_revoking_needs_the_same_rights_and_product_access(self):
        key, _ = APIKey.create_key(self.product, "k")
        url = reverse("products:api_key_revoke", args=[key.pk])
        for user, status in (("viewer", 403), ("support", 403), ("nodev", 404)):
            self.login(user)
            self.assertEqual(self.client.post(url).status_code, status, user)
        key.refresh_from_db()
        self.assertTrue(key.is_active)
        self.login("dev")
        self.client.post(url)
        key.refresh_from_db()
        self.assertFalse(key.is_active)

    def test_another_workspaces_key_cannot_be_revoked_or_rotated(self):
        key, _ = APIKey.create_key(self.theirs, "k")
        self.login("owner")
        self.assertEqual(self.client.post(reverse("products:api_key_revoke", args=[key.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("products:api_key_rotate", args=[key.pk])).status_code, 404)


class RotateTest(Base):
    def setUp(self):
        super().setUp()
        self.old, self.old_raw = APIKey.create_key(self.product, "server")
        self.login("owner")

    def rotate(self, grace="1d", key=None):
        return self.client.post(reverse("products:api_key_rotate", args=[(key or self.old).pk]), {"grace": grace}, headers={"HX-Request": "true"})

    def test_it_makes_a_new_key_with_the_same_name_and_shows_it_once(self):
        page = self.rotate().content.decode()
        new = APIKey.objects.exclude(pk=self.old.pk).get()
        self.assertEqual((new.name, new.product), ("server", self.product))
        self.assertTrue(new.is_usable)
        self.assertIn("Copy it now", page)
        self.assertNotIn(new.key_hash, page)

    def test_the_default_grace_keeps_the_old_key_working_for_a_day(self):
        self.rotate()
        self.old.refresh_from_db()
        self.assertEqual(self.old.state, "expiring")
        self.assertAlmostEqual((self.old.expires_at - timezone.now()).total_seconds(), 86400, delta=60)
        self.assertIsNotNone(APIKey.validate_key(self.old_raw))

    def test_a_week_of_grace(self):
        self.rotate("7d")
        self.old.refresh_from_db()
        self.assertAlmostEqual((self.old.expires_at - timezone.now()).total_seconds(), 7 * 86400, delta=60)

    def test_now_revokes_the_old_key_immediately(self):
        self.rotate("now")
        self.old.refresh_from_db()
        self.assertEqual(self.old.state, "revoked")
        self.assertIsNone(APIKey.validate_key(self.old_raw))

    def test_an_unknown_grace_changes_nothing(self):
        self.assertEqual(self.rotate("forever").status_code, 400)
        self.assertEqual(APIKey.objects.count(), 1)

    def test_a_revoked_or_expired_key_cannot_be_rotated(self):
        APIKey.objects.filter(pk=self.old.pk).update(is_active=False, revoked_at=timezone.now())
        self.old.refresh_from_db()
        self.assertEqual(self.rotate().status_code, 400)
        self.assertEqual(APIKey.objects.count(), 1)

    def test_rotating_twice_never_extends_the_old_ends(self):
        self.rotate("1d")
        self.old.refresh_from_db()
        first_end = self.old.expires_at
        self.rotate("7d")
        self.old.refresh_from_db()
        self.assertEqual(self.old.expires_at, first_end)  # the earlier end stands

    def test_the_old_row_is_refreshed_in_place(self):
        page = self.rotate().content.decode()
        self.assertIn(f'hx-swap-oob="outerHTML:#api-key-row-{self.old.pk}"', page)
        self.assertIn("Ends", page)

    def test_it_is_logged(self):
        self.rotate()
        self.assertTrue(ActivityLog.objects.filter(event_type="api_key_rotated", actor=self.owner).exists())

    def test_a_viewer_cannot_rotate(self):
        self.login("viewer")
        self.assertEqual(self.rotate().status_code, 403)
        self.assertEqual(APIKey.objects.count(), 1)


class DetailPageTest(Base):
    def test_viewers_do_not_get_the_create_form_or_buttons(self):
        APIKey.create_key(self.product, "k")
        self.login("viewer")
        page = self.client.get(reverse("products:product_detail", args=[self.product.pk])).content.decode()
        self.assertNotIn("Generate", page)
        self.assertNotIn("Rotate", page)
        self.assertIn("Owners, admins and developers can create and rotate keys", page)

    def test_developers_get_them_and_the_last_used_time(self):
        key, raw = APIKey.create_key(self.product, "k")
        APIKey.validate_key(raw)
        self.login("dev")
        page = self.client.get(reverse("products:product_detail", args=[self.product.pk])).content.decode()
        self.assertIn("Generate", page)
        self.assertIn("Rotate", page)
        self.assertIn("last used", page)


class DocsTest(Base):
    def docs_page(self, user="dev"):
        self.login(user)
        return self.client.get(reverse("products:product_api", args=[self.product.pk]))

    def test_members_with_access_can_read_it(self):
        for user in ("owner", "dev", "viewer"):
            self.assertEqual(self.docs_page(user).status_code, 200, user)

    def test_without_product_access_it_is_a_404(self):
        self.assertEqual(self.docs_page("nodev").status_code, 404)

    def test_another_workspaces_product_is_a_404(self):
        self.login("owner")
        self.assertEqual(self.client.get(reverse("products:product_api", args=[self.theirs.pk])).status_code, 404)

    def test_every_endpoint_and_language_is_there(self):
        page = self.docs_page().content.decode()
        for path in ("/api/v1/errors/capture/", "/api/v1/feedback/", "/api/v1/tickets/", "/api/v1/tickets/{ticket_id}/status/"):
            self.assertIn(path, page)
        for marker in ("curl -X POST", "import requests", "await fetch(", "curl_init("):
            self.assertIn(marker, page)

    def test_snippets_use_a_placeholder_never_a_real_key(self):
        _, raw = APIKey.create_key(self.product, "k")
        page = self.docs_page().content.decode()
        self.assertIn("YOUR_API_KEY", page)
        self.assertNotIn(raw, page)

    def test_the_base_url_is_this_server(self):
        self.assertIn("http://testserver/api/v1/", self.docs_page().content.decode())

    def test_every_serializer_field_is_documented_with_a_note(self):
        for key, serializer in (("errors", ErrorCaptureSerializer), ("feedback", FeedbackSerializer), ("tickets", TicketIngestSerializer)):
            for name in serializer().fields:
                self.assertTrue(docs.FIELD_NOTES[key].get(name), f"{key}.{name} has no note")

    def test_the_field_list_comes_from_the_serializer(self):
        built = {e["key"]: e for e in docs.build("http://x/")}
        names = [f["name"] for f in built["feedback"]["fields"]]
        self.assertEqual(names, list(FeedbackSerializer().fields))
        rating = next(f for f in built["feedback"]["fields"] if f["name"] == "rating")
        self.assertEqual((rating["required"], rating["limits"]), (True, "1 to 5"))

    def test_the_example_requests_are_valid_against_the_real_serializers(self):
        for key, serializer in (("errors", ErrorCaptureSerializer), ("feedback", FeedbackSerializer), ("tickets", TicketIngestSerializer)):
            example = next(e["example"] for e in docs.ENDPOINTS if e["key"] == key)
            s = serializer(data=example)
            self.assertTrue(s.is_valid(), f"{key}: {s.errors}")

    def test_the_docs_list_this_products_keys_without_secrets(self):
        key, raw = APIKey.create_key(self.product, "billing")
        page = self.docs_page().content.decode()
        self.assertIn(key.prefix, page)
        self.assertIn("billing", page)
        self.assertNotIn(key.key_hash, page)

    def test_the_product_sidebar_links_to_it(self):
        self.login("dev")
        page = self.client.get(reverse("products:product_detail", args=[self.product.pk])).content.decode()
        self.assertIn(reverse("products:product_api", args=[self.product.pk]), page)
