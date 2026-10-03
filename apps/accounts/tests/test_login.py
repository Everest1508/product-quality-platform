"""The sign-in page: accessibility, the `?next=` hop, and what it must not leak.

This page is reached precisely when something has already gone wrong for the
visitor, so it is the worst place to be ordinary -- a missing label, a control
that only a mouse can reach, or a success that drops you somewhere unrelated
all land hardest here.
"""

import os
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.html import strip_tags

from apps.accounts.forms import LoginForm
from apps.core.redirects import safe_next

User = get_user_model()


def body(html):
    """The rendered markup with `<style>`/`<script>` removed.

    base.html inlines the entire stylesheet into every page, so `aria-invalid`,
    `<svg` and `h2` all appear there as CSS selectors. Asserting against the
    raw response therefore matches the stylesheet instead of the page and
    passes (or fails) for the wrong reason -- which is exactly what the first
    version of these tests did.
    """
    start = html.find("<body")
    body_html = html[start:] if start != -1 else html
    body_html = re.sub(r"<style\b.*?</style>", "", body_html, flags=re.S)
    body_html = re.sub(r"<script\b.*?</script>", "", body_html, flags=re.S)
    return body_html


class LoginPageMarkupTest(TestCase):
    """The rendered page, asserted on the markup rather than on the template."""

    def setUp(self):
        self.url = reverse("accounts:login")
        self.html = body(self.client.get(self.url).content.decode())

    def test_the_heading_is_an_h1(self):
        """It used to be an <h2> -- the only heading on the page.

        A document whose top heading is level 2 tells a screen reader the real
        title is missing, and breaks the outline it navigates by. Exactly one
        <h1>: a second would give the page two titles.
        """
        self.assertEqual(self.html.count("<h1"), 1)
        self.assertIn("<h1>Sign in</h1>", self.html)
        # An <h2> would be the brand tagline jumping a level. <h3> is fine --
        # base.html's "What's new" dialog owns those.
        self.assertNotIn("<h2", self.html)

    def test_every_field_has_a_label_naming_it(self):
        """Password had a bare <label> with no `for`, naming nothing."""
        form = LoginForm()
        for name in form.fields:
            self.assertIn(
                f'<label class="auth-label" for="{form[name].id_for_label}"',
                self.html,
                msg=f"{name} has no <label for> pointing at it",
            )

    def test_the_password_toggle_is_reachable_by_keyboard(self):
        """It carried tabindex="-1".

        A control that cannot be tabbed to is not merely inconvenient for a
        keyboard user, it is invisible to them -- it is on the page and it does
        not work.
        """
        button = self.html.split('class="pw-toggle"')[1].split(">", 1)[0]
        self.assertNotIn("tabindex", button)

    def test_the_toggle_is_a_button_so_it_cannot_submit_the_form(self):
        self.assertIn('type="button"', self.html)

    def test_the_submit_button_has_a_label_without_javascript(self):
        """`x-cloak` is display:none until Alpine boots.

        Putting it on the default label meant a visitor whose script never
        loaded faced a full-width button with no text at all.
        """
        self.assertNotIn("x-cloak", self.html)
        self.assertIn('<span x-show="!busy">Sign in</span>', self.html)

    def test_fields_advertise_their_autocomplete_role(self):
        """Otherwise browsers offer a sign-up credential on a sign-in form."""
        self.assertIn('autocomplete="username"', self.html)
        self.assertIn('autocomplete="current-password"', self.html)

    def test_the_form_posts_without_javascript(self):
        """The pending state is an enhancement, not the mechanism."""
        self.assertIn('<form method="post"', self.html)
        self.assertIn("csrfmiddlewaretoken", self.html)

    def test_the_shell_is_not_nested_inside_itself(self):
        """base.html already supplies .auth-shell around this block."""
        full = self.client.get(self.url).content.decode()
        self.assertEqual(
            full.count('<div class="auth-shell">'), 1,
            "a second .auth-shell doubles the viewport height and the centring",
        )

    def test_no_template_comment_reaches_the_page(self):
        """Django's {# #} is line-scoped: a multi-line one renders verbatim.

        Three of them did exactly that here, printing developer notes about the
        form into the visitor's browser as ordinary body text.
        """
        self.assertNotIn("{#", self.html)
        self.assertNotIn("{%", self.html)

    def test_the_toggle_glyph_is_sized(self):
        """`render_icon` emits a viewBox and no width/height.

        An SVG with a viewBox but no intrinsic size falls back to the CSS
        default replaced-element size -- 300x150px. `.pw-toggle` is a 30px
        button, so an unsized glyph bursts out of it and covers the field.
        Every consumer of `{% icon %}` therefore needs a CSS size rule.
        """
        css = self.client.get(self.url).content.decode()
        self.assertRegex(
            css,
            r"\.pw-toggle \.ic\{[^}]*\bwidth:",
            msg="no CSS size for the glyph inside .pw-toggle; it renders 300x150",
        )

    def test_every_glyph_comes_from_the_vendored_icon_set(self):
        """No hand-written <svg>; each one is render_icon's `class="ic"`."""
        self.assertNotIn("<svg", self.html.replace('<svg class="ic"', ""))

    def test_every_auth_class_used_is_actually_styled(self):
        """Every `auth-*` class an auth template uses has a rule in base.html.

        The rewrite of the auth CSS dropped `.auth-card`, which
        `accounts/oauth_authorize.html` (the Serop loopback page) still uses.
        Nothing failed: no test rendered that page, so a whole sign-in screen
        came back as unstyled bare text. The class names are the contract
        between the templates and the one stylesheet, so check both directions.
        """
        css = self.client.get(self.url).content.decode()
        templates = ["templates/accounts/login.html",
                     "templates/accounts/oauth_authorize.html"]
        base = os.path.join(settings.BASE_DIR, "templates", "core", "base.html")
        with open(base) as fh:
            stylesheet = fh.read()

        for rel in templates:
            with open(os.path.join(settings.BASE_DIR, rel)) as fh:
                used = set(re.findall(r'class="([^"]*)"', fh.read()))
            for names in used:
                for name in names.split():
                    if not name.startswith("auth-"):
                        continue
                    self.assertRegex(
                        stylesheet,
                        r"\.%s\b" % re.escape(name),
                        msg="%s uses .%s but base.html never styles it" % (rel, name),
                    )

    def test_the_password_label_sits_outside_the_toggle_wrapper(self):
        """`.pw-toggle` is `top:50%` of `.pw-wrap`, so the wrapper must hold
        only the input.

        When the label was moved inside `.pw-wrap`, the wrapper grew to
        label+input and the 30px button centred across both -- landing on the
        label instead of the field, roughly 12px too high.
        """
        self.assertRegex(self.html, r'</label>\s*<div class="pw-wrap">')
        self.assertNotRegex(
            self.html, r'<div class="pw-wrap">\s*<label',
            msg="label is inside .pw-wrap, so .pw-toggle centres across it",
        )

    def test_the_brand_panel_is_hidden_on_narrow_screens(self):
        """Decoration that would push the form below the fold on a phone."""
        self.assertIn(".auth-brand{display:none;}", self.client.get(self.url).content.decode())


class LoginErrorStateTest(TestCase):
    def setUp(self):
        User.objects.create_user("realuser", "real@a.com", "pass1234")
        self.url = reverse("accounts:login")

    def test_a_wrong_password_is_announced_not_just_coloured(self):
        html = self.client.post(
            self.url, {"username": "realuser", "password": "wrong"}
        ).content.decode()
        self.assertIn('role="alert"', html)

    def test_the_message_does_not_reveal_whether_the_account_exists(self):
        """Naming which half was wrong makes the form an account probe."""
        no_such_user = self.client.post(
            self.url, {"username": "ghost", "password": "wrong"}
        ).content.decode()
        existing_user = self.client.post(
            self.url, {"username": "realuser", "password": "wrong"}
        ).content.decode()

        def only_alert_text(markup):
            block = markup.split('role="alert"')[1].split("</div>")[0]
            return strip_tags(block).strip()

        self.assertEqual(only_alert_text(no_such_user), only_alert_text(existing_user))
        self.assertIn("Incorrect username or password", only_alert_text(no_such_user))

    def test_the_username_survives_a_failed_attempt(self):
        """Retyping the email is the most common reason people give up."""
        html = self.client.post(
            self.url, {"username": "realuser", "password": "wrong"}
        ).content.decode()
        self.assertIn('value="realuser"', html)

    def test_an_errored_field_carries_aria_invalid(self):
        """So the announced state cannot disagree with the red border."""
        html = body(self.client.post(
            self.url, {"username": "", "password": ""}
        ).content.decode())
        self.assertIn('aria-invalid="true"', html)
        self.assertIn("aria-describedby", html)

    def test_a_clean_form_does_not_claim_to_be_invalid(self):
        self.assertNotIn('aria-invalid="true"', body(self.client.get(self.url).content.decode()))


class LoginNextTest(TestCase):
    """`?next=` exists because login is reached when access just failed.

    Dropping the destination on success is the worst possible moment to lose
    it, and accepting it unvalidated is how a link on your own domain becomes
    an open redirect.
    """

    def setUp(self):
        self.user = User.objects.create_user("dev", "dev@a.com", "pass1234")
        self.url = reverse("accounts:login")

    def test_a_valid_destination_is_honoured(self):
        response = self.client.post(
            self.url,
            {"username": "dev", "password": "pass1234", "next": "/tickets/"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/tickets/")

    def test_the_destination_survives_the_failed_attempt_that_precedes_success(self):
        html = self.client.post(
            self.url, {"username": "dev", "password": "wrong", "next": "/tickets/"}
        ).content.decode()
        self.assertIn('name="next" value="/tickets/"', html)

    def test_no_destination_still_lands_on_the_dashboard(self):
        response = self.client.post(
            self.url, {"username": "dev", "password": "pass1234"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:dashboard"))

    def test_an_offsite_destination_is_dropped(self):
        """The whole reason safe_next exists."""
        response = self.client.post(
            self.url,
            {
                "username": "dev",
                "password": "pass1234",
                "next": "https://evil.example/steal",
            },
        )
        self.assertEqual(response.url, reverse("accounts:dashboard"))

    def test_a_protocol_relative_destination_is_dropped(self):
        """`//evil.example` looks like a path and is not one."""
        response = self.client.post(
            self.url,
            {"username": "dev", "password": "pass1234", "next": "//evil.example"},
        )
        self.assertEqual(response.url, reverse("accounts:dashboard"))

    def test_an_already_signed_in_visitor_is_sent_on(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:dashboard"))


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


class NoCredentialsOnTheLoginPageTest(TestCase):
    """The page a stranger stares at must not contain a usable credential.

    This replaced a DEBUG-only demo-credentials panel. A login page rendering
    its own password is a bad trade even when it is gated: the gate is one
    settings flip away from being wrong, and the seeded demo accounts are the
    exact ones someone would try against a real deployment. `seed_data` prints
    the logins for whoever is setting the app up; the page does not.
    """

    def setUp(self):
        self.url = reverse("accounts:login")

    def test_no_seeded_password_appears_in_debug(self):
        with self.settings(DEBUG=True):
            html = body(self.client.get(self.url).content.decode())
        self.assertNotIn("testpass123", html)

    def test_no_seeded_password_appears_in_production(self):
        with self.settings(DEBUG=False):
            html = body(self.client.get(self.url).content.decode())
        self.assertNotIn("testpass123", html)

    def test_the_demo_setting_is_gone_rather_than_left_disabled(self):
        """Deleting the feature beats shipping it switched off and unexplained."""
        from django.conf import settings

        self.assertFalse(hasattr(settings, "DEMO_LOGIN_HINT"))
        self.assertNotIn(b"demo_users", self.client.get(self.url).content)