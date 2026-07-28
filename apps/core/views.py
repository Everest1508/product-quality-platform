from django.views.generic import TemplateView

from apps.core.mixins import LoginRequiredMixin


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/home.html"
