"""The `?next=` rule behind the sign-in page. The page itself and its API are in apps.uiapi.test_accounts."""

from django.test import TestCase

from apps.core.redirects import safe_next


class SafeNextTest(TestCase):
    def test_a_plain_path_is_kept(self):
        self.assertEqual(safe_next("/tickets/"), "/tickets/")

    def test_a_relative_path_is_kept(self):
        self.assertEqual(safe_next("team/"), "team/")

    def test_the_protocol_relative_forms_are_rejected(self):
        for hostile in ("//evil.example", "/\\evil.example", "///evil.example"):
            self.assertIsNone(safe_next(hostile), msg=hostile)

    def test_an_absolute_url_to_another_host_is_rejected(self):
        self.assertIsNone(safe_next("http://evil.example/x"))

    def test_its_own_host_is_still_not_trusted(self):
        """This app has no ALLOWED_HOSTS guarantee at this layer; be strict."""
        self.assertIsNone(safe_next("http://testserver/tickets/"))

    def test_empty_and_missing_values_are_none(self):
        for empty in (None, "", "   "):
            self.assertIsNone(safe_next(empty))
