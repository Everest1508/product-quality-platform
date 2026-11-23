import io
import json
import urllib.error
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, send_mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.appauth import mailflare_backend as mb
from apps.appauth.models import MailLog, MailflareConfig

BACKEND = {"EMAIL_BACKEND": "apps.appauth.mailflare_backend.MailflareEmailBackend",
           "DEFAULT_FROM_EMAIL": "CardSnap <no-reply@acme.test>", "DEBUG": False}
CFG = mb.Config("https://mf.test/api/v1/send", "SECRET-KEY-123", "box-1", "no-reply@acme.test", "env")


@override_settings(**BACKEND)
class BackendTest(TestCase):
    def send(self, **kw):
        return send_mail("Hi", "Body", None, ["a@x.com"], **kw)

    def test_posts_the_documented_payload_and_bearer_key(self):
        with mock.patch.object(mb, "load_config", return_value=CFG), \
             mock.patch.object(mb._opener, "open") as op:
            msg = EmailMessage("Hi", "Body", None, ["a@x.com"], bcc=["b@x.com"], cc=["c@x.com"])
            self.assertEqual(mb.MailflareEmailBackend().send_messages([msg]), 1)
        req = op.call_args[0][0]
        self.assertEqual(req.full_url, "https://mf.test/api/v1/send")
        self.assertEqual(req.get_header("Authorization"), "Bearer SECRET-KEY-123")
        self.assertEqual(json.loads(req.data), {
            "mailboxId": "box-1", "from": "CardSnap <no-reply@acme.test>", "to": ["a@x.com"],
            "cc": ["c@x.com"], "bcc": ["b@x.com"], "subject": "Hi", "text": "Body"})

    def test_wrong_from_address_fails_clearly_without_calling_the_api(self):
        with mock.patch.object(mb, "load_config", return_value=CFG), mock.patch.object(mb._opener, "open") as op:
            with self.assertRaisesMessage(mb.MailflareError, "not the allowed Mailflare mailbox"):
                send_mail("Hi", "Body", "other@evil.test", ["a@x.com"])
        op.assert_not_called()

    def test_api_error_is_reported_without_the_key(self):
        err = urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b'{"error":"bad key"}'))
        with mock.patch.object(mb, "load_config", return_value=CFG), mock.patch.object(mb._opener, "open", side_effect=err):
            with self.assertRaises(mb.MailflareError) as cm:
                self.send()
        self.assertIn("401", str(cm.exception))
        self.assertNotIn("SECRET-KEY-123", str(cm.exception))

    def test_fail_silently_and_not_configured(self):
        with mock.patch.object(mb, "load_config", return_value=None):
            self.assertEqual(self.send(fail_silently=True), 0)
            with self.assertRaisesMessage(mb.MailflareError, "not configured"):
                self.send()


class UiSettingsTest(TestCase):
    def setUp(self):
        U = get_user_model()
        co = Company.objects.create(name="Acme", slug="acme")
        self.admin = U.objects.create_user("adm", "adm@example.com", "pw-adm-123")
        self.dev = U.objects.create_user("dev", "dev@example.com", "pw-dev-123")
        Membership.objects.create(user=self.admin, company=co, role="admin")
        Membership.objects.create(user=self.dev, company=co, role="developer")
        self.url = reverse("email_settings")
        self.form = {"action": "save", "api_url": "https://mf.test/api/v1/send", "mailbox_id": "box-1",
                     "from_address": "no-reply@acme.test", "api_key": "SECRET-KEY-123"}

    def test_only_admins_can_see_or_change_it(self):
        self.client.force_login(self.dev)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.form).status_code, 403)
        self.assertFalse(MailflareConfig.objects.exists())

    def test_key_is_stored_encrypted_and_never_rendered(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.form)
        row = MailflareConfig.objects.get()
        self.assertNotIn("SECRET-KEY-123", row.api_key_encrypted)
        self.assertEqual(mb.load_config().key, "SECRET-KEY-123")
        self.assertNotContains(self.client.get(self.url), "SECRET-KEY-123")
        # blank key keeps the saved one; url must be https
        self.client.post(self.url, {**self.form, "api_key": "", "mailbox_id": "box-2"})
        self.assertEqual((mb.load_config().key, mb.load_config().mailbox_id), ("SECRET-KEY-123", "box-2"))
        self.assertEqual(self.client.post(self.url, {**self.form, "api_url": "http://x"}).status_code, 400)

    @override_settings(**BACKEND)
    def test_test_button_sends_to_the_admin(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.form)
        with mock.patch.object(mb._opener, "open") as op:
            self.client.post(self.url, {"action": "test"})
        self.assertEqual(json.loads(op.call_args[0][0].data)["to"], ["adm@example.com"])


@override_settings(**BACKEND)
class MailLogTest(TestCase):
    def test_sends_and_failures_are_counted_without_secrets(self):
        with mock.patch.object(mb, "load_config", return_value=CFG), mock.patch.object(mb._opener, "open"):
            send_mail("Welcome", "Body", None, ["a@x.com"])
        with mock.patch.object(mb, "load_config", return_value=CFG):
            with self.assertRaises(mb.MailflareError):
                send_mail("Bad", "Body", "other@evil.test", ["b@x.com"])
        self.assertEqual(list(MailLog.objects.order_by("id").values_list("status", "to_addrs", "subject")),
                         [("sent", "a@x.com", "Welcome"), ("failed", "b@x.com", "Bad")])
        self.assertNotIn("SECRET-KEY-123", "".join(MailLog.objects.values_list("error", flat=True)))

    def test_page_shows_counts_to_admins(self):
        U = get_user_model()
        co = Company.objects.create(name="Acme", slug="acme")
        adm = U.objects.create_user("adm", "adm@example.com", "pw-adm-123")
        Membership.objects.create(user=adm, company=co, role="admin")
        MailLog.objects.create(to_addrs="a@x.com", subject="Welcome", status="sent")
        self.client.force_login(adm)
        r = self.client.get(reverse("email_settings"))
        self.assertEqual((r.context["mail_stats"]["today"], r.context["mail_stats"]["total"]), (1, 1))
        self.assertContains(r, "Welcome")
