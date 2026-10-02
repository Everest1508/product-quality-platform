"""Reads ``CHANGELOG.md`` into structured data for the in-app changelog.

The changelog is a hand-written Markdown file, so this is a deliberately small
parser for the subset the file actually uses -- ``##`` releases, ``###``
sections, ``-`` bullets -- rather than a Markdown implementation. Two things
matter more than completeness:

* **Escape before formatting.** Every run of text is HTML-escaped first, and the
  handful of inline markers (``**bold**``, ``` `code` ```, ``[text](url)``) are
  only then turned back into tags. Formatting therefore can never introduce
  markup that came from the file. The one place raw text is emitted is link
  targets, which are restricted to http/https and site-relative paths so a
  ``javascript:`` URL in the changelog cannot become a live link.
* **Cache on mtime.** The parse result is memoised against the file's
  modification time, so every request is a ``stat()`` rather than a re-parse and
  editing the changelog shows up immediately with no restart.
"""

import html
import logging
import re
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# "## [Unreleased] - 2026-09-30 - office policy & sidebar"
# The separator is an em dash with a middot title in this file, but plain
# hyphens are accepted so the file can be reformatted without breaking this.
_RELEASE_RE = re.compile(
    r"^##\s+\[(?P<tag>[^\]]+)\]\s*[—–-]\s*(?P<date>[\d-]+)"
    r"(?:\s*[·–—-]\s*(?P<title>.+?))?\s*$"
)
_SECTION_RE = re.compile(r"^###\s+(?P<name>.+?)\s*$")
_BULLET_RE = re.compile(r"^[-*]\s+(?P<text>.*)$")
# An indented bullet is detail under the bullet above it. `CHANGELOG.md` uses
# one level, and only that level: a deeper indent is folded into the sub-bullet
# rather than becoming a third level a reader has to decode.
_NESTED_BULLET_RE = re.compile(r"^[ \t]+[-*]\s+(?P<text>.*)$")

_SAFE_SCHEME_RE = re.compile(r"^(?:https?:|mailto:)", re.I)
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]*)(?:\s+\"[^\"]*\")?\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")

# The `###` headings are written for whoever maintains the file. These are the
# words shown to a user reading "what changed in this version" -- "New" and
# "Improved" say what happened, where "Added" and "Changed" are diff vocabulary.
# The slug is stable and is what the dialog uses to build its filter buttons, so
# renaming a display label cannot silently break a filter.
_SECTION_DISPLAY = {
    "Added": ("added", "New"),
    "Changed": ("changed", "Improved"),
    "Fixed": ("fixed", "Fixed"),
    "Security": ("security", "Security"),
    "Removed": ("removed", "Removed"),
    "Deprecated": ("deprecated", "Deprecated"),
}
_KNOWN_ISSUES = ("Known issues (pre-existing, not addressed here)", "known-issues", "Known issues")


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _section_identity(name):
    """(slug, label) for a `###` heading."""
    if name in _SECTION_DISPLAY:
        return _SECTION_DISPLAY[name]
    if name == _KNOWN_ISSUES[0]:
        return _KNOWN_ISSUES[1], _KNOWN_ISSUES[2]
    return _slug(name) or "changes", name


def _inline(text):
    """Escape ``text``, then re-introduce the inline markup we allow."""
    out = html.escape(text, quote=False)

    # Code spans first: their contents must not be re-processed for bold or
    # links, which is why the code pass is not simply the last one.
    spans = []

    def stash_code(match):
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    out = _CODE_RE.sub(stash_code, out)

    def link(match):
        label, target = match.group(1), html.unescape(match.group(2))
        # Relative and anchor links are fine; anything with an unexpected scheme
        # is rendered as plain text rather than as a clickable link.
        if not (_SAFE_SCHEME_RE.match(target) or target.startswith(("/", "#", "?"))):
            return label
        return f'<a href="{html.escape(target, quote=True)}" rel="noopener">{label}</a>'

    out = _LINK_RE.sub(link, out)
    out = _BOLD_RE.sub(r"<strong>\1</strong>", out)

    for index, code in enumerate(spans):
        out = out.replace(f"\x00{index}\x00", f"<code>{code}</code>")
    return out


def _flush(bucket, buffer, sub_buffer, subs):
    """Close the item being accumulated, including any nested sub-bullets.

    ``CHANGELOG.md`` writes detail as an indented sub-bullet under a bolded
    lead-in, which is how a person reads well and is the majority of the file.
    Flattening those into the parent produced a single 2,600-character
    paragraph with literal ``-`` separators, so they are rendered as a real
    nested list instead.
    """
    if sub_buffer:
        subs.append(" ".join(sub_buffer))
    if bucket is not None and (buffer or subs):
        item = _inline(" ".join(buffer))
        if subs:
            item += '<ul class="changelog-sub">' + "".join(
                f"<li>{_inline(sub)}</li>" for sub in subs
            ) + "</ul>"
        bucket.append(item)
    buffer.clear()
    sub_buffer.clear()
    subs.clear()


def parse_changelog(text):
    """Return a list of releases, newest first, in document order."""
    releases = []
    release = None
    section = None
    buffer = []
    sub_buffer = []
    subs = []

    for raw in text.splitlines():
        line = raw.rstrip()

        match = _RELEASE_RE.match(line)
        if match:
            _flush(section["items"] if section else None, buffer, sub_buffer, subs)
            release = {
                "tag": match.group("tag"),
                "date": match.group("date"),
                "title": (match.group("title") or "").strip(),
                "released": match.group("tag").strip().lower() != "unreleased",
                "sections": [],
            }
            section = None
            releases.append(release)
            continue

        match = _SECTION_RE.match(line)
        if match and release is not None:
            _flush(section["items"] if section else None, buffer, sub_buffer, subs)
            slug, label = _section_identity(match.group("name"))
            section = {"name": match.group("name"), "label": label, "slug": slug, "items": []}
            release["sections"].append(section)
            continue

        if release is None:
            continue

        nested = _NESTED_BULLET_RE.match(line)
        if nested and (buffer or sub_buffer):
            # An indented bullet is a sub-point of the bullet above it. Only
            # recognised when there is a parent, so a stray indent does not
            # become an orphan.
            if sub_buffer:
                subs.append(" ".join(sub_buffer))
                sub_buffer.clear()
            sub_buffer.append(nested.group("text").strip())
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            if section is None:
                # A bullet before any "###" heading; give it a home rather than
                # dropping it on the floor.
                section = {"name": "Changes", "label": "Changes", "slug": "changes", "items": []}
                release["sections"].append(section)
            # Close the previous bullet first, otherwise every bullet in the
            # section accumulates in one buffer and renders as a single item.
            _flush(section["items"], buffer, sub_buffer, subs)
            buffer.append(bullet.group("text").strip())
            continue

        if not line.strip():
            _flush(section["items"] if section else None, buffer, sub_buffer, subs)
            continue

        if sub_buffer:
            sub_buffer[-1] += " " + line.strip()
        elif buffer:
            # An indented continuation line belongs to the bullet above it.
            buffer[-1] += " " + line.strip()

    _flush(section["items"] if section else None, buffer, sub_buffer, subs)

    # Drop empty sections. The bullets are already escaped and formatted by
    # `_flush` -- formatting them again here would escape the `<strong>` and the
    # nested `<ul>` that the previous pass just introduced.
    for item in releases:
        kept = []
        for candidate in item["sections"]:
            items = [i for i in candidate["items"] if i]
            if items:
                kept.append(
                    {
                        "name": candidate["name"],
                        "label": candidate.get("label", candidate["name"]),
                        "slug": candidate.get("slug", "changes"),
                        "count": len(items),
                        "items": items,
                    }
                )
        item["sections"] = kept
        item["item_count"] = sum(s["count"] for s in kept)
        # Two blocks can share a tag and a date, so the title is what tells a
        # reader which is which. Fall back to something rather than nothing.
        item["heading"] = item["title"] or "General updates"

    return [r for r in releases if r["sections"]]


def _path():
    return Path(getattr(settings, "CHANGELOG_PATH", Path("CHANGELOG.md")))


_cache = {}


def get_changelog():
    """Parsed changelog, memoised against the file's mtime."""
    path = _path()
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return _report_missing(path)
    if _cache.get("path") == str(path) and _cache.get("stamp") == stamp:
        return _cache["releases"]
    try:
        releases = parse_changelog(path.read_text(encoding="utf-8"))
    except OSError:
        return _report_missing(path)
    _cache.pop("missing", None)
    _cache.update(path=str(path), stamp=stamp, releases=releases)
    return releases


def _report_missing(path):
    """Return no releases, but say so once.

    A missing changelog used to be indistinguishable from an empty one: the
    sidebar "What's new" dialog simply opened empty, with no error and nothing
    in the logs, which is how a `*.md` pattern in `.dockerignore` shipped an app
    whose release notes were missing from production without anyone noticing.
    An empty panel is a correct response to a genuinely empty file, so the
    distinction has to come from a log line, not from the return value.

    The miss is cached per path so this is one `stat()` and one line per
    process, not one per page view.
    """
    if _cache.get("missing") != str(path):
        _cache["missing"] = str(path)
        _cache.pop("path", None)
        _cache.pop("stamp", None)
        logger.warning(
            "Changelog not found at %s, so the What's new dialog is empty. If "
            "this is a container build, check .dockerignore: a `*.md` pattern "
            "excludes CHANGELOG.md from the image.",
            path,
        )
    return []


def get_version_info():
    """What the footer shows and ``/api/v1/version/`` returns."""
    version = getattr(settings, "APP_VERSION", "0.0.0")
    releases = get_changelog()
    released = [r for r in releases if r["released"]]
    latest = (released or releases or [{}])[0]
    return {
        "version": version,
        "latest_release": latest.get("tag"),
        "latest_release_date": latest.get("date"),
        "has_unreleased": any(not r["released"] for r in releases),
        "release_count": len(releases),
    }
