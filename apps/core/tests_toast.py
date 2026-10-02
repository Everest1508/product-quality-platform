"""The toast queue has to survive the trip from a view to the DOM.

79 call sites across the app call `messages.success`/`error` and every one of
them rendered nothing. Two independent bugs, both in `core/base.html`:

  * the seed ran on `alpine:init`, which Alpine dispatches *before* it walks the
    DOM, so the container's state did not exist yet and the `if (container.__x)`
    guard silently did nothing;
  * it then reached into `container.__x.$data`, and `.$data` is a magic string
    that only Alpine's own evaluator understands -- in plain JavaScript it is
    `undefined.messages`, so even a reachable container would have thrown.

The seed is now a JSON payload the container's `x-init` parses, which is the
only place the messages can be handed to Alpine without one of those two traps.
"""

import json

from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.accounts.models import Company, Membership, User


class ToastPayloadTagTest(TestCase):
    """The payload must be valid JSON *and* safe inside a <script> block."""

    def render(self, level, text):
        request = RequestFactory().get("/")
        request.session = self.client.session
        storage = FallbackStorage(request)
        storage.add(level, text)
        request._messages = storage

        from apps.core.templatetags.toast_tags import toast_payload

        return str(toast_payload(storage, "toast-seed"))

    def test_emits_a_script_tag_with_the_element_id(self):
        html = self.render(message_constants.INFO, "Saved.")
        self.assertIn('id="toast-seed"', html)
        self.assertIn('type="application/json"', html)

    def test_payload_is_parseable_json(self):
        html = self.render(message_constants.SUCCESS, "Leave approved.")
        body = html.split(">", 1)[1].rsplit("<", 1)[0]
        self.assertEqual(
            json.loads(body), [{"text": "Leave approved.", "tags": "success"}]
        )

    def test_keeps_the_level_as_a_css_class(self):
        for level, expected in (
            (message_constants.SUCCESS, "success"),
            (message_constants.ERROR, "error"),
            (message_constants.WARNING, "warning"),
            (message_constants.INFO, "info"),
        ):
            html = self.render(level, "x")
            self.assertIn(f'"tags": "{expected}"', html)

    def test_closes_no_script_tag_from_user_text(self):
        """`</script>` in a message must not be able to end the block early."""
        html = self.render(message_constants.ERROR, "</script><script>alert(1)")
        body = html.split(">", 1)[1].rsplit("<", 1)[0]
        self.assertNotIn("</script", body)
        self.assertEqual(
            json.loads(body)[0]["text"], "</script><script>alert(1)"
        )

    def test_quotes_in_a_message_survive(self):
        html = self.render(message_constants.INFO, 'He said "no" & left')
        body = html.split(">", 1)[1].rsplit("<", 1)[0]
        self.assertEqual(json.loads(body)[0]["text"], 'He said "no" & left')


class ToastSeedIsWiredTest(TestCase):
    """The seed and the container have to be on the page, in that order."""

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.client.login(username="alice", password="pass1234")

    def get_html(self, path):
        return self.client.get(path).content.decode()

    def add_policy(self):
        """POST a policy, then read the page the redirect points at.

        Deliberately not `follow=True`: the test client would consume the queued
        message rendering the redirect, and the page fetched afterwards would
        carry an empty queue -- which is exactly what makes a toast test pass
        for the wrong reason.
        """
        response = self.client.post(
            "/leave/policies/add/",
            {
                "name": "Casual",
                "max_days_per_year": "12",
                "max_consecutive_days": "3",
                "is_paid": "on",
                "color": "green",
            },
        )
        self.assertEqual(response.status_code, 302)
        return self.get_html(response.url)

    def test_a_message_reaches_the_page(self):
        html = self.add_policy()
        self.assertIn('id="toast-seed"', html)
        self.assertIn("Casual leave type added.", html)

    def test_no_seed_tag_when_there_is_nothing_to_say(self):
        """An empty queue must not ship an empty script block."""
        html = self.get_html("/leave/")
        self.assertNotIn('id="toast-seed"', html)

    def test_the_seed_precedes_the_container_that_reads_it(self):
        html = self.add_policy()
        self.assertLess(
            html.index('id="toast-seed"'),
            html.index('id="toast-container"'),
        )

    def test_the_container_parses_the_seed_rather_than_reading_alpine_internals(self):
        """The regression itself: no `__x`, no `.$data`, and nothing toast-related
        on `alpine:init`.

        That hook fires before Alpine walks the DOM, so it is the wrong place to
        read the seed — but it is the *documented* place to register an Alpine
        component, which is why the ban is scoped to the toast rather than to the
        token. Any `alpine:init` handler that mentions the toast is the bug.
        """
        html = self.get_html("/leave/")
        self.assertNotIn("__x", html)
        self.assertNotIn(".$data", html)
        for hook in ("alpine:init",):
            start = 0
            while (at := html.find(hook, start)) != -1:
                window = html[max(0, at - 400):at + 400].lower()
                self.assertNotIn(
                    "toast", window,
                    msg="an alpine:init handler is touching the toast queue",
                )
                start = at + len(hook)
        self.assertIn("JSON.parse(seed.textContent)", html)
