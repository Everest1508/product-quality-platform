import uuid
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.appauth import service
from apps.appauth.models import AppAuthEvent, AppCard, AppCardAccessLog, AppUser, DeletedAppUser

BASE = "/api/app-auth/"
CLOUD = BASE + "cloud/"


def make_client(email):
    u = AppUser.objects.create(email=email, name=email.split("@")[0], email_verified=True)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {service.make_access_token(u)}")
    return u, c


def card(cid=None, name="Asha Rao", at=None, **extra):
    at = at or timezone.now() - timedelta(hours=1)
    return {"client_id": str(cid or uuid.uuid4()), "name": name, "updated_at_client": at.isoformat(), **extra}


class CloudApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.u, self.c = make_client("ann@example.com")
        self.c.post(CLOUD + "consent", {"enabled": True, "consent_version": 1}, format="json")

    def put(self, cards, c=None):
        return (c or self.c).put(CLOUD + "cards", {"cards": cards}, format="json")

    def test_consent_is_stored_and_audited(self):
        self.u.refresh_from_db()
        self.assertTrue(self.u.cloud_backup_enabled)
        self.assertEqual(self.u.cloud_consent_version, 1)
        self.assertIsNotNone(self.u.cloud_consent_at)
        self.c.post(CLOUD + "consent", {"enabled": False, "consent_version": 1}, format="json")
        self.u.refresh_from_db()
        self.assertFalse(self.u.cloud_backup_enabled)
        self.assertIsNotNone(self.u.cloud_consent_off_at)
        self.assertEqual(list(AppAuthEvent.objects.filter(event__startswith="cloud_consent").values_list("event", flat=True).order_by("id")),
                         ["cloud_consent_on", "cloud_consent_off"])

    def test_upload_refused_while_backup_off(self):
        self.c.post(CLOUD + "consent", {"enabled": False, "consent_version": 1}, format="json")
        r = self.put([card()])
        self.assertEqual((r.status_code, r.data["code"]), (403, "backup_off"))
        self.assertEqual(AppCard.objects.count(), 0)

    def test_old_consent_version_is_refused(self):
        r = self.c.post(CLOUD + "consent", {"enabled": True, "consent_version": 0}, format="json")
        self.assertEqual(r.status_code, 400)
        AppUser.objects.filter(pk=self.u.pk).update(cloud_consent_version=0)
        self.assertEqual(self.put([card()]).data["code"], "consent_required")

    def test_upsert_and_last_write_wins(self):
        cid, t = uuid.uuid4(), timezone.now() - timedelta(hours=2)
        self.assertEqual(self.put([card(cid, "Old", t)]).data, {"saved": 1})
        self.assertEqual(self.put([card(cid, "Newer", t + timedelta(hours=1))]).data, {"saved": 1})
        self.assertEqual(self.put([card(cid, "Stale", t - timedelta(hours=1))]).data, {"saved": 0})  # ignored
        self.assertEqual(AppCard.objects.get().name, "Newer")

    def test_same_card_twice_in_a_batch_keeps_the_newer(self):
        cid, t = uuid.uuid4(), timezone.now() - timedelta(hours=2)
        self.put([card(cid, "B", t + timedelta(minutes=5)), card(cid, "A", t)])
        self.assertEqual(AppCard.objects.get().name, "B")

    def test_future_client_clock_is_clamped(self):
        cid = uuid.uuid4()
        self.put([card(cid, "Future", timezone.now() + timedelta(days=400))])
        self.assertLess(AppCard.objects.get().updated_at_client, timezone.now() + timedelta(minutes=6))

    def test_upload_is_a_fixed_number_of_queries(self):
        cards = [card() for _ in range(200)]
        with self.assertNumQueries(6):  # user, savepoint, select, count, insert, release
            self.put(cards)
        self.assertEqual(AppCard.objects.count(), 200)

    def test_restore_pull_roundtrip_and_paging(self):
        sent = [card(name=f"P{i}", phones=["+91 99999 00000"], tags=["a"], is_favorite=True) for i in range(5)]
        self.put(sent)
        r = self.c.get(CLOUD + "cards", {"limit": 2})
        self.assertEqual(len(r.data["cards"]), 2)
        got, after = list(r.data["cards"]), r.data["next"]
        while after:
            r = self.c.get(CLOUD + "cards", {"limit": 2, "after": after})
            got += r.data["cards"]
            after = r.data["next"]
        self.assertEqual({c["client_id"] for c in got}, {c["client_id"] for c in sent})
        self.assertEqual(got[0]["phones"], ["+91 99999 00000"])
        self.assertTrue(got[0]["is_favorite"])
        self.assertNotIn("id", got[0])
        since = self.c.get(CLOUD + "cards").data["server_time"]
        self.assertEqual(self.c.get(CLOUD + "cards", {"since": since}).data["cards"], [])  # nothing changed since

    def test_users_cannot_see_or_touch_each_others_cards(self):
        _, other = make_client("bob@example.com")
        other.post(CLOUD + "consent", {"enabled": True, "consent_version": 1}, format="json")
        cid = uuid.uuid4()
        self.put([card(cid, "Mine")])
        self.assertEqual(other.get(CLOUD + "cards").data["cards"], [])
        self.put([card(cid, "Bobs", timezone.now())], other)  # same client id, different owner: a separate row
        self.assertEqual(sorted(AppCard.objects.values_list("name", flat=True)), ["Bobs", "Mine"])
        other.delete(CLOUD + f"cards/{cid}")
        self.assertEqual([c["name"] for c in self.c.get(CLOUD + "cards").data["cards"]], ["Mine"])
        self.assertEqual(APIClient().get(CLOUD + "cards").status_code, 401)

    def test_delete_one_card_is_immediate_and_idempotent(self):
        cid = uuid.uuid4()
        self.put([card(cid), card()])
        for _ in range(2):
            self.assertEqual(self.c.delete(CLOUD + f"cards/{cid}").data, {"ok": True})
        self.assertEqual(AppCard.objects.count(), 1)

    def test_delete_data_hides_now_and_purge_erases_after_30_days(self):
        self.put([card(), card()])
        r = self.c.delete(CLOUD + "data")
        self.assertEqual(r.data["purge_on"], (timezone.now() + timedelta(days=30)).date().isoformat())
        self.u.refresh_from_db()
        self.assertFalse(self.u.cloud_backup_enabled)
        self.assertEqual(self.c.get(CLOUD + "cards").data["cards"], [])
        self.assertEqual(AppCard.objects.live().count(), 0)
        self.assertEqual(AppCard.objects.count(), 2)
        call_command("purge_cardsnap_cards", stdout=StringIO())
        self.assertEqual(AppCard.objects.count(), 2)  # too early
        AppCard.objects.update(deletion_requested_at=timezone.now() - timedelta(days=31))
        call_command("purge_cardsnap_cards", stdout=StringIO())
        self.assertEqual(AppCard.objects.count(), 0)

    def test_upsert_clears_pending_deletion(self):
        cid = uuid.uuid4()
        self.put([card(cid, "A", timezone.now() - timedelta(hours=3))])
        self.c.delete(CLOUD + "data")
        self.c.post(CLOUD + "consent", {"enabled": True, "consent_version": 1}, format="json")
        self.put([card(cid, "A", timezone.now() - timedelta(hours=5))])  # even an older copy: it is wanted again
        self.assertEqual(AppCard.objects.live().count(), 1)

    def test_purge_also_removes_cards_whose_owner_is_gone(self):
        self.put([card()])
        service.delete_account(self.u)
        card_row = AppCard.objects.get()
        self.assertIsNone(card_row.user)
        self.assertIsNotNone(card_row.deletion_requested_at)
        self.assertEqual(DeletedAppUser.objects.count(), 1)  # the analytics snapshot is unchanged
        AppCard.objects.update(deletion_requested_at=timezone.now() - timedelta(days=40))
        call_command("purge_cardsnap_cards", stdout=StringIO())
        self.assertEqual(AppCard.objects.count(), 0)

    def test_delete_me_flags_cards(self):
        self.put([card()])
        self.assertEqual(self.c.delete(BASE + "me", {"confirm": "DELETE"}, format="json").status_code, 200)
        self.assertEqual(AppCard.objects.live().count(), 0)
        self.assertEqual(AppCard.objects.count(), 1)

    def test_caps_and_validation(self):
        self.assertEqual(self.put([card() for _ in range(201)]).status_code, 400)
        for bad in ({"phones": ["1"] * 21}, {"tags": ["x" * 101]}, {"name": "n" * 256}, {"notes": "n" * 5001},
                    {"emails": "a@b.c"}, {"updated_at_client": "yesterday"}):
            r = self.put([card(**bad) if "updated_at_client" not in bad else {**card(), **bad}])
            self.assertEqual((r.status_code, r.data["code"]), (400, "invalid_card"), bad)
        self.assertEqual(AppCard.objects.count(), 0)  # nothing from a rejected batch is kept

    def test_one_bad_card_rejects_the_whole_batch(self):
        self.assertEqual(self.put([card(), card(name="n" * 300)]).status_code, 400)
        self.assertEqual(AppCard.objects.count(), 0)

    def test_per_user_limit(self):
        from apps.appauth import cloud
        cloud.MAX_CARDS, old = 3, cloud.MAX_CARDS
        try:
            self.assertEqual(self.put([card() for _ in range(3)]).status_code, 200)
            r = self.put([card()])
            self.assertEqual((r.status_code, r.data["code"]), (409, "limit_reached"))
            first = AppCard.objects.first()
            self.assertEqual(self.put([card(first.client_id, "edit", timezone.now())]).status_code, 200)  # editing is fine
        finally:
            cloud.MAX_CARDS = old

    def test_photos_are_never_stored(self):
        self.put([card(photo="data:image/png;base64,AAAA", image_path="/x.jpg")])
        row = AppCard.objects.values().get()
        self.assertFalse(any("photo" in k or "image" in k for k in row))
        self.assertNotIn("photo", self.c.get(CLOUD + "cards").data["cards"][0])

    def test_unknown_card_id_in_url_is_a_404_not_a_crash(self):
        self.assertEqual(self.c.delete(CLOUD + "cards/not-a-uuid").status_code, 404)


class CloudAdminTest(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        from apps.accounts.models import Company, Membership
        co = Company.objects.create(name="Acme", slug="acme")
        self.staff = U.objects.create_user("staff", "s@example.com", "pw-staff-1")
        Membership.objects.create(user=self.staff, company=co, role="owner")
        self.plain = U.objects.create_user("plain", "p@example.com", "pw-plain-1")
        Membership.objects.create(user=self.plain, company=co, role="viewer")
        self.u, c = make_client("ann@example.com")
        c.post(CLOUD + "consent", {"enabled": True, "consent_version": 1}, format="json")
        self.cid = uuid.uuid4()
        c.put(CLOUD + "cards", {"cards": [card(self.cid, "Asha Rao", company="Zeta Ltd", emails=["asha@zeta.com"], phones=["+91 98765 43210"]),
                                           card(name="Hidden Person")]}, format="json")
        AppCard.objects.filter(name="Hidden Person").update(deletion_requested_at=timezone.now())
        self.row = AppCard.objects.get(client_id=self.cid)

    def test_only_team_admins_can_open_and_visits_are_logged(self):
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get(reverse("appauth_web:cards")).status_code, 403)
        self.assertEqual(self.client.get(reverse("appauth_web:card", args=[self.row.pk])).status_code, 403)
        self.assertEqual(AppCardAccessLog.objects.count(), 0)
        self.client.force_login(self.staff)
        r = self.client.get(reverse("appauth_web:cards"))
        self.assertContains(r, "Asha Rao")
        self.assertContains(r, "ann@example.com")
        self.assertNotContains(r, "Hidden Person")
        self.assertContains(self.client.get(reverse("appauth_web:card", args=[self.row.pk])), "asha@zeta.com")
        log = list(AppCardAccessLog.objects.order_by("id").values_list("staff_email", "action", "app_user_email"))
        self.assertEqual(log, [("s@example.com", "list", ""), ("s@example.com", "detail", "ann@example.com")])

    def test_pending_deletion_card_has_no_detail_page(self):
        hidden = AppCard.objects.get(name="Hidden Person")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("appauth_web:card", args=[hidden.pk])).status_code, 404)

    def test_search_filter_and_log(self):
        self.client.force_login(self.staff)
        url = reverse("appauth_web:cards")
        for q in ("asha", "zeta", "asha@zeta", "98765"):
            self.assertContains(self.client.get(url, {"q": q}), "Asha Rao", msg_prefix=q)
        self.assertNotContains(self.client.get(url, {"q": "nobody"}), "Asha Rao")
        self.assertContains(self.client.get(url, {"user": str(self.u.pk)}), "Asha Rao")
        self.assertNotContains(self.client.get(url, {"user": str(uuid.uuid4())}), "Asha Rao")
        self.assertEqual(self.client.get(url, {"user": "garbage"}).status_code, 200)
        self.assertTrue(AppCardAccessLog.objects.filter(action="search", detail="q=asha").exists())
        self.assertTrue(AppCardAccessLog.objects.filter(app_user=self.u).exists())

    def test_user_page_shows_backup_state_and_count(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("appauth_web:detail", args=[self.u.pk]))
        self.assertContains(r, "On since")
        self.assertContains(r, "Backed-up cards (1)")

    def test_admin_delete_hides_the_cards(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("appauth_web:action", args=[self.u.pk, "delete"]))
        self.assertEqual(AppCard.objects.live().count(), 0)
        self.client.post(reverse("appauth_web:action", args=[self.u.pk, "purge"]))
        self.assertEqual(AppCard.objects.live().count(), 0)
        self.assertNotContains(self.client.get(reverse("appauth_web:cards")), "Asha Rao")

    def test_public_pages_mention_backup_and_never_the_crm(self):
        for path in ("/cardsnap/privacy", "/cardsnap/delete-account"):
            body = self.client.get(path).content.decode()
            self.assertIn("30 days", body)
            self.assertIn("support@beforth.in", body)
            self.assertNotIn("CRM", body)
            self.assertNotIn("pq platform", body.lower())
