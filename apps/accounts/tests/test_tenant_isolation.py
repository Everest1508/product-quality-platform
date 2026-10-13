from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Company, Membership

User = get_user_model()


class TenantScopedManagerTest(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="Company A", slug="company-a")
        self.company_b = Company.objects.create(name="Company B", slug="company-b")

        self.user_a = User.objects.create_user("alice", "alice@a.com", "pass1234")
        self.user_b = User.objects.create_user("bob", "bob@b.com", "pass1234")

        Membership.objects.create(user=self.user_a, company=self.company_a, role="owner")
        Membership.objects.create(user=self.user_b, company=self.company_b, role="owner")

    def test_queryset_level_isolation(self):
        user_c = User.objects.create_user("carol", "carol@a.com", "pass1234")
        Membership.objects.create(user=user_c, company=self.company_a, role="developer")

        company_a_members = Membership.objects.for_company(self.company_a)
        company_b_members = Membership.objects.for_company(self.company_b)

        self.assertEqual(company_a_members.count(), 2)
        self.assertEqual(company_b_members.count(), 1)
        self.assertNotIn(
            self.user_b,
            company_a_members.values_list("user", flat=True),
        )


class MiddlewareCompanyResolutionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.user = User.objects.create_user("alice", "alice@acme.com", "pass1234")
        Membership.objects.create(user=self.user, company=self.company, role="owner")

    def test_request_has_company_after_login(self):
        self.client.login(username="alice", password="pass1234")
        # `accounts:dashboard` ('/') is a redirect to the real dashboard, so
        # follow it -- the middleware assertion has to be made on the page
        # that is actually rendered.
        response = self.client.get(reverse("accounts:dashboard"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse("dashboards:index"))
        self.assertEqual(response.context["request"].company, self.company)
        self.assertEqual(response.context["request"].company_role, "owner")


class SignupAndCompanyFlowTest(TestCase):
    def test_signup_creates_user(self):
        response = self.client.post(reverse("accounts:signup"), {
            "username": "newuser",
            "email": "new@test.com",
            "first_name": "New",
            "last_name": "User",
            "password1": "Str0ngP@ss!",
            "password2": "Str0ngP@ss!",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())
