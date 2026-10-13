from django.conf import settings
from django.shortcuts import render


def render_shell(request):
    """The standalone page that boots the React app. Callers must already have
    checked the visitor (login, company); this only renders."""
    return render(request, "uiapi/shell.html", {
        "frontend_built": (settings.FRONTEND_DIST / "app.js").is_file(),
    })
