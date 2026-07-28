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


class CrossTenantViewAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company_a = Company.objects.create(name="Company A", slug="company-a")
        self.company_b = Company.objects.create(name="Company B", slug="company-b")

        self.user_a = User.objects.create_user("alice", "alice@a.com", "pass1234")
        self.user_b = User.objects.create_user("bob", "bob@b.com", "pass1234")

        Membership.objects.create(user=self.user_a, company=self.company_a, role="owner")
        Membership.objects.create(user=self.user_b, company=self.company_b, role="owner")

    def test_user_a_cannot_see_company_b_team(self):
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("accounts:team_list"))
        self.assertEqual(response.status_code, 200)
        memberships = response.context["memberships"]
        for m in memberships:
            self.assertEqual(m.company, self.company_a)

    def test_user_b_cannot_see_company_a_team(self):
        self.client.login(username="bob", password="pass1234")
        response = self.client.get(reverse("accounts:team_list"))
        self.assertEqual(response.status_code, 200)
        memberships = response.context["memberships"]
        for m in memberships:
            self.assertEqual(m.company, self.company_b)

    def test_remove_member_only_within_own_company(self):
        self.client.login(username="alice", password="pass1234")
        member_b = Membership.objects.get(user=self.user_b, company=self.company_b)
        response = self.client.post(
            reverse("accounts:team_remove", kwargs={"pk": member_b.pk})
        )
        self.assertRedirects(response, reverse("accounts:team_list"))
        self.assertTrue(
            Membership.objects.filter(pk=member_b.pk).exists(),
            "Cross-tenant member removal should not work.",
        )


class MiddlewareCompanyResolutionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.user = User.objects.create_user("alice", "alice@acme.com", "pass1234")
        Membership.objects.create(user=self.user, company=self.company, role="owner")

    def test_request_has_company_after_login(self):
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 200)
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

    def test_company_setup_creates_company_and_membership(self):
        user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        response = self.client.post(reverse("accounts:company_setup"), {
            "name": "Test Corp",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Company.objects.filter(slug="test-corp").exists())
        membership = Membership.objects.get(user=user)
        self.assertEqual(membership.role, Membership.Role.OWNER)


class HTMXPartialIsolationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.company_a = Company.objects.create(name="A", slug="a")
        self.company_b = Company.objects.create(name="B", slug="b")
        self.user_a = User.objects.create_user("alice", "a@test.com", "pass1234")
        self.user_b = User.objects.create_user("bob", "b@test.com", "pass1234")
        Membership.objects.create(user=self.user_a, company=self.company_a, role="owner")
        Membership.objects.create(user=self.user_b, company=self.company_b, role="owner")

    def test_htmx_team_partial_isolation(self):
        self.client.login(username="alice", password="pass1234")
        response = self.client.get(
            reverse("accounts:team_list"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("bob", content)
