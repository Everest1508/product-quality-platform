from django.contrib.auth.mixins import LoginRequiredMixin as DjangoLoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect


class LoginRequiredMixin(DjangoLoginRequiredMixin):
    login_url = "/login/"


class CompanyMemberRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, HttpResponse) and response.status_code in (301, 302):
            return response
        if not request.company:
            return redirect("accounts:company_setup")
        return response


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
