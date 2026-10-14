"""Serve the built React files (frontend/dist: app.js, app.css and one page-<hash>.js per page) at /ui/<name>.

Same approach as brand.py: no static pipeline, so a view serves the named files. `name` is a single path segment and
must be a real file directly inside the dist folder.

Fast to load without a CDN in front:
* `app.js` and `app.css` are not content-hashed, so they are sent with `no-cache` and an ETag. The browser asks "has it
  changed?" and gets a tiny 304 instead of the whole file again; a new build shows up without a hard refresh.
* The `page-<hash>.js` files are named by their content, so they are cached for a year.
* Text files are sent gzipped to browsers that accept it (about a quarter of the size). Each file is compressed once per
  build and kept in memory.
"""

import gzip
import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotModified

_GZIP_TYPES = ("text/", "application/javascript", "application/json", "image/svg+xml")
_HASHED = re.compile(r"^page-[A-Za-z0-9_-]+\.js$")
_gzipped = {}  # (path, mtime_ns, size) -> compressed bytes


def _compressed(path, key):
    if key not in _gzipped:
        _gzipped.clear()  # only the current build is worth keeping
        _gzipped[key] = gzip.compress(path.read_bytes(), compresslevel=6, mtime=0)
    return _gzipped[key]


def ui_file(request, name):
    root = Path(settings.FRONTEND_DIST)
    path = root / name
    if path.parent != root or not path.is_file():
        raise Http404
    stat = path.stat()
    kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
    gz = "gzip" in request.headers.get("Accept-Encoding", "") and kind.startswith(_GZIP_TYPES)
    etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}{"-gz" if gz else ""}"'
    cache = "public, max-age=31536000, immutable" if _HASHED.match(name) else "no-cache"

    if etag in request.headers.get("If-None-Match", ""):
        response = HttpResponseNotModified()
    elif gz:
        response = HttpResponse(_compressed(path, (str(path), stat.st_mtime_ns, stat.st_size)), content_type=kind)
        response["Content-Encoding"] = "gzip"
    else:
        response = FileResponse(open(path, "rb"), content_type=kind)
    response["ETag"] = etag
    response["Cache-Control"] = cache
    response["Vary"] = "Accept-Encoding"
    return response
