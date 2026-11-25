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
        r = self.client.get(reverse("appauth_web:cards"))  # by user: one row per person, with a count
        self.assertContains(r, "ann@example.com")
        self.assertContains(r, "1 card")
        self.assertNotContains(r, "Asha Rao")
        r = self.client.get(reverse("appauth_web:cards"), {"user": str(self.u.pk)})
        self.assertContains(r, "Asha Rao")
        self.assertNotContains(r, "Hidden Person")
        self.assertContains(self.client.get(reverse("appauth_web:card", args=[self.row.pk])), "asha@zeta.com")
        log = list(AppCardAccessLog.objects.order_by("id").values_list("staff_email", "action", "app_user_email"))
        self.assertEqual(log, [("s@example.com", "list", ""), ("s@example.com", "list", "ann@example.com"),
                        ("s@example.com", "detail", "ann@example.com")])

    def test_pending_deletion_card_has_no_detail_page(self):
        hidden = AppCard.objects.get(name="Hidden Person")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("appauth_web:card", args=[hidden.pk])).status_code, 404)

    def test_search_filter_and_log(self):
        self.client.force_login(self.staff)
        url = reverse("appauth_web:cards") + "?view=cards"
        for q in ("asha", "zeta", "asha@zeta", "98765"):
            self.assertContains(self.client.get(url, {"q": q, "view": "cards"}), "Asha Rao", msg_prefix=q)
        self.assertNotContains(self.client.get(url, {"q": "nobody", "view": "cards"}), "Asha Rao")
        self.assertContains(self.client.get(url, {"user": str(self.u.pk)}), "Asha Rao")
        self.assertNotContains(self.client.get(url, {"user": str(uuid.uuid4())}), "Asha Rao")
        self.assertEqual(self.client.get(url, {"user": "garbage"}).status_code, 200)
        self.assertContains(self.client.get(reverse("appauth_web:cards"), {"q": "ann"}), "ann@example.com")  # user search
        self.assertNotContains(self.client.get(reverse("appauth_web:cards"), {"q": "zzz"}), "ann@example.com")
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
        self.assertEqual(len(self.client.get(reverse("appauth_web:cards")).context["page"]), 0)  # gone from the user list too

    def test_public_pages_mention_backup_and_never_the_crm(self):
        for path in ("/cardsnap/privacy", "/cardsnap/delete-account"):
            body = self.client.get(path).content.decode()
            self.assertIn("30 days", body)
            self.assertIn("support@beforth.in", body)
            self.assertNotIn("CRM", body)
            self.assertNotIn("pq platform", body.lower())


class CardsPageTest(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        from apps.accounts.models import Company, Membership
        co = Company.objects.create(name="Acme", slug="acme")
        self.staff = U.objects.create_user("staff", "s@example.com", "pw-staff-1")
        Membership.objects.create(user=self.staff, company=co, role="owner")
        self.ann, ann = make_client("ann@example.com")
        self.bob, bob = make_client("bob@example.com")
        for c in (ann, bob):
            c.post(CLOUD + "consent", {"enabled": True, "consent_version": 1}, format="json")
        now = timezone.now()
        ann.put(CLOUD + "cards", {"cards": [
            card(name="Amit", designation="Managing Director", company="Zeta Ltd", phones=["111", "222"], emails=["amit@zeta.com", "a2@zeta.com"],
                 exhibition_name="Gulfood", is_favorite=True),
            card(name="Chitra", company="Alpha Co", emails=["chitra@alpha.com"])]}, format="json")
        bob.put(CLOUD + "cards", {"cards": [card(name="Bela", company="Mid Co", exhibition_name="Gitex")]}, format="json")
        AppCard.objects.filter(name="Amit").update(updated_at=now - timedelta(days=10), created_at=now - timedelta(days=10))
        self.pending = AppCard.objects.create(user=self.ann, client_id=uuid.uuid4(), name="Gone", created_at_client=now,
                                              updated_at_client=now, deletion_requested_at=now)
        self.client.force_login(self.staff)
        self.url = reverse("appauth_web:cards")

    def names(self, **params):
        r = self.client.get(self.url, {"view": "cards", **params})
        return [c.name for c in r.context["page"]]

    def test_name_and_title_are_on_separate_lines(self):
        body = self.client.get(self.url, {"view": "cards"}).content.decode()
        self.assertNotIn("</b>Managing Director", body)  # never glued to the name
        self.assertIn('<span class="cd-sub">Managing Director</span>', body)
        self.assertContains(self.client.get(self.url, {"view": "cards"}), "+2")  # 2 phones + 2 emails: first of each shown

    def test_stat_tiles(self):
        s = self.client.get(self.url).context["stats"]
        self.assertEqual((s["total"], s["users_on"], s["week"]), (3, 2, 2))  # pending card is not counted

    def test_pending_cards_never_appear_anywhere(self):
        self.assertNotIn("Gone", self.names())
        self.assertNotIn("Gone", self.names(user=str(self.ann.pk)))
        self.assertNotIn("Gone", self.client.get(self.url, {"view": "cards", "q": "gone"}).content.decode())
        self.assertNotIn("Gone", self.client.get(reverse("appauth_web:cards_export")).content.decode())
        self.assertEqual(self.client.get(reverse("appauth_web:card", args=[self.pending.pk])).status_code, 404)

    def test_filters(self):
        self.assertEqual(sorted(self.names()), ["Amit", "Bela", "Chitra"])
        self.assertEqual(sorted(self.names(user=str(self.ann.pk))), ["Amit", "Chitra"])
        self.assertEqual(self.names(exhibition="Gitex"), ["Bela"])
        today = timezone.localdate().isoformat()
        self.assertEqual(sorted(self.names(**{"from": today})), ["Bela", "Chitra"])
        self.assertEqual(self.names(to=(timezone.localdate() - timedelta(days=5)).isoformat()), ["Amit"])
        self.assertEqual(self.names(user=str(self.ann.pk), exhibition="Gitex"), [])
        self.assertEqual(self.names(**{"from": "nonsense"}), self.names())  # a bad date is ignored, not a crash

    def test_active_filters_show_as_removable_chips(self):
        r = self.client.get(self.url, {"view": "cards", "exhibition": "Gitex", "q": "be"})
        labels = [c["label"] for c in r.context["chips"]]
        self.assertEqual(labels, ["Exhibition: Gitex", "Search: be"])
        self.assertNotIn("exhibition", r.context["chips"][0]["url"])
        self.assertIn("q=be", r.context["chips"][0]["url"])

    def test_sorting(self):
        self.assertEqual(self.names(), ["Bela", "Chitra", "Amit"])  # last changed, newest first, is the default
        self.assertEqual(self.names(sort="updated"), ["Amit", "Chitra", "Bela"])
        self.assertEqual(self.names(sort="name"), ["Amit", "Bela", "Chitra"])
        self.assertEqual(self.names(sort="-name"), ["Chitra", "Bela", "Amit"])
        self.assertEqual(self.names(sort="company"), ["Chitra", "Bela", "Amit"])  # Alpha, Mid, Zeta
        self.assertEqual(self.names(sort="owner")[2], "Bela")  # ann's two cards, then bob's
        self.assertEqual(self.names(sort="; drop table"), self.names())

    def test_rows_per_page_is_remembered(self):
        self.client.get(self.url, {"view": "cards", "per_page": "10"})
        self.assertEqual(self.client.get(self.url, {"view": "cards"}).context["page"].paginator.per_page, 10)

    def test_export_follows_the_filters_and_is_logged(self):
        r = self.client.get(reverse("appauth_web:cards_export"), {"user": str(self.ann.pk), "sort": "name"})
        self.assertEqual(r["Content-Type"], "text/csv")
        lines = r.content.decode().strip().splitlines()
        self.assertEqual(lines[0], "name,company,title,phones,emails,owner_email")
        self.assertEqual(len(lines), 3)
        self.assertIn("Amit,Zeta Ltd,Managing Director,111; 222,amit@zeta.com; a2@zeta.com,ann@example.com", lines[1])
        self.assertNotIn("bob@example.com", r.content.decode())
        log = AppCardAccessLog.objects.get(action="export")
        self.assertEqual((log.staff_email, log.app_user_email), ("s@example.com", "ann@example.com"))
        self.assertIn("2 rows", log.detail)

    def test_export_is_staff_only_and_safe_from_formulas(self):
        AppCard.objects.filter(name="Bela").update(name="=HYPERLINK(1)")
        self.assertIn("'=HYPERLINK(1)", self.client.get(reverse("appauth_web:cards_export")).content.decode())
        from apps.accounts.models import Membership
        viewer = get_user_model().objects.create_user("v", "v@example.com", "pw-v-123")
        Membership.objects.create(user=viewer, company=self.staff.memberships.first().company, role="viewer")
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("appauth_web:cards_export")).status_code, 403)

    def test_empty_states_and_detail_extras(self):
        AppCard.objects.all().delete()
        self.assertContains(self.client.get(self.url, {"view": "cards"}), "Cards appear when app users turn on cloud backup.")
        self.assertContains(self.client.get(self.url), "Cards appear when app users turn on cloud backup.")
        ann_card = AppCard.objects.create(user=self.ann, client_id=uuid.uuid4(), name="Solo", phones=["999"], created_at_client=timezone.now(),
                                          updated_at_client=timezone.now())
        AppCard.objects.create(user=self.ann, client_id=uuid.uuid4(), name="Twin", created_at_client=timezone.now(), updated_at_client=timezone.now())
        r = self.client.get(reverse("appauth_web:card", args=[ann_card.pk]))
        self.assertEqual(r.context["others"], 1)
        self.assertContains(r, 'data-copy="999"')

    def test_page_text_has_no_internal_product_names(self):
        for r in (self.client.get(self.url), self.client.get(self.url, {"view": "cards"})):
            main = r.content.decode().split('class="breadcrumbs"')[1].split("</main>")[0]
            self.assertNotIn("CRM", main)
            self.assertNotIn("PQ", main)
            self.assertNotIn("PQ", r.content.decode().split("<title>")[1].split("</title>")[0])


class ScanCountTest(TestCase):
    def setUp(self):
        cache.clear()
        self.u, self.c = make_client("ann@example.com")
        self.c.post(CLOUD + "consent", {"enabled": True, "consent_version": 1}, format="json")

    def put(self, **kw):
        return self.c.put(CLOUD + "cards", {"cards": [card(**kw)]}, format="json")

    def test_stored_returned_and_defaults_to_one(self):
        cid = uuid.uuid4()
        self.put(cid=cid, scan_count=3)
        self.assertEqual(AppCard.objects.get().scan_count, 3)
        self.assertEqual(self.c.get(CLOUD + "cards").data["cards"][0]["scan_count"], 3)
        AppCard.objects.all().delete()
        self.put()  # not sent: a new card counts as scanned once
        self.assertEqual(AppCard.objects.get().scan_count, 1)

    def test_bad_values_keep_the_stored_one(self):
        cid, t = uuid.uuid4(), timezone.now() - timedelta(hours=5)
        self.put(cid=cid, scan_count=4, at=t)
        for i, bad in enumerate((0, -2, 10001, "5", 2.5, True, None, [3])):
            r = self.put(cid=cid, scan_count=bad, name=f"Edit{i}", at=t + timedelta(minutes=i + 1))
            self.assertEqual(r.status_code, 200, bad)
            row = AppCard.objects.get()
            self.assertEqual((row.scan_count, row.name), (4, f"Edit{i}"), bad)  # other fields still saved
        AppCard.objects.all().delete()
        self.put(scan_count=0)  # invalid on a new card: the default
        self.assertEqual(AppCard.objects.get().scan_count, 1)

    def test_limits_are_accepted(self):
        for n in (1, 10000):
            AppCard.objects.all().delete()
            self.put(scan_count=n)
            self.assertEqual(AppCard.objects.get().scan_count, n)

    def test_last_write_wins(self):
        cid, t = uuid.uuid4(), timezone.now() - timedelta(hours=5)
        self.put(cid=cid, scan_count=2, at=t)
        self.put(cid=cid, scan_count=5, at=t + timedelta(hours=1))
        self.put(cid=cid, scan_count=9, at=t - timedelta(hours=1))  # stale: ignored
        self.assertEqual(AppCard.objects.get().scan_count, 5)

    def test_admin_shows_count_badge_and_filter(self):
        from apps.accounts.models import Company, Membership
        staff = get_user_model().objects.create_user("staff", "s@example.com", "pw-staff-1")
        Membership.objects.create(user=staff, company=Company.objects.create(name="Acme", slug="acme"), role="owner")
        self.put(name="Once", scan_count=1)
        self.put(name="Many", scan_count=3)
        self.client.force_login(staff)
        url = reverse("appauth_web:cards")
        r = self.client.get(url, {"view": "cards"})
        self.assertContains(r, "Scanned 1 time<")
        self.assertContains(r, "Scanned 3 times")
        self.assertEqual(r.content.decode().count('>Merged<'), 1)
        r = self.client.get(url, {"multi": "1"})  # the filter alone switches to the card list
        self.assertEqual([c.name for c in r.context["page"]], ["Many"])
        self.assertEqual([c["label"] for c in r.context["chips"]], ["Scanned more than once"])
        csv = self.client.get(reverse("appauth_web:cards_export"), {"multi": "1"}).content.decode()
        self.assertIn("Many", csv)
        self.assertNotIn("Once", csv)
        row = AppCard.objects.get(name="Many")
        d = self.client.get(reverse("appauth_web:card", args=[row.pk]))
        self.assertContains(d, "Scanned 3 times")
        self.assertContains(d, "Merged")


from apps.appauth.models import ScanFeedback  # noqa: E402

SCAN = BASE + "scan-feedback"


def fb(version="1.0.38", mode="front", parser="local", fields=None, conf=None):
    return {"app_version": version, "scan_mode": mode, "parser": parser, "fields": fields or {}, **({"confidence": conf} if conf else {})}


def seed(version, **statuses):
    kw = {"app_version": version}
    for f, st in statuses.items():
        kw[f"{f}_status"] = st
    return ScanFeedback.objects.create(**kw)


class ScanFeedbackApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.u, self.c = make_client("ann@example.com")

    def test_valid_body_is_saved_and_never_linked_to_the_user(self):
        r = self.c.post(SCAN, fb(fields={"name": "ok", "company": "edited", "phones": "fixed_format"}, conf={"company": 0.41}), format="json")
        self.assertEqual((r.status_code, r.data), (200, {"ok": True}))
        row = ScanFeedback.objects.get()
        self.assertEqual((row.app_version, row.scan_mode, row.parser), ("1.0.38", "front", "local"))
        self.assertEqual((row.name_status, row.company_status, row.phones_status, row.emails_status), ("ok", "edited", "fixed_format", ""))
        self.assertEqual((row.company_conf, row.name_conf), (0.41, None))
        self.assertIsNotNone(row.received_at)
        names = {f.name for f in ScanFeedback._meta.get_fields()}
        self.assertFalse(names & {"user", "user_id", "app_user", "email", "ip"})  # nothing identifies the sender

    def test_bad_values_are_dropped_not_stored(self):
        body = fb(mode="sideways", parser="magic",
                  fields={"name": "ok", "company": "great", "designation": "fixed_format", "emails": "fixed_format", "ssn": "ok",
                          "website": 7, "address": ["ok"], "phones": "added"},
                  conf={"name": 1.5, "company": -0.1, "phones": True, "emails": "0.5", "address": 0.2, "ssn": 0.9})
        body["notes"] = "Asha Rao +91 99999 00000"
        self.assertEqual(self.c.post(SCAN, body, format="json").status_code, 200)
        row = ScanFeedback.objects.values().get()
        self.assertEqual((row["scan_mode"], row["parser"]), ("", ""))
        self.assertEqual({k: v for k, v in row.items() if k.endswith("_status") and v}, {"name_status": "ok", "phones_status": "added"})
        self.assertEqual({k: v for k, v in row.items() if k.endswith("_conf") and v is not None}, {})
        self.assertNotIn("Asha", str(row))

    def test_nan_confidence_is_dropped(self):
        raw = '{"app_version": "1.0.38", "fields": {"name": "ok"}, "confidence": {"name": NaN}}'
        self.assertEqual(self.c.post(SCAN, raw, content_type="application/json").status_code, 200)
        self.assertIsNone(ScanFeedback.objects.get().name_conf)

    def test_missing_fields_are_fine_and_empty_reports_store_nothing(self):
        self.assertEqual(self.c.post(SCAN, fb(fields={"name": "ok"}), format="json").status_code, 200)
        self.assertEqual(self.c.post(SCAN, {"app_version": "1.0.38"}, format="json").status_code, 200)
        self.assertEqual(self.c.post(SCAN, fb(fields={"x": "ok"}), format="json").status_code, 200)
        self.assertEqual(ScanFeedback.objects.count(), 1)

    def test_invalid_requests(self):
        for body in ({"fields": {"name": "ok"}}, fb(version="x" * 21), fb(version="1 0"), fb(version=5), [1], "text"):
            r = self.c.post(SCAN, body, format="json")
            self.assertEqual((r.status_code, r.data["code"]), (400, "invalid_request"), body)
        self.assertEqual(self.c.post(SCAN, "{not json", content_type="application/json").status_code, 400)
        self.assertEqual(ScanFeedback.objects.count(), 0)

    def test_oversize_body_is_rejected(self):
        body = fb(fields={"name": "ok"})
        body["padding"] = "a" * 5000
        r = self.c.post(SCAN, body, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (400, "invalid_request"))
        self.assertEqual(ScanFeedback.objects.count(), 0)

    def test_needs_sign_in_and_is_rate_limited(self):
        self.assertEqual(APIClient().post(SCAN, fb(fields={"name": "ok"}), format="json").status_code, 401)
        for _ in range(120):
            self.assertEqual(self.c.post(SCAN, fb(fields={"name": "ok"}), format="json").status_code, 200)
        r = self.c.post(SCAN, fb(fields={"name": "ok"}), format="json")
        self.assertEqual((r.status_code, r.data["code"]), (429, "rate_limited"))
        _, other = make_client("bob@example.com")  # the limit is per person
        self.assertEqual(other.post(SCAN, fb(fields={"name": "ok"}), format="json").status_code, 200)

    def test_old_rows_are_purged_after_400_days(self):
        old, recent = seed("1.0.1", name="ok"), seed("1.0.2", name="ok")
        ScanFeedback.objects.filter(pk=old.pk).update(received_at=timezone.now() - timedelta(days=401))
        ScanFeedback.objects.filter(pk=recent.pk).update(received_at=timezone.now() - timedelta(days=399))
        call_command("purge_cardsnap_cards", stdout=StringIO())
        self.assertEqual(list(ScanFeedback.objects.values_list("pk", flat=True)), [recent.pk])


class ScanQualityPageTest(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        from apps.accounts.models import Company, Membership
        co = Company.objects.create(name="Acme", slug="acme")
        self.staff = U.objects.create_user("staff", "s@example.com", "pw-staff-1")
        Membership.objects.create(user=self.staff, company=co, role="owner")
        self.viewer = U.objects.create_user("v", "v@example.com", "pw-v-123")
        Membership.objects.create(user=self.viewer, company=co, role="viewer")
        # 1.0.37: company edited 3 of 4 (confidence 0.4); phones: 2 edited, 1 fixed_format, 1 ok.
        for co, ph in (("edited", "edited"), ("edited", "edited"), ("edited", "fixed_format"), ("ok", "ok")):
            ScanFeedback.objects.create(app_version="1.0.37", company_status=co, company_conf=0.4, phones_status=ph)
        for st in ("edited", "ok", "ok", "ok"):
            seed("1.0.38", company=st, name="ok")
        self.client.force_login(self.staff)
        self.url = reverse("appauth_web:scan_quality")

    def row(self, r, field):
        return next(x for x in r.context["rows"] if x["field"] == field)

    def test_fix_rate_maths_and_order(self):
        r = self.client.get(self.url)
        self.assertEqual(r.context["scans"], 8)
        co = self.row(r, "company")
        self.assertEqual((co["scans"], co["ok"], co["edited"], co["fixes"], co["fix_rate"]), (8, 4, 4, 4, 50.0))
        ph = self.row(r, "phones")
        self.assertEqual((ph["scans"], ph["edited"], ph["fixed_format"], ph["ok"], ph["fix_rate"]), (4, 2, 1, 1, 75.0))
        self.assertEqual(self.row(r, "name")["fix_rate"], 0.0)
        self.assertIsNone(self.row(r, "address")["fix_rate"])  # never reported
        self.assertEqual([x["field"] for x in r.context["rows"]][:4], ["phones", "company", "name", "address"])  # worst first, unreported last
        self.assertEqual(r.context["rate"], round(100 * (4 + 3 + 0) / (8 + 4 + 4), 1))  # fixes / all field results
        self.assertAlmostEqual(self.row(r, "company")["conf"], 0.4)

    def test_filters(self):
        r = self.client.get(self.url, {"version": "1.0.38"})
        self.assertEqual((r.context["scans"], self.row(r, "company")["fix_rate"]), (4, 25.0))
        self.assertEqual(self.client.get(self.url, {"version": "9.9"}).context["scans"], 8)  # unknown version: ignored
        ScanFeedback.objects.filter(app_version="1.0.38").update(scan_mode="front+back", parser="ai")
        self.assertEqual(self.client.get(self.url, {"mode": "front+back"}).context["scans"], 4)
        self.assertEqual(self.client.get(self.url, {"parser": "ai", "mode": "front"}).context["scans"], 0)
        today = timezone.localdate().isoformat()
        self.assertEqual(self.client.get(self.url, {"from": today, "to": today}).context["scans"], 8)
        self.assertEqual(self.client.get(self.url, {"to": "2020-01-01"}).context["scans"], 0)
        self.assertEqual({v["app_version"]: v["n"] for v in self.client.get(self.url).context["per_version"]}, {"1.0.37": 4, "1.0.38": 4})

    def test_compare_two_versions(self):
        r = self.client.get(self.url, {"view": "compare", "a": "1.0.37", "b": "1.0.38"})
        co = next(x for x in r.context["rows"] if x["label"] == "Company")
        self.assertEqual((co["a"]["fix_rate"], co["b"]["fix_rate"], co["change"], co["tone"]), (75.0, 25.0, -50.0, "good"))
        self.assertContains(r, "sq-good")
        r = self.client.get(self.url, {"view": "compare", "a": "1.0.38", "b": "1.0.37"})
        self.assertEqual(next(x for x in r.context["rows"] if x["label"] == "Company")["tone"], "bad")
        self.assertContains(r, "sq-bad")
        self.assertEqual(self.client.get(self.url, {"view": "compare", "a": "1.0.37"}).context.get("rows"), None)  # needs both

    def test_csv_export(self):
        r = self.client.get(reverse("appauth_web:scan_quality_export"))
        lines = r.content.decode().strip().splitlines()
        self.assertEqual(lines[0], "field,app_version,scans,ok,edited,added,removed,fixed_format,fix_rate,avg_confidence")
        self.assertEqual(len(lines), 8)
        self.assertIn("phones,all,4,1,2,0,0,1,75.0,", "\n".join(lines))
        one = self.client.get(reverse("appauth_web:scan_quality_export"), {"version": "1.0.38"}).content.decode()
        self.assertIn("company,1.0.38,4,3,1,0,0,0,25.0,", one)
        both = self.client.get(reverse("appauth_web:scan_quality_export"), {"view": "compare", "a": "1.0.37", "b": "1.0.38"}).content.decode()
        self.assertEqual(len(both.strip().splitlines()), 15)

    def test_staff_only(self):
        self.client.force_login(self.viewer)
        for name in ("scan_quality", "scan_quality_export"):
            self.assertEqual(self.client.get(reverse(f"appauth_web:{name}")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_empty_state_and_no_internal_names(self):
        ScanFeedback.objects.all().delete()
        r = self.client.get(self.url)
        self.assertContains(r, "No scan feedback yet")
        self.assertContains(r, "It arrives when users save scanned cards.")
        seed("1.0.38", name="ok")
        for params in ({}, {"view": "compare"}):
            r = self.client.get(self.url, params)
            main = r.content.decode().split('class="breadcrumbs"')[1].split("</main>")[0]
            self.assertNotIn("CRM", main)
            self.assertNotIn("PQ", main)
            self.assertNotIn("PQ", r.content.decode().split("<title>")[1].split("</title>")[0])

    def test_privacy_page_explains_it(self):
        body = self.client.get("/cardsnap/privacy").content.decode()
        self.assertIn("Improving scanning", body)
        self.assertIn("Help improve scanning", body)
        self.assertNotIn("CRM", body)
