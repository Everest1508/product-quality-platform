from datetime import timedelta

from django.test import Client
from django.utils import timezone

from apps.accounts.models import Membership
from apps.dashboards.models import ActivityLog
from apps.ingestion import docs
from apps.ingestion.serializers import ErrorCaptureSerializer, FeedbackSerializer, TicketIngestSerializer
from apps.products.models import APIKey, Product, ProductAccess, ProductMilestone, ProductVersion
from apps.uiapi.test_tickets import Base, member


class P(Base):
    """Base has owner, dev (access to p_open), p_open, p_hidden, p_foreign (other company)."""

    def setUp(self):
        super().setUp()
        self.viewer = member("viewer", self.acme, "viewer")
        self.support = member("support", self.acme, "support")
        self.admin = member("admin", self.acme, "admin")
        for u in (self.viewer, self.support):
            ProductAccess.objects.create(company=self.acme, product=self.p_open, user=u)

    def post(self, url, body=None):
        return self.client.post(url, body or {}, content_type="application/json")

    def detail(self, p=None):
        return f"/ui-api/v1/products/{(p or self.p_open).pk}/"


class ProductListApiTest(P):
    def test_shape_summary_and_scoping(self):
        self.login("dev")
        data = self.client.get("/ui-api/v1/products/").json()
        self.assertEqual([i["name"] for i in data["items"]], ["Open"])
        item = data["items"][0]
        self.assertEqual(item["url"], f"/products/{self.p_open.pk}/")
        self.assertEqual(len(item["spark"]), 7)
        self.assertEqual(data["summary"]["products"], 1)
        self.assertFalse(data["can_create"])
        self.login("owner")
        data = self.client.get("/ui-api/v1/products/").json()
        self.assertEqual(data["summary"]["products"], 2)
        self.assertTrue(data["can_create"])

    def test_search_sort_and_odd_params(self):
        self.login("owner")
        self.assertEqual([i["name"] for i in self.client.get("/ui-api/v1/products/?q=hid").json()["items"]], ["Hidden"])
        names = [i["name"] for i in self.client.get("/ui-api/v1/products/?sort=-name").json()["items"]]
        self.assertEqual(names, ["Open", "Hidden"])
        self.assertEqual(self.client.get("/ui-api/v1/products/?sort=-versions&page=zzz").status_code, 200)


class ProductCrudApiTest(P):
    body = {"name": "My App", "description": "d", "default_environment": "staging", "key": "", "discord_webhook_url": ""}

    def test_admins_create_with_milestones(self):
        self.login("admin")
        r = self.post("/ui-api/v1/products/", {**self.body, "milestones": [{"title": "MVP", "date": "2026-12-01"}, {"title": "", "date": ""}]})
        self.assertEqual(r.status_code, 201)
        p = Product.objects.get(slug="my-app")
        self.assertEqual(r.json()["url"], f"/products/{p.pk}/")
        self.assertEqual(list(p.milestones.values_list("title", flat=True)), ["MVP"])
        self.assertTrue(ActivityLog.objects.filter(event_type="product_created").exists())

    def test_others_cannot_create_edit_or_delete(self):
        self.login("dev")
        self.assertEqual(self.post("/ui-api/v1/products/", self.body).status_code, 403)
        self.assertEqual(self.client.patch(self.detail(), self.body, content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(self.detail()).status_code, 403)
        self.assertEqual(Product.objects.filter(company=self.acme).count(), 2)

    def test_validation(self):
        self.login("owner")
        r = self.post("/ui-api/v1/products/", {**self.body, "name": ""})
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.json()["errors"])
        self.post("/ui-api/v1/products/", self.body)
        self.assertEqual(self.post("/ui-api/v1/products/", self.body).status_code, 400)  # same slug

    def test_edit_and_delete(self):
        self.login("owner")
        r = self.client.patch(self.detail(), {**self.body, "name": "Renamed", "key": "OPN"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.p_open.refresh_from_db()
        self.assertEqual((self.p_open.name, self.p_open.key), ("Renamed", "OPN"))
        self.assertEqual(self.client.delete(self.detail()).status_code, 200)
        self.assertFalse(Product.objects.filter(pk=self.p_open.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="product_deleted").exists())

    def test_key_suggestion_avoids_taken_keys(self):
        self.login("owner")
        self.assertTrue(self.client.get("/ui-api/v1/products/key-suggestion/?name=Billing%20Portal").json()["key"])
        self.login("dev")
        self.assertEqual(self.client.get("/ui-api/v1/products/key-suggestion/?name=x").status_code, 403)


class ProductDetailApiTest(P):
    def test_shape_and_secret_only_for_admins(self):
        self.p_open.discord_webhook_url = "https://discord.com/api/webhooks/1/x"
        self.p_open.save()
        ProductVersion.objects.create(company=self.acme, product=self.p_open, version_string="1.0", is_current=True)
        self.login("dev")
        d = self.client.get(self.detail()).json()
        self.assertTrue(d["product"]["webhook_configured"])
        self.assertEqual(d["product"]["discord_webhook_url"], "")
        self.assertEqual(d["members"], [])
        self.assertTrue(d["can_manage_keys"])
        self.assertEqual(d["versions"][0]["version_string"], "1.0")
        self.login("owner")
        d = self.client.get(self.detail()).json()
        self.assertEqual(d["product"]["discord_webhook_url"], "https://discord.com/api/webhooks/1/x")
        self.assertIn("dev", [m["username"] for m in d["members"]])

    def test_viewers_cannot_manage_keys(self):
        self.login("viewer")
        self.assertFalse(self.client.get(self.detail()).json()["can_manage_keys"])

    def test_isolation(self):
        self.login("dev")
        self.assertEqual(self.client.get(self.detail(self.p_hidden)).status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(self.detail(self.p_foreign)).status_code, 404)


class VersionApiTest(P):
    def test_add_make_current_and_delete(self):
        self.login("dev")
        self.post(self.detail() + "versions/", {"version_string": "1.0.0", "is_current": True})
        self.post(self.detail() + "versions/", {"version_string": "2.0.0", "is_current": True})
        self.assertEqual(list(ProductVersion.objects.filter(is_current=True).values_list("version_string", flat=True)), ["2.0.0"])
        self.assertEqual(self.post(self.detail() + "versions/", {"version_string": ""}).status_code, 400)
        v = ProductVersion.objects.get(version_string="1.0.0")
        r = self.client.delete(self.detail() + f"versions/{v.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ProductVersion.objects.count(), 1)

    def test_needs_access(self):
        self.login("dev")
        self.assertEqual(self.post(self.detail(self.p_hidden) + "versions/", {"version_string": "1"}).status_code, 404)


class KeysApiTest(P):
    def create(self, name="k", p=None):
        return self.post(f"/ui-api/v1/products/{(p or self.p_open).pk}/api-keys/", {"name": name})

    def test_who_can_create(self):
        for u in ("owner", "dev"):
            self.login(u)
            self.assertEqual(self.create(u).status_code, 200, u)
        for u in ("viewer", "support"):
            self.login(u)
            self.assertEqual(self.create().status_code, 403, u)
        self.assertEqual(self.p_open.api_keys.count(), 2)

    def test_raw_key_shown_once_and_never_stored(self):
        self.login("owner")
        d = self.create().json()
        self.assertEqual(len(d["raw_key"]), 64)
        self.assertNotIn("key_hash", str(d["api_keys"]))
        self.assertNotIn("raw_key", self.client.get(self.detail()).json())

    def test_no_access_and_foreign_are_404(self):
        self.login("owner")
        self.assertEqual(self.create(p=self.p_foreign).status_code, 404)
        member("nodev", self.acme)
        self.login("nodev")
        self.assertEqual(self.create(p=self.p_hidden).status_code, 404)

    def test_name_is_trimmed_defaulted_capped(self):
        self.login("owner")
        self.create("   ")
        self.create("n" * 300)
        names = sorted(self.p_open.api_keys.values_list("name", flat=True), key=len)
        self.assertEqual((names[0], len(names[1])), ("default", 100))

    def test_revoke_rights(self):
        key, _ = APIKey.create_key(self.p_open, "k")
        url = f"/ui-api/v1/api-keys/{key.pk}/revoke/"
        for u, code in (("viewer", 403), ("support", 403)):
            self.login(u)
            self.assertEqual(self.post(url).status_code, code, u)
        key.refresh_from_db()
        self.assertTrue(key.is_active)
        self.login("dev")
        self.post(url)
        key.refresh_from_db()
        self.assertFalse(key.is_active)
        self.assertTrue(ActivityLog.objects.filter(event_type="api_key_revoked").exists())

    def test_foreign_key_is_404(self):
        key, _ = APIKey.create_key(self.p_foreign, "k")
        self.login("owner")
        for tail in ("revoke", "rotate"):
            self.assertEqual(self.post(f"/ui-api/v1/api-keys/{key.pk}/{tail}/").status_code, 404)


class RotateApiTest(P):
    def setUp(self):
        super().setUp()
        self.old, self.raw = APIKey.create_key(self.p_open, "server")
        self.login("owner")

    def rotate(self, grace="1d", key=None):
        return self.post(f"/ui-api/v1/api-keys/{(key or self.old).pk}/rotate/", {"grace": grace})

    def test_new_key_same_name_shown_once(self):
        d = self.rotate().json()
        new = APIKey.objects.exclude(pk=self.old.pk).get()
        self.assertEqual((new.name, new.product), ("server", self.p_open))
        self.assertTrue(d["raw_key"])
        self.assertIn("works until", d["message"])

    def test_graces(self):
        self.rotate()
        self.old.refresh_from_db()
        self.assertEqual(self.old.state, "expiring")
        self.assertAlmostEqual((self.old.expires_at - timezone.now()).total_seconds(), 86400, delta=60)
        k2, _ = APIKey.create_key(self.p_open, "b")
        self.rotate("7d", k2)
        k2.refresh_from_db()
        self.assertAlmostEqual((k2.expires_at - timezone.now()).total_seconds(), 7 * 86400, delta=60)
        k3, raw3 = APIKey.create_key(self.p_open, "c")
        self.assertIn("revoked now", self.rotate("now", k3).json()["message"])
        k3.refresh_from_db()
        self.assertEqual(k3.state, "revoked")
        self.assertIsNone(APIKey.validate_key(raw3))

    def test_bad_requests_change_nothing(self):
        self.assertEqual(self.rotate("forever").status_code, 400)
        APIKey.objects.filter(pk=self.old.pk).update(is_active=False, revoked_at=timezone.now())
        self.assertEqual(self.rotate().status_code, 400)
        self.assertEqual(APIKey.objects.count(), 1)

    def test_twice_never_extends(self):
        self.rotate("1d")
        self.old.refresh_from_db()
        end = self.old.expires_at
        self.rotate("7d")
        self.old.refresh_from_db()
        self.assertEqual(self.old.expires_at, end)

    def test_logged_and_viewer_refused(self):
        self.rotate()
        self.assertTrue(ActivityLog.objects.filter(event_type="api_key_rotated", actor=self.owner).exists())
        self.login("viewer")
        self.assertEqual(self.rotate().status_code, 403)


class AccessApiTest(P):
    def test_grant_and_remove(self):
        extra = member("extra", self.acme)
        self.login("owner")
        r = self.post(self.detail() + "access/", {"user_id": extra.pk})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ProductAccess.objects.filter(user=extra, product=self.p_open).exists())
        self.assertEqual(self.post(self.detail() + "access/", {"user_id": extra.pk}).status_code, 200)  # idempotent
        self.assertEqual(ProductAccess.objects.filter(user=extra).count(), 1)
        self.assertEqual(self.client.delete(self.detail() + f"access/{extra.pk}/").status_code, 200)
        self.assertFalse(ProductAccess.objects.filter(user=extra).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="access_granted").exists())

    def test_only_company_members_and_only_admins(self):
        stranger = member("zed", self.other)
        self.login("owner")
        self.assertEqual(self.post(self.detail() + "access/", {"user_id": stranger.pk}).status_code, 400)
        self.assertEqual(self.post(self.detail() + "access/", {"user_id": "x"}).status_code, 400)
        self.assertEqual(self.client.delete(self.detail() + f"access/{stranger.pk}/").status_code, 404)
        self.login("dev")
        self.assertEqual(self.post(self.detail() + "access/", {"user_id": self.viewer.pk}).status_code, 404)


class MilestoneApiTest(P):
    def test_add_toggle_delete_are_audited(self):
        self.login("owner")
        d = self.post(self.detail() + "milestones/", {"title": "Beta", "target_date": (timezone.localdate() + timedelta(days=7)).isoformat(), "order": 2}).json()
        m = ProductMilestone.objects.get(title="Beta")
        self.assertEqual(m.order, 2)
        self.assertEqual(d["milestones"][0]["status"], "upcoming")
        self.post(f"/ui-api/v1/milestones/{m.pk}/toggle/")
        self.post(f"/ui-api/v1/milestones/{m.pk}/toggle/")
        m.refresh_from_db()
        self.assertEqual(m.status, "completed")
        self.assertIsNotNone(m.completed_at)
        self.post(f"/ui-api/v1/milestones/{m.pk}/toggle/")
        m.refresh_from_db()
        self.assertEqual((m.status, m.completed_at), ("upcoming", None))
        self.assertEqual(self.client.delete(f"/ui-api/v1/milestones/{m.pk}/").status_code, 200)
        for ev in ("milestone_added", "milestone_toggled", "milestone_deleted"):
            self.assertTrue(ActivityLog.objects.filter(event_type=ev).exists(), ev)

    def test_bad_input_and_access(self):
        self.login("owner")
        self.assertEqual(self.post(self.detail() + "milestones/", {"title": "x", "target_date": "nope"}).status_code, 400)
        self.assertEqual(self.post(self.detail() + "milestones/", {"title": "", "target_date": "2026-01-01"}).status_code, 400)
        m = ProductMilestone.objects.create(company=self.other, product=self.p_foreign, title="t", target_date=timezone.localdate())
        self.assertEqual(self.post(f"/ui-api/v1/milestones/{m.pk}/toggle/").status_code, 404)
        h = ProductMilestone.objects.create(company=self.acme, product=self.p_hidden, title="t", target_date=timezone.localdate())
        self.login("dev")
        self.assertEqual(self.post(f"/ui-api/v1/milestones/{h.pk}/toggle/").status_code, 404)


class ApiDocsApiTest(P):
    def url(self, p=None):
        return f"/ui-api/v1/products/{(p or self.p_open).pk}/api-docs/"

    def test_access(self):
        for u in ("owner", "dev", "viewer"):
            self.login(u)
            self.assertEqual(self.client.get(self.url()).status_code, 200, u)
        self.login("dev")
        self.assertEqual(self.client.get(self.url(self.p_hidden)).status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(self.url(self.p_foreign)).status_code, 404)

    def test_content(self):
        _, raw = APIKey.create_key(self.p_open, "billing")
        self.login("dev")
        d = self.client.get(self.url()).json()
        paths = [e["path"] for e in d["endpoints"]]
        for path in ("/api/v1/errors/capture/", "/api/v1/feedback/", "/api/v1/tickets/", "/api/v1/tickets/{ticket_id}/status/"):
            self.assertIn(path, paths)
        text = str(d)
        for marker in ("curl -X POST", "import requests", "await fetch(", "curl_init("):
            self.assertIn(marker, text)
        self.assertIn("YOUR_API_KEY", text)
        self.assertNotIn(raw, text)
        self.assertEqual(d["base_url"], "http://testserver/")
        self.assertEqual(d["keys"][0]["name"], "billing")
        self.assertNotIn("key_hash", str(d["keys"]))

    def test_every_serializer_field_is_documented_with_a_note(self):
        for key, serializer in (("errors", ErrorCaptureSerializer), ("feedback", FeedbackSerializer), ("tickets", TicketIngestSerializer)):
            for name in serializer().fields:
                self.assertTrue(docs.FIELD_NOTES[key].get(name), f"{key}.{name} has no note")

    def test_examples_are_valid_against_the_real_serializers(self):
        for key, serializer in (("errors", ErrorCaptureSerializer), ("feedback", FeedbackSerializer), ("tickets", TicketIngestSerializer)):
            example = next(e["example"] for e in docs.ENDPOINTS if e["key"] == key)
            s = serializer(data=example)
            self.assertTrue(s.is_valid(), f"{key}: {s.errors}")
