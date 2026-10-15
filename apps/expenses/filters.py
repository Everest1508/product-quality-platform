"""Filters shared by the list page and the CSV export, so they always agree."""

import re

from django.utils import timezone

from apps.expenses.models import Expense

MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class Filters:
    """Read from the query string. No `month` means this month; `month=all` means
    every month."""

    def __init__(self, params):
        month = params.get("month")
        if month is None:
            month = f"{timezone.localdate():%Y-%m}"
        self.month = month if MONTH.match(month or "") else "all"
        cat = params.get("category", "")
        self.category = cat if cat in Expense.Category.values else ""
        paid = params.get("paid_by", "")
        self.paid_by = int(paid) if paid.isdigit() else None
        self.q = (params.get("q") or "").strip()[:100]

    def apply(self, qs):
        if self.month != "all":
            y, m = self.month.split("-")
            qs = qs.filter(date__year=int(y), date__month=int(m))
        if self.category:
            qs = qs.filter(category=self.category)
        if self.paid_by:
            qs = qs.filter(paid_by_id=self.paid_by)
        if self.q:
            from django.db.models import Q

            qs = qs.filter(Q(note__icontains=self.q) | Q(category_other__icontains=self.q))
        return qs

    @property
    def is_filtered(self):
        return bool(self.category or self.paid_by or self.q)

    @property
    def query(self):
        """The filters as a query string, for links that must keep them."""
        from urllib.parse import urlencode

        d = {"month": self.month}
        if self.category:
            d["category"] = self.category
        if self.paid_by:
            d["paid_by"] = self.paid_by
        if self.q:
            d["q"] = self.q
        return urlencode(d)

    @property
    def period_label(self):
        if self.month == "all":
            return "All time"
        y, m = self.month.split("-")
        return f"{['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][int(m)]} {y}"
