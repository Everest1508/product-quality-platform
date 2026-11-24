from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.appauth import service
from apps.appauth.models import AppAuthEvent, AppRefreshToken, AppUser, DeletedAppUser
from apps.appauth.service import AuthError

BASE = "/api/app-auth/"
GOOD = {"email": "Ann@Example.com", "password": "correct-horse", "name": "Ann"}


def signup_with(c):
    """Register and confirm the emailed code on client `c`. Returns the sign-in response (tokens + user)."""
    c.post(BASE + "register", GOOD, format="json")
    u = AppUser.objects.get(email=GOOD["email"].lower())
    return c.post(BASE + "verify-email-otp", {"email": u.email, "code": service.make_otp("verify", u)}, format="json")


class ApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = APIClient()

    def register(self, **over):
        return self.c.post(BASE + "register", {**GOOD, **over}, format="json")

    def signup(self, **over):
        """Register, then confirm the emailed code: the same shape register used to return (tokens + user)."""
        email = {**GOOD, **over}["email"].lower()
        self.register(**over)
        code = service.make_otp("verify", AppUser.objects.get(email=email))
        return self.c.post(BASE + "verify-email-otp", {"email": email, "code": code}, format="json")

    def bearer(self, token):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return c

    def test_register_sends_a_code_not_a_link_and_signs_nobody_in(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data, {"email_verification_required": True, "email": "ann@example.com"})
        u = AppUser.objects.get(email="ann@example.com")
        self.assertTrue(u.password_hash.startswith("argon2"))
        self.assertFalse(u.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        code = service.make_otp("verify", u)
        self.assertIn(code, m.body)
        self.assertNotIn("http", m.body)
        html = m.alternatives[0][0]
        self.assertIn(code, html)
        self.assertNotIn("href", html)  # nothing that points at the CRM
        # cannot sign in until the code is confirmed
        r = self.c.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (403, "email_not_verified"))

    def test_verify_email_otp_signs_in_and_wrong_codes_do_not(self):
        self.register()
        bad = self.c.post(BASE + "verify-email-otp", {"email": "ann@example.com", "code": "000000"}, format="json")
        self.assertEqual((bad.status_code, bad.data["code"]), (400, "invalid_code"))
        r = signup_with(self.c)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(AppUser.objects.get().email_verified)
        self.assertEqual(self.bearer(r.data["access_token"]).get(BASE + "me").data["email"], "ann@example.com")
        # only a hash of the refresh token is stored
        self.assertFalse(AppRefreshToken.objects.filter(token_hash=r.data["refresh_token"]).exists())

    def test_otp_expires_and_is_rate_limited(self):
        self.register()
        u = AppUser.objects.get()
        code = service.make_otp("verify", u)
        with mock.patch("apps.appauth.service.time.time", return_value=timezone.now().timestamp() + 21 * 60):
            r = self.c.post(BASE + "verify-email-otp", {"email": u.email, "code": code}, format="json")
        self.assertEqual(r.status_code, 400)
        for _ in range(8):
            r = self.c.post(BASE + "verify-email-otp", {"email": u.email, "code": "111111"}, format="json")
        self.assertEqual(r.status_code, 429)

    def test_resend_is_uniform(self):
        self.register()
        mail.outbox.clear()
        a = self.c.post(BASE + "resend-verification", {"email": "ann@example.com"}, format="json")
        b = self.c.post(BASE + "resend-verification", {"email": "nobody@example.com"}, format="json")
        self.assertEqual((a.status_code, a.data), (b.status_code, b.data))
        self.assertEqual(len(mail.outbox), 1)

    def test_register_validation_and_duplicates(self):
        self.assertEqual(self.register(password="short").data["code"], "weak_password")
        self.register()
        # never confirmed: the sign-up can be retried (new password), still one account
        r = self.register(password="another-pass")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(AppUser.objects.count(), 1)
        signup_with(self.c)
        r = self.register(email="ann@example.com", password="third-pass-1")
        self.assertEqual((r.status_code, r.data["code"]), (409, "email_exists"))

    def test_login_generic_error_for_unknown_and_bad_password(self):
        self.signup()
        bad = self.c.post(BASE + "login", {"email": "ann@example.com", "password": "nope-nope"}, format="json")
        unknown = self.c.post(BASE + "login", {"email": "who@example.com", "password": "nope-nope"}, format="json")
        self.assertEqual((bad.status_code, unknown.status_code), (401, 401))
        self.assertEqual(bad.data, unknown.data)
        self.assertEqual(bad.data["message"], "Invalid email or password")
        ok = self.c.post(BASE + "login", {"email": "ANN@example.com", "password": "correct-horse"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertIsNotNone(AppUser.objects.get().last_login_at)

    def test_revoked_user_blocked_on_login_and_on_existing_token(self):
        tokens = self.signup().data
        user = AppUser.objects.get()
        user.status = "revoked"
        user.save()
        r = self.c.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (403, "account_revoked"))
        me = self.bearer(tokens["access_token"]).get(BASE + "me")
        self.assertEqual((me.status_code, me.data["code"]), (403, "account_revoked"))  # no refresh needed
        r = self.c.post(BASE + "refresh", {"refresh_token": tokens["refresh_token"]}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_me_rejects_bad_and_expired_tokens(self):
        self.assertEqual(self.bearer("garbage").get(BASE + "me").status_code, 401)
        self.assertEqual(self.c.get(BASE + "me").status_code, 401)
        self.signup()
        with mock.patch.object(service, "ACCESS_TTL", timedelta(seconds=-5)):
            tok = service.make_access_token(AppUser.objects.get())
        self.assertEqual(self.bearer(tok).get(BASE + "me").status_code, 401)

    def test_refresh_rotates_and_reuse_kills_the_family(self):
        first = self.signup().data["refresh_token"]
        second = self.c.post(BASE + "refresh", {"refresh_token": first}, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(second.data["refresh_token"], first)
        # replaying the rotated token is reuse: rejected, and the newest token dies too
        self.assertEqual(self.c.post(BASE + "refresh", {"refresh_token": first}, format="json").status_code, 401)
        self.assertEqual(self.c.post(BASE + "refresh", {"refresh_token": second.data["refresh_token"]}, format="json").status_code, 401)
        self.assertTrue(AppAuthEvent.objects.filter(event="refresh_reuse").exists())

    def test_expired_refresh_and_logout(self):
        tokens = self.signup().data
        self.c.post(BASE + "logout", {"refresh_token": tokens["refresh_token"]}, format="json")
        self.assertEqual(self.c.post(BASE + "refresh", {"refresh_token": tokens["refresh_token"]}, format="json").status_code, 401)
        t2 = self.c.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json").data
        AppRefreshToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.c.post(BASE + "refresh", {"refresh_token": t2["refresh_token"]}, format="json").status_code, 401)

    def test_forgot_is_uniform_and_reset_needs_the_emailed_code(self):
        self.signup()
        mail.outbox.clear()
        a = self.c.post(BASE + "forgot-password", {"email": "ann@example.com"}, format="json")
        b = self.c.post(BASE + "forgot-password", {"email": "nobody@example.com"}, format="json")
        self.assertEqual((a.status_code, a.data), (b.status_code, b.data))
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("http", mail.outbox[0].body)
        code = service.make_otp("reset", AppUser.objects.get())
        self.assertIn(code, mail.outbox[0].body)
        # a wrong code earns nothing, so there is no token to reset with
        bad = self.c.post(BASE + "verify-reset-otp", {"email": "ann@example.com", "code": "000000"}, format="json")
        self.assertEqual((bad.status_code, bad.data["code"]), (400, "invalid_code"))
        self.assertEqual(self.c.post(BASE + "reset-password", {"token": "junk", "new_password": "brand-new-pass"}, format="json").status_code, 400)
        token = self.c.post(BASE + "verify-reset-otp", {"email": "ann@example.com", "code": code}, format="json").data["reset_token"]
        old = self.c.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json").data
        r = self.c.post(BASE + "reset-password", {"token": token, "new_password": "brand-new-pass"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.post(BASE + "reset-password", {"token": token, "new_password": "third-pass-1"}, format="json").status_code, 400)
        # the used code stops working too
        self.assertEqual(self.c.post(BASE + "verify-reset-otp", {"email": "ann@example.com", "code": code}, format="json").status_code, 400)
        self.assertEqual(self.bearer(old["access_token"]).get(BASE + "me").status_code, 401)  # sessions ended
        self.assertEqual(self.c.post(BASE + "login", {"email": "ann@example.com", "password": "brand-new-pass"}, format="json").status_code, 200)

    def test_reset_token_expires_after_30_minutes(self):
        self.signup()
        token = service.make_reset_token(AppUser.objects.get())
        with mock.patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 31 * 60):
            with self.assertRaises(AuthError):
                service.reset_password(token, "brand-new-pass")

    def test_login_is_rate_limited(self):
        codes = [self.c.post(BASE + "login", {"email": "x@example.com", "password": "wrong-pass"}, format="json").status_code for _ in range(12)]
        self.assertEqual(codes[0], 401)
        self.assertEqual(codes[-1], 429)


class GoogleTest(TestCase):
    CLAIMS = {"sub": "g-1", "email": "Zed@Example.com", "email_verified": True, "name": "Zed", "picture": "https://x/p.png"}

    def setUp(self):
        cache.clear()
        self.c = APIClient()

    def google(self, claims=None):
        with mock.patch("apps.appauth.google.verify_google_id_token", return_value=claims or self.CLAIMS):
            return self.c.post(BASE + "google", {"id_token": "t"}, format="json")

    def test_creates_then_reuses_account_with_server_side_profile(self):
        r = self.google()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["user"]["email"], "zed@example.com")
        self.google({**self.CLAIMS, "email": "changed@example.com"})  # same sub -> same account
        self.assertEqual(AppUser.objects.count(), 1)

    def test_links_to_existing_password_account(self):
        u = AppUser.objects.create(email="zed@example.com", password_hash=service.hash_password("whatever-1"), email_verified=True)
        self.google()
        u.refresh_from_db()
        self.assertEqual((u.google_sub, AppUser.objects.count()), ("g-1", 1))
        self.assertIsNotNone(u.password_hash)

    def test_unverified_password_account_loses_its_password_on_link(self):
        u = AppUser.objects.create(email="zed@example.com", password_hash=service.hash_password("squatter-1"))
        self.google()
        u.refresh_from_db()
        self.assertIsNone(u.password_hash)

    def test_revoked_google_user_blocked(self):
        self.google()
        AppUser.objects.update(status="revoked")
        self.assertEqual(self.google().status_code, 403)

    def test_verifier_rejects_unverified_email_and_bad_token(self):
        from apps.appauth import google
        with self.settings(GOOGLE_CLIENT_IDS=["cid"]):
            with mock.patch.object(google._JWKS, "get_signing_key_from_jwt", side_effect=google.jwt.PyJWTError):
                with self.assertRaises(AuthError):
                    google.verify_google_id_token("junk")
            with mock.patch.object(google._JWKS, "get_signing_key_from_jwt"), \
                 mock.patch.object(google.jwt, "decode", return_value={"sub": "1", "email": "a@b.c", "email_verified": False}):
                with self.assertRaises(AuthError):
                    google.verify_google_id_token("x")
        with self.settings(GOOGLE_CLIENT_IDS=[]):
            with self.assertRaises(AuthError):
                google.verify_google_id_token("x")


class AdminTest(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.staff = U.objects.create_user("staff", "s@example.com", "pw-staff-1")
        from apps.accounts.models import Company, Membership
        co = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.staff, company=co, role="owner")
        self.plain = U.objects.create_user("plain", "p@example.com", "pw-plain-1")
        Membership.objects.create(user=self.plain, company=co, role="viewer")
        self.api = APIClient()
        self.tokens = signup_with(self.api).data
        self.user = AppUser.objects.get()

    def test_only_staff_can_open_pages(self):
        self.client.force_login(self.plain)
        self.assertEqual(self.client.get(reverse("appauth_web:users")).status_code, 403)
        self.assertEqual(self.client.post(reverse("appauth_web:action", args=[self.user.pk, "revoke"])).status_code, 403)
        self.client.force_login(self.staff)
        r = self.client.get(reverse("appauth_web:users"), {"q": "ann", "status": "active", "sort": "-login"})
        self.assertContains(r, "ann@example.com")
        self.assertContains(self.client.get(reverse("appauth_web:detail", args=[self.user.pk])), "Active sessions · 1")

    def test_revoke_then_restore(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("appauth_web:action", args=[self.user.pk, "revoke"]), {"reason": "abuse"})
        self.user.refresh_from_db()
        self.assertEqual((self.user.status, self.user.revoked_reason), ("revoked", "abuse"))
        self.assertEqual(self.user.refresh_tokens.count(), 0)
        me = APIClient(); me.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens['access_token']}")
        self.assertEqual(me.get(BASE + "me").status_code, 403)
        self.client.post(reverse("appauth_web:action", args=[self.user.pk, "restore"]))
        self.user.refresh_from_db()
        self.assertEqual(self.user.status, "active")
        self.assertEqual(me.get(BASE + "me").status_code, 401)  # old token stays dead: version was bumped
        events = set(AppAuthEvent.objects.values_list("event", flat=True))
        self.assertTrue({"revoke", "restore"} <= events)

    def test_force_logout_delete_and_csv(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("appauth_web:action", args=[self.user.pk, "logout"]))
        self.assertEqual(self.user.refresh_tokens.count(), 0)
        csv = self.client.get(reverse("appauth_web:export")).content.decode()
        self.assertIn("ann@example.com", csv)
        self.client.post(reverse("appauth_web:action", args=[self.user.pk, "delete"]))
        self.user.refresh_from_db()
        self.assertEqual(self.user.status, "deleted")
        self.assertEqual(len(self.client.get(reverse("appauth_web:users")).context["page"]), 0)  # the toast still names them
        r = self.api.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json")
        self.assertEqual(r.status_code, 401)


    def test_purge_erases_the_account_and_frees_the_email(self):
        self.client.force_login(self.plain)
        self.assertEqual(self.client.post(reverse("appauth_web:action", args=[self.user.pk, "purge"])).status_code, 403)
        self.client.force_login(self.staff)
        self.client.post(reverse("appauth_web:action", args=[self.user.pk, "purge"]))
        self.assertFalse(AppUser.objects.filter(email="ann@example.com").exists())
        r = self.api.post(BASE + "register", GOOD, format="json")  # the email can be used again
        self.assertEqual(r.status_code, 201)


class CompanyAdminAccessTest(TestCase):
    def test_company_admin_can_revoke_from_list(self):
        from apps.accounts.models import Company, Membership
        U = get_user_model()
        co = Company.objects.create(name="Acme", slug="acme")
        admin, viewer = U.objects.create_user("adm", "a@e.com", "pw-adm-12"), U.objects.create_user("vw", "v@e.com", "pw-vw-123")
        Membership.objects.create(user=admin, company=co, role="admin")
        Membership.objects.create(user=viewer, company=co, role="viewer")
        target = AppUser.objects.create(email="t@example.com")
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(reverse("appauth_web:action", args=[target.pk, "revoke"])).status_code, 403)
        self.client.force_login(admin)
        r = self.client.post(reverse("appauth_web:action", args=[target.pk, "revoke"]), {"next": "list"})
        self.assertRedirects(r, reverse("appauth_web:users"))
        target.refresh_from_db()
        self.assertEqual(target.status, "revoked")


class AccountSelfServiceTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = APIClient()
        self.tokens = signup_with(self.c).data
        self.auth = APIClient()
        self.auth.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens['access_token']}")

    def test_change_password_ends_other_sessions_and_returns_fresh_tokens(self):
        other = self.c.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json").data
        r = self.auth.post(BASE + "change-password", {"current_password": "wrong-one-1", "new_password": "new-secret-9"}, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (403, "reauth_failed"))
        r = self.auth.post(BASE + "change-password", {"current_password": "correct-horse", "new_password": "new-secret-9"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.auth.get(BASE + "me").status_code, 401)  # old access token dead
        self.assertEqual(self.c.post(BASE + "refresh", {"refresh_token": other["refresh_token"]}, format="json").status_code, 401)
        fresh = APIClient(); fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access_token']}")
        self.assertEqual(fresh.get(BASE + "me").status_code, 200)

    def test_google_only_user_needs_fresh_google_token_to_set_password(self):
        u = AppUser.objects.create(email="g@example.com", google_sub="g-9", auth_provider="google", email_verified=True)
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"Bearer {service.make_access_token(u)}")
        r = c.post(BASE + "change-password", {"new_password": "new-secret-9"}, format="json")
        self.assertEqual(r.data["code"], "reauth_required")
        with mock.patch("apps.appauth.google.verify_google_id_token", return_value={"sub": "someone-else"}):
            r = c.post(BASE + "change-password", {"new_password": "new-secret-9", "id_token": "t"}, format="json")
        self.assertEqual(r.status_code, 403)
        with mock.patch("apps.appauth.google.verify_google_id_token", return_value={"sub": "g-9"}):
            r = c.post(BASE + "change-password", {"new_password": "new-secret-9", "id_token": "t"}, format="json")
        self.assertEqual(r.status_code, 200)
        u.refresh_from_db()
        self.assertTrue(u.password_hash)

    def test_logout_all(self):
        self.c.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json")
        self.assertEqual(self.auth.post(BASE + "logout-all").status_code, 200)
        self.assertEqual(AppRefreshToken.objects.count(), 0)
        self.assertEqual(self.auth.get(BASE + "me").status_code, 401)

    def test_delete_account_needs_reauth_and_blocks_everything_after(self):
        self.assertEqual(self.auth.delete(BASE + "me").status_code, 400)
        self.assertEqual(self.auth.delete(BASE + "me", {"current_password": "nope-nope"}, format="json").status_code, 403)
        self.assertEqual(self.auth.delete(BASE + "me", {"current_password": "correct-horse"}, format="json").data, {"ok": True})
        self.assertFalse(AppUser.objects.exists())  # account gone
        self.assertEqual(DeletedAppUser.objects.get().email, "ann@example.com")  # snapshot kept
        self.assertEqual(self.auth.get(BASE + "me").status_code, 401)
        self.assertEqual(self.c.post(BASE + "login", {"email": "ann@example.com", "password": "correct-horse"}, format="json").status_code, 401)


class AppleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.c = APIClient()

    def apple(self, claims, **body):
        with mock.patch("apps.appauth.apple.verify_apple_identity_token", return_value=claims):
            return self.c.post(BASE + "apple", {"identity_token": "t", **body}, format="json")

    def test_first_sign_in_uses_relay_email_and_client_name_then_sub_only(self):
        r = self.apple({"sub": "a-1", "email": "xyz@privaterelay.appleid.com"}, name="Mia Jones")
        self.assertEqual((r.status_code, r.data["user"]["name"], r.data["user"]["auth_provider"]), (200, "Mia Jones", "apple"))
        r = self.apple({"sub": "a-1"})  # later tokens carry no email
        self.assertEqual((r.status_code, AppUser.objects.count()), (200, 1))

    def test_no_email_and_unknown_sub_is_rejected_and_revoked_blocked(self):
        self.assertEqual(self.apple({"sub": "a-2"}).data["code"], "email_missing")
        self.apple({"sub": "a-3", "email": "r@privaterelay.appleid.com"})
        AppUser.objects.update(status="revoked")
        self.assertEqual(self.apple({"sub": "a-3"}).status_code, 403)

    def test_real_email_links_to_existing_account(self):
        AppUser.objects.create(email="zed@example.com", email_verified=True, password_hash=service.hash_password("whatever-1"))
        self.apple({"sub": "a-4", "email": "Zed@Example.com"})
        self.assertEqual((AppUser.objects.count(), AppUser.objects.get().apple_sub), (1, "a-4"))


class PublicPagesTest(TestCase):
    def test_privacy_and_delete_pages_need_no_login(self):
        for path in ("/cardsnap/privacy", "/cardsnap/delete-account"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "CardSnap")


class GoogleOnlyDeleteTest(TestCase):
    def test_account_without_password_deletes_with_confirm(self):
        user = AppUser.objects.create(email="g@example.com", name="G", google_sub="sub-1", email_verified=True)
        token = service.issue_tokens(user)["access_token"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(c.delete(BASE + "me").status_code, 400)  # nothing sent: still refused
        self.assertEqual(c.delete(BASE + "me", {"confirm": "DELETE"}, format="json").status_code, 200)
        self.assertFalse(AppUser.objects.exists())
        self.assertEqual(DeletedAppUser.objects.get().email, "g@example.com")
