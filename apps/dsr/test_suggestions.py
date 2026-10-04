from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.dashboards.service import log_activity
from apps.dsr import service
from apps.dsr.models import DSREntry
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


def make(username, company, role="developer"):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = make("owner", self.company, "owner")
        self.dev = make("dev", self.company)
        self.other_dev = make("other", self.company)
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.hidden = Product.objects.create(name="Hidden", slug="hidden", company=self.company)
        for user in (self.dev, self.other_dev):
            ProductAccess.objects.create(company=self.company, product=self.product, user=user)
        self.today = timezone.localdate()

    def ticket(self, title="Fix login", product=None, ticket_type="bug", status="open", assignee=None):
        t = Ticket.objects.create(company=self.company, product=product or self.product, title=title,
                                  ticket_type=ticket_type, status=status, created_by=self.owner)
        if assignee:
            t.set_assignees([assignee])
        return t

    def did(self, ticket, user=None, event="ticket_status_changed", hour=9, minute=0, day=None, to=None):
        day = day or self.today
        entry = log_activity(
            self.company, event, f"{event} #{ticket.pk}", actor=user or self.dev,
            target_content_type="ticket", target_object_id=ticket.pk,
            metadata={"to": to} if to else None,
        )
        moment = timezone.make_aware(datetime.combine(day, time(hour, minute)))
        ActivityLog.objects.filter(pk=entry.pk).update(created_at=moment)
        return entry

    def suggest(self, user=None, day=None):
        return service.suggestions(self.company, user or self.dev, day or self.today)


class SuggestionTest(Base):
    def test_a_ticket_you_touched_today_is_suggested(self):
        t = self.ticket()
        self.did(t, event="ticket_commented")
        rows = self.suggest()
        self.assertEqual([r["number"] for r in rows], [t.pk])
        self.assertEqual(rows[0]["did"], "Commented")

    def test_what_happened_is_in_words(self):
        t = self.ticket()
        self.did(t, event="ticket_status_changed", to="testing")
        self.did(t, event="ticket_commented", hour=10)
        self.assertEqual(self.suggest()[0]["did"], "Moved it to testing and commented")

    def test_resolving_suggests_a_completed_entry(self):
        t = self.ticket(status="resolved")
        self.did(t, to="resolved")
        row = self.suggest()[0]
        self.assertEqual((row["status"], row["did"]), ("completed", "Resolved it"))

    def test_category_follows_the_ticket_type(self):
        bug, feat, other = self.ticket("a", ticket_type="bug"), self.ticket("b", ticket_type="feature"), self.ticket("c", ticket_type="question")
        for t in (bug, feat, other):
            self.did(t, event="ticket_commented")
        cats = {r["number"]: r["category"] for r in self.suggest()}
        self.assertEqual(cats, {bug.pk: "bug_fix", feat.pk: "feature", other.pk: "ticket"})

    def test_an_assigned_ticket_in_progress_is_suggested_even_without_activity(self):
        t = self.ticket(status="in_progress", assignee=self.dev)
        row = self.suggest()[0]
        self.assertEqual((row["number"], row["touched"], row["did"]), (t.pk, False, "Assigned to you, in progress"))

    def test_touched_tickets_come_before_merely_assigned_ones(self):
        quiet = self.ticket("quiet", status="in_progress", assignee=self.dev)
        busy = self.ticket("busy")
        self.did(busy, event="ticket_commented")
        self.assertEqual([r["number"] for r in self.suggest()], [busy.pk, quiet.pk])

    def test_a_ticket_already_logged_today_is_left_out(self):
        t = self.ticket()
        self.did(t, event="ticket_commented")
        DSREntry.objects.create(company=self.company, user=self.dev, date=self.today, ticket=t, task_name="x", hours_spent=Decimal("1"))
        self.assertEqual(self.suggest(), [])

    def test_an_entry_on_another_day_does_not_hide_it(self):
        t = self.ticket()
        self.did(t, event="ticket_commented")
        DSREntry.objects.create(company=self.company, user=self.dev, date=self.today - timedelta(days=1), ticket=t, task_name="x", hours_spent=Decimal("1"))
        self.assertEqual(len(self.suggest()), 1)

    def test_other_peoples_activity_is_not_yours(self):
        t = self.ticket()
        self.did(t, user=self.other_dev, event="ticket_commented")
        self.assertEqual(self.suggest(), [])

    def test_other_days_are_not_today(self):
        t = self.ticket()
        self.did(t, event="ticket_commented", day=self.today - timedelta(days=1))
        self.assertEqual(self.suggest(), [])
        self.assertEqual(len(self.suggest(day=self.today - timedelta(days=1))), 1)

    def test_a_product_you_cannot_open_is_never_suggested(self):
        secret = self.ticket("secret", product=self.hidden)
        self.did(secret, event="ticket_commented")
        self.assertEqual(self.suggest(), [])
        # an owner sees every product, so the same activity is theirs to log
        self.did(secret, user=self.owner, event="ticket_commented")
        self.assertEqual(len(self.suggest(user=self.owner)), 1)

    def test_hours_are_a_guess_from_the_span_in_quarters(self):
        t = self.ticket()
        self.did(t, event="ticket_commented", hour=9, minute=0)
        self.did(t, event="ticket_commented", hour=10, minute=40)
        self.assertEqual(self.suggest()[0]["hours"], Decimal("1.75"))  # 100 min is 6.67 quarters, so 7

    def test_a_single_touch_defaults_to_an_hour_and_long_spans_are_capped(self):
        a, b = self.ticket("a"), self.ticket("b")
        self.did(a, event="ticket_commented")
        self.did(b, event="ticket_commented", hour=8)
        self.did(b, event="ticket_commented", hour=19)
        hours = {r["number"]: r["hours"] for r in self.suggest()}
        self.assertEqual(hours, {a.pk: Decimal("1.00"), b.pk: Decimal("4.00")})

    def test_the_list_is_capped(self):
        for i in range(12):
            self.did(self.ticket(f"t{i}"), event="ticket_commented")
        self.assertEqual(len(self.suggest()), 8)


class AddViewTest(Base):
    url = lambda self: reverse("dsr:dsr_suggestion_add")

    def setUp(self):
        super().setUp()
        self.t = self.ticket("Login bug")
        self.did(self.t, event="ticket_commented")
        self.client.login(username="dev", password="pass1234")

    def add(self, **extra):
        data = {"ticket_id": self.t.pk, "hours": "1.5", "date": self.today.isoformat()}
        data.update(extra)
        return self.client.post(self.url(), data)

    def test_it_logs_the_ticket_with_the_confirmed_hours(self):
        self.add()
        e = DSREntry.objects.get()
        self.assertEqual((e.user, e.ticket, e.hours_spent, e.category, e.is_auto_logged), (self.dev, self.t, Decimal("1.50"), "bug_fix", False))
        self.assertEqual(e.task_name, f"{self.t.key} Login bug")

    def test_the_htmx_reply_is_the_refreshed_table_without_that_suggestion(self):
        page = self.client.post(self.url(), {"ticket_id": self.t.pk, "hours": "1", "date": self.today.isoformat()}, headers={"HX-Request": "true"})
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "From your work today")
        self.assertContains(page, "Login bug")

    def test_a_ticket_that_was_not_suggested_is_refused(self):
        other = self.ticket("Unrelated")
        self.add(ticket_id=other.pk)
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_a_ticket_in_a_product_you_cannot_open_is_refused(self):
        secret = self.ticket("secret", product=self.hidden)
        self.add(ticket_id=secret.pk)
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_bad_hours_are_refused(self):
        for bad in ("", "abc", "0", "-1", "25", "NaN"):
            self.add(hours=bad)
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_a_closed_day_cannot_be_added_to_by_an_employee(self):
        yesterday = self.today - timedelta(days=1)
        self.did(self.t, event="ticket_commented", day=yesterday)
        self.add(date=yesterday.isoformat())
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_an_admin_can_add_for_a_colleague_on_a_closed_day(self):
        yesterday = self.today - timedelta(days=1)
        self.did(self.t, event="ticket_commented", day=yesterday)
        self.client.login(username="owner", password="pass1234")
        self.add(date=yesterday.isoformat(), user_id=self.dev.pk)
        self.assertEqual(DSREntry.objects.get().user, self.dev)

    def test_an_employee_cannot_add_for_a_colleague(self):
        self.did(self.t, user=self.other_dev, event="ticket_commented")
        self.add(user_id=self.other_dev.pk)
        self.assertEqual(DSREntry.objects.get().user, self.dev)  # the user_id was ignored

    def test_the_sheet_shows_the_panel_to_the_person_who_can_use_it(self):
        page = self.client.get(reverse("dsr:dsr_sheet"))
        self.assertContains(page, "From your work today")
        self.assertContains(page, "Login bug")
        past = self.client.get(reverse("dsr:dsr_sheet"), {"date": (self.today - timedelta(days=1)).isoformat()})
        self.assertNotContains(past, "From your work today")

    def test_double_submitting_does_not_log_twice(self):
        self.add(); self.add()
        self.assertEqual(DSREntry.objects.count(), 1)  # the second is no longer a suggestion
