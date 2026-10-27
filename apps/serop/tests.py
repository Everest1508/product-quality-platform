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


class ProjectHostingTest(TestCase):
    """Servers are added and assigned in the CRM; Serop lists what a person may open."""

    def setUp(self):
        from apps.products.models import Product, ProductAccess

        self.company = Company.objects.create(name="Acme", slug="acme")
        self.users = {}
        for name, role in (("admin", "admin"), ("dev", "developer"), ("other", "developer")):
            user = User.objects.create_user(name, password="pass1234", email=f"{name}@example.com")
            Membership.objects.create(user=user, company=self.company, role=role)
            self.users[name] = user
        self.app = Product.objects.create(company=self.company, name="App", slug="app")
        self.site = Product.objects.create(company=self.company, name="Site", slug="site")
        ProductAccess.objects.create(company=self.company, product=self.app, user=self.users["dev"])

    def web_client(self, name):
        from django.test import Client

        client = Client()
        client.force_login(self.users[name])
        session = client.session
        session[settings.ACTIVE_COMPANY_SESSION_KEY] = self.company.pk
        session.save()
        return client

    def api_client(self, name):
        _, raw = ExternalAccessToken.create_token(self.users[name])
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        return client

    def add_server(self, password="S3cret!"):
        res = self.web_client("admin").post(
            "/servers/", {"name": "prod", "host": "10.0.0.5", "username": "deploy", "password": password}
        )
        self.assertEqual(res.status_code, 302)
        return SeropSharedServer.objects.get(name="prod")

    def host(self, product, server, path):
        return self.web_client("admin").post(
            f"/products/{product.pk}/hosting/", {"server": server.pk, "server_path": path}
        )

    def test_password_is_encrypted_at_rest(self):
        server = self.add_server()
        self.assertNotIn("S3cret!", server.encrypted_password)
        self.assertEqual(Fernet(settings.SHARED_SERVER_ENCRYPTION_KEY).decrypt(server.encrypted_password.encode()), b"S3cret!")
        page = self.web_client("admin").get("/servers/").content.decode()
        self.assertIn("password stored", page)
        self.assertNotIn("S3cret!", page)
        self.assertNotIn(server.encrypted_password, page)

    def test_server_needs_all_fields(self):
        res = self.web_client("admin").post("/servers/", {"name": "x", "host": "h", "username": "u", "password": ""})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(SeropSharedServer.objects.exists())

    def test_only_admins_manage_servers_and_hosting(self):
        server = self.add_server()
        dev = self.web_client("dev")
        self.assertEqual(dev.get("/servers/").status_code, 403)
        self.assertEqual(dev.post("/servers/", {"name": "x", "host": "h", "username": "u", "password": "p"}).status_code, 403)
        self.assertEqual(dev.post(f"/servers/{server.pk}/delete/").status_code, 403)
        res = dev.post(f"/products/{self.app.pk}/hosting/", {"server": server.pk, "server_path": "/srv/app"})
        self.assertEqual(res.status_code, 403)

    def test_hosting_path_is_validated(self):
        server = self.add_server()
        for bad in ("srv/app", "/srv/../etc", "/", "/srv/app; rm -rf /", "/srv/app name"):
            self.host(self.app, server, bad)
            self.app.refresh_from_db()
            self.assertIsNone(self.app.server_id, bad)
        self.host(self.app, server, "/srv/app/")
        self.app.refresh_from_db()
        self.assertEqual((self.app.server_id, self.app.server_path), (server.pk, "/srv/app"))

    def test_server_from_another_company_is_refused(self):
        other = Company.objects.create(name="Other", slug="other")
        foreign = SeropSharedServer.objects.create(company=other, owner=self.users["admin"], name="x", host="h", username="u")
        self.host(self.app, foreign, "/srv/app")
        self.app.refresh_from_db()
        self.assertIsNone(self.app.server_id)

    def test_person_sees_only_projects_they_are_allocated_to(self):
        server = self.add_server()
        self.host(self.app, server, "/srv/app")
        self.host(self.site, server, "/srv/site")

        dev = self.api_client("dev").get("/api/serop/projects").json()["projects"]
        self.assertEqual([p["name"] for p in dev], ["App"])
        self.assertEqual(dev[0]["path"], "/srv/app")
        self.assertEqual(dev[0]["server"]["password"], "S3cret!")

        self.assertEqual(self.api_client("other").get("/api/serop/projects").json()["projects"], [])
        admin = self.api_client("admin").get("/api/serop/projects").json()["projects"]
        self.assertEqual(sorted(p["name"] for p in admin), ["App", "Site"])

    def test_unhosted_projects_are_not_listed(self):
        self.assertEqual(self.api_client("dev").get("/api/serop/projects").json()["projects"], [])

    def test_removing_a_server_unhosts_its_projects(self):
        server = self.add_server()
        self.host(self.app, server, "/srv/app")
        self.web_client("admin").post(f"/servers/{server.pk}/delete/")
        self.assertEqual(self.api_client("dev").get("/api/serop/projects").json()["projects"], [])

    def test_project_page_shows_hosting_to_admins_only(self):
        server = self.add_server()
        self.host(self.app, server, "/srv/app")
        page = self.web_client("admin").get(f"/products/{self.app.pk}/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="hosting"')
        self.assertContains(page, "/srv/app")
        dev_page = self.web_client("dev").get(f"/products/{self.app.pk}/")
        self.assertEqual(dev_page.status_code, 200)
        self.assertNotContains(dev_page, 'id="hosting"')
        self.assertNotContains(dev_page, "10.0.0.5")
