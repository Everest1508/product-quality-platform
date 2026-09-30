"""Tests for the version footer and the changelog API behind it."""

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Company, Membership
from apps.core import changelog as changelog_module
from apps.core.changelog import parse_changelog

SAMPLE = """\
# Changelog

All notable changes.

## [2.1.0] - 2026-10-02 - second release

### Fixed

- A **bold** thing with `code` and a [link](https://example.com/x).
- A second bullet that
  wraps onto a further line.

### Added

- Only one bullet here.

## [2.0.0] - 2026-09-01

### Changed

- The first release body.
"""

UNRELEASED = """\
## [Unreleased] - 2026-10-05 - work in progress

### Added

- Something not shipped yet.
"""


class ChangelogParserTest(TestCase):
    def test_splits_releases_sections_and_items(self):
        releases = parse_changelog(SAMPLE)
        self.assertEqual([r["tag"] for r in releases], ["2.1.0", "2.0.0"])
        self.assertEqual([s["name"] for s in releases[0]["sections"]], ["Fixed", "Added"])
        self.assertEqual(len(releases[0]["sections"][0]["items"]), 2)

    def test_title_and_date_are_captured(self):
        newest = parse_changelog(SAMPLE)[0]
        self.assertEqual(newest["date"], "2026-10-02")
        self.assertEqual(newest["title"], "second release")

    def test_wrapped_bullet_lines_are_joined_not_split(self):
        items = parse_changelog(SAMPLE)[0]["sections"][0]["items"]
        self.assertIn("wraps onto a further line.", items[1])
        self.assertNotIn("and a further line.", items)

    def test_bullet_count_is_preserved(self):
        """A bullet must not swallow the next one, and none may be dropped."""
        self.assertEqual(
            len(parse_changelog(SAMPLE)[0]["sections"][0]["items"]),
            SAMPLE.split("### Fixed")[1].split("### Added")[0].count("\n- "),
        )

    def test_unreleased_is_flagged_and_released_is_not(self):
        released = parse_changelog(SAMPLE)
        self.assertTrue(all(r["released"] for r in released))
        unreleased = parse_changelog(UNRELEASED)
        self.assertEqual(len(unreleased), 1)
        self.assertFalse(unreleased[0]["released"])

    def test_inline_markup_becomes_html(self):
        item = parse_changelog(SAMPLE)[0]["sections"][0]["items"][0]
        self.assertIn("<strong>bold</strong>", item)
        self.assertIn("<code>code</code>", item)
        self.assertIn('href="https://example.com/x"', item)
        self.assertIn('rel="noopener"', item)

    def test_html_in_the_file_is_escaped(self):
        hostile = "## [9.9.9] - 2026-01-01\n\n### Fixed\n\n- <script>alert(1)</script> and <b>x</b>\n"
        item = parse_changelog(hostile)[0]["sections"][0]["items"][0]
        self.assertNotIn("<script>", item)
        self.assertIn("&lt;script&gt;", item)

    def test_javascript_link_is_not_left_clickable(self):
        hostile = "## [9.9.9] - 2026-01-01\n\n### Fixed\n\n- [go](javascript:alert(1))\n"
        item = parse_changelog(hostile)[0]["sections"][0]["items"][0]
        self.assertNotIn("javascript:", item)
        self.assertNotIn("<a ", item)

    def test_code_span_contents_are_not_formatted(self):
        hostile = "## [9.9.9] - 2026-01-01\n\n### Fixed\n\n- `**not bold** <b>x</b>`\n"
        item = parse_changelog(hostile)[0]["sections"][0]["items"][0]
        self.assertIn("<code>**not bold** &lt;b&gt;x&lt;/b&gt;</code>", item)
        self.assertNotIn("<strong>", item)

    def test_empty_sections_are_dropped(self):
        text = "## [9.9.9] - 2026-01-01\n\n### Added\n\n### Fixed\n\n- real\n"
        sections = parse_changelog(text)[0]["sections"]
        self.assertEqual([s["name"] for s in sections], ["Fixed"])

    def test_bullet_before_any_heading_is_kept(self):
        text = "## [9.9.9] - 2026-01-01\n\n- orphan bullet\n"
        sections = parse_changelog(text)[0]["sections"]
        self.assertEqual(sections[0]["items"], ["orphan bullet"])

    def test_text_without_releases_parses_to_nothing(self):
        self.assertEqual(parse_changelog("# Changelog\n\nJust prose.\n"), [])


class ChangelogNestingTest(TestCase):
    """Indented sub-bullets are detail, not more of the same sentence.

    `CHANGELOG.md` writes most of its detail as an indented sub-bullet under a
    bolded lead-in. Flattening those into their parent produced one 2,600-character
    paragraph with literal `-` separators, which is the exact wall the dialog
    exists to avoid.
    """

    NESTED = (
        "## [Unreleased] - 2026-09-30 - a feature\n\n"
        "### Added\n\n"
        "- **One thing.** Short lead-in.\n"
        "  - Detail that matters.\n"
        "  - A second detail.\n"
        "    continued onto another line.\n"
        "- A second top-level item.\n"
    )

    def test_sub_bullets_become_a_nested_list_not_prose(self):
        items = parse_changelog(self.NESTED)[0]["sections"][0]["items"]
        self.assertIn('<ul class="changelog-sub">', items[0])
        self.assertEqual(items[0].count("<li>"), 2)

    def test_a_sub_bullet_does_not_become_its_own_item(self):
        items = parse_changelog(self.NESTED)[0]["sections"][0]["items"]
        self.assertEqual(len(items), 2)

    def test_a_wrapped_sub_bullet_is_joined(self):
        items = parse_changelog(self.NESTED)[0]["sections"][0]["items"]
        self.assertIn("A second detail. continued onto another line.", items[0])

    def test_the_nested_list_is_real_markup_not_escaped_text(self):
        """A second formatting pass escaped the `<ul>` into visible dashes."""
        items = parse_changelog(self.NESTED)[0]["sections"][0]["items"]
        self.assertNotIn("&lt;ul", items[0])
        self.assertIn("<strong>One thing.</strong>", items[0])

    def test_an_orphan_indented_bullet_does_not_become_an_item(self):
        text = "## [Unreleased] - 2026-09-30\n\n### Added\n\n  - dangling indent\n"
        # Nothing is left, so the section is dropped and with it the release.
        self.assertEqual(parse_changelog(text), [])

    def test_the_shipped_changelog_produces_nested_lists(self):
        releases = changelog_module.get_changelog()
        nested = sum(
            item.count('<ul class="changelog-sub">')
            for release in releases
            for section in release["sections"]
            for item in section["items"]
        )
        self.assertGreater(nested, 0, "the shipped file writes sub-bullets; none parsed")

    def test_the_longest_item_is_readable(self):
        """The flattened version of the version/changelog entry was 2,602 chars."""
        releases = changelog_module.get_changelog()
        lead_in = max(
            (item for release in releases for section in release["sections"] for item in section["items"]),
            key=lambda item: len(item),
        )
        self.assertLess(
            len(lead_in.split("</li>")[0]),
            700,
            "an item's own text should be a paragraph, not the whole entry",
        )


class ChangelogPresentationTest(TestCase):
    """The fields the dialog renders from.

    The parser used to hand the dialog raw `###` headings and nothing else, so
    "Added" and "Changed" -- diff vocabulary -- were the only words on screen for
    someone asking what changed in the version they are looking at, and the dialog
    had to count and date-format everything itself. These are pinned here so the
    UI cannot drift from the parser again.
    """

    SAMPLE = (
        "## [Unreleased] - 2026-09-30 - office policy & sidebar\n\n"
        "### Added\n\n- one\n- two\n\n"
        "### Changed\n\n- three\n\n"
        "### Fixed\n\n- four\n\n"
        "### Security\n\n- five\n\n"
        "### Known issues (pre-existing, not addressed here)\n\n- six\n"
    )

    def test_added_and_changed_are_shown_as_plain_english(self):
        sections = parse_changelog(self.SAMPLE)[0]["sections"]
        labels = {s["name"]: s["label"] for s in sections}
        self.assertEqual(labels["Added"], "New")
        self.assertEqual(labels["Changed"], "Improved")
        self.assertEqual(labels["Fixed"], "Fixed")
        self.assertEqual(labels["Security"], "Security")
        # The maintenance heading is long; a user only needs to know there are
        # known issues, not which release introduced them.
        self.assertEqual(
            labels["Known issues (pre-existing, not addressed here)"], "Known issues"
        )

    def test_slugs_are_stable_and_machine_readable(self):
        sections = parse_changelog(self.SAMPLE)[0]["sections"]
        self.assertEqual(
            [s["slug"] for s in sections],
            ["added", "changed", "fixed", "security", "known-issues"],
        )

    def test_an_unrecognised_heading_keeps_its_own_words(self):
        text = "## [Unreleased] - 2026-09-30\n\n### Infrastructure\n\n- x\n"
        section = parse_changelog(text)[0]["sections"][0]
        self.assertEqual(section["label"], "Infrastructure")
        self.assertEqual(section["slug"], "infrastructure")

    def test_counts_match_the_items_shown(self):
        release = parse_changelog(self.SAMPLE)[0]
        for section in release["sections"]:
            self.assertEqual(section["count"], len(section["items"]))
        self.assertEqual(release["item_count"], 6)

    def test_heading_prefers_the_title_so_same_dated_blocks_are_distinguishable(self):
        release = parse_changelog(self.SAMPLE)[0]
        self.assertEqual(release["heading"], "office policy & sidebar")

    def test_heading_falls_back_when_a_release_has_no_title(self):
        text = "## [Unreleased] - 2026-09-30\n\n### Fixed\n\n- x\n"
        self.assertEqual(parse_changelog(text)[0]["heading"], "General updates")

    def test_two_blocks_with_the_same_tag_and_date_are_told_apart_by_heading(self):
        """Two `[Unreleased] - 2026-09-04` blocks really exist in the file."""
        text = (
            "## [Unreleased] - 2026-09-04 - dashboard & ticket boards\n\n"
            "### Added\n\n- a\n\n"
            "## [Unreleased] - 2026-09-04 - product form & payroll\n\n"
            "### Added\n\n- b\n"
        )
        headings = [r["heading"] for r in parse_changelog(text)]
        self.assertEqual(
            headings, ["dashboard & ticket boards", "product form & payroll"]
        )


class ChangelogFileTest(TestCase):
    def setUp(self):
        changelog_module._cache.clear()

    def tearDown(self):
        changelog_module._cache.clear()

    def test_real_changelog_parses_and_loses_no_bullets(self):
        releases = changelog_module.get_changelog()
        self.assertTrue(releases, "the shipped CHANGELOG.md should parse")
        raw = Path(changelog_module._path()).read_text(encoding="utf-8")
        expected = sum(1 for line in raw.splitlines() if line.startswith("- "))
        parsed = sum(len(s["items"]) for r in releases for s in r["sections"])
        self.assertEqual(parsed, expected)

    def test_missing_file_yields_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.md"
            with override_settings(CHANGELOG_PATH=missing):
                changelog_module._cache.clear()
                self.assertEqual(changelog_module.get_changelog(), [])

    def test_result_is_cached_until_the_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(SAMPLE, encoding="utf-8")
            with override_settings(CHANGELOG_PATH=path):
                changelog_module._cache.clear()
                first = changelog_module.get_changelog()
                self.assertEqual(len(first), 2)
                # Same mtime -> served from cache.
                self.assertIs(changelog_module.get_changelog(), first)
                # A different mtime forces a re-parse.
                path.write_text(UNRELEASED, encoding="utf-8")
                import os

                stat = path.stat()
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
                self.assertEqual(len(changelog_module.get_changelog()), 1)

    def test_version_info_reports_configured_version(self):
        with override_settings(APP_VERSION="9.9.9"):
            self.assertEqual(changelog_module.get_version_info()["version"], "9.9.9")


class VersionApiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.user = get_user_model().objects.create_user(username="owner", password="pass1234")
        Membership.objects.create(user=self.user, company=self.company, role=Membership.Role.OWNER)

    def test_version_requires_a_session(self):
        response = self.client.get("/api/v1/version/")
        self.assertEqual(response.status_code, 403)

    def test_changelog_requires_a_session(self):
        response = self.client.get("/api/v1/changelog/")
        self.assertEqual(response.status_code, 403)

    def test_changelog_is_not_public_even_though_it_names_a_security_finding(self):
        """The changelog describes a leaked-credential bug; keep it off /api/ anon."""
        body = self.client.get("/api/v1/changelog/").content.decode().lower()
        self.assertNotIn("bearer", body)

    def test_version_returns_the_running_version(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/version/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], "1.0.0")
        self.assertIn("latest_release", payload)
        self.assertIn("release_count", payload)

    def test_changelog_returns_releases_newest_first(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/changelog/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], "1.0.0")
        dates = [r["date"] for r in payload["releases"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        for release in payload["releases"]:
            self.assertIn("tag", release)
            self.assertIn("released", release)
            self.assertTrue(release["sections"])

    def test_endpoints_are_json_only_get(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/api/v1/changelog/").status_code, 405)

    def test_api_carries_the_fields_the_dialog_renders_from(self):
        """If this drops a key the dialog goes blank, so pin the contract."""
        self.client.force_login(self.user)
        release = self.client.get("/api/v1/changelog/").json()["releases"][0]
        self.assertIn("item_count", release)
        self.assertIn("heading", release)
        for section in release["sections"]:
            self.assertIn("slug", section)
            self.assertIn("label", section)
            self.assertEqual(section["count"], len(section["items"]))


class VersionFooterUiTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.user = get_user_model().objects.create_user(username="owner", password="pass1234")
        Membership.objects.create(user=self.user, company=self.company, role=Membership.Role.OWNER)

    def test_sidebar_shows_a_clickable_version(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn("data-changelog-open", body)
        self.assertIn('aria-haspopup="dialog"', body)
        self.assertIn("v1.0.0", body)

    def test_version_label_describes_what_the_button_does(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn('aria-label="What\'s new in v1.0.0"', body)

    def test_dialog_is_present_and_reads_from_the_api(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn('id="pq-changelog"', body)
        self.assertIn("/api/v1/changelog/", body)
        self.assertIn('role="dialog"', body)

    def test_dialog_sits_outside_the_clipped_sidebar(self):
        """.sidebar is overflow-x:hidden; a dialog inside it would be clipped."""
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertGreater(body.index('id="pq-changelog"'), body.index('class="shell"'))

    def test_trigger_dispatches_the_event_the_dialog_listens_for(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn("[data-changelog-open]", body)
        self.assertIn("pq:changelog", body)

    def test_logged_out_pages_have_no_version_footer(self):
        body = self.client.get("/login/").content.decode()
        self.assertNotIn("data-changelog-open", body)
        self.assertNotIn('id="pq-changelog"', body)

    def test_trigger_is_reachable_by_keyboard(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn("side-version:focus-visible", body)

    def test_dialog_opens_on_this_version_rather_than_the_whole_file(self):
        """`releases.slice(1)` is what keeps 56 bullets off the first screen."""
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn("releases.slice(1)", body)
        self.assertIn("var older = releases.slice(1);", body)

    def test_older_releases_are_a_disclosure_not_a_dead_end(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn("changelog-older", body)
        self.assertIn("aria-expanded", body)
        self.assertIn("aria-controls=\"pq-changelog-older-list\"", body)

    def test_type_filters_are_real_buttons_with_pressed_state(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn('id="pq-changelog-filters"', body)
        self.assertIn('aria-label="Filter changes by type"', body)
        self.assertIn('aria-pressed="', body)

    def test_dates_are_formatted_for_a_reader_not_shown_as_iso_columns(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn("function fmtDate", body)
        self.assertIn("esc(fmtDate(rel.date))", body)

    def test_header_states_how_many_changes_are_in_this_version(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        # The phrase is assembled from a pluralising helper, so assert its parts
        # rather than a string that never appears contiguously.
        self.assertIn("plural(total, 'change', 'changes')", body)
        self.assertIn("' in this version'", body)
        self.assertIn('id="pq-changelog-sub"', body)

    def test_filtering_is_keyboard_and_mouse_driven_from_the_body(self):
        self.client.force_login(self.user)
        body = self.client.get("/tickets/").content.decode()
        self.assertIn("data-filter", body)
        self.assertIn("closest('#pq-changelog-older')", body)

