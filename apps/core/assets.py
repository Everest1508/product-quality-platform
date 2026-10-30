"""The app stylesheet as one cached file instead of 230 KB pasted into every page.

There is no static pipeline (see `brand.py`), so the CSS files under
templates/core/css/ are joined here and served from /assets/app.<hash>.css.
The hash is of the content, so a changed file gets a new URL and the old one can
be cached for a year. Gzipped once per change, not per request. The files are
re-read only when a file's modified time changes, so editing CSS in development
shows on the next reload.
"""

import gzip
import hashlib

from django.conf import settings
from django.http import HttpResponse

CSS_DIR = settings.BASE_DIR / "templates" / "core" / "css"
LEGACY_FILES = ("_tokens.css", "_app.css", "_components.css", "_pages.css", "_responsive.css")
UI_FILES = ("_ui.css",)
CSS_FILES = LEGACY_FILES + UI_FILES
# The older files go into ONE layer, so they cascade exactly as they did before layers existed.
# (Giving each file its own layer was tried and changed the page: a generic rule in a later file
# started beating a more specific one in an earlier file, which greyed every status dot.) New CSS
# goes in _ui.css, a layer above, so it wins over the old rules without longer selectors.
# Styles outside any layer (a template's own <style>, inline style="") still beat both.
# @view-transition is only valid at the top level, so it cannot live inside a layer.
VIEW_TRANSITION = "@media (prefers-reduced-motion:no-preference){@view-transition{navigation:auto;}}"
_cache = {"stamp": None, "hash": "", "raw": b"", "gz": b""}


def bundle():
    stamp = tuple((CSS_DIR / n).stat().st_mtime_ns for n in CSS_FILES)
    if stamp != _cache["stamp"]:
        read = lambda names: "\n".join((CSS_DIR / n).read_text() for n in names)
        raw = f"@layer legacy, ui;\n@layer legacy {{\n{read(LEGACY_FILES)}\n}}\n@layer ui {{\n{read(UI_FILES)}\n}}\n{VIEW_TRANSITION}\n".encode()
        _cache.update(stamp=stamp, raw=raw, gz=gzip.compress(raw, 9),
                      hash=hashlib.sha1(raw).hexdigest()[:10])
    return _cache


def css_url():
    return f"/assets/app.{bundle()['hash']}.css"


def css(request, version):
    b = bundle()
    wants_gzip = "gzip" in request.headers.get("Accept-Encoding", "")
    resp = HttpResponse(b["gz"] if wants_gzip else b["raw"], content_type="text/css; charset=utf-8")
    if wants_gzip:
        resp["Content-Encoding"] = "gzip"
    resp["Vary"] = "Accept-Encoding"
    # A stale URL (an old tab after a deploy) still gets the current CSS, just not cached for a year.
    resp["Cache-Control"] = "public, max-age=31536000, immutable" if version == b["hash"] else "no-cache"
    return resp
