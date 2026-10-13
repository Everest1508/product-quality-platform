from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.payroll.models import Payslip, PayrollRun
from apps.uiapi.shell import render_shell


class PayrollAdminShellView(CompanyAdminRequiredMixin, View):
    """Runs, preview, salaries and holidays: owners and admins only, served by the React shell."""

    def get(self, request):
        return render_shell(request)


class PayrollRunShellView(CompanyAdminRequiredMixin, View):
    """404 outside the company, as before."""

    def get(self, request, pk):
        get_object_or_404(PayrollRun, pk=pk, company=request.company)
        return render_shell(request)


class PayslipShellView(CompanyAdminRequiredMixin, View):
    def get(self, request, pk):
        get_object_or_404(Payslip, pk=pk, company=request.company)
        return render_shell(request)


class MyPayslipsShellView(CompanyMemberRequiredMixin, View):
    """Every member's own pay; the API pins the query to the signed-in person."""

    def get(self, request):
        return render_shell(request)


class MyPayslipShellView(CompanyMemberRequiredMixin, View):
    """404 (not 403) for anyone else's slip, so the id is not confirmed to exist."""

    def get(self, request, pk):
        get_object_or_404(Payslip, pk=pk, company=request.company, user=request.user)
        return render_shell(request)
