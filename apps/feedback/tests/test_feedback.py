from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.feedback.models import SentimentRecord, Survey, SurveyResponse
from apps.products.models import Product

User = get_user_model()


class SurveyModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)

    def test_nps_score_range(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        self.assertEqual(list(survey.score_range()), list(range(0, 11)))

    def test_csat_score_range(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="CSAT", survey_type="csat", status="active",
        )
        self.assertEqual(list(survey.score_range()), list(range(1, 6)))

    def test_ces_score_range(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="CES", survey_type="ces", status="active",
        )
        self.assertEqual(list(survey.score_range()), list(range(1, 8)))

    def test_compute_nps(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        for score in [9, 10, 10, 7, 3]:
            SurveyResponse.objects.create(
                survey=survey, company=self.company, score=score,
            )
        # 3 promoters (9,10,10) - 1 detractor (3) = 2, /5 = 0.4 * 100 = 40
        self.assertEqual(survey.compute_nps(), 40)

    def test_compute_nps_empty(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        self.assertIsNone(survey.compute_nps())

    def test_compute_avg_score(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="CSAT", survey_type="csat", status="active",
        )
        for score in [3, 4, 5]:
            SurveyResponse.objects.create(
                survey=survey, company=self.company, score=score,
            )
        self.assertEqual(survey.compute_avg_score(), 4.0)

    def test_response_count(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        self.assertEqual(survey.response_count, 0)
        SurveyResponse.objects.create(survey=survey, company=self.company, score=5)
        self.assertEqual(survey.response_count, 1)

    def test_score_label_nps(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        self.assertEqual(survey.score_label(3), "Detractor")
        self.assertEqual(survey.score_label(7), "Passive")
        self.assertEqual(survey.score_label(9), "Promoter")

    def test_tenant_isolation(self):
        company2 = Company.objects.create(name="Beta", slug="beta")
        Survey.objects.create(
            company=self.company, product=self.product,
            name="My Survey", survey_type="nps", status="active",
        )
        Survey.objects.create(
            company=company2, product=self.product,
            name="Other Survey", survey_type="nps", status="active",
        )
        self.assertEqual(Survey.objects.filter(company=self.company).count(), 1)
        self.assertEqual(Survey.objects.filter(company=company2).count(), 1)


class SurveyViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_survey_list(self):
        response = self.client.get(reverse("feedback:survey_list"))
        self.assertEqual(response.status_code, 200)

    def test_create_survey(self):
        response = self.client.post(reverse("feedback:survey_create"), {
            "name": "Q1 NPS",
            "description": "Quarterly NPS",
            "survey_type": "nps",
            "product": self.product.pk,
            "status": "draft",
        })
        self.assertRedirects(response, reverse("feedback:survey_detail", kwargs={"pk": 1}))
        self.assertEqual(Survey.objects.count(), 1)
        survey = Survey.objects.first()
        self.assertEqual(survey.company, self.company)
        self.assertEqual(survey.created_by, self.user)

    def test_survey_detail(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        response = self.client.get(reverse("feedback:survey_detail", kwargs={"pk": survey.pk}))
        self.assertEqual(response.status_code, 200)

    def test_toggle_survey(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="draft",
        )
        response = self.client.post(reverse("feedback:survey_toggle", kwargs={"pk": survey.pk}))
        survey.refresh_from_db()
        self.assertEqual(survey.status, "active")

    def test_delete_survey(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="Delete me", survey_type="nps", status="draft",
        )
        response = self.client.post(reverse("feedback:survey_delete", kwargs={"pk": survey.pk}))
        self.assertFalse(Survey.objects.filter(pk=survey.pk).exists())

    def test_cannot_see_other_company_survey(self):
        company2 = Company.objects.create(name="Beta", slug="beta")
        other_survey = Survey.objects.create(
            company=company2, product=self.product,
            name="Other Survey", survey_type="nps", status="active",
        )
        response = self.client.get(reverse("feedback:survey_detail", kwargs={"pk": other_survey.pk}))
        self.assertEqual(response.status_code, 404)


class PublicSurveyTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )

    def test_public_survey_view(self):
        response = self.client.get(reverse("feedback:public_survey", kwargs={"pk": self.survey.pk}))
        self.assertEqual(response.status_code, 200)

    def test_submit_response(self):
        response = self.client.post(reverse("feedback:public_survey", kwargs={"pk": self.survey.pk}), {
            "score": 9,
            "comment": "Great product!",
            "contact_name": "Bob",
            "contact_email": "bob@test.com",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SurveyResponse.objects.count(), 1)
        resp = SurveyResponse.objects.first()
        self.assertEqual(resp.score, 9)
        self.assertEqual(resp.contact_name, "Bob")

    def test_closed_survey_not_accessible(self):
        self.survey.status = "closed"
        self.survey.save()
        response = self.client.get(reverse("feedback:public_survey", kwargs={"pk": self.survey.pk}))
        self.assertEqual(response.status_code, 404)


class CSHubTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_cs_hub_page(self):
        response = self.client.get(reverse("feedback:cs_hub"))
        self.assertEqual(response.status_code, 200)

    def test_cs_hub_with_data(self):
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        for score in [7, 8, 9, 10]:
            SurveyResponse.objects.create(survey=survey, company=self.company, score=score)

        SentimentRecord.objects.create(
            company=self.company, product=self.product,
            source="survey", score=0.75,
        )

        response = self.client.get(reverse("feedback:cs_hub"))
        self.assertEqual(response.status_code, 200)
