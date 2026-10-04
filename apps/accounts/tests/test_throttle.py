from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.accounts import throttle

User = get_user_model()


class LoginThrottleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user("ann", password="right-pass-1", email="ann@example.com")
        User.objects.create_user("bob", password="right-pass-2")
        self.url = reverse("accounts:login")

    def attempt(self, username, password):
        return self.client.post(self.url, {"username": username, "password": password})

    def test_five_wrong_passwords_lock_that_account(self):
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.assertEqual(self.attempt("ann", "wrong").status_code, 200)
        locked = self.attempt("ann", "wrong")
        self.assertEqual(locked.status_code, 429)
        self.assertContains(locked, "Too many failed attempts", status_code=429)

    def test_the_right_password_is_refused_while_locked(self):
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.attempt("ann", "wrong")
        response = self.attempt("ann", "right-pass-1")
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_good_sign_in_resets_the_count(self):
        for _ in range(throttle.MAX_PER_ACCOUNT - 1):
            self.attempt("ann", "wrong")
        self.assertEqual(self.attempt("ann", "right-pass-1").status_code, 302)
        self.client.logout()
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.assertEqual(self.attempt("ann", "wrong").status_code, 200)

    def test_locking_one_account_leaves_another_alone(self):
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.attempt("ann", "wrong")
        self.assertEqual(self.attempt("bob", "right-pass-2").status_code, 302)

    def test_one_address_trying_many_usernames_is_locked(self):
        for i in range(throttle.MAX_PER_IP):
            self.attempt(f"nobody{i}", "wrong")
        self.assertEqual(self.attempt("bob", "right-pass-2").status_code, 429)

    def test_forwarded_for_cannot_dodge_the_limit(self):
        for _ in range(throttle.MAX_PER_ACCOUNT):
            self.client.post(self.url, {"username": "ann", "password": "wrong"}, headers={"X-Forwarded-For": "9.9.9.9"})
        response = self.client.post(
            self.url, {"username": "ann", "password": "wrong"}, headers={"X-Forwarded-For": "8.8.8.8"}
        )
        self.assertEqual(response.status_code, 429)
