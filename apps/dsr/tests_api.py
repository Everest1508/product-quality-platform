from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Company, ExternalAccessToken, Membership
from apps.dsr.models import DSREntry
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


class DSRApiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        self.other = User.objects.create_user("other", "o@t.local", "pass1234")
        for u in (self.dev, self.other):
            Membership.objects.create(user=u, company=self.company, role="developer")
        self.mine = Product.objects.create(company=self.company, name="Billing", slug="billing", key="BIL")
        self.secret = Product.objects.create(company=self.company, name="Vault", slug="vault", key="VLT")
        ProductAccess.objects.create(company=self.company, product=self.mine, user=self.dev)
        _, self.token = ExternalAccessToken.create_token(self.dev, client_id="dsr-mcp")
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.today = timezone.localdate()

    def post(self, **data):
        body = {"task_name": "Fixed login bug", "category": "bug_fix", "hours_spent": "2", "status": "completed"}
        body.update(data)
        return self.api.post(reverse("dsr_api:create"), body, format="json")

    def test_needs_a_dsr_token(self):
        self.assertEqual(APIClient().get(reverse("dsr_api:me")).status_code, 403)
        _, serop = ExternalAccessToken.create_token(self.dev, client_id="serop")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {serop}")
        self.assertEqual(c.get(reverse("dsr_api:me")).status_code, 403)

    def test_dsr_token_does_not_open_serop(self):
        self.assertEqual(self.api.get(reverse("serop:teams")).status_code, 403)

    def test_me_and_projects(self):
        me = self.api.get(reverse("dsr_api:me")).json()
        self.assertEqual((me["username"], me["company"]["name"]), ("dev", "Acme"))
        projects = self.api.get(reverse("dsr_api:projects")).json()
        self.assertEqual([p["name"] for p in projects], ["Billing"])

    def test_submit_then_read_back_with_audit_fields(self):
        res = self.post(product=self.mine.pk, source="github", source_id="commit_abc123")
        self.assertEqual(res.status_code, 201)
        today = self.api.get(reverse("dsr_api:today")).json()
        self.assertTrue(today["exists"] and today["can_edit"])
        self.assertEqual(today["entries"][0]["source_id"], "commit_abc123")
        self.assertFalse(DSREntry.objects.get().is_auto_logged)

    def test_duplicates_answer_409_with_the_existing_entry(self):
        first = self.post(source="github", source_id="c1").json()
        by_source = self.post(task_name="Different words", source="github", source_id="c1")
        by_name = self.post(task_name="FIXED LOGIN BUG")
        for res in (by_source, by_name):
            self.assertEqual(res.status_code, 409)
            self.assertEqual(res.json()["existing"]["id"], first["id"])
        self.assertEqual(DSREntry.objects.count(), 1)

    def test_a_ticket_already_logged_is_a_duplicate(self):
        t = Ticket.objects.create(company=self.company, product=self.mine, title="T", created_by=self.dev)
        DSREntry.objects.create(company=self.company, user=self.dev, ticket=t, task_name="auto", hours_spent=1)
        self.assertEqual(self.post(task_name="Other words", ticket=t.pk).status_code, 409)

    def test_cannot_use_a_product_or_ticket_outside_access(self):
        self.assertEqual(self.post(product=self.secret.pk).status_code, 400)
        t = Ticket.objects.create(company=self.company, product=self.secret, title="T", created_by=self.other)
        self.assertEqual(self.post(ticket=t.pk).status_code, 400)
        self.assertFalse(DSREntry.objects.exists())

    def test_validation_matches_the_web_form(self):
        self.assertEqual(self.post(task_name="").status_code, 400)
        self.assertEqual(self.post(hours_spent="0").status_code, 400)
        self.assertEqual(self.post(hours_spent="25").status_code, 400)
        self.assertEqual(self.post(hours_spent="abc").status_code, 400)

    def test_future_and_past_days_are_closed(self):
        tomorrow = (self.today + timedelta(days=1)).isoformat()
        yesterday = (self.today - timedelta(days=1)).isoformat()
        self.assertEqual(self.post(date=tomorrow).status_code, 403)
        self.assertEqual(self.post(date=yesterday).status_code, 403)
        self.assertEqual(self.post(date="nope").status_code, 400)

    def test_update_changes_only_what_is_sent(self):
        eid = self.post().json()["id"]
        res = self.api.put(reverse("dsr_api:detail", args=[eid]), {"hours_spent": "3.5"}, format="json")
        self.assertEqual(res.status_code, 200)
        e = DSREntry.objects.get()
        self.assertEqual((str(e.hours_spent), e.task_name), ("3.50", "Fixed login bug"))

    def test_cannot_update_someone_elses_entry(self):
        e = DSREntry.objects.create(company=self.company, user=self.other, task_name="x", hours_spent=1)
        res = self.api.put(reverse("dsr_api:detail", args=[e.pk]), {"hours_spent": "2"}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_activities_lists_tickets_in_progress_not_yet_logged(self):
        t = Ticket.objects.create(
            company=self.company, product=self.mine, title="Fix export", created_by=self.dev, status="in_progress"
        )
        t.assignees.add(self.dev)
        rows = self.api.get(reverse("dsr_api:activities")).json()
        self.assertEqual([(r["source"], r["source_id"]) for r in rows], [("crm_ticket", t.key)])
        self.post(task_name="Logged", ticket=t.pk)
        self.assertEqual(self.api.get(reverse("dsr_api:activities")).json(), [])


class DSRApiRealTimeTest(DSRApiTest):
    """What the MCP needs to measure time instead of guessing it."""

    def test_today_reports_attendance_minutes(self):
        from apps.attendance.models import AttendanceRecord

        self.assertIsNone(self.api.get(reverse("dsr_api:today")).json()["attendance"])
        start = timezone.make_aware(timezone.datetime.combine(self.today, timezone.datetime.min.time())) + timedelta(hours=9)
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=self.today, check_in=start, check_out=start + timedelta(hours=4)
        )
        att = self.api.get(reverse("dsr_api:today")).json()["attendance"]
        self.assertEqual(att["net_minutes"], 240)  # under the shift, so no break comes off
        self.assertTrue(att["check_in"].startswith(self.today.isoformat()))

    def test_activities_carry_event_times_and_touched(self):
        from apps.dashboards.models import ActivityLog

        t = Ticket.objects.create(company=self.company, product=self.mine, title="Fix export", created_by=self.dev, status="in_progress")
        t.assignees.add(self.dev)
        row = self.api.get(reverse("dsr_api:activities")).json()[0]
        self.assertEqual((row["touched"], row["events"]), (False, []))  # assigned only, no work today
        ActivityLog.objects.create(
            company=self.company, actor=self.dev, event_type="ticket_commented", title="c",
            target_content_type="ticket", target_object_id=t.pk,
        )
        row = self.api.get(reverse("dsr_api:activities")).json()[0]
        self.assertTrue(row["touched"])
        self.assertEqual(len(row["events"]), 1)

    def test_mcp_rows_show_a_pill_and_manual_rows_do_not(self):
        self.post(task_name="From the MCP", source="git", source_id="crm:today")
        DSREntry.objects.create(company=self.company, user=self.dev, date=self.today, task_name="By hand", hours_spent=1, is_auto_logged=False)
        self.client.login(username="dev", password="pass1234")
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        self.assertEqual(body.count('class="dsr-tag mcp"'), 1)
