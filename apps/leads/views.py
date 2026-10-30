import json

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import User
from apps.core.mixins import CompanyAdminRequiredMixin
from apps.core.pagination import paginate
from apps.leads.forms import LeadForm
from apps.leads import service
from apps.leads.models import Lead, LeadWebhook, new_token
from apps.notifications.models import Notification
from apps.notifications.service import mark_read, notify_many


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
        lead = Lead.objects.create(
            company=hook.company, full_name=d["full_name"], email=d["email"], phone=d["phone"],
            company_name=d["company"], need=d["need"], details=d["details"],
        )
        admins = User.objects.filter(
            memberships__company=hook.company, memberships__role__in=("owner", "admin")
        )
        notify_many(
            admins, company=hook.company, kind=Notification.Kind.LEAD,
            title=f"New website lead: {lead.full_name}",
            body=lead.company_name or lead.need or lead.email, url="/leads/",
        )
        return JsonResponse({"ok": True}, status=201)


class LeadListView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        hook, _ = LeadWebhook.objects.get_or_create(company=request.company)
        leads = Lead.objects.filter(company=request.company)
        page = paginate(request, leads)
        # Looking at the list clears this person's "new lead" bell items and sidebar count.
        ids = Notification.objects.filter(
            user=request.user, company=request.company, kind=Notification.Kind.LEAD
        ).values_list("pk", flat=True)
        mark_read(request.user, request.company, ids=list(ids))
        return render(request, "leads/lead_list.html", {
            "page": page,
            "webhook_url": request.build_absolute_uri(f"/api/v1/leads/{hook.token}/"),
        })


class LeadWebhookRotateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        LeadWebhook.objects.update_or_create(company=request.company, defaults={"token": new_token()})
        messages.success(request, "New webhook URL created. The old one no longer works.")
        return redirect("leads:lead_list")


class LeadDetailView(CompanyAdminRequiredMixin, View):
    """One lead: who they are, what was done on it, and the button that turns it into a project."""

    def get(self, request, pk):
        lead = get_object_or_404(Lead.objects.select_related("product"), pk=pk, company=request.company)
        return render(request, "leads/lead_detail.html", {
            "lead": lead,
            "logs": lead.logs.select_related("author"),
            "statuses": [(v, t) for v, t in Lead.Status.choices if v != Lead.Status.CONVERTED],
        })


class LeadLogView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, company=request.company)
        text = request.POST.get("text", "").strip()[:2000]
        if text:
            service.add_log(lead, request.user, text)
            messages.success(request, "Added to the log.")
        else:
            messages.error(request, "Write what you did first.")
        return redirect("leads:lead_detail", pk=lead.pk)


class LeadStatusView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, company=request.company)
        status = request.POST.get("status", "")
        if lead.product_id:
            messages.error(request, "This lead is already a project.")
        elif status == Lead.Status.CONVERTED:
            return LeadConvertView.convert(request, lead)
        elif status in Lead.Status.values:
            service.set_status(lead, status, request.user)
            messages.success(request, f"Marked {lead.get_status_display().lower()}.")
        return redirect("leads:lead_detail", pk=lead.pk)


class LeadConvertView(CompanyAdminRequiredMixin, View):
    @staticmethod
    def convert(request, lead):
        product = service.convert(lead, request.user)
        messages.success(request, f"Created the project {product.name}.")
        return redirect("leads:lead_detail", pk=lead.pk)

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, company=request.company)
        if lead.product_id:
            messages.error(request, "This lead is already a project.")
            return redirect("leads:lead_detail", pk=lead.pk)
        return self.convert(request, lead)
