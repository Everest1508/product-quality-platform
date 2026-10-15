from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.expenses import service
from apps.expenses.forms import ExpenseForm, display_name
from apps.expenses.models import Expense


class ExpenseAccessMixin(CompanyMemberRequiredMixin):
    """Company members except viewers. Everyone sees the shared ledger."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request, "company_role", None) == "viewer":
            return HttpResponseForbidden("Expenses are not available to viewers.")
        return super().dispatch(request, *args, **kwargs)

    def is_admin(self):
        return self.request.company_role in ("owner", "admin")

    def can_change(self, expense):
        return self.is_admin() or expense.created_by_id == self.request.user.pk

    def expense_or_404(self, pk):
        try:
            return Expense.objects.select_related("paid_by").prefetch_related("split_with").get(
                pk=pk, company=self.request.company
            )
        except Expense.DoesNotExist:
            raise Http404


def _save(form, company, user, expense=None):
    d = form.cleaned_data
    expense = expense or Expense(company=company, created_by=user)
    expense.title = d["title"].strip()
    expense.amount_paise = int((d["amount"] * 100).to_integral_value())
    expense.date = d["date"]
    expense.category = d["category"]
    expense.note = d["note"].strip()
    expense.paid_by = d["paid_by"]
    expense.save()
    expense.split_with.set(d["split_with"])
    return expense


def _initial(expense):
    return {
        "title": expense.title,
        "amount": Decimal(expense.amount_paise) / 100,
        "paid_by": expense.paid_by_id,
        "date": expense.date,
        "category": expense.category,
        "split_with": [u.pk for u in expense.split_with.all()],
        "note": expense.note,
    }


class ExpenseListView(ExpenseAccessMixin, View):
    def get(self, request, form=None):
        return self.render(request, form or ExpenseForm(company=request.company, user=request.user))

    def post(self, request):
        form = ExpenseForm(request.POST, company=request.company, user=request.user)
        if not form.is_valid():
            return self.render(request, form)
        with transaction.atomic():
            e = _save(form, request.company, request.user)
        log_activity(
            request.company, "expense_added", f"Expense added: {e.title} ({service.format_paise(e.amount_paise)})",
            actor=request.user, target_content_type="expense", target_object_id=e.pk,
            metadata={"paid_by": e.paid_by_id, "amount_paise": e.amount_paise},
        )
        messages.success(request, f"Added {e.title}.")
        return redirect("expenses:expense_list")

    def render(self, request, form):
        show = "settled" if request.GET.get("show") == "settled" else "open"
        qs = Expense.objects.filter(company=request.company).select_related("paid_by").prefetch_related("split_with")
        open_qs = list(qs.filter(settled_at__isnull=True))
        rows = open_qs if show == "open" else list(qs.filter(settled_at__isnull=False)[:100])
        names = {}
        for e in open_qs:
            names[e.paid_by_id] = display_name(e.paid_by)
            names.update({u.pk: display_name(u) for u in e.split_with.all()})
        for e in rows:
            e.amount_label = service.format_paise(e.amount_paise)
            e.can_change = self.can_change(e)
            e.split_names = [display_name(u) for u in e.split_with.all()]
            e.share_label = service.format_paise(min(service.shares(e.amount_paise, [u.pk for u in e.split_with.all()]).values())) if e.split_names else ""
        net = service.balances(open_qs)
        me = net.get(request.user.pk, 0)

        payments = [
            {"from": names[a], "to": names[b], "amount": service.format_paise(p), "mine": a == request.user.pk}
            for a, b, p in service.settlements(net)
        ]
        return render(request, "expenses/index.html", {
            "form": form,
            "rows": rows,
            "show": show,
            "payments": payments,
            "open_count": len(open_qs),
            "open_total": service.format_paise(sum(e.amount_paise for e in open_qs)),
            "my_balance": service.format_paise(abs(me)),
            "my_state": "owed" if me > 0 else "owe" if me < 0 else "even",
            "can_settle": self.is_admin() and bool(open_qs),
        })


class ExpenseEditView(ExpenseAccessMixin, View):
    def get(self, request, pk, form=None):
        e = self.expense_or_404(pk)
        if not self.can_change(e):
            return HttpResponseForbidden("Only the person who added it or an admin can change this.")
        form = form or ExpenseForm(company=request.company, user=request.user, initial=_initial(e))
        return render(request, "expenses/edit.html", {"form": form, "expense": e})

    def post(self, request, pk):
        e = self.expense_or_404(pk)
        if not self.can_change(e):
            return HttpResponseForbidden("Only the person who added it or an admin can change this.")
        form = ExpenseForm(request.POST, company=request.company, user=request.user)
        if not form.is_valid():
            return render(request, "expenses/edit.html", {"form": form, "expense": e})
        with transaction.atomic():
            _save(form, request.company, request.user, e)
        log_activity(
            request.company, "expense_edited", f"Expense edited: {e.title}",
            actor=request.user, target_content_type="expense", target_object_id=e.pk,
        )
        messages.success(request, f"Saved {e.title}.")
        return redirect("expenses:expense_list")


class ExpenseDeleteView(ExpenseAccessMixin, View):
    def post(self, request, pk):
        e = self.expense_or_404(pk)
        if not self.can_change(e):
            return HttpResponseForbidden("Only the person who added it or an admin can delete this.")
        title = e.title
        e.delete()
        log_activity(
            request.company, "expense_deleted", f"Expense deleted: {title}",
            actor=request.user, target_content_type="expense",
        )
        messages.success(request, f"Deleted {title}.")
        return redirect("expenses:expense_list")


class ExpenseSettleView(ExpenseAccessMixin, View):
    def post(self, request):
        if not self.is_admin():
            return HttpResponseForbidden("Only owners and admins can settle up.")
        n = Expense.objects.filter(company=request.company, settled_at__isnull=True).update(settled_at=timezone.now())
        if n:
            log_activity(
                request.company, "expense_settled", f"Settled up {n} expense{'s' if n != 1 else ''}",
                actor=request.user, target_content_type="expense",
            )
        messages.success(request, f"Settled {n} expense{'s' if n != 1 else ''}.")
        return redirect("expenses:expense_list")
