"""Serve the favicon files from brand/favicon/.

The project has no static pipeline (no whitenoise, no `static/`), and the
Dockerfile runs daphne, which does not serve static files. So the handful of
files a browser asks for by URL are served here. Only names that exist in
brand/favicon/ resolve, so no path from the request reaches the filesystem.
"""

import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404

FAVICON_DIR = settings.BASE_DIR / "brand" / "favicon"


def brand_file(request, name):
    path = FAVICON_DIR / name
    # `name` is a single path segment (the URL converter is `str`), and it must
    # also be a real file directly inside the favicon folder.
    if path.parent != FAVICON_DIR or not path.is_file():
        raise Http404
    response = FileResponse(open(path, "rb"), content_type=mimetypes.guess_type(name)[0])
    response["Cache-Control"] = "public, max-age=86400"
    return response


def favicon_ico(request):
    return brand_file(request, "favicon.ico")
