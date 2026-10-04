from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase

from apps.accounts.models import Company, Membership
from apps.presence import service
from apps.presence.models import PresenceSession

User = get_user_model()


class ActivityLabelTest(TestCase):
    """The label comes from the path, so a client cannot choose its own."""

    def test_known_paths(self):
        cases = {
            "/tickets/": "Browsing tickets",
            "/tickets/14/": "Viewing ticket #14",
            "/errors/7/": "Looking at error group #7",
            "/dsr/": "Filling in the DSR",
            "/attendance/team/": "Checking team attendance",
            "/dashboards/": "On the home dashboard",
            "/": "On the home dashboard",
        }
        for path, label in cases.items():
            self.assertEqual(service.activity_for(path), label, path)

    def test_payroll_is_not_described(self):
        self.assertEqual(service.activity_for("/payroll/profiles/"), "In an admin area")

    def test_product_pages_name_no_product(self):
        self.assertEqual(service.activity_for("/products/9/"), "Browsing products")

    def test_unknown_path_is_generic(self):
        self.assertEqual(service.activity_for("/something/else/"), "Using the app")


class PresenceSocketTest(TransactionTestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.ann = User.objects.create_user("ann", password="pass1234", first_name="Ann")
        self.bob = User.objects.create_user("bob", password="pass1234")
        self.eve = User.objects.create_user("eve", password="pass1234")
        Membership.objects.create(user=self.ann, company=self.company, role="admin")
        Membership.objects.create(user=self.bob, company=self.company, role="developer")
        Membership.objects.create(user=self.eve, company=self.other, role="owner")

        # Log in here, in sync code: the test client touches the database, which
        # an async test body must not do directly.
        self.cookies = {}
        for name in ("ann", "bob", "eve"):
            # One client each: logging out of a shared client deletes the session
            # the previous cookie points at.
            client = Client()
            client.login(username=name, password="pass1234")
            self.cookies[name] = f"sessionid={client.cookies['sessionid'].value}".encode()

    def cookie(self, username):
        return self.cookies[username]

    def communicator(self, username=None, origin=b"http://localhost"):
        from core.asgi import application

        headers = [(b"origin", origin)]
        if username:
            headers.append((b"cookie", self.cookie(username)))
        return WebsocketCommunicator(application, "/ws/presence/", headers=headers)

    def test_anonymous_is_refused(self):
        async def run():
            comm = self.communicator()
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4401)

        async_to_sync(run)()

    def test_a_foreign_origin_is_refused_even_with_a_valid_session(self):
        async def run():
            comm = self.communicator("ann", origin=b"https://evil.example")
            connected, _ = await comm.connect()
            self.assertFalse(connected)

        async_to_sync(run)()

    def test_connect_sends_a_snapshot_with_the_user(self):
        async def run():
            comm = self.communicator("ann")
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            msg = await comm.receive_json_from()
            self.assertEqual(msg["event"], "presence")
            self.assertEqual([u["username"] for u in msg["users"]], ["ann"])
            self.assertEqual(msg["users"][0]["status"], "online")
            await comm.disconnect()

        async_to_sync(run)()

    def test_activity_is_labelled_by_the_server_and_seen_by_colleagues(self):
        async def run():
            ann = self.communicator("ann")
            bob = self.communicator("bob")
            await ann.connect()
            await ann.receive_json_from()
            await bob.connect()
            await bob.receive_json_from()
            await ann.receive_json_from()  # ann hears that bob joined

            await bob.send_json_to(
                {"type": "activity", "path": "/tickets/4/", "active": True, "activity": "Hacking the planet"}
            )
            update = await ann.receive_json_from()
            bob_row = next(u for u in update["users"] if u["username"] == "bob")
            self.assertEqual(bob_row["activity"], "Viewing ticket #4")
            await ann.disconnect()
            await bob.disconnect()

        async_to_sync(run)()

    def test_an_inactive_tab_shows_as_away(self):
        async def run():
            comm = self.communicator("ann")
            await comm.connect()
            await comm.receive_json_from()
            await comm.send_json_to({"type": "activity", "path": "/dsr/", "active": False})
            update = await comm.receive_json_from()
            self.assertEqual(update["users"][0]["status"], "away")
            await comm.disconnect()

        async_to_sync(run)()

    def test_other_companies_are_never_listed(self):
        async def run():
            ann = self.communicator("ann")
            eve = self.communicator("eve")
            await ann.connect()
            await ann.receive_json_from()
            await eve.connect()
            eve_snapshot = await eve.receive_json_from()
            self.assertEqual([u["username"] for u in eve_snapshot["users"]], ["eve"])
            self.assertTrue(await ann.receive_nothing())
            await ann.disconnect()
            await eve.disconnect()

        async_to_sync(run)()

    def test_leaving_removes_the_session(self):
        async def run():
            comm = self.communicator("ann")
            await comm.connect()
            await comm.receive_json_from()
            self.assertEqual(await database_sync_to_async(PresenceSession.objects.count)(), 1)
            await comm.disconnect()
            self.assertEqual(await database_sync_to_async(PresenceSession.objects.count)(), 0)

        async_to_sync(run)()

    def test_a_stale_session_is_not_listed(self):
        from datetime import timedelta

        from django.utils import timezone

        PresenceSession.objects.create(
            company=self.company, user=self.bob, channel_name="gone",
            last_seen=timezone.now() - timedelta(minutes=2),
        )
        PresenceSession.objects.filter(channel_name="gone").update(
            last_seen=timezone.now() - timedelta(minutes=2)
        )
        self.assertEqual(service.snapshot(self.company), [])
