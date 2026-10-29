"""Filters shared by the list page and the CSV export, so they always agree."""

import re

from datetime import date

from django.utils import timezone

from apps.expenses.models import Expense
from apps.payroll.service import cycle_bounds

MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def cycle_key(day):
    """The pay cycle a date falls in, named by the month it ends in (26 Oct -> 2026-10).

    The books run 27th to 26th, so 27 Oct already belongs to November's cycle.
    """
    return f"{cycle_bounds(day)[1]:%Y-%m}"


def cycle_range(key):
    """(first day, last day) of the cycle `key` names."""
    y, m = key.split("-")
    return cycle_bounds(date(int(y), int(m), 1))


class Filters:
    """Read from the query string. `month` is a pay cycle (see `cycle_key`); none
    means the cycle we are in now, and `month=all` means every cycle."""

    def __init__(self, params):
        month = params.get("month")
        if month is None:
            month = cycle_key(timezone.localdate())
        self.month = month if MONTH.match(month or "") else "all"
        cat = params.get("category", "")
        self.category = cat if cat in Expense.Category.values else ""
        paid = params.get("paid_by", "")
        self.paid_by = int(paid) if paid.isdigit() else None
        self.q = (params.get("q") or "").strip()[:100]

    def apply(self, qs):
        if self.month != "all":
            first, last = cycle_range(self.month)
            qs = qs.filter(date__gte=first, date__lte=last)
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
        first, last = cycle_range(self.month)
        return f"{last:%B %Y} ({first:%-d %b} to {last:%-d %b})"
