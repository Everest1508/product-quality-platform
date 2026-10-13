from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import Client, TestCase
from django.urls import NoReverseMatch, reverse

from apps.accounts import throttle
from apps.accounts.models import Company, ExternalAuthCode, Membership
from apps.dashboards.models import ActivityLog

User = get_user_model()
LOGIN = "/ui-api/v1/auth/login/"


def post(client, url, body=None, **kw):
    return client.post(url, body or {}, content_type="application/json", **kw)


class LoginApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user("ann", password="right-pass-1", email="ann@example.com")
        User.objects.create_user("bob", password="right-pass-2")

    def attempt(self, username, password, **extra):
        return post(self.client, LOGIN, {"username": username, "password": password, **extra})

    def test_sign_in_by_username_or_email_lands_on_the_dashboard(self):
        r = self.attempt("ann", "right-pass-1")
        self.assertEqual((r.status_code, r.json()["redirect"]), (200, "/dashboards/"))
        self.assertIn("_auth_user_id", self.client.session)
        self.client.logout()
        self.assertEqual(self.attempt("ann@example.com", "right-pass-1").status_code, 200)

    def test_one_message_for_no_such_user_and_wrong_password(self):
        a = self.attempt("ghost", "wrong")
        b = self.attempt("ann", "wrong")
        self.assertEqual((a.status_code, b.status_code), (400, 400))
        self.assertEqual(a.json()["detail"], b.json()["detail"])
        self.assertEqual(a.json()["detail"], "Incorrect username or password.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_blank_fields_and_odd_bodies(self):
        self.assertEqual(self.attempt("", "").status_code, 400)
        self.assertEqual(post(self.client, LOGIN, [1]).status_code, 400)

    def test_next_is_honoured_only_when_it_is_a_site_path(self):
        self.assertEqual(self.attempt("ann", "right-pass-1", next="/tickets/").json()["redirect"], "/tickets/")
        self.client.logout()
        for hostile in ("https://evil.example/steal", "//evil.example", "/\\evil.example"):
            self.assertEqual(self.attempt("ann", "right-pass-1", next=hostile).json()["redirect"], "/dashboards/", hostile)
            self.client.logout()

    def test_the_page_state_carries_next_and_flash_messages(self):
        self.client.post("/logout/")  # queues "Signed out."
        d = self.client.get(LOGIN, {"next": "/tickets/"}).json()
        self.assertEqual((d["authenticated"], d["next"]), (False, "/tickets/"))
        self.assertEqual(self.client.get(LOGIN, {"next": "//evil.example"}).json()["next"], "")
        self.assertEqual(self.client.get(LOGIN).json()["messages"], [])  # shown once

    def test_five_wrong_passwords_lock_that_account(self):
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.assertEqual(self.attempt("ann", "wrong").status_code, 400)
        locked = self.attempt("ann", "wrong")
        self.assertEqual(locked.status_code, 429)
        self.assertIn("Too many failed attempts", locked.json()["detail"])

    def test_the_right_password_is_refused_while_locked(self):
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.attempt("ann", "wrong")
        self.assertEqual(self.attempt("ann", "right-pass-1").status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_good_sign_in_resets_the_count_and_one_lock_leaves_others_alone(self):
        for _ in range(throttle.MAX_PER_ACCOUNT - 1):
            self.attempt("ann", "wrong")
        self.assertEqual(self.attempt("ann", "right-pass-1").status_code, 200)
        self.client.logout()
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.assertEqual(self.attempt("ann", "wrong").status_code, 400)
        self.assertEqual(self.attempt("bob", "right-pass-2").status_code, 200)

    def test_one_address_trying_many_usernames_is_locked(self):
        for i in range(throttle.MAX_PER_IP):
            self.attempt(f"nobody{i}", "wrong")
        self.assertEqual(self.attempt("bob", "right-pass-2").status_code, 429)

    def test_forwarded_for_cannot_dodge_the_limit(self):
        for _ in range(throttle.MAX_PER_ACCOUNT):
            post(self.client, LOGIN, {"username": "ann", "password": "wrong"}, headers={"X-Forwarded-For": "9.9.9.9"})
        r = post(self.client, LOGIN, {"username": "ann", "password": "wrong"}, headers={"X-Forwarded-For": "8.8.8.8"})
        self.assertEqual(r.status_code, 429)

    def test_a_forged_cross_site_sign_in_is_refused(self):
        strict = Client(enforce_csrf_checks=True)
        r = strict.post(LOGIN, {"username": "ann", "password": "right-pass-1"}, content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("_auth_user_id", strict.session)


class PagesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ann", password="pass1234")

    def test_pages_are_the_react_shell_and_the_login_page_leaks_no_credential(self):
        r = self.client.get("/login/")
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "uiapi/shell.html")
        self.assertNotIn("testpass123", r.content.decode())
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/login/").status_code, 302)  # already in: sent on

    def test_company_setup_page_needs_login_and_no_company(self):
        self.assertEqual(Client().get("/company/setup/").status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/company/setup/").status_code, 200)
        Membership.objects.create(user=self.user, company=Company.objects.create(name="A", slug="a"), role="owner")
        self.assertEqual(self.client.get("/company/setup/").status_code, 302)

    def test_legacy_pieces_are_gone(self):
        for name in ("login.html", "company_setup.html", "team_list.html", "profile.html", "oauth_authorize.html"):
            with self.assertRaises(TemplateDoesNotExist, msg=name):
                get_template(f"accounts/{name}")
        for name in ("team_invite", "team_edit", "team_remove"):
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(f"accounts:{name}", args=[1] if name != "team_invite" else [])


class CompanySetupApiTest(TestCase):
    def test_creates_the_company_with_the_person_as_owner(self):
        user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        r = post(self.client, "/ui-api/v1/auth/company/", {"name": "Test Corp"})
        self.assertEqual((r.status_code, r.json()["redirect"]), (201, "/dashboards/"))
        m = Membership.objects.get(user=user)
        self.assertEqual((m.role, m.company.slug), ("owner", "test-corp"))
        self.assertEqual(self.client.session[settings.ACTIVE_COMPANY_SESSION_KEY], m.company_id)
        self.assertEqual(ActivityLog.objects.get(event_type="company_created").actor, user)
        self.assertEqual(post(self.client, "/ui-api/v1/auth/company/", {"name": "Second"}).status_code, 400)  # already has one

    def test_validation_and_login_required(self):
        self.assertIn(post(self.client, "/ui-api/v1/auth/company/", {"name": "x"}).status_code, (401, 403))
        User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.assertIn("name", post(self.client, "/ui-api/v1/auth/company/", {"name": ""}).json()["errors"])
        Company.objects.create(name="Taken", slug="taken")
        self.assertEqual(post(self.client, "/ui-api/v1/auth/company/", {"name": "Taken"}).status_code, 400)


class OAuthApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ann", password="pass1234")
        self.url = "/ui-api/v1/auth/oauth/authorize/"
        self.body = {"username": "ann", "password": "pass1234", "client_id": "serop", "redirect_uri": "http://127.0.0.1:5173/cb", "state": "xyz"}

    def test_a_code_goes_back_to_the_loopback_address(self):
        r = post(self.client, self.url, self.body)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["redirect"].startswith("http://127.0.0.1:5173/cb?code="))
        self.assertIn("state=xyz", r.json()["redirect"])
        self.assertEqual(ExternalAuthCode.objects.count(), 1)

    def test_only_loopback_redirects_and_real_credentials(self):
        for uri in ("https://evil.example/cb", "http://evil.example/cb", "http://127.0.0.1.evil.example/cb", ""):
            self.assertEqual(post(self.client, self.url, {**self.body, "redirect_uri": uri}).status_code, 400, uri)
        r = post(self.client, self.url, {**self.body, "password": "nope"})
        self.assertEqual((r.status_code, r.json()["detail"]), (400, "Invalid credentials."))
        self.assertFalse(ExternalAuthCode.objects.exists())

    def test_the_page_sends_a_signed_in_person_straight_back_and_an_anonymous_one_to_the_shell(self):
        page = "/oauth/authorize/?client_id=serop&redirect_uri=http://127.0.0.1:5173/cb&state=s"
        r = self.client.get(page)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "uiapi/shell.html")
        self.assertEqual(self.client.get("/oauth/authorize/?redirect_uri=https://evil.example/cb").status_code, 400)
        self.client.force_login(self.user)
        r = self.client.get(page)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.startswith("http://127.0.0.1:5173/cb?code="))


class TeamApiBase(TestCase):
    def setUp(self):
        self.a = Company.objects.create(name="A", slug="a")
        self.b = Company.objects.create(name="B", slug="b")
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.admin = User.objects.create_user("admin", "admin@test.com", "pass1234")
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        self.bob = User.objects.create_user("bob", "bob@test.com", "pass1234")
        self.m_owner = Membership.objects.create(user=self.owner, company=self.a, role="owner")
        self.m_admin = Membership.objects.create(user=self.admin, company=self.a, role="admin")
        self.m_dev = Membership.objects.create(user=self.dev, company=self.a, role="developer")
        self.m_bob = Membership.objects.create(user=self.bob, company=self.b, role="owner")

    def login(self, name, company=None):
        self.client.login(username=name, password="pass1234")
        s = self.client.session
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = (company or self.a).pk
        s.save()

    def new_member(self, **over):
        return {"username": "newbie", "email": "newbie@test.com", "first_name": "New", "last_name": "Bie", "password": "pass1234", "role": "developer", **over}

    def edit_body(self, **over):
        return {"first_name": "Dev", "last_name": "Team", "email": "dev@test.com", "discord_id": "", "role": "developer", **over}


class TeamListApiTest(TeamApiBase):
    def test_a_company_only_sees_its_own_people(self):
        self.login("owner")
        d = self.client.get("/ui-api/v1/team/").json()
        self.assertEqual(sorted(i["user"]["username"] for i in d["items"]), ["admin", "dev", "owner"])
        self.assertEqual(d["counts"], {"total": 3, "owner_admin": 2, "developer": 1, "support_viewer": 0})
        self.login("bob", self.b)
        self.assertEqual([i["user"]["username"] for i in self.client.get("/ui-api/v1/team/").json()["items"]], ["bob"])

    def test_search_role_sort_and_rights_flags(self):
        self.login("admin")
        get = lambda p: [i["user"]["username"] for i in self.client.get("/ui-api/v1/team/", p).json()["items"]]
        self.assertEqual(get({"role": "developer"}), ["dev"])
        self.assertEqual(get({"q": "OWN"}), ["owner"])
        self.assertEqual(get({"sort": "name"}), ["admin", "dev", "owner"])
        items = {i["user"]["username"]: i for i in self.client.get("/ui-api/v1/team/").json()["items"]}
        self.assertEqual((items["owner"]["can_edit"], items["owner"]["can_remove"]), (False, False))
        self.assertEqual((items["dev"]["can_edit"], items["dev"]["can_remove"]), (True, True))
        self.assertEqual((items["admin"]["can_edit"], items["admin"]["can_remove"], items["admin"]["is_you"]), (True, False, True))
        self.login("dev")
        self.assertFalse(self.client.get("/ui-api/v1/team/").json()["can_manage"])
        self.assertFalse(self.client.get("/ui-api/v1/team/").json()["items"][0]["can_edit"])


class TeamWriteApiTest(TeamApiBase):
    def test_developers_cannot_add_edit_or_remove(self):
        self.login("dev")
        self.assertEqual(post(self.client, "/ui-api/v1/team/", self.new_member()).status_code, 403)
        self.assertEqual(self.client.patch(f"/ui-api/v1/team/{self.m_dev.pk}/", self.edit_body(role="admin"), content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(f"/ui-api/v1/team/{self.m_admin.pk}/").status_code, 403)
        self.m_dev.refresh_from_db()
        self.assertEqual(self.m_dev.role, "developer")
        self.assertTrue(Membership.objects.filter(pk=self.m_admin.pk).exists())

    def test_admin_adds_a_member_and_it_is_logged(self):
        self.login("admin")
        r = post(self.client, "/ui-api/v1/team/", self.new_member())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["message"], "newbie added as Developer.")
        self.assertTrue(Membership.objects.filter(user__username="newbie", company=self.a, role="developer").exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="member_joined").exists())
        for over, field in (({"username": "owner", "email": "x@y.z"}, "username"), ({"username": "n2", "email": "owner@test.com"}, "email"),
                            ({"username": "n3", "email": "n3@t.io", "role": "owner"}, "role"), ({"username": "n4", "email": "n4@t.io", "password": ""}, "password")):
            r = post(self.client, "/ui-api/v1/team/", self.new_member(**over))
            self.assertEqual(r.status_code, 400, over)
            self.assertIn(field, r.json()["errors"], over)

    def test_edit_updates_discord_id_and_can_clear_it_and_logs_role_changes(self):
        self.login("owner")
        url = f"/ui-api/v1/team/{self.m_dev.pk}/"
        patch = lambda **o: self.client.patch(url, self.edit_body(**o), content_type="application/json")
        self.assertEqual(patch(discord_id="987654321098765432").status_code, 200)
        self.dev.refresh_from_db()
        self.assertEqual(self.dev.discord_id, "987654321098765432")
        self.assertEqual(patch(discord_id="").status_code, 200)
        self.dev.refresh_from_db()
        self.assertEqual(self.dev.discord_id, "")
        r = patch(role="admin", is_leave_approver=True)
        self.assertEqual(r.json()["member"]["role"], "admin")
        self.assertTrue(r.json()["member"]["is_leave_approver"])
        row = ActivityLog.objects.get(event_type="member_role_changed")
        self.assertEqual((row.metadata["from"], row.metadata["to"]), ("developer", "admin"))
        self.assertEqual(patch(email="owner@test.com").status_code, 400)

    def test_an_admin_can_flag_a_leave_approver_and_unflag_one(self):
        self.login("owner")
        url = f"/ui-api/v1/team/{self.m_dev.pk}/"
        patch = lambda **o: self.client.patch(url, self.edit_body(**o), content_type="application/json")
        patch(is_leave_approver=True)
        self.m_dev.refresh_from_db()
        self.assertTrue(self.m_dev.is_leave_approver)
        patch()  # the box left unticked
        self.m_dev.refresh_from_db()
        self.assertFalse(self.m_dev.is_leave_approver)

    def test_the_owner_cannot_be_edited_or_removed_and_nobody_removes_themselves(self):
        self.login("admin")
        self.assertEqual(self.client.patch(f"/ui-api/v1/team/{self.m_owner.pk}/", self.edit_body(role="viewer"), content_type="application/json").status_code, 403)
        self.m_owner.refresh_from_db()
        self.assertEqual(self.m_owner.role, "owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/team/{self.m_owner.pk}/").status_code, 400)
        self.assertEqual(self.client.delete(f"/ui-api/v1/team/{self.m_admin.pk}/").status_code, 400)
        self.assertEqual(Membership.objects.filter(company=self.a).count(), 3)

    def test_remove_works_and_is_logged(self):
        self.login("owner")
        r = self.client.delete(f"/ui-api/v1/team/{self.m_dev.pk}/")
        self.assertEqual((r.status_code, r.json()["message"]), (200, "dev removed from team."))
        self.assertFalse(Membership.objects.filter(pk=self.m_dev.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="member_removed").exists())

    def test_other_companies_members_are_404(self):
        self.login("owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/team/{self.m_bob.pk}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/ui-api/v1/team/{self.m_bob.pk}/", self.edit_body(), content_type="application/json").status_code, 404)
        self.assertTrue(Membership.objects.filter(pk=self.m_bob.pk).exists())


class WorkspaceSwitchTest(TestCase):
    def setUp(self):
        self.a, self.b, self.c = (Company.objects.create(name=n, slug=n.lower()) for n in ("Alpha", "Beta", "Gamma"))
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        Membership.objects.create(user=self.user, company=self.a, role="owner")
        Membership.objects.create(user=self.user, company=self.b, role="developer")
        self.client.login(username="alice", password="pass1234")

    def test_switching_persists_and_unrelated_companies_are_rejected(self):
        self.assertIsNone(self.client.session.get("active_company_id"))
        r = post(self.client, "/ui-api/v1/company/switch/", {"company_id": self.b.pk})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.session["active_company_id"], self.b.pk)
        self.assertEqual(self.client.get("/ui-api/v1/team/").json()["items"][0]["user"]["username"], "alice")
        post(self.client, "/ui-api/v1/company/switch/", {"company_id": self.c.pk})
        self.assertEqual(self.client.session["active_company_id"], self.b.pk)  # unchanged

    def test_an_invalid_session_company_falls_back_to_a_real_membership(self):
        s = self.client.session
        s["active_company_id"] = self.c.pk
        s.save()
        d = self.client.get("/ui-api/v1/bootstrap/").json()
        self.assertIn(d["company"]["id"], (self.a.pk, self.b.pk))


class ProfileApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="developer")
        self.client.login(username="alice", password="pass1234")

    def patch(self, **o):
        return self.client.patch("/ui-api/v1/profile/", {"first_name": "Alice", "last_name": "Wonder", "email": "alice@test.com", "discord_id": "", **o}, content_type="application/json")

    def test_get_and_edit_is_audited(self):
        d = self.client.get("/ui-api/v1/profile/").json()
        self.assertEqual((d["user"]["username"], d["company"], d["role"]), ("alice", "Acme", "developer"))
        r = self.patch()
        self.assertEqual((r.status_code, r.json()["message"]), (200, "Profile updated."))
        row = ActivityLog.objects.get(company=self.company, event_type="profile_updated")
        self.assertEqual(row.actor, self.user)
        self.assertIn("first_name", row.description)
        self.assertIn("last_name", row.description)

    def test_an_unchanged_edit_is_not_audited_and_bad_email_is_refused(self):
        self.user.first_name = "Alice"
        self.user.last_name = "Wonder"
        self.user.save()
        self.patch()
        self.assertFalse(ActivityLog.objects.filter(event_type="profile_updated").exists())
        r = self.patch(email="not an email")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json()["errors"])


class ProfileOverviewApiTest(TeamApiBase):
    def test_the_profile_carries_a_membership_date_numbers_and_recent_activity(self):
        self.login("dev")
        d = self.client.get("/ui-api/v1/profile/").json()
        self.assertEqual(sorted(d["stats"]), ["days_present", "dsr_week", "open_tickets", "products", "resolved_30d"])
        self.assertIsNotNone(d["joined"])
        self.assertIsInstance(d["recent"], list)
        self.assertEqual(d["user"]["username"], "dev")


class KudosTest(TeamApiBase):
    def _in(self, day, hour, minute=0):
        from django.utils import timezone

        from apps.attendance.models import AttendanceRecord

        at = timezone.make_aware(timezone.datetime(day.year, day.month, day.day, hour, minute), timezone.get_current_timezone())
        return AttendanceRecord.objects.create(company=self.a, user=self.dev, date=day, check_in=at)

    def test_streak_counts_on_time_weekdays_and_a_late_day_breaks_it(self):
        from datetime import date, timedelta

        from apps.attendance.service import shift_for
        from apps.uiapi import kudos

        shift = shift_for(self.a)
        today = date(2026, 10, 14)  # a Wednesday
        h, m = shift.start_time.hour, shift.start_time.minute
        self._in(today, h, m)
        self._in(today - timedelta(days=1), h, m)
        self._in(today - timedelta(days=2), h + 3)  # late
        self._in(today - timedelta(days=3), h, m)
        self.assertEqual(kudos.on_time_streak(self.a, self.dev, today), 2)

    def test_a_weekend_does_not_break_the_streak_and_today_without_a_punch_is_skipped(self):
        from datetime import date

        from apps.attendance.service import shift_for
        from apps.uiapi import kudos

        shift = shift_for(self.a)
        h, m = shift.start_time.hour, shift.start_time.minute
        self._in(date(2026, 10, 9), h, m)  # Friday
        self._in(date(2026, 10, 12), h, m)  # Monday
        self.assertEqual(kudos.on_time_streak(self.a, self.dev, date(2026, 10, 13)), 2)

    def test_a_work_anniversary_this_week_is_a_milestone(self):
        from datetime import date

        from django.utils import timezone

        from apps.uiapi import kudos

        m = self.m_dev
        Membership.objects.filter(pk=m.pk).update(created_at=timezone.make_aware(timezone.datetime(2024, 10, 12, 10), timezone.get_current_timezone()))
        out = kudos.milestones(self.a, self.dev, date(2026, 10, 14))
        self.assertTrue(any("2 years" in s for s in out))
        self.assertEqual(kudos.milestones(self.a, self.dev, date(2026, 12, 1)), [])

    def test_profile_and_home_carry_both(self):
        self.login("dev")
        d = self.client.get("/ui-api/v1/profile/").json()
        self.assertIn("streak", d)
        self.assertIsInstance(d["milestones"], list)
        h = self.client.get("/ui-api/v1/dashboard/").json()
        self.assertIn("streak", h)
