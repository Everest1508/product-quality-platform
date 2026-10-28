from django.contrib.auth.mixins import LoginRequiredMixin as DjangoLoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect


class LoginRequiredMixin(DjangoLoginRequiredMixin):
    login_url = "/login/"


class CompanyMemberRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        # Check before dispatching: super().dispatch() runs the view, which
        # would otherwise execute with request.company = None.
        if request.user.is_authenticated and not request.company:
            return redirect("accounts:company_setup")
        return super().dispatch(request, *args, **kwargs)


class CompanyAdminRequiredMixin(CompanyMemberRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.company_role not in ("owner", "admin"):
            return HttpResponseForbidden("Only company admins can perform this action.")
        return super().dispatch(request, *args, **kwargs)


class HTMXRequiredMixin:
    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return self.htmx_partial_template
        return self.template_name

    @property
    def htmx_partial_template(self):
        raise NotImplementedError(
            "Subclasses must define htmx_partial_template for HTMX requests."
        )
