import csv
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Sum
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.accounts.models import User
from apps.core.mixins import CompanyAdminRequiredMixin
from apps.dashboards.service import log_activity
from apps.expenses import service
from apps.expenses.filters import Filters
from apps.expenses.forms import CommentForm, ExpenseForm, display_name
from apps.expenses.models import Expense, ExpenseComment

LIST_LIMIT = 200


class ExpenseAccessMixin(CompanyAdminRequiredMixin):
    """Owners and admins only: the ledger is not shown to anyone else."""

    def expense_or_404(self, pk):
        try:
            return Expense.objects.select_related("paid_by").get(pk=pk, company=self.request.company)
        except Expense.DoesNotExist:
            raise Http404


def _save(form, company, user, expense=None):
    d = form.cleaned_data
    expense = expense or Expense(company=company, created_by=user)
    expense.amount_paise = int((d["amount"] * 100).to_integral_value())
    expense.date = d["date"]
    expense.category = d["category"]
    expense.category_other = d["category_other"].strip()
    expense.note = d["note"].strip()
    expense.paid_by = d["paid_by"]
    expense.save()
    return expense


def _initial(expense):
    return {
        "amount": Decimal(expense.amount_paise) / 100,
        "paid_by": expense.paid_by_id,
        "date": expense.date,
        "category": expense.category,
        "category_other": expense.category_other,
        "note": expense.note,
    }


class ExpenseListView(ExpenseAccessMixin, View):
    def get(self, request, form=None):
        return self.render(request, form or ExpenseForm(company=request.company, user=request.user))

    def post(self, request):
        form = ExpenseForm(request.POST, company=request.company, user=request.user)
        if not form.is_valid():
            return self.render(request, form)
        e = _save(form, request.company, request.user)
        log_activity(
            request.company, "expense_added", f"Expense added: {e.category_label} ({service.format_paise(e.amount_paise)})",
            actor=request.user, target_content_type="expense", target_object_id=e.pk,
            metadata={"paid_by": e.paid_by_id, "amount_paise": e.amount_paise},
        )
        messages.success(request, f"Added {e.category_label}.")
        return redirect("expenses:expense_list")

    def render(self, request, form):
        every = Expense.objects.filter(company=request.company)
        f = Filters(request.GET)
        qs = f.apply(every)
        rows = list(qs.select_related("paid_by").annotate(comment_count=Count("comments"))[:LIST_LIMIT])
        for e in rows:
            e.amount_label = service.format_paise(e.amount_paise)
        total = qs.aggregate(t=Sum("amount_paise"))["t"] or 0

        paid = list(qs.values("paid_by").annotate(t=Sum("amount_paise")).order_by("-t"))
        people = User.objects.in_bulk([r["paid_by"] for r in paid])
        by_person = [{"name": display_name(people[r["paid_by"]]), "total": service.format_paise(r["t"])} for r in paid]

        labels = dict(Expense.Category.choices)
        by_category = [
            {"name": r["category_other"] or labels[r["category"]], "total": service.format_paise(r["t"])}
            for r in qs.values("category", "category_other").annotate(t=Sum("amount_paise")).order_by("-t")
        ]

        months = [f"{d:%Y-%m}" for d in every.dates("date", "month", order="DESC")]
        current = f"{timezone.localdate():%Y-%m}"
        if current not in months:
            months.insert(0, current)
        if f.month != "all" and f.month not in months:
            months.append(f.month)
        member_ids = every.values_list("paid_by", flat=True).distinct()
        return render(request, "expenses/index.html", {
            "form": form,
            "rows": rows,
            "has_any": every.exists(),
            "f": f,
            "count": qs.count(),
            "total": service.format_paise(total),
            "by_person": by_person,
            "by_category": by_category,
            "months": [{"value": m, "label": Filters({"month": m}).period_label} for m in months],
            "categories": Expense.Category.choices,
            "payers": [{"pk": u.pk, "name": display_name(u)} for u in User.objects.filter(pk__in=member_ids)],
            "limited": len(rows) == LIST_LIMIT,
        })


def _csv_safe(text):
    """A spreadsheet runs a cell that starts with = + - @ as a formula."""
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


class ExpenseExportView(ExpenseAccessMixin, View):
    def get(self, request):
        f = Filters(request.GET)
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="expenses-{f.month}.csv"'
        w = csv.writer(resp)
        w.writerow(["Date", "Category", "Paid by", "Amount (INR)", "Details"])
        total = 0
        for e in f.apply(Expense.objects.filter(company=request.company)).select_related("paid_by").order_by("date", "id"):
            total += e.amount_paise
            w.writerow([e.date.isoformat(), _csv_safe(e.category_label), _csv_safe(display_name(e.paid_by)),
                        f"{e.amount_paise / 100:.2f}", _csv_safe(e.note)])
        w.writerow(["", "", "Total", f"{total / 100:.2f}", ""])
        return resp


def _discussion_url(expense):
    return reverse("expenses:expense_edit", args=[expense.pk]) + "#discussion"


class ExpenseEditView(ExpenseAccessMixin, View):
    def page(self, request, expense, form):
        comments = expense.comments.select_related("author")
        return render(request, "expenses/edit.html", {
            "form": form, "expense": expense, "comments": comments, "comment_form": CommentForm(),
        })

    def get(self, request, pk, form=None):
        e = self.expense_or_404(pk)
        form = form or ExpenseForm(company=request.company, user=request.user, initial=_initial(e))
        return self.page(request, e, form)

    def post(self, request, pk):
        e = self.expense_or_404(pk)
        form = ExpenseForm(request.POST, company=request.company, user=request.user)
        if not form.is_valid():
            return self.page(request, e, form)
        _save(form, request.company, request.user, e)
        log_activity(
            request.company, "expense_edited", f"Expense edited: {e.category_label}",
            actor=request.user, target_content_type="expense", target_object_id=e.pk,
        )
        messages.success(request, f"Saved {e.category_label}.")
        return redirect("expenses:expense_list")


class ExpenseDeleteView(ExpenseAccessMixin, View):
    def post(self, request, pk):
        e = self.expense_or_404(pk)
        title = e.category_label
        e.delete()
        log_activity(
            request.company, "expense_deleted", f"Expense deleted: {title}",
            actor=request.user, target_content_type="expense",
        )
        messages.success(request, f"Deleted {title}.")
        return redirect("expenses:expense_list")


class ExpenseCommentView(ExpenseAccessMixin, View):
    """Add a comment to an expense's thread (owners and admins, like the ledger)."""

    def post(self, request, pk):
        e = self.expense_or_404(pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            service.add_comment(e, request.user, form.cleaned_data["body"])
            log_activity(
                request.company, "expense_commented", f"Comment on expense: {e.category_label}",
                actor=request.user, target_content_type="expense", target_object_id=e.pk,
            )
            messages.success(request, "Comment added.")
        else:
            messages.error(request, form.errors["body"][0])
        return redirect(_discussion_url(e))


class ExpenseCommentDeleteView(ExpenseAccessMixin, View):
    """Delete your own comment. Nobody can delete somebody else's, owners included."""

    def post(self, request, pk, comment_pk):
        e = self.expense_or_404(pk)
        comment = get_object_or_404(ExpenseComment, pk=comment_pk, expense=e, company=request.company)
        if comment.author_id != request.user.pk:
            return HttpResponseForbidden("You can only delete your own comments.")
        comment.delete()
        log_activity(
            request.company, "expense_comment_deleted", f"Comment deleted on expense: {e.category_label}",
            actor=request.user, target_content_type="expense", target_object_id=e.pk,
        )
        messages.success(request, "Comment deleted.")
        return redirect(_discussion_url(e))
