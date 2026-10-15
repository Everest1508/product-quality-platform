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


class ExpenseForm(forms.Form):
    title = forms.CharField(max_length=120, label="What was it for?")
    amount = forms.DecimalField(
        min_value=Decimal("0.01"), max_value=Decimal("10000000"), decimal_places=2, label="Amount (₹)"
    )
    paid_by = forms.ModelChoiceField(queryset=None, label="Who paid?")
    date = forms.DateField(label="Date")
    category = forms.ChoiceField(choices=Expense.Category.choices, label="Category", initial="other")
    split_with = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple, label="Shared between"
    )
    note = forms.CharField(max_length=255, required=False, label="Note")

    def __init__(self, *args, company, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.people = members_of(company)
        pool = User.objects.filter(pk__in=[u.pk for u in self.people])
        self.fields["paid_by"].queryset = pool
        self.fields["split_with"].queryset = pool
        if not self.is_bound:
            self.initial.setdefault("paid_by", user.pk)
            self.initial.setdefault("date", timezone.localdate())
            self.initial.setdefault("split_with", [u.pk for u in self.people])
            self.initial.setdefault("category", "other")

    @property
    def selected_split(self):
        return {str(v) for v in (self["split_with"].value() or [])}
