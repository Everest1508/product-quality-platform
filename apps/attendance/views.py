from django.shortcuts import get_object_or_404
from django.views import View

from apps.attendance.models import AttendanceRecord
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.uiapi.shell import render_shell


class AttendanceShellView(CompanyMemberRequiredMixin, View):
    """My attendance and the correction request form, served by the React shell."""

    def get(self, request):
        return render_shell(request)


class AttendanceAdminShellView(CompanyAdminRequiredMixin, View):
    """Team, timesheet and the correction queue: owners and admins only, as before."""

    def get(self, request, **kwargs):
        return render_shell(request)


class AttendanceEditView(CompanyAdminRequiredMixin, View):
    """404 unless the record is in this company."""

    def get(self, request, pk):
        get_object_or_404(AttendanceRecord, pk=pk, company=request.company)
        return render_shell(request)
