"""Serve the built React files (frontend/dist/app.js, app.css) at /ui/<name>.

Same approach as brand.py: no static pipeline, so a view serves the few named
files. `name` is a single path segment and must be a real file directly inside
the dist folder. `no-cache` makes the browser revalidate, so a new build shows
up without a hard refresh (the file is not content-hashed).
"""

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404


def ui_file(request, name):
    root = Path(settings.FRONTEND_DIST)
    path = root / name
    if path.parent != root or not path.is_file():
        raise Http404
    response = FileResponse(open(path, "rb"), content_type=mimetypes.guess_type(name)[0])
    response["Cache-Control"] = "no-cache"
    return response
