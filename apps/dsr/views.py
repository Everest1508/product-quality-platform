from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.uiapi.shell import render_shell


class DSRSheetView(CompanyMemberRequiredMixin, View):
    """The sheet, served by the React shell (data and writes through /ui-api/v1/dsr/)."""

    def get(self, request):
        return render_shell(request)
