import json
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import User
from apps.core.mixins import CompanyAdminRequiredMixin
from apps.core.pagination import paginate
from apps.core.redirects import safe_next
from apps.dashboards.service import log_activity
from apps.leads.forms import LeadForm, NewLeadForm
from apps.leads import service
from apps.leads.models import Lead, LeadLog, LeadWebhook, new_token
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
            company_name=d["company"], need=d["need"], details=d["details"], is_submission=True,
        )
        admins = User.objects.filter(
            memberships__company=hook.company, memberships__role__in=("owner", "admin")
        )
        notify_many(
            admins, company=hook.company, kind=Notification.Kind.LEAD,
            title=f"New website lead: {lead.full_name}",
            body=lead.company_name or lead.need or lead.email, url="/leads/website/",
        )
        return JsonResponse({"ok": True}, status=201)


def _clear_bell(request):
    """Looking at the leads clears this person's "new lead" bell items and sidebar count."""
    ids = Notification.objects.filter(
        user=request.user, company=request.company, kind=Notification.Kind.LEAD
    ).values_list("pk", flat=True)
    mark_read(request.user, request.company, ids=list(ids))


LOGGABLE = [k for k, _ in LeadLog.Kind.choices if k not in ("status", "converted")]


class LeadBoardView(CompanyAdminRequiredMixin, View):
    """The sales pipeline: one column per stage, drag a card to move it."""

    def get(self, request):
        _clear_bell(request)
        leads = Lead.objects.filter(company=request.company, is_submission=False).order_by("-created_at")
        cols = {v: {"key": v, "label": t, "leads": [], "total": None} for v, t in Lead.Status.choices}
        for lead in leads:
            cols[lead.status]["leads"].append(lead)
        for key, field in (("quote_sent", "quoted_amount"), ("won", "won_amount")):
            cols[key]["total"] = sum((getattr(l, field) or 0 for l in cols[key]["leads"]), Decimal(0))
        return render(request, "leads/lead_board.html", {"columns": list(cols.values()), "total": len(leads)})


class LeadCreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = NewLeadForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            lead = Lead.objects.create(company=request.company, **d)
            service.add_log(lead, request.user, "Lead added by hand")
            messages.success(request, f"Added {lead.full_name}.")
        else:
            messages.error(request, "Could not add the lead: " + "; ".join(
                f"{f.replace('_', ' ')}: {e[0]}" for f, e in form.errors.items()))
        return redirect("leads:lead_board")


class LeadListView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        hook, _ = LeadWebhook.objects.get_or_create(company=request.company)
        leads = Lead.objects.filter(company=request.company).order_by("-created_at")
        page = paginate(request, leads)
        _clear_bell(request)
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
            "log_kinds": [(k, l) for k, l in LeadLog.Kind.choices if k in LOGGABLE],
            "statuses": Lead.Status.choices,
        })


class LeadLogView(CompanyAdminRequiredMixin, View):
    """Write down something that happened: a call, an email, a meeting."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, company=request.company, is_submission=False)
        kind = request.POST.get("kind", "")
        if kind not in LOGGABLE:
            kind = LeadLog.Kind.NOTE
        title = request.POST.get("title", "").strip()[:200]
        text = request.POST.get("text", "").strip()[:2000]
        if title or text:
            service.add_log(lead, request.user, text, kind, title=title)
            messages.success(request, "Added to the activity.")
        else:
            messages.error(request, "Write a title or some details first.")
        return redirect("leads:lead_detail", pk=lead.pk)


def _amount(raw):
    """A positive money value that fits the column, or None."""
    try:
        d = Decimal(re.sub(r"[,\s₹]", "", raw or ""))
    except InvalidOperation:
        return None
    return d.quantize(Decimal("0.01")) if d.is_finite() and 0 < d < Decimal(10) ** 10 else None


class LeadStatusView(CompanyAdminRequiredMixin, View):
    """Move a lead to a stage. Quotation sent and Won must come with the amount."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, company=request.company, is_submission=False)
        status = request.POST.get("status", "")
        amount = _amount(request.POST.get("amount"))
        reason = request.POST.get("reason", "").strip()[:1000]
        if status not in Lead.Status.values:
            error = "Unknown stage."
        elif not reason and status != lead.status:
            error = "Say why you are moving this lead."
        elif lead.product_id:
            error = "This lead is already a project."
        elif status in (Lead.Status.QUOTE_SENT, Lead.Status.WON) and status != lead.status and amount is None:
            error = "Enter the amount " + ("quoted." if status == Lead.Status.QUOTE_SENT else "it was won for.")
        else:
            error = None
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            if error:
                return JsonResponse({"error": error}, status=400)
            service.set_status(lead, status, request.user, amount, reason)
            return JsonResponse({"ok": True})
        if error:
            messages.error(request, error)
        else:
            service.set_status(lead, status, request.user, amount, reason)
            messages.success(request, f"Moved to {lead.get_status_display().lower()}.")
        return redirect("leads:lead_detail", pk=lead.pk)


class LeadConvertView(CompanyAdminRequiredMixin, View):
    """Won leads can be turned into a project, once."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, company=request.company, is_submission=False)
        if lead.product_id:
            messages.error(request, "This lead is already a project.")
        elif lead.status != Lead.Status.WON:
            messages.error(request, "Only won leads can become a project.")
        else:
            product = service.convert(lead, request.user)
            messages.success(request, f"Created the project {product.name}.")
        return redirect("leads:lead_detail", pk=lead.pk)


class LeadPromoteView(CompanyAdminRequiredMixin, View):
    """A website form submission becomes a lead in the pipeline, once an admin says so."""

    def post(self, request, pk):
        submission = get_object_or_404(Lead, pk=pk, company=request.company)
        if not submission.is_submission:
            messages.error(request, "This is already a lead.")
            return redirect("leads:lead_detail", pk=submission.pk)
        submission.is_submission = False
        submission.save(update_fields=["is_submission"])
        service.add_log(submission, request.user, "Promoted from a website form submission")
        log_activity(
            request.company, "lead_created", f"Lead created: {submission.full_name}",
            actor=request.user, target_content_type="lead", target_object_id=submission.pk,
        )
        messages.success(request, f"{submission.full_name} is now a lead.")
        back = safe_next(request.POST.get("next"))
        if back:
            return redirect(back)
        return redirect("leads:lead_detail", pk=submission.pk)


class LeadDeleteView(CompanyAdminRequiredMixin, View):
    """Admins can remove a submission or a lead. Its activity goes with it; a project made from it stays."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, company=request.company)
        lead_pk, name = lead.pk, lead.full_name
        lead.delete()
        log_activity(
            request.company, "lead_deleted", f"Lead deleted: {name}",
            actor=request.user, target_content_type="lead", target_object_id=lead_pk,
        )
        messages.success(request, f"Deleted {name}.")
        return redirect("leads:lead_list")
