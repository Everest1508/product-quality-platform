import json

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.core.mixins import CompanyAdminRequiredMixin
from apps.core.pagination import paginate
from apps.leads.forms import LeadForm
from apps.leads.models import Lead, LeadWebhook, new_token


@method_decorator(csrf_exempt, name="dispatch")
class LeadWebhookView(View):
    """Public endpoint the website form posts to. The token is the credential."""

    def post(self, request, token):
        hook = LeadWebhook.objects.filter(token=token).select_related("company").first()
        if not hook:
            raise Http404
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body or b"{}")
            except ValueError:
                data = None
            if not isinstance(data, dict):
                return JsonResponse({"ok": False, "errors": {"body": "Send a JSON object."}}, status=400)
        else:
            data = request.POST
        form = LeadForm(data)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
        d = form.cleaned_data
        Lead.objects.create(
            company=hook.company, full_name=d["full_name"], email=d["email"],
            company_name=d["company"], need=d["need"], details=d["details"],
        )
        return JsonResponse({"ok": True}, status=201)


class LeadListView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        hook, _ = LeadWebhook.objects.get_or_create(company=request.company)
        leads = Lead.objects.filter(company=request.company)
        page = paginate(request, leads)
        return render(request, "leads/lead_list.html", {
            "page": page,
            "webhook_url": request.build_absolute_uri(f"/api/v1/leads/{hook.token}/"),
        })


class LeadWebhookRotateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        LeadWebhook.objects.update_or_create(company=request.company, defaults={"token": new_token()})
        messages.success(request, "New webhook URL created. The old one no longer works.")
        return redirect("leads:lead_list")
