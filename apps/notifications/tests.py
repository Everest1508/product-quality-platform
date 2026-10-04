import json
import types
from unittest import mock

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.notifications import service
from apps.notifications.models import Notification, PushSubscription
from apps.products.models import Product
from apps.tickets.models import Ticket

User = get_user_model()


class SyncThread:
    """Runs the target when started, so a test can see what a background send did."""

    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


def sync_threads():
    """Swap the `threading` name inside the service module only. Patching
    `threading.Thread` itself replaces it for every library in the process."""
    return mock.patch.object(service, "threading", types.SimpleNamespace(Thread=SyncThread))


def make(username, company, role="developer"):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.ann = make("ann", self.company, "owner")
        self.bob = make("bob", self.company)
        self.eve = make("eve", self.other, "owner")


class NotifyTest(Base):
    def test_it_creates_a_row_for_the_recipient(self):
        n = service.notify(user=self.bob, company=self.company, kind="comment", title="Hi", url="/tickets/1/", actor=self.ann)
        self.assertEqual((n.user, n.company, n.actor), (self.bob, self.company, self.ann))
        self.assertFalse(n.is_read)

    def test_you_are_never_notified_of_your_own_action(self):
        self.assertIsNone(service.notify(user=self.ann, company=self.company, kind="comment", title="x", actor=self.ann))
        self.assertEqual(Notification.objects.count(), 0)

    def test_notify_many_sends_one_per_person(self):
        rows = service.notify_many([self.bob, self.bob, self.ann], company=self.company, kind="system", title="x", actor=self.ann)
        self.assertEqual([r.user for r in rows], [self.bob])

    def test_only_site_relative_paths_are_kept(self):
        for bad in ("https://evil.example/x", "//evil.example", "javascript:alert(1)", "/\\evil", ""):
            self.assertEqual(service.safe_path(bad), "", bad)
        self.assertEqual(service.safe_path("/tickets/3/"), "/tickets/3/")

    def test_long_text_is_trimmed_not_rejected(self):
        n = service.notify(user=self.bob, company=self.company, kind="system", title="t" * 500, body="b" * 900)
        self.assertEqual((len(n.title), len(n.body)), (200, 300))


class ViewsTest(Base):
    def setUp(self):
        super().setUp()
        self.mine = service.notify(user=self.bob, company=self.company, kind="comment", title="Mine", url="/tickets/9/")
        self.theirs = service.notify(user=self.ann, company=self.company, kind="comment", title="Hers", url="/tickets/9/")
        self.client.login(username="bob", password="pass1234")

    def test_the_feed_has_only_my_notifications(self):
        data = self.client.get(reverse("notifications:feed")).json()
        self.assertEqual(data["unread"], 1)
        self.assertEqual([i["title"] for i in data["items"]], ["Mine"])

    def test_the_feed_is_per_workspace(self):
        service.notify(user=self.bob, company=self.other, kind="system", title="Elsewhere")
        data = self.client.get(reverse("notifications:feed")).json()
        self.assertNotIn("Elsewhere", [i["title"] for i in data["items"]])

    def test_opening_marks_read_and_goes_to_the_page(self):
        response = self.client.get(reverse("notifications:open", args=[self.mine.pk]))
        self.assertRedirects(response, "/tickets/9/", fetch_redirect_response=False)
        self.mine.refresh_from_db()
        self.assertTrue(self.mine.is_read)

    def test_someone_elses_notification_is_a_404(self):
        self.assertEqual(self.client.get(reverse("notifications:open", args=[self.theirs.pk])).status_code, 404)
        self.theirs.refresh_from_db()
        self.assertFalse(self.theirs.is_read)

    def test_a_stored_unsafe_url_cannot_redirect_off_site(self):
        Notification.objects.filter(pk=self.mine.pk).update(url="https://evil.example/")
        response = self.client.get(reverse("notifications:open", args=[self.mine.pk]))
        self.assertRedirects(response, reverse("notifications:list"), fetch_redirect_response=False)

    def test_mark_all_read_touches_only_mine(self):
        self.client.post(reverse("notifications:read_all"))
        self.mine.refresh_from_db(); self.theirs.refresh_from_db()
        self.assertTrue(self.mine.is_read)
        self.assertFalse(self.theirs.is_read)

    def test_the_list_page_renders_and_filters(self):
        self.assertContains(self.client.get(reverse("notifications:list")), "Mine")
        self.client.get(reverse("notifications:open", args=[self.mine.pk]))
        self.assertNotContains(self.client.get(reverse("notifications:list") + "?filter=unread"), "Mine")

    def test_signed_out_visitors_are_sent_away(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(reverse("notifications:feed")).status_code, 200)


class AssignmentTest(Base):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.ticket = Ticket.objects.create(company=self.company, product=self.product, title="Broken", created_by=self.ann)

    def test_new_assignees_are_told_but_not_the_actor(self):
        self.ticket.set_assignees([self.ann, self.bob], actor=self.ann)
        rows = Notification.objects.filter(kind="assigned")
        self.assertEqual([r.user for r in rows], [self.bob])
        self.assertEqual(rows[0].url, f"/tickets/{self.ticket.pk}/")

    def test_people_already_assigned_are_not_told_again(self):
        self.ticket.set_assignees([self.bob], actor=self.ann)
        self.ticket.set_assignees([self.bob], actor=self.ann)
        self.assertEqual(Notification.objects.filter(kind="assigned").count(), 1)


class PushSubscriptionTest(Base):
    payload = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}

    def post(self, data, name="bob"):
        c = Client(); c.login(username=name, password="pass1234")
        return c.post(reverse("notifications:push_subscribe"), json.dumps(data), content_type="application/json")

    def test_it_stores_a_subscription(self):
        self.assertEqual(self.post(self.payload).status_code, 200)
        self.assertEqual(PushSubscription.objects.get().user, self.bob)

    def test_a_second_person_on_the_same_browser_takes_it_over(self):
        self.post(self.payload, "bob"); self.post(self.payload, "ann")
        self.assertEqual(PushSubscription.objects.get().user, self.ann)

    def test_bad_payloads_are_a_400(self):
        for bad in ({}, {"endpoint": "http://insecure", "keys": {"p256dh": "k", "auth": "a"}}, {"endpoint": "https://x", "keys": {}}):
            self.assertEqual(self.post(bad).status_code, 400, bad)

    @override_settings(WEBPUSH_VAPID_PRIVATE_KEY="priv", WEBPUSH_VAPID_SUBJECT="mailto:a@b.c")
    def test_a_push_goes_to_each_subscription_of_the_recipient_only(self):
        PushSubscription.objects.create(user=self.bob, endpoint="https://push.example/b", p256dh="k", auth="a")
        PushSubscription.objects.create(user=self.ann, endpoint="https://push.example/a", p256dh="k", auth="a")
        sent = []
        with mock.patch.object(service, "_send_all", lambda subs, payload: sent.append((subs, payload))), sync_threads():
            service.notify(user=self.bob, company=self.company, kind="comment", title="Hello", actor=self.ann)
        self.assertEqual(len(sent), 1)
        self.assertEqual([s.endpoint for s in sent[0][0]], ["https://push.example/b"])
        self.assertEqual(json.loads(sent[0][1])["title"], "Hello")

    def test_no_keys_means_no_push(self):
        PushSubscription.objects.create(user=self.bob, endpoint="https://push.example/b", p256dh="k", auth="a")
        sent = []
        with mock.patch.object(service, "_send_all", lambda subs, payload: sent.append(1)), sync_threads():
            service.notify(user=self.bob, company=self.company, kind="comment", title="Hello", actor=self.ann)
        self.assertEqual(sent, [])


class LiveDeliveryTest(TransactionTestCase):
    """The row is pushed down the same socket as presence."""

    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.bob = make("bob", self.company)
        client = Client(); client.login(username="bob", password="pass1234")
        self.cookie = f"sessionid={client.cookies['sessionid'].value}".encode()

    def test_a_new_notification_arrives_on_the_open_socket(self):
        from core.asgi import application

        async def run():
            comm = WebsocketCommunicator(application, "/ws/presence/", headers=[(b"origin", b"http://localhost"), (b"cookie", self.cookie)])
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            await comm.receive_json_from()  # presence snapshot
            await database_sync_to_async(service.notify)(user=self.bob, company=self.company, kind="comment", title="Ping", url="/tickets/1/")
            msg = await comm.receive_json_from()
            self.assertEqual(msg["event"], "notification")
            self.assertEqual(msg["notification"]["title"], "Ping")
            self.assertEqual(msg["unread"], 1)
            await comm.disconnect()

        async_to_sync(run)()
