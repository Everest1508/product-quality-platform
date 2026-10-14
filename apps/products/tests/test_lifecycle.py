"""The project lifecycle: phases, who may move a project, the reason, the log and who is told."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.notifications.models import Notification
from apps.products import lifecycle as lc
from apps.products.models import Product, ProductAccess, ProjectLogEntry


class LifecycleBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name="Acme", slug="acme-lc")
        self.owner = User.objects.create_user("owner", password="x")
        self.lead = User.objects.create_user("lead", password="x")
        self.dev = User.objects.create_user("dev", password="x")
        self.outsider = User.objects.create_user("outsider", password="x")
        for u, r in ((self.owner, "owner"), (self.lead, "developer"), (self.dev, "developer"), (self.outsider, "developer")):
            Membership.objects.create(user=u, company=self.company, role=r)
        self.product = Product.objects.create(company=self.company, name="Billing", slug="billing")
        lc.set_team(self.product, self.lead, [self.dev], self.owner)
        self.product.refresh_from_db()


class MovingTests(LifecycleBase):
    def test_a_reason_is_required_and_becomes_the_log_entry(self):
        with self.assertRaises(lc.LifecycleError):
            lc.move_stage(self.product, "fe", "  ", self.lead, "developer")
        entry = lc.move_stage(self.product, "fe", "Design signed off", self.lead, "developer")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stage, "fe")
        self.assertEqual((entry.kind, entry.from_stage, entry.to_stage, entry.body), ("stage", "creation", "fe", "Design signed off"))

    def test_only_the_pod_and_admins_may_move(self):
        with self.assertRaises(lc.LifecycleError):
            lc.move_stage(self.product, "fe", "why", self.outsider, "developer")
        lc.move_stage(self.product, "fe", "why", self.dev, "developer")
        lc.move_stage(self.product, "be", "admin step in", self.owner, "owner")

    def test_unused_phases_are_refused_and_skipped(self):
        lc.save_plan(self.product, user=self.owner, phases=["creation", "be", "deploy", "live", "close"])
        with self.assertRaises(lc.LifecycleError):
            lc.move_stage(self.product, "fe", "x", self.lead, "developer")
        self.assertEqual(lc.next_stage(self.product), "be")
        entry = lc.move_stage(self.product, "deploy", "skip ahead", self.lead, "developer")
        self.assertEqual(entry.meta["skipped"], ["FE", "Connection"])

    def test_moving_back_is_marked_and_the_pod_is_told_but_not_the_mover(self):
        lc.move_stage(self.product, "fe", "forward", self.lead, "developer")
        entry = lc.move_stage(self.product, "creation", "Needs a rethink", self.dev, "developer")
        self.assertTrue(entry.meta["back"])
        titles = list(Notification.objects.filter(user=self.lead).values_list("title", flat=True))
        self.assertTrue(any("sent back to Creation" in t for t in titles))
        self.assertFalse(Notification.objects.filter(user=self.dev, title__contains="sent back").exists())

    def test_same_phase_is_refused(self):
        with self.assertRaises(lc.LifecycleError):
            lc.move_stage(self.product, "creation", "same", self.lead, "developer")


class LogTests(LifecycleBase):
    def test_pod_member_can_write_and_tag_another_member(self):
        entry = lc.add_entry(self.product, self.dev, "developer", "update", "API done @lead please check")
        self.assertEqual([u.username for u in entry.mentions.all()], ["lead"])
        kinds = set(Notification.objects.filter(user=self.lead).values_list("kind", flat=True))
        self.assertIn("mention", kinds)

    def test_tagging_a_non_member_does_nothing(self):
        entry = lc.add_entry(self.product, self.dev, "developer", "update", "hey @outsider")
        self.assertEqual(entry.mentions.count(), 0)
        self.assertFalse(Notification.objects.filter(user=self.outsider).exists())

    def test_outsiders_cannot_write(self):
        with self.assertRaises(lc.LifecycleError):
            lc.add_entry(self.product, self.outsider, "developer", "update", "hi")

    def test_entries_cannot_be_edited_or_forged_into_a_stage_change(self):
        entry = lc.add_entry(self.product, self.dev, "developer", "update", "first")
        entry.body = "changed"
        with self.assertRaises(ValueError):
            entry.save()
        forged = lc.add_entry(self.product, self.dev, "developer", "stage", "sneaky")
        self.assertEqual(forged.kind, "update")

    def test_every_pod_member_hears_about_an_update_except_its_author(self):
        lc.add_entry(self.product, self.dev, "developer", "update", "progress")
        self.assertTrue(Notification.objects.filter(user=self.lead, kind="project").exists())
        self.assertFalse(Notification.objects.filter(user=self.dev, kind="project").exists())


class PlanTests(LifecycleBase):
    def test_pod_members_get_access_and_the_change_is_logged(self):
        self.assertTrue(ProductAccess.objects.filter(product=self.product, user=self.dev).exists())
        self.assertTrue(self.product.log_entries.filter(kind="setup").exists())

    def test_schedule_must_sit_inside_the_project_dates(self):
        with self.assertRaises(lc.LifecycleError):
            lc.save_plan(self.product, user=self.owner, start="2026-11-01", end="2026-11-30",
                         schedule={"fe": {"start": "2026-10-20", "end": "2026-11-10"}})
        self.product.refresh_from_db()
        self.assertIsNone(self.product.start_date)

    def test_dates_must_be_ordered_and_current_phase_cannot_be_removed(self):
        with self.assertRaises(lc.LifecycleError):
            lc.save_plan(self.product, user=self.owner, start="2026-11-10", end="2026-11-01")
        with self.assertRaises(lc.LifecycleError):
            lc.save_plan(self.product, user=self.owner, phases=["fe", "be"])

    def test_saving_a_plan_logs_one_schedule_entry(self):
        lc.save_plan(self.product, user=self.owner, start="2026-11-01", end="2026-11-30", tech_stack=["Django", " ", "React"],
                     srs="Must do X", schedule={"creation": {"start": "2026-11-01", "end": "2026-11-05", "hours": "16"}})
        self.product.refresh_from_db()
        self.assertEqual(self.product.tech_stack, ["Django", "React"])
        self.assertEqual(self.product.phase_plans.get(phase="creation").planned_hours, 16)
        self.assertEqual(self.product.log_entries.filter(kind="schedule").count(), 1)
        lc.save_plan(self.product, user=self.owner, start="2026-11-01", end="2026-11-30", srs="Must do X",
                     schedule={"creation": {"start": "2026-11-01", "end": "2026-11-05", "hours": "16"}})
        self.assertEqual(self.product.log_entries.filter(kind="schedule").count(), 1)  # nothing changed, nothing logged


class CrunchTests(LifecycleBase):
    def test_a_crunch_item_is_logged_and_must_beat_the_end_date(self):
        lc.save_plan(self.product, user=self.owner, start="2026-11-01", end="2026-11-30")
        with self.assertRaises(lc.LifecycleError):
            lc.add_crunch(self.product, self.lead, "developer", "Login", "2026-12-15")
        item = lc.add_crunch(self.product, self.lead, "developer", "Login", "2026-11-10", "Client demo")
        self.assertEqual(lc.crunch_state(item, date(2026, 11, 9)), "soon")
        self.assertEqual(lc.crunch_state(item, date(2026, 11, 11)), "late")
        lc.finish_crunch(item, self.dev, "developer")
        self.assertEqual(lc.crunch_state(item), "done")
        self.assertEqual(self.product.log_entries.filter(kind="crunch").count(), 2)


class HistoryTests(LifecycleBase):
    def test_history_shows_time_in_each_phase(self):
        lc.move_stage(self.product, "fe", "go", self.lead, "developer")
        lc.move_stage(self.product, "be", "go", self.lead, "developer")
        segs = lc.history(self.product)
        self.assertEqual([s["stage"] for s in segs], ["creation", "fe", "be"])
        self.assertIsNone(segs[-1]["end"])


class ProjectPagesTests(LifecycleBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.lead)

    def url(self, name, *args):
        from django.urls import reverse

        return reverse(f"products:{name}", args=args)

    def test_board_journey_lifecycle_and_plan_pages_open(self):
        for name, args in (("project_board", ()), ("project_lifecycle", (self.product.pk,)), ("project_details", (self.product.pk,))):
            self.assertEqual(self.client.get(self.url(name, *args)).status_code, 200, name)
        self.assertEqual(self.client.get(self.url("project_board") + "?view=journey").status_code, 200)

    def test_moving_needs_a_reason_and_works_over_json(self):
        r = self.client.post(self.url("project_move", self.product.pk), {"to": "fe", "reason": ""}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(self.url("project_move", self.product.pk), {"to": "fe", "reason": "Design done"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stage, "fe")

    def test_a_non_pod_developer_cannot_move_or_write(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.url("project_move", self.product.pk), {"to": "fe", "reason": "x"}).status_code, 404)  # no access to the product at all
        ProductAccess.objects.create(product=self.product, user=self.outsider, company=self.company)
        r = self.client.post(self.url("project_move", self.product.pk), {"to": "fe", "reason": "x"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stage, "creation")

    def test_log_entry_with_a_tag_shows_highlighted_and_notifies(self):
        self.client.post(self.url("project_log_add", self.product.pk), {"kind": "update", "body": "ready @dev"})
        page = self.client.get(self.url("project_lifecycle", self.product.pk)).content.decode()
        self.assertIn('class="pj-mention">@dev', page)
        self.assertTrue(Notification.objects.filter(user=self.dev, kind="mention").exists())

    def test_new_project_form_saves_the_whole_plan(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.url("project_new"), {
            "name": "Portal", "start_date": "2026-11-01", "end_date": "2026-12-01", "lead": self.lead.pk, "pod": [self.dev.pk],
            "tech_stack": "Django, React", "srs": "Must log in",
            "phase_creation": "1", "phase_be": "1", "phase_live": "1",
            "s_be": "2026-11-05", "e_be": "2026-11-20", "h_be": "40",
            "crunch_feature": ["Login"], "crunch_due": ["2026-11-10"], "crunch_reason": ["Demo"],
        })
        self.assertEqual(r.status_code, 302)
        p = Product.objects.get(name="Portal")
        self.assertEqual((p.stage, p.phases, p.tech_stack, p.lead_id), ("creation", ["creation", "be", "live"], ["Django", "React"], self.lead.pk))
        self.assertEqual(p.phase_plans.get(phase="be").planned_hours, 40)
        self.assertEqual(p.crunch_items.count(), 1)
        self.assertEqual({u.username for u in lc.pod_users(p)}, {"lead", "dev"})
        self.assertGreaterEqual(p.log_entries.count(), 3)

    def test_quick_add_creates_a_project_in_that_column(self):
        self.client.force_login(self.owner)
        self.client.post(self.url("project_quick_add"), {"name": "Quick one", "stage": "be"})
        p = Product.objects.get(name="Quick one")
        self.assertEqual(p.stage, "be")
        self.assertEqual(p.lead_id, self.owner.pk)
        self.client.force_login(self.lead)  # developers cannot create products
        self.assertEqual(self.client.post(self.url("project_quick_add"), {"name": "Nope"}).status_code, 403)

    def test_plan_page_saves_and_rejects_bad_dates_with_a_message(self):
        r = self.client.post(self.url("project_details", self.product.pk), {"start_date": "2026-11-10", "end_date": "2026-11-01", "phase_creation": "1"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("before the start date", r.content.decode())
