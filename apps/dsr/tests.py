from datetime import timedelta
from decimal import Decimal
import re
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dsr.models import DSREntry
from apps.dsr.service import auto_log_ticket_dsr
from apps.tickets.models import Ticket

User = get_user_model()


class DSRSystemTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp", slug="acme")
        self.owner = User.objects.create_user(username="owner", password="password")
        self.member = User.objects.create_user(username="member", password="password")

        Membership.objects.create(user=self.owner, company=self.company, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.member, company=self.company, role=Membership.Role.DEVELOPER)

        self.ticket = Ticket.objects.create(
            company=self.company,
            title="Fix SSL certificate renewal",
            created_by=self.member,
            ticket_type="bug",
        )
        self.ticket.assignees.add(self.member)

    def test_auto_log_ticket_dsr(self):
        # Move ticket status to resolved
        self.ticket.transition_to("resolved", actor=self.member)

        # Check DSR entry created automatically
        entry = DSREntry.objects.filter(company=self.company, user=self.member, ticket=self.ticket).first()
        self.assertIsNotNone(entry)
        self.assertTrue(entry.is_auto_logged)
        self.assertIn("Fix SSL certificate renewal", entry.task_name)
        self.assertEqual(entry.status, "completed")
        self.assertGreater(entry.hours_spent, Decimal("0"))

    def test_dsr_sheet_view_permissions(self):
        self.client.login(username="member", password="password")
        url = reverse("dsr:dsr_sheet")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daily Status Report")

    def test_dsr_inline_update(self):
        self.ticket.transition_to("resolved", actor=self.member)
        entry = DSREntry.objects.get(ticket=self.ticket)

        self.client.login(username="member", password="password")
        url = reverse("dsr:dsr_update", kwargs={"pk": entry.pk})
        response = self.client.post(url, {"hours_spent": "3.50", "notes": "Fixed certificate issue"})
        self.assertEqual(response.status_code, 302)

        entry.refresh_from_db()
        self.assertEqual(entry.hours_spent, Decimal("3.50"))
        self.assertEqual(entry.notes, "Fixed certificate issue")


class ManualEntryTest(TestCase):
    """The add-entry form used to hardcode 'New Task' / 1.00h / completed."""

    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.member = User.objects.create_user(username="member", password="password")
        self.viewer = User.objects.create_user(username="viewer", password="password")
        self.outsider = User.objects.create_user(username="outsider", password="password")

        Membership.objects.create(user=self.member, company=self.company, role=Membership.Role.DEVELOPER)
        Membership.objects.create(user=self.viewer, company=self.company, role=Membership.Role.VIEWER)
        Membership.objects.create(user=self.outsider, company=self.other, role=Membership.Role.OWNER)

        self.today = timezone.localdate()

    def add(self, user="member", **overrides):
        payload = {
            "task_name": "Wrote the leave policy screen",
            "category": "feature",
            "hours_spent": "2.50",
            "status": "completed",
            "notes": "",
        }
        payload.update(overrides)
        self.client.login(username=user, password="password")
        return self.client.post(reverse("dsr:dsr_add"), payload)

    def test_creates_entry_from_the_form(self):
        self.add()
        entry = DSREntry.objects.get()
        self.assertEqual(entry.task_name, "Wrote the leave policy screen")
        self.assertEqual(entry.category, "feature")
        self.assertEqual(entry.hours_spent, Decimal("2.50"))
        self.assertEqual(entry.status, "completed")
        self.assertEqual(entry.user, self.member)
        self.assertFalse(entry.is_auto_logged)

    def test_is_not_hardcoded(self):
        self.add(
            task_name="Pairing on the punch bug",
            category="bug_fix",
            hours_spent="0.75",
            status="in_progress",
        )
        entry = DSREntry.objects.get()
        self.assertEqual(entry.task_name, "Pairing on the punch bug")
        self.assertNotEqual(entry.task_name, "New Task")
        self.assertEqual(entry.category, "bug_fix")
        self.assertEqual(entry.hours_spent, Decimal("0.75"))
        self.assertEqual(entry.status, "in_progress")

    def test_task_name_is_required(self):
        before = DSREntry.objects.count()
        self.add(task_name="   ")
        self.assertEqual(DSREntry.objects.count(), before)

    def test_zero_hours_is_rejected(self):
        self.add(hours_spent="0")
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_absurd_hours_is_rejected(self):
        self.add(hours_spent="99")
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_unknown_category_is_rejected(self):
        self.add(category="nonsense")
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_unknown_status_is_rejected(self):
        self.add(status="almost_done")
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_bare_post_creates_nothing(self):
        """The old button sent no fields; it must not invent a task now."""
        self.client.login(username="member", password="password")
        self.client.post(reverse("dsr:dsr_add"), {})
        self.assertEqual(DSREntry.objects.count(), 0)

    def test_viewer_can_log_their_own_work(self):
        self.add(user="viewer")
        self.assertEqual(DSREntry.objects.get().user, self.viewer)

    def test_cannot_log_for_someone_else(self):
        self.client.login(username="member", password="password")
        self.client.post(
            reverse("dsr:dsr_add"),
            {
                "task_name": "Not mine",
                "category": "other",
                "hours_spent": "1",
                "status": "completed",
                "user_id": self.viewer.pk,
            },
        )
        entry = DSREntry.objects.get()
        self.assertEqual(entry.user, self.member)

    def test_htmx_add_returns_the_table_with_errors(self):
        self.add(task_name="")
        # The POST above redirected; repeat it as HTMX to inspect the response.
        self.client.login(username="member", password="password")
        response = self.client.post(
            reverse("dsr:dsr_add"),
            {"task_name": "", "category": "other", "hours_spent": "1", "status": "completed"},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Describe the task.")


class InlineUpdateValidationTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp", slug="acme")
        self.member = User.objects.create_user(username="member", password="password")
        self.other = User.objects.create_user(username="other", password="password")
        Membership.objects.create(user=self.member, company=self.company, role=Membership.Role.DEVELOPER)
        Membership.objects.create(user=self.other, company=self.company, role=Membership.Role.DEVELOPER)
        self.entry = DSREntry.objects.create(
            company=self.company,
            user=self.member,
            date=timezone.localdate(),
            task_name="Original",
            hours_spent=Decimal("1.00"),
        )

    def update(self, user="member", **payload):
        self.client.login(username=user, password="password")
        return self.client.post(reverse("dsr:dsr_update", kwargs={"pk": self.entry.pk}), payload)

    def test_valid_update_applies(self):
        self.update(task_name="Renamed", hours_spent="4.00", status="in_progress")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.task_name, "Renamed")
        self.assertEqual(self.entry.hours_spent, Decimal("4.00"))
        self.assertEqual(self.entry.status, "in_progress")

    def test_invalid_status_is_ignored(self):
        self.update(status="almost_done")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, self.entry.Status.COMPLETED)

    def test_invalid_category_is_ignored(self):
        self.update(category="nonsense")
        self.entry.refresh_from_db()
        self.assertNotEqual(self.entry.category, "nonsense")

    def test_non_numeric_hours_is_ignored(self):
        self.update(hours_spent="three hours")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.hours_spent, Decimal("1.00"))

    def test_out_of_range_hours_is_ignored(self):
        self.update(hours_spent="99")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.hours_spent, Decimal("1.00"))

    def test_cannot_edit_another_members_entry(self):
        self.update(user="other", task_name="Hijacked")
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.task_name, "Original")


class DSRSheetRenderTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp", slug="acme")
        self.member = User.objects.create_user(username="member", password="password")
        Membership.objects.create(user=self.member, company=self.company, role=Membership.Role.DEVELOPER)

    def test_sheet_renders_the_real_add_form(self):
        self.client.login(username="member", password="password")
        response = self.client.get(reverse("dsr:dsr_sheet"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for field in ("task_name", "category", "hours_spent", "status", "notes"):
            self.assertIn(field, body)
        self.assertIn("placeholder=\"What did you work on?\"", body)

    def test_add_form_is_editable_htmx_scope(self):
        self.client.login(username="member", password="password")
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        self.assertIn('x-data="{ addOpen: false }"', body)
        self.assertIn('x-show="addOpen"', body)

    def test_add_form_ids_are_unique_across_both_copies(self):
        """The sheet renders the add form twice, so ids must not repeat.

        Both copies share one form's field names, and the empty-state row is
        rendered in addition to the bar. Duplicate ids are invalid HTML and
        leave `label[for]` pointing at an ambiguous element.
        """
        self.client.login(username="member", password="password")
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        ids = re.findall(r'\sid="([^"]+)"', body)
        repeated = {i for i in ids if ids.count(i) > 1}
        self.assertEqual(repeated, set(), f"duplicate ids on the DSR sheet: {sorted(repeated)}")
        # both prefixes are present, i.e. the two forms really are distinct
        self.assertIn("dsr-bar-task_name", body)
        self.assertIn("dsr-row-task_name", body)

    def test_every_add_form_label_points_at_a_real_control(self):
        self.client.login(username="member", password="password")
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        targets = set(re.findall(r'\sid="([^"]+)"', body))
        for target in re.findall(r'<label[^>]*\sfor="([^"]+)"', body):
            self.assertIn(target, targets, f"label points at missing id {target!r}")
