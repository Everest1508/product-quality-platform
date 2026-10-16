"""A person removed from their team is locked out, not handed a workspace of their own.

Removing a member deletes their Membership. A person with no Membership used to
land in company setup after signing in, where they could open a new company and
own it. They are now stopped at sign-in, and signed out if it happens mid-session.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.access import NO_WORKSPACE_MESSAGE
from apps.accounts.models import Company, ExternalAccessToken, Membership

User = get_user_model()


class RemovedMemberTest(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=self.owner, company=self.acme, role="owner")
        self.dev_membership = Membership.objects.create(user=self.dev, company=self.acme, role="developer")
        self.login_url = reverse("accounts:login")

    def remove_dev(self):
        """The owner removes the developer from the Team page, in their own browser."""
        owner = Client()
        owner.login(username="owner", password="pass1234")
        response = owner.post(reverse("accounts:team_remove", kwargs={"pk": self.dev_membership.pk}))
        self.assertRedirects(response, reverse("accounts:team_list"))

    def sign_in(self, password="pass1234"):
        return self.client.post(self.login_url, {"username": "dev", "password": password})

    def test_a_removed_member_cannot_sign_in(self):
        self.remove_dev()
        response = self.sign_in()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, NO_WORKSPACE_MESSAGE)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_removed_member_cannot_open_a_company_of_their_own(self):
        self.remove_dev()
        self.sign_in()
        response = self.client.post(reverse("accounts:company_setup"), {"name": "Mine"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(self.login_url))
        self.assertFalse(Company.objects.filter(name="Mine").exists())

    def test_a_wrong_password_does_not_reveal_that_the_account_has_no_workspace(self):
        self.remove_dev()
        response = self.sign_in("wrong")
        self.assertContains(response, "Incorrect username or password")
        self.assertNotContains(response, NO_WORKSPACE_MESSAGE)

    def test_a_member_removed_while_signed_in_is_signed_out_and_told_why(self):
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(self.client.get(reverse("accounts:team_list")).status_code, 200)
        self.remove_dev()

        refresh = self.client.get(reverse("accounts:team_list"))
        self.assertRedirects(refresh, self.login_url, fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(self.client.get(self.login_url), NO_WORKSPACE_MESSAGE)

    def test_a_member_removed_while_signed_in_cannot_open_a_company_either(self):
        self.client.login(username="dev", password="pass1234")
        self.remove_dev()
        response = self.client.post(reverse("accounts:company_setup"), {"name": "Mine"})
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)
        self.assertFalse(Company.objects.filter(name="Mine").exists())

    def test_a_member_removed_from_one_company_keeps_the_other(self):
        beta = Company.objects.create(name="Beta", slug="beta")
        Membership.objects.create(user=self.dev, company=beta, role="viewer")
        self.client.login(username="dev", password="pass1234")
        session = self.client.session
        session["active_company_id"] = self.acme.pk
        session.save()

        self.remove_dev()

        response = self.client.get(reverse("accounts:team_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["request"].company, beta)

    def test_a_removed_member_loses_the_team_in_serop_too(self):
        """Serop teams are the same Membership rows, so one removal covers both."""
        _, raw = ExternalAccessToken.create_token(self.dev)
        serop = APIClient()
        serop.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        self.assertEqual(len(serop.get("/api/serop/teams").json()["teams"]), 1)

        self.remove_dev()

        self.assertEqual(serop.get("/api/serop/teams").json()["teams"], [])


class FirstWorkspaceTest(TestCase):
    """Company setup is still there for whoever starts an install."""

    def setUp(self):
        self.user = User.objects.create_user("first", "first@test.com", "pass1234")

    def test_the_first_person_on_an_empty_install_can_sign_in_and_open_a_company(self):
        response = self.client.post(reverse("accounts:login"), {"username": "first", "password": "pass1234"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("accounts:company_setup")).status_code, 200)

    def test_staff_can_still_reach_company_setup_once_companies_exist(self):
        Company.objects.create(name="Acme", slug="acme")
        self.user.is_staff = True
        self.user.save()
        self.client.login(username="first", password="pass1234")
        self.assertEqual(self.client.get(reverse("accounts:company_setup")).status_code, 200)
