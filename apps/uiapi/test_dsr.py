from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import Client
from django.utils import timezone

from apps.dashboards.models import ActivityLog
from apps.dashboards.service import log_activity
from apps.dsr.models import DSREntry
from apps.tickets.models import Ticket
from apps.uiapi.test_tickets import Base, member


class DsrBase(Base):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.past = self.today - timedelta(days=1)
        self.future = self.today + timedelta(days=1)

    def post(self, url, body=None):
        return self.client.post(url, body or {}, content_type="application/json")

    def sheet(self, **params):
        return self.client.get("/ui-api/v1/dsr/", params)

    def add_at(self, query, **over):
        body = {"task_name": "x", "category": "other", "hours_spent": "1", "status": "completed"}
        return self.client.post(f"/ui-api/v1/dsr/entries/{query}", {**body, **over}, content_type="application/json")

    def add(self, **over):
        body = {"task_name": "Wrote the report", "category": "documentation", "hours_spent": "1h 30m", "status": "completed", "notes": "", "product": ""}
        return self.post("/ui-api/v1/dsr/entries/", {**body, **over})

    def entry(self, user=None, day=None, **kw):
        kw.setdefault("task_name", "Task")
        kw.setdefault("hours_spent", Decimal("2.00"))
        return DSREntry.objects.create(company=self.acme, user=user or self.dev, date=day or self.today, **kw)


class SheetApiTest(DsrBase):
    def test_shape_totals_and_summary(self):
        self.entry(task_name="Fix it", hours_spent=Decimal("1.50"), product=self.p_open, notes="done")
        self.entry(task_name="Meeting", hours_spent=Decimal("0.50"), status="in_progress", category="meeting")
        self.login("dev")
        d = self.sheet().json()
        self.assertEqual((d["total"], d["completed"], d["can_submit"], d["target"]["is_me"]), ("2h", 1, True, True))
        self.assertEqual(len(d["entries"]), 2)
        self.assertIn("[Open] Fix it", d["summary_text"])  # the copied summary names the product
        self.assertIn("Note: done", d["summary_text"])
        self.assertEqual([p["name"] for p in d["products"]], ["Open"])
        self.assertEqual(d["next"], self.today.isoformat())  # no forward link past today
        self.assertEqual(d["entries"][0]["hours"] in ("1h 30m", "30m"), True)

    def test_a_ticket_row_links_to_its_ticket_and_hours_show_as_hm(self):
        t = Ticket.objects.create(company=self.acme, product=self.p_open, title="Bug")
        self.entry(ticket=t, product=self.p_open, task_name=f"{t.key} Bug", hours_spent=Decimal("0.75"))
        self.login("dev")
        e = self.sheet().json()["entries"][0]
        self.assertEqual((e["hours"], e["ticket"]["key"], e["ticket"]["url"]), ("45m", t.key, f"/products/{self.p_open.pk}/tickets/{t.pk}/"))

    def test_only_my_sheet_unless_admin_asks_for_a_members(self):
        self.entry(user=self.owner, task_name="Owner task")
        self.login("dev")
        d = self.sheet(user_id=self.owner.pk).json()  # ignored for a non-admin
        self.assertEqual((d["target"]["name"], d["entries"]), ("dev", []))
        self.assertEqual(d["team_overview"], [])
        self.login("owner")
        d = self.sheet(user_id=self.dev.pk).json()
        self.assertEqual(d["target"]["name"], "dev")
        self.assertEqual([m["name"] for m in d["team_overview"]], ["dev", "owner"])
        self.assertEqual(self.sheet(user_id=member("zed", self.other).pk).status_code, 404)
        self.assertEqual(self.sheet(user_id="²").status_code, 404)

    def test_odd_dates_fall_back_to_today(self):
        self.login("dev")
        self.assertEqual(self.sheet(date="garbage").json()["date"], self.today.isoformat())

    def test_closed_days_are_read_only_future_is_closed_to_everyone(self):
        self.entry(day=self.past)
        self.login("dev")
        d = self.sheet(date=self.past.isoformat()).json()
        self.assertEqual((d["can_submit"], len(d["entries"])), (False, 1))
        self.assertIn("closed", d["locked_reason"])
        self.assertEqual(d["work_suggestions"], [])
        self.assertFalse(self.sheet(date=self.future.isoformat()).json()["can_submit"])
        self.login("owner")
        self.assertTrue(self.sheet(date=self.past.isoformat()).json()["can_submit"])
        self.assertFalse(self.sheet(date=self.future.isoformat()).json()["can_submit"])

    def test_suggestions_come_from_assigned_open_tickets_and_respect_product_access(self):
        mine = Ticket.objects.create(company=self.acme, product=self.p_open, title="Mine", status="in_progress")
        mine.set_assignees([self.dev])
        secret = Ticket.objects.create(company=self.acme, product=self.p_hidden, title="Secret", status="in_progress")
        secret.set_assignees([self.dev])
        self.login("dev")
        d = self.sheet().json()
        self.assertEqual([t["title"] for t in d["ticket_suggestions"]], ["Mine"])
        self.assertEqual([w["title"] for w in d["work_suggestions"]], ["Mine"])
        self.assertEqual(d["work_suggestions"][0]["hours"], "1h")

    def test_anonymous_and_foreign_company_get_nothing(self):
        self.assertIn(Client().get("/ui-api/v1/dsr/").status_code, (401, 403))


class EntryApiTest(DsrBase):
    def test_add_a_manual_row_with_minutes_a_product_and_an_audit_row(self):
        self.login("dev")
        r = self.add(product=self.p_open.pk)
        self.assertEqual(r.status_code, 201)
        e = DSREntry.objects.get()
        self.assertEqual((e.user, e.hours_spent, e.product, e.is_auto_logged, e.date), (self.dev, Decimal("1.50"), self.p_open, False, self.today))
        self.assertEqual(r.json()["message"], 'Added "Wrote the report".')
        self.assertTrue(ActivityLog.objects.filter(event_type="dsr_entry_added", actor=self.dev).exists())

    def test_validation(self):
        self.login("dev")
        for over, field in (({"task_name": ""}, "task_name"), ({"hours_spent": "0"}, "hours"), ({"hours_spent": "25"}, "hours"),
                            ({"hours_spent": "nonsense"}, "hours"), ({"category": "nope"}, "category"), ({"status": "nope"}, "status")):
            r = self.add(**over)
            self.assertEqual(r.status_code, 400, over)
            self.assertIn(field, r.json()["errors"], over)
        self.assertFalse(DSREntry.objects.exists())
        self.assertEqual(self.client.post("/ui-api/v1/dsr/entries/", {}, content_type="application/json").status_code, 400)

    def test_a_product_the_person_cannot_open_is_refused(self):
        self.login("dev")
        for p in (self.p_hidden, self.p_foreign):
            r = self.add(product=p.pk)
            self.assertEqual(r.status_code, 400, p)
            self.assertIn("product", r.json()["errors"])
        self.assertFalse(DSREntry.objects.exists())

    def test_the_day_window(self):
        self.login("dev")
        self.assertEqual(self.add_at(f"?date={self.past.isoformat()}").status_code, 403)
        self.assertEqual(self.add_at(f"?date={self.future.isoformat()}").status_code, 403)
        self.assertFalse(DSREntry.objects.exists())
        self.login("owner")
        r = self.add_at(f"?date={self.past.isoformat()}&user_id={self.dev.pk}")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(DSREntry.objects.get().user, self.dev)

    def test_nobody_logs_for_someone_else_unless_admin(self):
        self.login("dev")
        self.assertEqual(self.add_at(f"?user_id={self.owner.pk}").status_code, 201)
        self.assertEqual(DSREntry.objects.get().user, self.dev)

    def test_inline_edit_keeps_what_is_not_sent(self):
        e = self.entry(product=self.p_open, task_name="Keep me", notes="n")
        self.login("dev")
        url = f"/ui-api/v1/dsr/entries/{e.pk}/"
        r = self.client.patch(url, {"hours_spent": "45m"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        e.refresh_from_db()
        self.assertEqual((e.hours_spent, e.task_name, e.product, e.notes), (Decimal("0.75"), "Keep me", self.p_open, "n"))
        self.client.patch(url, {"status": "blocked", "notes": "waiting"}, content_type="application/json")
        e.refresh_from_db()
        self.assertEqual((e.status, e.notes, e.hours_spent), ("blocked", "waiting", Decimal("0.75")))
        self.assertTrue(ActivityLog.objects.filter(event_type="dsr_entry_updated").exists())

    def test_bad_edits_are_refused_and_change_nothing(self):
        e = self.entry()
        self.login("dev")
        url = f"/ui-api/v1/dsr/entries/{e.pk}/"
        for body in ({"status": "nope"}, {"category": "nope"}, {"hours_spent": "abc"}, {"hours_spent": "30"}, {"product": self.p_hidden.pk}):
            self.assertEqual(self.client.patch(url, body, content_type="application/json").status_code, 400, body)
        e.refresh_from_db()
        self.assertEqual((e.status, e.hours_spent, e.product), ("completed", Decimal("2.00"), None))

    def test_a_wide_entry_stays_editable_but_cannot_be_raised_past_the_cap(self):
        e = self.entry(hours_spent=Decimal("1440.00"))
        self.login("dev")
        url = f"/ui-api/v1/dsr/entries/{e.pk}/"
        self.assertEqual(self.client.patch(url, {"notes": "just a note"}, content_type="application/json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"hours_spent": "1500"}, content_type="application/json").status_code, 400)

    def test_edit_and_delete_rights_and_window(self):
        theirs = self.entry(user=self.owner)
        past = self.entry(day=self.past)
        self.login("dev")
        for e in (theirs,):
            self.assertEqual(self.client.patch(f"/ui-api/v1/dsr/entries/{e.pk}/", {"notes": "x"}, content_type="application/json").status_code, 403)
            self.assertEqual(self.client.delete(f"/ui-api/v1/dsr/entries/{e.pk}/").status_code, 403)
        self.assertEqual(self.client.patch(f"/ui-api/v1/dsr/entries/{past.pk}/", {"notes": "x"}, content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(f"/ui-api/v1/dsr/entries/{past.pk}/").status_code, 403)
        self.assertEqual(DSREntry.objects.count(), 2)
        self.login("owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/dsr/entries/{past.pk}/").status_code, 200)  # an admin may fix a past day

    def test_delete_returns_the_sheet_and_is_audited(self):
        e = self.entry()
        self.login("dev")
        r = self.client.delete(f"/ui-api/v1/dsr/entries/{e.pk}/")
        self.assertEqual((r.status_code, r.json()["entries"], r.json()["message"]), (200, [], 'Deleted "Task".'))
        self.assertTrue(ActivityLog.objects.filter(event_type="dsr_entry_deleted").exists())

    def test_foreign_company_entries_are_404(self):
        foreign = DSREntry.objects.create(company=self.other, user=member("zed", self.other), date=self.today, task_name="x", hours_spent=1)
        self.login("owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/dsr/entries/{foreign.pk}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/ui-api/v1/dsr/entries/{foreign.pk}/", {"notes": "x"}, content_type="application/json").status_code, 404)


class SuggestionApiTest(DsrBase):
    def setUp(self):
        super().setUp()
        self.t = Ticket.objects.create(company=self.acme, product=self.p_open, title="Fix login", ticket_type="bug", status="in_progress")
        self.t.set_assignees([self.dev])

    def add(self, **body):
        return self.post("/ui-api/v1/dsr/suggestions/add/", {"ticket_id": self.t.pk, "hours": "1h 30m", **body})

    def test_logs_a_suggested_ticket_with_the_confirmed_time(self):
        self.login("dev")
        r = self.add()
        self.assertEqual(r.status_code, 201)
        e = DSREntry.objects.get()
        self.assertEqual((e.ticket, e.hours_spent, e.category, e.status, e.product), (self.t, Decimal("1.50"), "bug_fix", "in_progress", self.p_open))
        self.assertEqual(r.json()["message"], f"Added {self.t.key} with 1h 30m.")
        self.assertEqual(r.json()["work_suggestions"], [])  # no longer suggested once logged

    def test_only_a_suggested_ticket_and_sane_hours(self):
        other = Ticket.objects.create(company=self.acme, product=self.p_hidden, title="Not yours", status="in_progress")
        self.login("dev")
        self.assertEqual(self.add(ticket_id=other.pk).status_code, 400)
        self.assertEqual(self.add(ticket_id="x").status_code, 400)
        for hours in ("", "0", "30", "abc"):
            self.assertEqual(self.add(hours=hours).status_code, 400, hours)
        self.assertFalse(DSREntry.objects.exists())

    def test_add_all_logs_every_suggestion_once_and_then_has_nothing_left(self):
        second = Ticket.objects.create(company=self.acme, product=self.p_open, title="Fix logout", ticket_type="feature", status="in_progress")
        second.set_assignees([self.dev])
        self.login("dev")
        r = self.post("/ui-api/v1/dsr/suggestions/add-all/", {})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(DSREntry.objects.count(), 2)
        self.assertIn("Added 2 tickets", r.json()["message"])
        self.assertEqual(r.json()["work_suggestions"], [])
        again = self.post("/ui-api/v1/dsr/suggestions/add-all/", {})
        self.assertEqual(again.status_code, 400)
        self.assertEqual(DSREntry.objects.count(), 2)

    def test_add_all_respects_the_day_window(self):
        self.login("dev")
        self.assertEqual(self.post(f"/ui-api/v1/dsr/suggestions/add-all/?date={self.past.isoformat()}", {}).status_code, 403)

    def test_window_applies(self):
        self.login("dev")
        self.assertEqual(self.post(f"/ui-api/v1/dsr/suggestions/add/?date={self.past.isoformat()}", {"ticket_id": self.t.pk, "hours": "1"}).status_code, 403)
        self.assertFalse(DSREntry.objects.exists())

    def test_activity_makes_a_ticket_suggested_on_its_day(self):
        quiet = Ticket.objects.create(company=self.acme, product=self.p_open, title="Touched", status="open")
        e = log_activity(self.acme, "ticket_commented", "c", actor=self.dev, target_content_type="ticket", target_object_id=quiet.pk)
        ActivityLog.objects.filter(pk=e.pk).update(created_at=timezone.make_aware(datetime.combine(self.today, time(9, 0))))
        self.login("dev")
        keys = [w["key"] for w in self.sheet().json()["work_suggestions"]]
        self.assertEqual(keys[0], quiet.key)  # touched comes first


class DsrShellPageTest(DsrBase):
    def test_the_page_is_the_react_shell_and_the_old_routes_are_gone(self):
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template
        from django.urls import NoReverseMatch, reverse

        self.login("dev")
        r = self.client.get("/dsr/")
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "uiapi/shell.html")
        self.assertEqual(Client().get("/dsr/").status_code, 302)
        for name in ("dsr:dsr_add", "dsr:dsr_suggestion_add"):
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(name)
        with self.assertRaises(TemplateDoesNotExist):
            get_template("dsr/dsr_sheet.html")


class LogApiTest(DsrBase):
    def log(self, **params):
        return self.client.get("/ui-api/v1/dsr/log/", params)

    def test_today_and_history_come_in_one_list_newest_day_first_with_day_totals(self):
        self.entry(task_name="Today A", hours_spent=Decimal("1.00"))
        self.entry(task_name="Yesterday", day=self.past, hours_spent=Decimal("2.50"))
        self.entry(task_name="Old", day=self.today - timedelta(days=20))
        self.login("dev")
        d = self.log().json()  # default: the last 7 days
        self.assertEqual([r["task_name"] for r in d["rows"]], ["Today A", "Yesterday"])
        self.assertEqual([(x["date"], x["hours"], x["count"]) for x in d["days"]], [(self.today.isoformat(), "1h", 1), (self.past.isoformat(), "2h 30m", 1)])
        self.assertEqual((d["total"], d["count"], d["scope"]), ("3h 30m", 2, "me"))
        self.assertEqual(len(self.log(range="30d").json()["rows"]), 3)
        self.assertEqual([r["task_name"] for r in self.log(range="yesterday").json()["rows"]], ["Yesterday"])

    def test_only_todays_rows_are_editable_for_a_member_and_all_for_an_admin(self):
        self.entry(task_name="Today"), self.entry(task_name="Past", day=self.past)
        self.login("dev")
        self.assertEqual({r["task_name"]: r["editable"] for r in self.log().json()["rows"]}, {"Today": True, "Past": False})
        self.login("owner")
        self.assertEqual({r["task_name"]: r["editable"] for r in self.log(user_id="all").json()["rows"]}, {"Today": True, "Past": True})

    def test_a_member_never_sees_others_but_an_admin_can_pick_everyone_or_one_person(self):
        self.entry(task_name="Mine"), self.entry(user=self.owner, task_name="Boss")
        self.login("dev")
        d = self.log(user_id="all").json()  # ignored for a member
        self.assertEqual(([r["task_name"] for r in d["rows"]], d["scope"], d["members"]), (["Mine"], "me", []))
        self.assertEqual(self.log(user_id=self.owner.pk).status_code, 200)
        self.assertEqual([r["task_name"] for r in self.log(user_id=self.owner.pk).json()["rows"]], ["Mine"])
        self.login("owner")
        d = self.log(user_id="all").json()
        self.assertEqual(sorted(r["task_name"] for r in d["rows"]), ["Boss", "Mine"])
        self.assertEqual(d["rows"][0]["person"]["username"] in ("dev", "owner"), True)
        self.assertEqual([r["task_name"] for r in self.log(user_id=self.dev.pk).json()["rows"]], ["Mine"])

    def test_search_custom_range_and_bad_input(self):
        self.entry(task_name="Invoice export", notes="for finance"), self.entry(task_name="Standup")
        self.login("dev")
        self.assertEqual([r["task_name"] for r in self.log(q="finance").json()["rows"]], ["Invoice export"])
        self.assertEqual(self.log(**{"from": "garbage", "to": "x"}).status_code, 200)
        wide = self.log(**{"from": "2020-01-01", "to": self.today.isoformat()}).json()
        self.assertEqual(wide["range"], "custom")
        self.assertEqual(wide["from"], (self.today - timedelta(days=91)).isoformat())  # capped at 92 days
        self.login("owner")
        self.assertEqual(self.log(user_id="²").status_code, 404)  # not a number
        self.assertIn(Client().get("/ui-api/v1/dsr/log/").status_code, (401, 403))

    def test_the_form_state_and_the_copy_summary(self):
        self.entry(task_name="Fix it", hours_spent=Decimal("1.50"))
        self.login("dev")
        d = self.log().json()
        self.assertEqual((d["can_log"], [p["name"] for p in d["products"]]), (True, ["Open"]))
        self.assertIn("Fix it (Ticket Completion) - 1h 30m", d["summary_text"])
        self.assertIn("No tasks recorded", self.log(range="yesterday").json()["summary_text"])

    def test_an_entry_with_start_and_end_times_carries_them_as_local_clock_times(self):
        start = timezone.make_aware(datetime.combine(self.today, time(9, 15)))
        self.entry(task_name="Timed", created_time=start, completed_time=start + timedelta(hours=8, minutes=15))
        self.entry(task_name="Untimed")
        self.login("dev")
        rows = {r["task_name"]: r for r in self.log().json()["rows"]}
        self.assertEqual((rows["Timed"]["from_time"], rows["Timed"]["to_time"]), ("09:15", "17:30"))
        self.assertEqual((rows["Untimed"]["from_time"], rows["Untimed"]["to_time"]), ("", ""))
        self.assertEqual((rows["Timed"]["elapsed"], rows["Untimed"]["elapsed"]), ("8h 15m", ""))

    def test_a_start_on_an_earlier_day_carries_its_date(self):
        done = timezone.make_aware(datetime.combine(self.today, time(17, 30)))
        self.entry(task_name="Long", created_time=done - timedelta(days=3), completed_time=done)
        self.login("dev")
        row = self.log().json()["rows"][0]
        self.assertEqual(row["to_time"], "17:30")
        self.assertRegex(row["from_time"], r"^\d{1,2} \w{3} \d\d:\d\d$")
        self.assertEqual(row["elapsed"], "3d 0h")  # how long it really took, even though the hours column is capped
