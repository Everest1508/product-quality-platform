from django.http import HttpResponseForbidden
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.leave.actions import is_approver
from apps.uiapi.shell import render_shell


class LeaveShellView(CompanyMemberRequiredMixin, View):
    """My leave, apply and the calendar: any member, served by the React shell."""

    def get(self, request):
        return render_shell(request)


class LeaveApproverShellView(CompanyMemberRequiredMixin, View):
    """The approvals queue. 403 for a plain member, as before; the API enforces it too."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.company and not is_approver(request.user, request.company):
            return HttpResponseForbidden("Only leave approvers can do this.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render_shell(request)


class LeavePolicyShellView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        return render_shell(request)
