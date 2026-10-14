"""Serve the vendored befui HTML build (custom elements: <bef-button>, <bef-dialog>, ...).

The files live in apps/core/vendor/befui/ (copied from https://befui.vercel.app/html/, MIT).
`befui.js` is a small ES module that loads `chunks/entry.js`, and each component's code is fetched from
`chunks/` only when a page uses it. There is no static pipeline, so they are served here: only the two
top-level names and real files directly inside `chunks/` resolve, gzipped once in memory, with an ETag
so a reload costs a 304.
"""

import gzip
import hashlib
import re
from functools import lru_cache

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseNotModified

DIR = settings.BASE_DIR / "apps" / "core" / "vendor" / "befui"
FILES = {"befui.css": "text/css; charset=utf-8", "befui.js": "text/javascript; charset=utf-8"}


CHUNK = re.compile(r"^[A-Za-z0-9_.-]+\.js$")


@lru_cache(maxsize=None)
def _load(name):
    raw = (DIR / name).read_bytes()
    return raw, gzip.compress(raw, 6), '"' + hashlib.sha1(raw).hexdigest()[:20] + '"'


def asset(request, name):
    if name in FILES:
        key, ctype = name, FILES[name]
    elif name.startswith("chunks/") and CHUNK.match(name[7:]) and (DIR / name).is_file():
        key, ctype = name, FILES["befui.js"]
    else:
        raise Http404
    raw, packed, etag = _load(key)
    if request.headers.get("If-None-Match") == etag:
        return HttpResponseNotModified()
    wants_gzip = "gzip" in request.headers.get("Accept-Encoding", "")
    response = HttpResponse(packed if wants_gzip else raw, content_type=ctype)
    if wants_gzip:
        response["Content-Encoding"] = "gzip"
    response["Vary"] = "Accept-Encoding"
    response["ETag"] = etag
    response["Cache-Control"] = "public, max-age=3600"
    return response
