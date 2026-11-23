import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Company, Membership, User

URL = "apps.accounts.google_login.verify_google_id_token"


@override_settings(CRM_GOOGLE_LOGIN=True, CRM_GOOGLE_LOGIN_DOMAIN="", GOOGLE_CLIENT_IDS=["web.apps.googleusercontent.com"])
class GoogleLoginTest(TestCase):
    def post(self, email="new@x.com"):
        with patch(URL, return_value={"email": email, "given_name": "N"}):
            return self.client.post(reverse("accounts:google_login"), json.dumps({"credential": "t"}),
                                    content_type="application/json")

    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")

    def test_new_email_becomes_viewer_and_logs_in(self):
        r = self.post()
        self.assertEqual(r.status_code, 200)
        u = User.objects.get(email="new@x.com")
        self.assertEqual(Membership.objects.get(user=u).role, "viewer")
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)

    def test_existing_email_is_linked_not_duplicated(self):
        u = User.objects.create_user("bob", "bob@x.com", "pw")
        Membership.objects.create(user=u, company=self.company, role="owner")
        self.assertEqual(self.post("BOB@x.com").status_code, 200)
        self.assertEqual(User.objects.filter(email__iexact="bob@x.com").count(), 1)

    def test_domain_limit(self):
        with override_settings(CRM_GOOGLE_LOGIN_DOMAIN="corp.com"):
            self.assertEqual(self.post().status_code, 403)
        self.assertFalse(User.objects.filter(email="new@x.com").exists())

    @override_settings(CRM_GOOGLE_LOGIN=False)
    def test_off_by_default(self):
        self.assertEqual(self.post().status_code, 404)
