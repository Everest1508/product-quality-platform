"""App metadata for the browser: the running version and the changelog.

These are API endpoints rather than template context because the changelog is
only wanted when the user actually opens it -- it is tens of kilobytes and
nobody scrolls past the version number on a page they are working in.

Both require a logged-in session, deliberately. ``/api/v1/changelog/`` is not
public information: this project's changelog carries a ``Security`` section that
names the credential-leak class of bug by name, and serving that to an anonymous
caller would be handing over the attack surface. ``/api/v1/`` also serves the
public ingestion API, which is why these are namespaced under ``core`` rather
than appended to the ingestion routes.
"""

from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.changelog import get_changelog, get_version_info


class _SessionOnlyView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(self.payload())

    def payload(self):  # pragma: no cover - overridden
        raise NotImplementedError


class VersionView(_SessionOnlyView):
    """The running version, for the sidebar footer and for support questions."""

    def payload(self):
        return get_version_info()


class ChangelogView(_SessionOnlyView):
    """``CHANGELOG.md`` parsed into releases, newest first.

    Item HTML is escaped and only the inline bold/code/link markers in the file
    are re-introduced, so this is safe to inject; see ``apps.core.changelog``.
    """

    def payload(self):
        info = get_version_info()
        info["releases"] = get_changelog()
        return info
