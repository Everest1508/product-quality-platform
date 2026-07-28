from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.automation.forms import AutoTicketRuleForm
from apps.automation.models import AutoTicketLog, AutoTicketRule
from apps.core.mixins import CompanyMemberRequiredMixin


RULE_SORT_MAP = {
    "created": "created_at",
    "-created": "-created_at",
    "name": "name",
    "-name": "-name",
    "fired": "-trigger_count",
    "-fired": "trigger_count",
}


class RuleListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = AutoTicketRule.objects.filter(company=request.company).select_related("product", "assign_to")

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        trigger = request.GET.get("trigger")
        if trigger:
            qs = qs.filter(trigger_type=trigger)

        active = request.GET.get("active")
        if active == "1":
            qs = qs.filter(is_active=True)
        elif active == "0":
            qs = qs.filter(is_active=False)

        sort = request.GET.get("sort", "-created")
        order = RULE_SORT_MAP.get(sort, "-created_at")
        qs = qs.order_by(order)

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        recent_logs = AutoTicketLog.objects.filter(company=request.company).select_related("rule", "ticket")[:10]

        if request.headers.get("HX-Request") == "true":
            return render(request, "automation/partials/_rule_list_body.html", {
                "page": page,
            })

        return render(request, "automation/rule_list.html", {
            "page": page,
            "recent_logs": recent_logs,
            "search": search,
            "current_trigger": trigger,
            "current_active": active,
            "current_sort": sort,
        })


class RuleCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        form = AutoTicketRuleForm(company=request.company)
        return render(request, "automation/rule_form.html", {"form": form})

    def post(self, request):
        form = AutoTicketRuleForm(request.POST, company=request.company)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.company = request.company
            rule.save()
            messages.success(request, f"Rule '{rule.name}' created.")
            return redirect("automation:rule_list")
        return render(request, "automation/rule_form.html", {"form": form})


class RuleEditView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        rule = get_object_or_404(AutoTicketRule, pk=pk, company=request.company)
        form = AutoTicketRuleForm(instance=rule, company=request.company)
        return render(request, "automation/rule_form.html", {"form": form, "editing": True, "rule": rule})

    def post(self, request, pk):
        rule = get_object_or_404(AutoTicketRule, pk=pk, company=request.company)
        form = AutoTicketRuleForm(request.POST, instance=rule, company=request.company)
        if form.is_valid():
            form.save()
            messages.success(request, f"Rule '{rule.name}' updated.")
            return redirect("automation:rule_list")
        return render(request, "automation/rule_form.html", {"form": form, "editing": True, "rule": rule})


class RuleDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        rule = get_object_or_404(AutoTicketRule, pk=pk, company=request.company)
        name = rule.name
        rule.delete()
        messages.success(request, f"Rule '{name}' deleted.")
        return redirect("automation:rule_list")


class RuleToggleView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        rule = get_object_or_404(AutoTicketRule, pk=pk, company=request.company)
        rule.is_active = not rule.is_active
        rule.save(update_fields=["is_active"])
        status = "enabled" if rule.is_active else "disabled"
        messages.success(request, f"Rule '{rule.name}' {status}.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "automation/partials/_rule_row.html", {"rule": rule})
        return redirect("automation:rule_list")
