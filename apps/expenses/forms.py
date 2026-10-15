from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.accounts.models import Membership, User
from apps.expenses.models import Expense


def members_of(company):
    """People an expense can be paid by or shared with. Viewers (often just Serop
    team guests) are left out."""
    return [
        m.user
        for m in Membership.objects.filter(company=company, user__is_active=True)
        .exclude(role=Membership.Role.VIEWER)
        .select_related("user")
        .order_by("user__first_name", "user__username")
    ]


def display_name(user):
    return user.get_full_name() or user.username


class AmountField(forms.DecimalField):
    """The amount box shows 12,34,567 as you type, so accept the commas."""

    def to_python(self, value):
        return super().to_python(str(value).replace(",", "").strip() if value else value)


class ExpenseForm(forms.Form):
    amount = AmountField(
        min_value=Decimal("0.01"), max_value=Decimal("10000000"), decimal_places=2, label="Amount (₹)"
    )
    paid_by = forms.ModelChoiceField(queryset=None, label="Who paid?")
    date = forms.DateField(label="Date")
    category = forms.ChoiceField(choices=Expense.Category.choices, label="Category", initial="tea")
    category_other = forms.CharField(max_length=60, required=False, label="What kind?")
    note = forms.CharField(max_length=255, required=False, label="Note")

    def clean(self):
        data = super().clean()
        if data.get("category") == "other":
            if not (data.get("category_other") or "").strip():
                self.add_error("category_other", "Type what kind of expense it is.")
        else:
            data["category_other"] = ""
        return data

    def __init__(self, *args, company, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.people = members_of(company)
        pool = User.objects.filter(pk__in=[u.pk for u in self.people])
        self.fields["paid_by"].queryset = pool
        if not self.is_bound:
            self.initial.setdefault("paid_by", user.pk)
            self.initial.setdefault("date", timezone.localdate())
            self.initial.setdefault("category", "tea")
