from django.test import Client

from apps.automation.models import AutoTicketRule
from apps.dashboards.models import ActivityLog
from apps.feedback.models import SentimentRecord, Survey, SurveyResponse
from apps.uiapi.test_tickets import Base, member


class FB(Base):
    def survey(self, product=None, name="NPS Q1", **kw):
        product = product or self.p_open
        return Survey.objects.create(company=product.company, product=product, name=name, **kw)

    def post(self, url, body=None):
        return self.client.post(url, body or {}, content_type="application/json")


class SurveyListApiTest(FB):
    def test_scoped_to_accessible_products(self):
        self.survey(self.p_open, "mine")
        self.survey(self.p_hidden, "secret")
        self.survey(self.p_foreign, "foreign")
        self.login("dev")
        self.assertEqual([i["name"] for i in self.client.get("/ui-api/v1/surveys/").json()["items"]], ["mine"])
        self.login("owner")
        self.assertEqual(self.client.get("/ui-api/v1/surveys/").json()["page"]["count"], 2)

    def test_filters_sort_and_product_scope(self):
        a = self.survey(self.p_open, "a", status="active", survey_type="csat")
        self.survey(self.p_open, "b")
        SurveyResponse.objects.create(company=self.acme, survey=a, score=4)
        self.survey(self.p_hidden, "elsewhere")
        self.login("owner")
        get = lambda q: [i["name"] for i in self.client.get("/ui-api/v1/surveys/" + q).json()["items"]]
        self.assertEqual(get("?status=active"), ["a"])
        self.assertEqual(get("?type=csat"), ["a"])
        self.assertEqual(get("?q=B"), ["b"])
        self.assertEqual(get("?sort=-responses")[0], "a")
        self.assertEqual(get(f"?scope=product&product={self.p_open.pk}").__len__(), 2)
        self.login("dev")
        self.assertEqual(self.client.get(f"/ui-api/v1/surveys/?scope=product&product={self.p_hidden.pk}").status_code, 404)


class SurveyCrudApiTest(FB):
    body = {"name": "Q1", "description": "", "survey_type": "nps", "status": "draft"}

    def test_create_global_and_product(self):
        self.login("dev")
        r = self.post("/ui-api/v1/surveys/", {**self.body, "product": self.p_open.pk})
        self.assertEqual(r.status_code, 201)
        s = Survey.objects.get()
        self.assertEqual((s.created_by, r.json()["url"]), (self.dev, f"/feedback/{s.pk}/"))
        self.assertTrue(ActivityLog.objects.filter(event_type="survey_created").exists())
        r = self.post(f"/ui-api/v1/surveys/?scope=product&product={self.p_open.pk}", {**self.body, "name": "Q2", "product": self.p_hidden.pk})
        self.assertEqual(Survey.objects.get(name="Q2").product, self.p_open)  # the page's product wins

    def test_product_must_be_accessible(self):
        self.login("dev")
        for p in (self.p_hidden, self.p_foreign):
            r = self.post("/ui-api/v1/surveys/", {**self.body, "product": p.pk})
            self.assertEqual(r.status_code, 400, p)
            self.assertIn("product", r.json()["errors"])
        self.assertFalse(Survey.objects.exists())

    def test_validation(self):
        self.login("dev")
        r = self.post("/ui-api/v1/surveys/", {**self.body, "name": "", "product": self.p_open.pk})
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.json()["errors"])

    def test_detail_toggle_delete(self):
        s = self.survey()
        SurveyResponse.objects.create(company=self.acme, survey=s, score=10, comment="great", contact_name="Zed")
        SurveyResponse.objects.create(company=self.acme, survey=s, score=2)
        self.login("dev")
        d = self.client.get(f"/ui-api/v1/surveys/{s.pk}/").json()
        self.assertEqual(d["survey"]["nps"], 0)
        self.assertEqual(d["survey"]["public_path"], f"/feedback/respond/{s.pk}/")
        self.assertEqual({x["score"]: x["count"] for x in d["distribution"]}[10], 1)
        self.assertEqual(len(d["distribution"]), 11)
        self.assertEqual(d["responses"][-1]["score"], 10)
        states = [self.post(f"/ui-api/v1/surveys/{s.pk}/toggle/").json()["survey"]["status"] for _ in range(3)]
        self.assertEqual(states, ["active", "closed", "draft"])
        r = self.client.delete(f"/ui-api/v1/surveys/{s.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Survey.objects.exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="survey_deleted").exists())

    def test_no_access_and_foreign_are_404_for_every_action(self):
        hidden, foreign = self.survey(self.p_hidden), self.survey(self.p_foreign)
        self.login("dev")
        for s in (hidden, foreign):
            self.assertEqual(self.client.get(f"/ui-api/v1/surveys/{s.pk}/").status_code, 404)
            self.assertEqual(self.post(f"/ui-api/v1/surveys/{s.pk}/toggle/").status_code, 404)
            self.assertEqual(self.client.delete(f"/ui-api/v1/surveys/{s.pk}/").status_code, 404)
        self.assertEqual(Survey.objects.count(), 2)


class PublicSurveyApiTest(FB):
    def test_only_active_surveys_and_no_login(self):
        draft, live = self.survey(name="d"), self.survey(name="l", status="active", description="Tell us")
        anon = Client()
        self.assertEqual(anon.get(f"/ui-api/v1/public/surveys/{draft.pk}/").status_code, 404)
        d = anon.get(f"/ui-api/v1/public/surveys/{live.pk}/").json()
        self.assertEqual((d["name"], d["scores"]), ("l", list(range(0, 11))))
        self.assertEqual(d["product"], "Open")
        self.assertNotIn("company", d)

    def test_submit_and_validation(self):
        live = self.survey(status="active", survey_type="csat")
        anon = Client()
        url = f"/ui-api/v1/public/surveys/{live.pk}/"
        post = lambda body: anon.post(url, body, content_type="application/json")
        self.assertEqual(post({"score": 11}).status_code, 400)
        self.assertEqual(post({}).status_code, 400)
        self.assertEqual(post([1]).status_code, 400)
        self.assertEqual(post({"score": 5, "contact_email": "nope"}).status_code, 400)
        self.assertEqual(post({"score": 5, "comment": "ok", "contact_name": "Zed", "contact_email": "z@t.io"}).status_code, 201)
        r = SurveyResponse.objects.get()
        self.assertEqual((r.score, r.comment, r.company), (5, "ok", self.acme))
        self.assertTrue(ActivityLog.objects.filter(event_type="survey_response").exists())

    def test_closed_surveys_take_no_answers(self):
        s = self.survey(status="closed")
        self.assertEqual(Client().post(f"/ui-api/v1/public/surveys/{s.pk}/", {"score": 5}, content_type="application/json").status_code, 404)
        self.assertFalse(SurveyResponse.objects.exists())


class CsHubApiTest(FB):
    def test_numbers_only_cover_accessible_products(self):
        s = self.survey(status="active")
        h = self.survey(self.p_hidden, "h", status="active")
        for sv, score in ((s, 4), (s, 5), (h, 1)):
            SurveyResponse.objects.create(company=self.acme, survey=sv, score=score)
        SentimentRecord.objects.create(company=self.acme, product=self.p_open, score="0.5")
        SentimentRecord.objects.create(company=self.acme, product=self.p_hidden, score="-0.5")
        self.login("dev")
        d = self.client.get("/ui-api/v1/cs-hub/").json()
        self.assertEqual((d["total_responses"], d["avg_all"], d["sentiment_total"]), (2, 4.5, 1))
        self.assertEqual([x["name"] for x in d["active_surveys"]], ["NPS Q1"])
        self.assertEqual([x["product"]["name"] for x in d["product_stats"]], ["Open"])
        self.assertEqual(d["product_stats"][0]["response_count"], 2)
        self.login("owner")
        self.assertEqual(self.client.get("/ui-api/v1/cs-hub/").json()["total_responses"], 3)


class RulesApiTest(FB):
    body = {"name": "Spike", "trigger_type": "error_threshold", "severity": "", "threshold_count": 5, "window_minutes": 30,
            "action": "create_ticket", "assign_to": "", "is_active": True}

    def rule(self, product, name="r", **kw):
        return AutoTicketRule.objects.create(company=product.company if product else self.acme, product=product, name=name, **kw)

    def test_list_scoping_and_company_wide_visibility(self):
        self.rule(self.p_open, "mine")
        self.rule(self.p_hidden, "secret")
        self.rule(None, "wide")
        self.login("dev")
        self.assertEqual([i["name"] for i in self.client.get("/ui-api/v1/rules/").json()["items"]], ["mine"])
        self.login("owner")
        self.assertEqual(sorted(i["name"] for i in self.client.get("/ui-api/v1/rules/").json()["items"]), ["mine", "secret", "wide"])

    def test_filters_and_product_scope(self):
        self.rule(self.p_open, "a")
        self.rule(self.p_open, "b", is_active=False)
        self.rule(self.p_hidden, "c")
        self.login("owner")
        get = lambda q: sorted(i["name"] for i in self.client.get("/ui-api/v1/rules/" + q).json()["items"])
        self.assertEqual(get("?active=0"), ["b"])
        self.assertEqual(get("?q=c"), ["c"])
        self.assertEqual(get(f"?scope=product&product={self.p_open.pk}"), ["a", "b"])

    def test_create_for_a_product_and_company_wide_rules_are_for_admins(self):
        self.login("dev")
        r = self.post("/ui-api/v1/rules/", {**self.body, "product": self.p_open.pk})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.post("/ui-api/v1/rules/", {**self.body, "name": "wide", "product": ""}).status_code, 403)
        r = self.post("/ui-api/v1/rules/", {**self.body, "name": "x", "product": self.p_hidden.pk})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(AutoTicketRule.objects.count(), 1)
        self.login("owner")
        self.assertEqual(self.post("/ui-api/v1/rules/", {**self.body, "name": "wide", "product": ""}).status_code, 201)
        self.assertTrue(ActivityLog.objects.filter(event_type="rule_created").exists())

    def test_product_page_creates_on_its_product(self):
        self.login("dev")
        self.post(f"/ui-api/v1/rules/?scope=product&product={self.p_open.pk}", {**self.body, "product": ""})
        self.assertEqual(AutoTicketRule.objects.get().product, self.p_open)

    def test_edit_toggle_delete(self):
        r = self.rule(self.p_open, "r")
        self.login("dev")
        url = f"/ui-api/v1/rules/{r.pk}/"
        resp = self.client.patch(url, {**self.body, "name": "Renamed", "product": self.p_open.pk, "threshold_count": 9}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual((r.name, r.threshold_count), ("Renamed", 9))
        self.assertFalse(self.post(url + "toggle/").json()["rule"]["is_active"])
        self.assertEqual(self.client.patch(url, {**self.body, "product": ""}, content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertFalse(AutoTicketRule.objects.exists())
        for ev in ("rule_updated", "rule_toggled", "rule_deleted"):
            self.assertTrue(ActivityLog.objects.filter(event_type=ev).exists(), ev)

    def test_other_products_and_foreign_and_wide_rules_are_404_for_members(self):
        hidden, wide = self.rule(self.p_hidden), self.rule(None)
        foreign = AutoTicketRule.objects.create(company=self.other, product=self.p_foreign, name="f")
        self.login("dev")
        for r in (hidden, wide, foreign):
            url = f"/ui-api/v1/rules/{r.pk}/"
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.post(url + "toggle/").status_code, 404)
            self.assertEqual(self.client.delete(url).status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(f"/ui-api/v1/rules/{foreign.pk}/").status_code, 404)

    def test_meta(self):
        self.login("dev")
        m = self.client.get("/ui-api/v1/rules/meta/").json()
        self.assertEqual([p["name"] for p in m["products"]], ["Open"])
        self.assertFalse(m["can_company_wide"])
        self.assertIn("dev", [u["name"] for u in m["members"]])
