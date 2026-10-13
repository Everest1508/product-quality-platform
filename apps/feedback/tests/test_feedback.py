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


class SurveyPagesTest(TestCase):
    """The pages themselves are the React shell; what the API returns is in apps.uiapi.test_feedback_automation."""

    def setUp(self):
        self.user = User.objects.create_user("alice", "a@t.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.survey = Survey.objects.create(company=self.company, product=self.product, name="NPS", status="active")

    def test_pages_serve_the_shell(self):
        self.client.login(username="alice", password="pass1234")
        for url in ("/feedback/", "/feedback/create/", "/feedback/cs-hub/", f"/feedback/{self.survey.pk}/", f"/products/{self.product.pk}/surveys/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTemplateUsed(r, "uiapi/shell.html")

    def test_the_public_link_needs_no_login_and_only_works_while_active(self):
        self.assertEqual(self.client.get(f"/feedback/respond/{self.survey.pk}/").status_code, 200)
        self.survey.status = "closed"
        self.survey.save()
        self.assertEqual(self.client.get(f"/feedback/respond/{self.survey.pk}/").status_code, 404)

