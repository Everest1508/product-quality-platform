"""The report catalogue: one decorated function per report, found by key.

A report function takes a `Ctx` (who is asking, which company, the chosen period/project/person) and returns a
`Result`. Everything a report shows is already scoped by the function itself through `accessible_*` helpers, so
the page and the exports can never return more than the person could open elsewhere.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from django.utils import timezone

from apps.products.access import accessible_products

GROUPS = [
    ("tickets", "Tickets", "ticket"),
    ("errors", "Errors", "triangle-alert"),
    ("customers", "Customers and leads", "headset"),
    ("projects", "Projects and time", "package"),
    ("people", "People", "users"),
    ("money", "Money", "banknote"),
    ("audit", "Audit and access", "eye"),
]

PERIODS = [
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("90d", "Last 90 days"),
    ("month", "This month"),
    ("lastmonth", "Last month"),
    ("year", "This year"),
]


@dataclass
class Ctx:
    user: object
    company: object
    start: date
    end: date
    product: object = None
    person: object = None
    is_admin: bool = False

    @property
    def products(self):
        return accessible_products(self.user, self.company)

    @property
    def today(self):
        return timezone.localdate()


@dataclass
class Result:
    columns: list
    rows: list
    kpis: list = field(default_factory=list)  # [(label, text)]
    note: str = ""


@dataclass
class Report:
    key: str
    title: str
    group: str
    blurb: str
    icon: str
    run: Callable
    admin: bool
    filters: tuple
    rpt: str

    @property
    def snapshot(self):
        return "period" not in self.filters


REPORTS = {}


def report(key, title, group, blurb, rpt, icon="chart-column", admin=False, filters=("period",)):
    def deco(fn):
        REPORTS[key] = Report(key, title, group, blurb, icon, fn, admin, tuple(filters), rpt)
        return fn

    return deco


def visible(is_admin):
    return [r for r in REPORTS.values() if is_admin or not r.admin]


def period_dates(preset, today):
    if preset == "7d":
        return today - timedelta(days=6), today
    if preset == "90d":
        return today - timedelta(days=89), today
    if preset == "month":
        return today.replace(day=1), today
    if preset == "lastmonth":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if preset == "year":
        return today.replace(month=1, day=1), today
    return today - timedelta(days=29), today
