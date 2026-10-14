from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dsr.models import DSREntry
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


class LogBase(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("owner", password="pw")
        self.dev = User.objects.create_user("dev", password="pw")
        Membership.objects.create(user=self.owner, company=self.co, role="owner")
        Membership.objects.create(user=self.dev, company=self.co, role="developer")
        self.product = Product.objects.create(company=self.co, name="Aum", slug="aum", key="AUM")
        ProductAccess.objects.create(company=self.co, user=self.dev, product=self.product)
        self.today = timezone.localdate()

    def login(self, name):
        self.client.login(username=name, password="pw")
        s = self.client.session
        s["active_company_id"] = self.co.pk
        s.save()

    def entry(self, user=None, **kw):
        kw.setdefault("date", self.today)
        return DSREntry.objects.create(company=self.co, user=user or self.dev, task_name=kw.pop("task_name", "Task"), hours_spent=kw.pop("hours_spent", Decimal("1.00")), is_auto_logged=False, **kw)


class LogViewTest(LogBase):
    def test_a_member_sees_only_their_own_rows_even_when_asking_for_everyone(self):
        self.entry(task_name="Mine")
        self.entry(user=self.owner, task_name="Boss")
        self.login("dev")
        r = self.client.get(reverse("dsr:dsr_sheet") + "?user_id=all")
        self.assertContains(r, "Mine")
        self.assertNotContains(r, "Boss")

    def test_an_owner_can_read_everyone_and_the_table_names_each_person(self):
        self.entry(task_name="Mine")
        self.entry(user=self.owner, task_name="Boss")
        self.login("owner")
        r = self.client.get(reverse("dsr:dsr_sheet") + "?user_id=all")
        self.assertContains(r, "Mine")
        self.assertContains(r, "Boss")
        self.assertContains(r, "Employee")

    def test_ranges_search_and_day_totals(self):
        self.entry(task_name="Today job", hours_spent=Decimal("1.50"))
        self.entry(task_name="Old job", date=self.today - timedelta(days=3))
        self.login("dev")
        today = self.client.get(reverse("dsr:dsr_sheet") + "?range=today")
        self.assertContains(today, "Today job")
        self.assertNotContains(today, "Old job")
        self.assertContains(today, "1h 30m")
        both = self.client.get(reverse("dsr:dsr_sheet") + "?range=7d")
        self.assertContains(both, "Old job")
        found = self.client.get(reverse("dsr:dsr_sheet") + "?range=7d&q=old")
        self.assertNotContains(found, "Today job")

    def test_csv_export_neutralises_formulas(self):
        self.entry(task_name='=HYPERLINK("x")')
        self.login("dev")
        r = self.client.get(reverse("dsr:dsr_sheet") + "?range=today&export=csv")
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        body = r.content.decode("utf-8-sig")
        self.assertIn("Date,Employee,Task", body)
        self.assertIn("'=HYPERLINK", body)

    def test_a_past_day_has_no_edit_controls_for_a_member(self):
        self.entry(task_name="Old job", date=self.today - timedelta(days=3))
        self.login("dev")
        r = self.client.get(reverse("dsr:dsr_sheet") + "?range=7d")
        self.assertNotContains(r, 'aria-label="Edit Old job"')

    def test_writes_go_back_to_the_page_they_came_from(self):
        self.login("dev")
        r = self.client.post(reverse("dsr:dsr_add") + f"?user_id={self.dev.pk}", {"task_name": "From dialog", "hours_spent": "45m", "category": "other", "status": "completed", "next": "/dsr/?range=30d"})
        self.assertRedirects(r, "/dsr/?range=30d", fetch_redirect_response=False)
        self.assertEqual(DSREntry.objects.get(task_name="From dialog").hours_spent, Decimal("0.75"))
        evil = self.client.post(reverse("dsr:dsr_add"), {"task_name": "x2", "hours_spent": "1h", "category": "other", "status": "completed", "next": "https://evil.example/"})
        self.assertNotIn("evil.example", evil["Location"])


class NeedsTimeTest(LogBase):
    def long_ticket(self):
        t = Ticket.objects.create(company=self.co, product=self.product, title="Slow one", status="in_progress")
        t.set_assignees([self.dev])
        Ticket.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(days=11, hours=1))
        t.refresh_from_db()
        return t

    def test_resolving_a_long_ticket_asks_for_the_time_and_counts_none_until_entered(self):
        t = self.long_ticket()
        self.login("dev")
        r = self.client.post(reverse("tickets:ticket_status", kwargs={"pk": t.pk}), {"status": "resolved"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        body = r.json()
        self.assertIn("was open for 11d 1h", body["warning"])
        self.assertIn("status", body["message"])
        page = self.client.get(reverse("dsr:dsr_sheet") + "?range=today")
        self.assertContains(page, "was open a long time")
        self.assertContains(page, "Add time")
        self.assertContains(page, "(not counted)")
        entry = DSREntry.objects.get(ticket=t)
        self.client.post(reverse("dsr:dsr_update", kwargs={"pk": entry.pk}), {"hours_spent": "2h 30m"})
        entry.refresh_from_db()
        self.assertEqual(entry.hours_spent, Decimal("2.50"))
        self.assertFalse(entry.needs_time)

    def test_a_short_ticket_gives_no_warning(self):
        t = Ticket.objects.create(company=self.co, product=self.product, title="Quick", status="in_progress")
        t.set_assignees([self.dev])
        self.login("dev")
        r = self.client.post(reverse("tickets:ticket_status", kwargs={"pk": t.pk}), {"status": "resolved"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.json()["warning"], "")

    def test_add_all_logs_every_suggestion_once(self):
        a = Ticket.objects.create(company=self.co, product=self.product, title="One", status="in_progress")
        b = Ticket.objects.create(company=self.co, product=self.product, title="Two", status="in_progress")
        a.set_assignees([self.dev]); b.set_assignees([self.dev])
        self.login("dev")
        r = self.client.post(reverse("dsr:dsr_suggestion_add_all"), {"next": "/dsr/"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(DSREntry.objects.filter(user=self.dev).count(), 2)
        self.client.post(reverse("dsr:dsr_suggestion_add_all"), {"next": "/dsr/"})
        self.assertEqual(DSREntry.objects.filter(user=self.dev).count(), 2)


class DateSpanAndTodayWorkTest(LogBase):
    def test_from_and_to_pick_any_span(self):
        old = self.today - timedelta(days=20)
        self.entry(task_name="Old one", date=old)
        self.entry(task_name="Recent one")
        self.login("dev")
        r = self.client.get(reverse("dsr:dsr_sheet"), {"from": (old - timedelta(days=1)).isoformat(), "to": (old + timedelta(days=1)).isoformat()})
        self.assertContains(r, "Old one")
        self.assertNotContains(r, "Recent one")
        self.assertEqual(r.context["rng"], "custom")

    def test_a_backwards_span_is_put_in_order_and_the_future_is_cut_off(self):
        self.entry(task_name="Today one")
        self.login("dev")
        r = self.client.get(reverse("dsr:dsr_sheet"), {"from": (self.today + timedelta(days=5)).isoformat(), "to": (self.today - timedelta(days=2)).isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertLessEqual(r.context["end"], self.today)
        self.assertLessEqual(r.context["start"], r.context["end"])

    def test_the_csv_export_keeps_the_span(self):
        self.entry(task_name="Exported")
        self.login("dev")
        r = self.client.get(reverse("dsr:dsr_sheet"), {"from": self.today.isoformat(), "to": self.today.isoformat(), "export": "csv"})
        self.assertEqual(r["Content-Type"].split(";")[0], "text/csv")
        self.assertIn("Exported", r.content.decode())

    def test_today_work_compares_the_dsr_with_the_time_on_the_clock(self):
        from apps.attendance.models import AttendanceRecord

        now = timezone.now()
        AttendanceRecord.objects.create(company=self.co, user=self.dev, date=self.today, check_in=now - timedelta(hours=4), check_out=now)
        self.entry(hours_spent=Decimal("2.00"))
        self.login("dev")
        w = self.client.get(reverse("dsr:dsr_sheet")).context["today_work"]
        self.assertEqual(w["logged"], "2h 00m")
        self.assertEqual(w["basis_word"], "worked today")
        self.assertEqual(w["percent"], 50)
        self.assertFalse(w["no_punch"])

    def test_without_a_punch_it_is_measured_against_a_full_day_and_says_so(self):
        self.entry(hours_spent=Decimal("1.00"))
        self.login("dev")
        r = self.client.get(reverse("dsr:dsr_sheet"))
        self.assertTrue(r.context["today_work"]["no_punch"])
        self.assertContains(r, "no punch yet today")

    def test_the_everyone_view_has_no_single_person_bar(self):
        self.login("owner")
        r = self.client.get(reverse("dsr:dsr_sheet"), {"user_id": "all"})
        self.assertIsNone(r.context["today_work"])
