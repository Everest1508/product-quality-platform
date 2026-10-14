"""Serve the vendored befui HTML build (custom elements: <bef-button>, <bef-dialog>, ...).

The files live in apps/core/vendor/befui/ (copied from https://befui.vercel.app/html/, MIT).
There is no static pipeline, so they are served here: only the names in FILES resolve,
gzipped once in memory, with an ETag so a reload costs a 304.
"""

import gzip
import hashlib
from functools import lru_cache

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotModified

DIR = settings.BASE_DIR / "apps" / "core" / "vendor" / "befui"
FILES = {"befui.css": "text/css; charset=utf-8", "befui.js": "text/javascript; charset=utf-8"}


@lru_cache(maxsize=None)
def _load(name):
    raw = (DIR / name).read_bytes()
    return raw, gzip.compress(raw, 6), '"' + hashlib.sha1(raw).hexdigest()[:20] + '"'


def asset(request, name):
    if name not in FILES:
        raise Http404
    raw, packed, etag = _load(name)
    if request.headers.get("If-None-Match") == etag:
        return HttpResponseNotModified()
    wants_gzip = "gzip" in request.headers.get("Accept-Encoding", "")
    response = HttpResponse(packed if wants_gzip else raw, content_type=FILES[name])
    if wants_gzip:
        response["Content-Encoding"] = "gzip"
    response["Vary"] = "Accept-Encoding"
    response["ETag"] = etag
    response["Cache-Control"] = "public, max-age=3600"
    return response
