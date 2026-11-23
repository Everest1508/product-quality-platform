from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User
from apps.leads.models import Lead, LeadWebhook

GOOD = {"full_name": "Test", "email": "t@example.com", "company": "Acme", "need": "CRM", "details": "hello"}


class LeadWebhookTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme")
        self.hook = LeadWebhook.objects.create(company=self.company)
        self.url = reverse("lead_webhook", args=[self.hook.token])

    def test_json_post_creates_lead(self):
        r = self.client.post(self.url, GOOD, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Lead.objects.get().company, self.company)
        self.assertTrue(Lead.objects.get().is_submission)

    def test_phone_is_stored_as_typed(self):
        r = self.client.post(self.url, {**GOOD, "phone": "+91 98765 43210"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Lead.objects.get().phone, "+91 98765 43210")

    def test_phone_is_optional_and_may_be_empty(self):
        self.assertEqual(self.client.post(self.url, {**GOOD, "phone": ""}, content_type="application/json").status_code, 201)
        self.assertEqual(self.client.post(self.url, GOOD, content_type="application/json").status_code, 201)
        self.assertEqual(set(Lead.objects.values_list("phone", flat=True)), {""})

    def test_form_post_creates_lead(self):
        self.assertEqual(self.client.post(self.url, GOOD).status_code, 201)

    def test_missing_required_fields_rejected(self):
        r = self.client.post(self.url, {"full_name": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Lead.objects.count(), 0)

    def test_bad_token_404(self):
        self.assertEqual(self.client.post(reverse("lead_webhook", args=["nope"]), GOOD).status_code, 404)

    def test_only_admins_see_list(self):
        for role, code in (("developer", 403), ("admin", 200)):
            u = User.objects.create_user(username=role, email=f"{role}@x.com", password="p")
            Membership.objects.create(user=u, company=self.company, role=role)
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("leads:lead_list")).status_code, code)

    def test_rotate_invalidates_old_url(self):
        u = User.objects.create_user(username="o", email="o@x.com", password="p")
        Membership.objects.create(user=u, company=self.company, role="owner")
        self.client.force_login(u)
        self.client.post(reverse("leads:webhook_rotate"))
        self.assertEqual(self.client.post(self.url, GOOD).status_code, 404)


class LeadNotifyTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme")
        self.hook = LeadWebhook.objects.create(company=self.company)
        self.owner = User.objects.create_user(username="o", email="o@x.com", password="p")
        self.dev = User.objects.create_user(username="d", email="d@x.com", password="p")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")

    def test_admins_notified_then_cleared_on_visit(self):
        from apps.notifications.models import Notification
        self.client.post(reverse("lead_webhook", args=[self.hook.token]), GOOD)
        self.assertEqual(Notification.objects.filter(user=self.owner, kind="lead").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.dev).count(), 0)
        self.client.force_login(self.owner)
        r = self.client.get(reverse("dashboards:index"), follow=True)
        self.assertEqual(r.context["nav_new_leads"], 1)
        r = self.client.get(reverse("leads:lead_list"))
        self.assertEqual(r.context["nav_new_leads"], 0)


class LeadFlowTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = User.objects.create_user(username="o", email="o@x.com", password="p")
        self.dev = User.objects.create_user(username="d", email="d@x.com", password="p")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.lead = Lead.objects.create(company=self.company, full_name="Asha Rao", email="a@x.com",
                                        company_name="Rao Textiles", details="Need an ERP")
        self.client.force_login(self.owner)
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()

    def url(self, name):
        return reverse(f"leads:{name}", args=[self.lead.pk])

    def test_log_status_and_convert(self):
        self.client.post(self.url("lead_log"), {"text": "Called, wants a demo"})
        self.client.post(self.url("lead_status"), {"status": "req_gathering", "reason": "Asked for a call"})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "req_gathering")
        self.assertEqual([l.kind for l in self.lead.logs.all()], ["status", "note"])

        self.client.post(self.url("lead_status"), {"status": "won", "amount": "₹ 1,50,000", "reason": "Signed"})
        self.client.post(self.url("lead_convert"))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "won")
        self.assertEqual(self.lead.product.name, "Rao Textiles")
        self.assertEqual(self.lead.product.company, self.company)
        self.assertEqual(self.lead.logs.filter(kind="converted").count(), 1)
        self.assertContains(self.client.get(self.url("lead_detail")), "Open project")

    def test_quote_and_won_need_an_amount(self):
        for status in ("quote_sent", "won"):
            for bad in ("", "abc", "-5", "0", "nan"):
                r = self.client.post(self.url("lead_status"), {"status": status, "amount": bad, "reason": "x"},
                                     headers={"X-Requested-With": "XMLHttpRequest"})
                self.assertEqual(r.status_code, 400, (status, bad))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "generated")

    def test_amounts_are_saved(self):
        ajax = {"X-Requested-With": "XMLHttpRequest"}
        self.assertEqual(self.client.post(self.url("lead_status"), {"status": "quote_sent", "amount": "250000", "reason": "Sent PDF"}, headers=ajax).status_code, 200)
        self.client.post(self.url("lead_status"), {"status": "won", "amount": "240000.50", "reason": "Signed"}, headers=ajax)
        self.lead.refresh_from_db()
        self.assertEqual((self.lead.quoted_amount, self.lead.won_amount), (250000, Decimal("240000.50")))

    def test_a_reason_is_required_and_lands_in_the_activity(self):
        self.assertEqual(self.client.post(self.url("lead_status"), {"status": "req_gathering"},
                                          headers={"X-Requested-With": "XMLHttpRequest"}).status_code, 400)
        self.client.post(self.url("lead_status"), {"status": "req_gathering", "reason": "Client replied"})
        log = self.lead.logs.get()
        self.assertEqual((log.text, log.from_status, log.to_status), ("Client replied", "generated", "req_gathering"))

    def test_log_an_email_with_title(self):
        self.client.post(self.url("lead_log"), {"kind": "email", "title": "Shared specs", "text": "Sent the PDF"})
        self.client.post(self.url("lead_log"), {"kind": "status", "title": "sneaky"})  # not a loggable kind
        kinds = [(l.kind, l.title) for l in self.lead.logs.order_by("pk")]
        self.assertEqual(kinds, [("email", "Shared specs"), ("note", "sneaky")])
        self.assertContains(self.client.get(self.url("lead_detail")), "Shared specs")

    def test_only_won_leads_convert(self):
        from apps.products.models import Product
        self.client.post(self.url("lead_convert"))
        self.assertEqual(Product.objects.filter(company=self.company).count(), 0)

    def test_converting_twice_makes_one_project(self):
        from apps.products.models import Product
        self.client.post(self.url("lead_status"), {"status": "won", "amount": "10", "reason": "ok"})
        self.client.post(self.url("lead_convert"))
        self.client.post(self.url("lead_convert"))
        self.assertEqual(Product.objects.filter(company=self.company).count(), 1)

    def test_name_clash_gets_a_number(self):
        from apps.products.models import Product
        Product.objects.create(company=self.company, name="Rao Textiles", slug="rao-textiles")
        self.client.post(self.url("lead_status"), {"status": "won", "amount": "10", "reason": "ok"})
        self.client.post(self.url("lead_convert"))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.product.name, "Rao Textiles 2")

    def test_add_lead_by_hand_lands_in_generated_on_the_board(self):
        r = self.client.post(reverse("leads:lead_create"), {
            "full_name": "Ravi", "industry": "Retail", "details": "Billing app"})
        self.assertRedirects(r, reverse("leads:lead_board"))
        lead = Lead.objects.get(full_name="Ravi")
        self.assertEqual((lead.status, lead.industry, lead.email), ("generated", "Retail", ""))
        self.assertContains(self.client.get(reverse("leads:lead_board")), "Ravi")
        self.client.post(reverse("leads:lead_create"), {"full_name": "", "details": ""})
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 2)

    def test_admin_only(self):
        self.client.force_login(self.dev)
        self.assertEqual(self.client.get(self.url("lead_detail")).status_code, 403)
        self.assertEqual(self.client.get(reverse("leads:lead_board")).status_code, 403)
        self.assertEqual(self.client.post(reverse("leads:lead_create"), {"full_name": "x", "details": "y"}).status_code, 403)
        for name in ("lead_log", "lead_status", "lead_convert"):
            self.assertEqual(self.client.post(self.url(name), {"text": "x", "status": "lost"}).status_code, 403)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "generated")

    def test_other_companys_lead_is_404(self):
        theirs = Lead.objects.create(company=self.other, full_name="X", email="x@x.com", details="d")
        self.assertEqual(self.client.get(reverse("leads:lead_detail", args=[theirs.pk])).status_code, 404)


class LeadDeleteTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = User.objects.create_user(username="o", email="o@x.com", password="p")
        self.dev = User.objects.create_user(username="d", email="d@x.com", password="p")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.lead = Lead.objects.create(company=self.company, full_name="Asha Rao", email="a@x.com",
                                        details="Need an ERP", is_submission=True)
        self.client.force_login(self.owner)
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()

    def url(self, name):
        return reverse(f"leads:{name}", args=[self.lead.pk])

    def test_owner_can_delete_and_sees_a_confirmation_and_toast(self):
        from apps.dashboards.models import ActivityLog

        detail = self.client.get(self.url("lead_detail"))
        self.assertContains(detail, self.url("lead_delete"))
        self.assertContains(detail, 'data-confirm-label="Delete"')

        listing = self.client.get(reverse("leads:lead_list"))
        self.assertContains(listing, self.url("lead_delete"))
        self.assertContains(listing, 'aria-label="Delete Asha Rao"')

        r = self.client.post(self.url("lead_delete"))
        # Do not follow here: that request would consume the message the toast needs.
        self.assertRedirects(r, reverse("leads:lead_list"), fetch_redirect_response=False)
        self.assertFalse(Lead.objects.filter(pk=self.lead.pk).exists())
        after = self.client.get(reverse("leads:lead_list"))
        self.assertEqual(after.status_code, 200)
        self.assertContains(after, 'id="toast-seed"')
        self.assertContains(after, "Deleted Asha Rao")
        log = ActivityLog.objects.get(company=self.company, event_type="lead_deleted")
        self.assertEqual((log.actor, log.target_content_type, log.target_object_id),
                         (self.owner, "lead", self.lead.pk))
        self.assertIn(("lead_deleted", "Lead Deleted"), ActivityLog.EventType.choices)
        audit = self.client.get(reverse("dashboards:audit_log"), {"category": "system"})
        self.assertContains(audit, "Lead deleted: Asha Rao")

    def test_developer_cannot_delete(self):
        self.client.force_login(self.dev)
        self.assertEqual(self.client.post(self.url("lead_delete")).status_code, 403)
        self.assertTrue(Lead.objects.filter(pk=self.lead.pk).exists())

    def test_other_companys_lead_cannot_be_deleted(self):
        theirs = Lead.objects.create(company=self.other, full_name="X", email="x@x.com", details="d")
        url = reverse("leads:lead_delete", args=[theirs.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Lead.objects.filter(pk=theirs.pk).exists())

    def test_deleting_a_converted_lead_keeps_the_project_and_removes_its_activity(self):
        from apps.leads.models import LeadLog
        from apps.products.models import Product

        self.client.post(self.url("lead_promote"))
        self.client.post(self.url("lead_status"), {"status": "won", "amount": "10", "reason": "ok"})
        self.client.post(self.url("lead_convert"))
        self.lead.refresh_from_db()
        project_pk = self.lead.product_id
        self.assertEqual(self.lead.logs.count(), 3)  # promoted, moved, converted

        self.client.post(self.url("lead_delete"))
        self.assertTrue(Product.objects.filter(pk=project_pk, company=self.company).exists())
        self.assertEqual(LeadLog.objects.count(), 0)


class LeadPromoteTest(TestCase):
    """A website form post stays a submission until an admin promotes it into the pipeline."""

    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = User.objects.create_user(username="o", email="o@x.com", password="p")
        self.dev = User.objects.create_user(username="d", email="d@x.com", password="p")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.lead = Lead.objects.create(company=self.company, full_name="Asha Rao", email="a@x.com",
                                        company_name="Rao Textiles", details="Need an ERP", is_submission=True)
        self.client.force_login(self.owner)
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()

    def url(self, name):
        return reverse(f"leads:{name}", args=[self.lead.pk])

    def test_submission_stays_on_the_website_list_and_out_of_the_pipeline(self):
        listing = self.client.get(reverse("leads:lead_list"))
        self.assertContains(listing, self.url("lead_promote"))
        self.assertContains(listing, 'aria-label="Convert Asha Rao to a lead"')
        self.assertContains(listing, 'data-confirm-label="Convert to lead"')
        self.assertContains(listing, 'name="next" value="/leads/website/"')
        self.assertContains(listing, 'aria-label="Delete Asha Rao"')
        self.assertContains(listing, "Form submission")
        self.assertNotContains(self.client.get(reverse("leads:lead_board")), "Asha Rao")

    def test_website_list_keeps_showing_leads_after_promotion_and_always_shows_hand_added_ones(self):
        hand_added = Lead.objects.create(company=self.company, full_name="Ravi", email="r@x.com", details="Billing")

        listing = self.client.get(reverse("leads:lead_list"))
        self.assertContains(listing, "Asha Rao")
        self.assertContains(listing, "Ravi")
        self.assertContains(listing, "Form submission")
        self.assertContains(listing, "Lead · Generated")
        self.assertNotContains(listing, 'aria-label="Convert Ravi to a lead"')
        self.assertContains(listing, 'aria-label="Open Ravi"')

        self.client.post(self.url("lead_promote"), {"next": reverse("leads:lead_list")})
        listing = self.client.get(reverse("leads:lead_list"))
        self.assertContains(listing, "Asha Rao")
        self.assertContains(listing, "Lead · Generated")
        self.assertContains(listing, 'aria-label="Open Asha Rao"')
        self.assertNotContains(listing, 'aria-label="Convert Asha Rao to a lead"')
        self.assertContains(listing, 'aria-label="Delete Asha Rao"')

    def test_reports_do_not_count_a_submission_as_a_lead(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.reports.registry import Ctx, REPORTS

        today = timezone.localdate()
        ctx = Ctx(self.owner, self.company, today - timedelta(days=7), today, is_admin=True)
        self.assertEqual(REPORTS["lead-funnel"].run(ctx).kpis[0][1], "0")
        self.assertEqual(REPORTS["lead-response"].run(ctx).kpis[0][1], "0")
        self.assertEqual(REPORTS["lead-stale"].run(ctx).kpis[0][1], "0")
        self.assertEqual(REPORTS["lead-demand"].run(ctx).kpis[0][1], "0")
        self.assertEqual(REPORTS["lead-duplicates"].run(ctx).kpis[0][1], "0")

        self.client.post(self.url("lead_promote"), {"next": reverse("leads:lead_list")})
        self.assertEqual(REPORTS["lead-response"].run(ctx).kpis[0][1], "1")
        self.assertEqual(REPORTS["lead-stale"].run(ctx).kpis[0][1], "1")
        self.assertEqual(REPORTS["lead-demand"].run(ctx).kpis[0][1], "1")

    def test_detail_holds_the_stage_and_log_forms_until_it_is_a_lead(self):
        detail = self.client.get(self.url("lead_detail"))
        self.assertContains(detail, "Form submission")
        self.assertContains(detail, self.url("lead_promote"))
        self.assertContains(detail, "Not a lead yet")
        self.assertNotContains(detail, self.url("lead_status"))
        self.assertNotContains(detail, self.url("lead_log"))
        self.assertContains(detail, "/leads/website/")

    def test_promoting_moves_it_to_the_board_with_a_toast_and_an_audit_row(self):
        from apps.dashboards.models import ActivityLog

        r = self.client.post(self.url("lead_promote"), {"next": reverse("leads:lead_list")})
        # Do not follow here: that request would consume the message the toast needs.
        self.assertRedirects(r, reverse("leads:lead_list"), fetch_redirect_response=False)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.is_submission)
        self.assertEqual(self.lead.logs.get().text, "Promoted from a website form submission")

        after = self.client.get(reverse("leads:lead_list"))
        self.assertContains(after, 'id="toast-seed"')
        self.assertContains(after, "Asha Rao is now a lead")
        self.assertContains(after, "Lead · Generated")
        self.assertContains(after, 'aria-label="Open Asha Rao"')
        self.assertNotContains(after, 'aria-label="Convert Asha Rao to a lead"')
        self.assertContains(self.client.get(reverse("leads:lead_board")), "Asha Rao")

        log = ActivityLog.objects.get(company=self.company, event_type="lead_created")
        self.assertEqual((log.actor, log.target_content_type, log.target_object_id),
                         (self.owner, "lead", self.lead.pk))
        audit = self.client.get(reverse("dashboards:audit_log"), {"category": "system"})
        self.assertContains(audit, "Lead created: Asha Rao")

    def test_a_hostile_next_falls_back_to_the_detail_page(self):
        r = self.client.post(self.url("lead_promote"), {"next": "//evil.example/phish"})
        self.assertRedirects(r, self.url("lead_detail"), fetch_redirect_response=False)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.is_submission)

    def test_a_second_promotion_is_refused_without_a_second_log(self):
        self.client.post(self.url("lead_promote"))
        r = self.client.post(self.url("lead_promote"))
        self.assertRedirects(r, self.url("lead_detail"), fetch_redirect_response=False)
        self.assertEqual(self.lead.logs.count(), 1)
        messages = list(get_messages(r.wsgi_request))
        self.assertTrue(any("already a lead" in str(m) for m in messages))

    def test_only_admins_can_promote_and_only_their_companys_submissions(self):
        self.client.force_login(self.dev)
        self.assertEqual(self.client.post(self.url("lead_promote")).status_code, 403)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.is_submission)

        self.client.force_login(self.owner)
        theirs = Lead.objects.create(company=self.other, full_name="X", email="x@x.com",
                                     details="d", is_submission=True)
        self.assertEqual(self.client.post(reverse("leads:lead_promote", args=[theirs.pk])).status_code, 404)
