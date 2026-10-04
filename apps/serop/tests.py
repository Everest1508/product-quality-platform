from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Company, ExternalAccessToken, Membership
from apps.serop.models import SeropSharedServer

User = get_user_model()


class SharedServerRoleTest(TestCase):
    """The password of a shared server is for people who work on it.

    Serop adds new team members as `viewer`, and `viewer` used to be enough to
    read every credential in the company.
    """

    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.users = {}
        for name, role in (("owner", "owner"), ("admin", "admin"), ("dev", "developer"),
                           ("support", "support"), ("viewer", "viewer")):
            user = User.objects.create_user(name, password="pass1234", email=f"{name}@example.com")
            Membership.objects.create(user=user, company=self.company, role=role)
            self.users[name] = user
        key = Fernet(settings.SHARED_SERVER_ENCRYPTION_KEY)
        self.server = SeropSharedServer.objects.create(
            company=self.company, owner=self.users["owner"], name="prod", host="10.0.0.5",
            username="root", encrypted_password=key.encrypt(b"S3cret!").decode(),
        )

    def client_for(self, name):
        _, raw = ExternalAccessToken.create_token(self.users[name])
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        return client

    def credentials(self, name):
        return self.client_for(name).get(f"/api/serop/shared-servers/{self.server.pk}/credentials")

    def test_owner_admin_and_developer_can_read_the_password(self):
        for name in ("owner", "admin", "dev"):
            response = self.credentials(name)
            self.assertEqual(response.status_code, 200, name)
            self.assertEqual(response.json()["credentials"]["password"], "S3cret!")

    def test_viewer_and_support_cannot(self):
        for name in ("viewer", "support"):
            response = self.credentials(name)
            self.assertEqual(response.status_code, 403, name)
            self.assertNotIn("S3cret!", response.content.decode())

    def test_a_stranger_gets_a_404(self):
        outsider = User.objects.create_user("outsider", password="pass1234")
        _, raw = ExternalAccessToken.create_token(outsider)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        response = client.get(f"/api/serop/shared-servers/{self.server.pk}/credentials")
        self.assertEqual(response.status_code, 404)

    def test_the_server_list_never_carries_the_password(self):
        response = self.client_for("viewer").get("/api/serop/shared-servers")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("S3cret!", response.content.decode())

    def test_only_owner_or_admin_can_add_a_server(self):
        body = {"teamId": self.company.pk, "name": "x", "host": "h", "username": "u", "password": "p"}
        for name, expected in (("owner", 201), ("admin", 201), ("dev", 403), ("viewer", 403)):
            response = self.client_for(name).post("/api/serop/shared-servers", body, format="json")
            self.assertEqual(response.status_code, expected, name)

    def test_a_non_string_password_is_a_400_not_a_crash(self):
        body = {"teamId": self.company.pk, "name": "x", "host": "h", "username": "u", "password": 12345}
        response = self.client_for("owner").post("/api/serop/shared-servers", body, format="json")
        self.assertEqual(response.status_code, 400)
