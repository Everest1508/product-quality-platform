from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.notifications import service
from apps.notifications.models import Notification

User = get_user_model()


def make(username, company, role="developer"):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class NotificationsApiTest(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.ann = make("ann", self.acme, "owner")
        self.bob = make("bob", self.acme)
        # bob also belongs to the other company
        Membership.objects.create(user=self.bob, company=self.other, role="viewer")
        self.mine = service.notify(user=self.bob, company=self.acme, kind="comment", title="Mine", url="/tickets/9/", actor=self.ann)
        self.read = service.notify(user=self.bob, company=self.acme, kind="assigned", title="Old", actor=self.ann)
        Notification.objects.filter(pk=self.read.pk).update(read_at=self.read.created_at)
        self.hers = service.notify(user=self.ann, company=self.acme, kind="comment", title="Hers", actor=self.bob)
        self.elsewhere = service.notify(user=self.bob, company=self.other, kind="system", title="Elsewhere")
        self.client.login(username="bob", password="pass1234")
        self.activate(self.acme)
        self.url = reverse("uiapi:notifications")

    def activate(self, company):
        # With two memberships and no session key the middleware picks one by
        # its own ordering, so say which workspace is active.
        session = self.client.session
        session[settings.ACTIVE_COMPANY_SESSION_KEY] = company.pk
        session.save()

    def test_lists_only_my_notifications_in_the_active_company(self):
        data = self.client.get(self.url).json()
        self.assertEqual([i["title"] for i in data["items"]], ["Old", "Mine"])  # newest first
        self.assertEqual(data["unread"], 1)
        item = next(i for i in data["items"] if i["title"] == "Mine")
        self.assertEqual(item["kind_label"], "New comment")
        self.assertEqual(item["url"], f"/notifications/{self.mine.pk}/open/")
        self.assertFalse(item["read"])

    def test_company_switch_changes_what_is_listed(self):
        self.activate(self.other)
        titles = [i["title"] for i in self.client.get(self.url).json()["items"]]
        self.assertEqual(titles, ["Elsewhere"])

    def test_unread_filter_hides_read_rows_but_count_is_unchanged(self):
        data = self.client.get(self.url, {"filter": "unread"}).json()
        self.assertEqual([i["title"] for i in data["items"]], ["Mine"])
        self.assertEqual(data["unread"], 1)

    def test_list_is_capped_at_100(self):
        for i in range(105):
            service.notify(user=self.bob, company=self.acme, kind="system", title=f"n{i}")
        self.assertEqual(len(self.client.get(self.url).json()["items"]), 100)

    def test_anonymous_gets_json_403_not_a_redirect(self):
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_signed_in_without_a_company_gets_403(self):
        User.objects.create_user("loner", "l@t.local", "pass1234")
        c = Client()
        c.login(username="loner", password="pass1234")
        response = c.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "No active company.")

    def test_read_all_marks_only_my_rows_in_this_company(self):
        response = self.client.post(reverse("uiapi:notifications_read_all"))
        self.assertEqual(response.json(), {"unread": 0})
        self.assertEqual(Notification.objects.filter(user=self.bob, company=self.acme, read_at__isnull=True).count(), 0)
        self.hers.refresh_from_db()
        self.elsewhere.refresh_from_db()
        self.assertFalse(self.hers.is_read)  # someone else's
        self.assertFalse(self.elsewhere.is_read)  # another company

    def test_post_without_csrf_token_is_rejected(self):
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="bob", password="pass1234")
        self.assertEqual(strict.post(reverse("uiapi:notifications_read_all")).status_code, 403)
        self.mine.refresh_from_db()
        self.assertFalse(self.mine.is_read)


import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

from django.test import override_settings  # noqa: E402


class NotificationsPageSwitchTest(TestCase):
    def setUp(self):
        co = Company.objects.create(name="Acme", slug="acme")
        make("bob", co)
        self.client.login(username="bob", password="pass1234")

    def test_default_is_the_legacy_page(self):
        response = self.client.get("/notifications/")
        self.assertTemplateUsed(response, "notifications/list.html")
        self.assertNotContains(response, 'id="react-root"')

    def test_switch_on_renders_the_react_shell(self):
        dist = Path(tempfile.mkdtemp())
        (dist / "app.js").write_text("")
        with override_settings(REACT_PAGES={"notifications"}, FRONTEND_DIST=dist):
            response = self.client.get("/notifications/")
        self.assertTemplateUsed(response, "notifications/list_react.html")
        self.assertContains(response, 'id="react-root"')
        self.assertContains(response, 'data-page="notifications"')
        self.assertContains(response, 'data-csrf="')
        self.assertContains(response, "/ui/app.js")

    @override_settings(REACT_PAGES={"notifications"}, FRONTEND_DIST=Path("/nonexistent"))
    def test_switch_on_with_no_build_says_so(self):
        self.assertContains(self.client.get("/notifications/"), "frontend has not been built")


from apps.products.models import Product, ProductAccess  # noqa: E402
from apps.tickets.models import Ticket  # noqa: E402


class BootstrapTest(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = make("owner", self.acme, "owner")
        self.dev = make("dev", self.acme, "developer")
        self.p_open = Product.objects.create(company=self.acme, name="Open", slug="open")
        self.p_hidden = Product.objects.create(company=self.acme, name="Hidden", slug="hidden")
        self.p_other = Product.objects.create(company=self.other, name="Foreign", slug="foreign")
        ProductAccess.objects.create(company=self.acme, user=self.dev, product=self.p_open)
        for p in (self.p_open, self.p_hidden, self.p_other):
            Ticket.objects.create(company=p.company, product=p, title="t")
        self.url = reverse("uiapi:bootstrap")

    def login(self, name):
        self.client.login(username=name, password="pass1234")
        session = self.client.session
        session[settings.ACTIVE_COMPANY_SESSION_KEY] = self.acme.pk
        session.save()

    def test_shape_and_identity(self):
        self.login("dev")
        data = self.client.get(self.url).json()
        self.assertEqual(data["user"]["name"], "dev")
        self.assertEqual(data["user"]["initial"], "D")
        self.assertEqual(data["user"]["role_label"], "Developer")
        self.assertEqual(data["company"]["name"], "Acme")
        self.assertFalse(data["is_admin"])
        self.assertTrue(data["version"])
        self.assertTrue(data["csrf"])
        self.assertEqual(data["urls"]["tickets"], reverse("tickets:ticket_board"))
        self.assertEqual(data["urls"]["search"], "/search/")
        self.assertEqual(
            data["workspaces"],
            [{"company_id": self.acme.pk, "name": "Acme", "role_label": "Developer", "current": True}],
        )

    def test_counts_only_cover_products_the_user_can_open(self):
        self.login("dev")
        self.assertEqual(self.client.get(self.url).json()["counts"]["open_tickets"], 1)

    def test_owner_sees_every_product_in_the_company_but_not_other_companies(self):
        self.login("owner")
        data = self.client.get(self.url).json()
        self.assertEqual(data["counts"]["open_tickets"], 2)
        self.assertTrue(data["is_admin"])

    def test_flash_messages_are_delivered_once(self):
        self.login("dev")
        # queue a message the way a legacy view would
        self.client.post(reverse("accounts:company_switch"), {"company_id": self.acme.pk})
        first = self.client.get(self.url).json()["messages"]
        again = self.client.get(self.url).json()["messages"]
        self.assertEqual([m["tags"] for m in first], ["success"])
        self.assertEqual(first[0]["text"], "Switched to Acme.")
        self.assertEqual(again, [])

    def test_anonymous_and_no_company_are_403(self):
        self.assertEqual(Client().get(self.url).status_code, 403)
        User.objects.create_user("loner", "l@t.local", "pass1234")
        c = Client()
        c.login(username="loner", password="pass1234")
        self.assertEqual(c.get(self.url).status_code, 403)
