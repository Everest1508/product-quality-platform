from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.notifications.models import Notification
from apps.presence import service as presence
from apps.products.models import Product, ProductAccess
from apps.tickets import mentions
from apps.tickets.models import Ticket, TicketComment

User = get_user_model()


def make(username, company, role="developer", first=""):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234", first_name=first)
    Membership.objects.create(user=user, company=company, role=role)
    return user


class ExtractTest(TestCase):
    def test_finds_plain_mentions_once_in_order(self):
        self.assertEqual(mentions.extract_usernames("hi @Ann and @bob, @ann again"), ["ann", "bob"])

    def test_an_email_is_not_a_mention(self):
        self.assertEqual(mentions.extract_usernames("write to ann@example.com"), [])
        self.assertEqual(mentions.extract_usernames("x@y @ok"), ["ok"])

    def test_a_trailing_full_stop_is_not_part_of_the_name(self):
        self.assertEqual(mentions.extract_usernames("thanks @ann."), ["ann"])

    def test_empty_and_none(self):
        self.assertEqual(mentions.extract_usernames(""), [])
        self.assertEqual(mentions.extract_usernames(None), [])


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = make("owner", self.company, "owner", "Olive")
        self.ann = make("ann", self.company, "developer", "Ann")
        self.bob = make("bob", self.company, "developer", "Bob")
        self.cat = make("cat", self.company, "viewer", "Cat")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        ProductAccess.objects.create(company=self.company, product=self.product, user=self.ann)
        ProductAccess.objects.create(company=self.company, product=self.product, user=self.bob)
        self.ticket = Ticket.objects.create(company=self.company, product=self.product, title="Bug", created_by=self.owner)
        self.ticket.set_assignees([self.bob], actor=self.owner)
        Notification.objects.all().delete()

    def comment(self, as_user, body):
        self.client.login(username=as_user.username, password="pass1234")
        return self.client.post(f"/ui-api/v1/tickets/{self.ticket.pk}/comments/", {"body": body}, content_type="application/json")


class ResolveTest(Base):
    def test_only_people_who_can_open_the_ticket_resolve(self):
        found = {u.username for u in mentions.resolve("@ann @cat @owner @nobody", self.ticket, self.company)}
        self.assertEqual(found, {"ann", "owner"})  # cat has no access to the product

    def test_lookup_ignores_case(self):
        self.assertEqual([u.username for u in mentions.resolve("@ANN", self.ticket, self.company)], ["ann"])

    def test_autocomplete_offers_only_people_with_access(self):
        names = {c["username"] for c in mentions.candidates_json(self.ticket, self.company)}
        self.assertEqual(names, {"owner", "ann", "bob"})


class CommentNotificationTest(Base):
    def test_a_mention_notifies_the_person_once_with_a_mention_not_a_comment(self):
        self.comment(self.owner, "please look @ann")
        kinds = {n.user.username: n.kind for n in Notification.objects.all()}
        self.assertEqual(kinds["ann"], "mention")
        self.assertEqual(Notification.objects.filter(user=self.ann).count(), 1)

    def test_assignees_get_a_plain_comment_notice(self):
        self.comment(self.owner, "any update?")
        self.assertEqual(Notification.objects.get(user=self.bob).kind, "comment")

    def test_the_author_is_never_notified(self):
        self.comment(self.bob, "done, @bob will recheck")
        self.assertFalse(Notification.objects.filter(user=self.bob).exists())

    def test_the_creator_hears_about_comments_too(self):
        self.comment(self.bob, "started")
        self.assertEqual(Notification.objects.get(user=self.owner).kind, "comment")

    def test_someone_without_access_is_not_notified_and_stays_plain_text(self):
        self.comment(self.owner, "psst @cat")
        self.assertFalse(Notification.objects.filter(user=self.cat).exists())
        comment = TicketComment.objects.get()
        self.assertEqual(comment.mentions.count(), 0)
        shown = self.client.get(f"/ui-api/v1/tickets/{self.ticket.pk}/").json()["comments"][0]
        self.assertEqual(shown["mentions"], [])

    def test_the_notification_points_at_the_ticket(self):
        self.comment(self.owner, "@ann look")
        self.assertEqual(Notification.objects.get(user=self.ann).url, f"/tickets/{self.ticket.pk}/")




class DetailPageTest(Base):
    def test_the_comment_box_offers_only_people_with_access(self):
        self.client.login(username="owner", password="pass1234")
        offered = [c["username"] for c in self.client.get(f"/ui-api/v1/tickets/{self.ticket.pk}/").json()["mention_candidates"]]
        self.assertIn("ann", offered)
        self.assertNotIn("cat", offered)


class ViewerMarkerTest(TestCase):
    def test_a_ticket_page_exposes_its_number(self):
        self.assertEqual(presence.ticket_id_for("/tickets/14/"), 14)
        self.assertEqual(presence.ticket_id_for("/products/3/tickets/14/"), 14)

    def test_other_pages_expose_nothing(self):
        for path in ("/tickets/", "/tickets/14/edit/", "/payroll/profiles/", "/dsr/", "", None):
            self.assertIsNone(presence.ticket_id_for(path), path)
