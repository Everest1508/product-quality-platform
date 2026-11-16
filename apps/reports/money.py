"""Expenses and payroll. Owner/admin only."""

from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.accounts.models import Membership
from apps.expenses.models import Expense
from apps.payroll.models import PayrollProfile, PayrollRun, Payslip

from .registry import Result, report
from .work import _name


def _inr(paise):
    return round(paise / 100, 2)


@report("expense-trend", "Expenses by month and category", "money", "How spending moves month to month: tea, milk, AI, server, trips.",
        "RPT-052", icon="wallet", admin=True, filters=("period",))
def expense_trend(ctx):
    per = defaultdict(lambda: defaultdict(int))
    cats = []
    for e in Expense.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end)):
        per[f"{e.date:%Y-%m}"][e.category_label] += e.amount_paise
        if e.category_label not in cats:
            cats.append(e.category_label)
    cats.sort()
    rows, prev = [], None
    for m in sorted(per):
        total = sum(per[m].values())
        rows.append([m, *[_inr(per[m].get(c, 0)) for c in cats], _inr(total), round((total - prev) * 100 / prev, 1) if prev else None])
        prev = total
    return Result(["Month", *cats, "Total (INR)", "Change on last month %"], rows,
                  [("Total spent", f"{sum(r[-2] for r in rows):,.2f} INR")])


@report("reimbursement-ageing", "Money owed to people for expenses", "money", "Expenses someone paid out of pocket that have not been repaid, by age.",
        "RPT-053", icon="coins", admin=True, filters=())
def reimbursement_ageing(ctx):
    today = ctx.today
    bands = ["0-30 days", "31-60 days", "Over 60 days"]
    per = defaultdict(lambda: {"b": [0, 0, 0], "n": 0, "oldest": 0, "run": 0})
    for e in Expense.objects.filter(company=ctx.company, repaid_on__isnull=True, paid_in_run__isnull=True).select_related("paid_by"):
        age = (today - e.date).days
        d = per[e.paid_by]
        d["b"][0 if age <= 30 else 1 if age <= 60 else 2] += e.amount_paise
        d["n"] += 1
        d["oldest"] = max(d["oldest"], age)
        d["run"] += e.to_salary * e.amount_paise
    rows = [[_name(u), *[_inr(x) for x in d["b"]], _inr(sum(d["b"])), d["n"], d["oldest"], _inr(d["run"])] for u, d in per.items()]
    rows.sort(key=lambda r: -r[4])
    return Result(["Person", *[f"{b} (INR)" for b in bands], "Total owed (INR)", "Expenses", "Oldest (days)", "Waiting for payroll (INR)"], rows,
                  [("Total owed", f"{sum(r[4] for r in rows):,.2f} INR")],
                  "An expense counts as owed until it is marked repaid or paid through a payroll run.")


@report("payroll-trend", "Payroll cost by cycle", "money", "What each payroll cycle cost, and how gross pay and deductions move.",
        "RPT-057", icon="banknote", admin=True, filters=())
def payroll_trend(ctx):
    rows, prev = [], None
    for run in PayrollRun.objects.filter(company=ctx.company).order_by("-period_start")[:24][::-1]:
        s = run.payslips.aggregate(n=Count("id"), g=Sum("gross"), d=Sum("deduction"), p=Sum("late_penalty"), r=Sum("reimbursement"))
        g = s["g"] or Decimal("0")
        rows.append([run.label, "Locked" if run.is_locked else "Open", s["n"], float(g), float(s["d"] or 0), float(s["p"] or 0),
                     float(s["r"] or 0), round(float(g) / s["n"], 2) if s["n"] else None,
                     round(float(g - prev) * 100 / float(prev), 1) if prev else None])
        prev = g
    return Result(["Cycle", "Run", "People paid", "Gross pay", "Unpaid-leave deductions", "Late penalties", "Expenses repaid",
                   "Gross per person", "Change on last cycle %"], rows,
                  [("Cycles", f"{len(rows):,}")], "Gross already includes expenses repaid. The last 24 cycles.")


@report("payroll-variance", "Payroll change since last cycle", "money", "Whose pay changed from the previous run, and by how much.",
        "RPT-059", icon="percent", admin=True, filters=())
def payroll_variance(ctx):
    runs = list(PayrollRun.objects.filter(company=ctx.company).order_by("-period_start")[:2])
    if len(runs) < 2:
        return Result(["Person", "Previous gross", "Latest gross", "Change", "Change %", "Why"], [], note="Needs at least two payroll runs.")
    new, old = ({p.user_id: p for p in r.payslips.select_related("user")} for r in runs)
    rows = []
    for uid in sorted(set(new) | set(old), key=lambda u: _name((new.get(u) or old[u]).user)):
        n, o = new.get(uid), old.get(uid)
        ng, og = (n.gross if n else Decimal(0)), (o.gross if o else Decimal(0))
        why = ("Joined this cycle" if not o else "Not paid this cycle" if not n else
               ", ".join(w for w, c in (("unpaid leave", n.unpaid_leave_days != o.unpaid_leave_days), ("lateness", n.late_penalty != o.late_penalty or n.late_half_days != o.late_half_days),
                                        ("expenses", n.reimbursement != o.reimbursement), ("salary rate", n.daily_rate != o.daily_rate)) if c))
        rows.append([_name((n or o).user), float(og), float(ng), float(ng - og), round(float(ng - og) * 100 / float(og), 1) if og else None, why])
    rows.sort(key=lambda r: -abs(r[3]))
    return Result(["Person", "Previous gross", "Latest gross", "Change", "Change %", "Why"], rows,
                  [("Latest run", runs[0].label), ("Compared with", runs[1].label)])


@report("payroll-exceptions", "Payroll completeness check", "money", "People who should be paid but are missing from the latest run, or paid nothing.",
        "RPT-061", icon="triangle-alert", admin=True, filters=())
def payroll_exceptions(ctx):
    run = PayrollRun.objects.filter(company=ctx.company).order_by("-period_start").first()
    if not run:
        return Result(["Person", "Problem", "Detail"], [], note="No payroll run yet.")
    paid = {p.user_id: p for p in run.payslips.all()}
    current = {}
    for p in PayrollProfile.objects.filter(company=ctx.company, effective_from__lte=ctx.today).select_related("user").order_by("user_id", "-effective_from"):
        current.setdefault(p.user_id, p)
    rows = []
    for uid, p in current.items():
        if p.is_on_payroll and not (p.monthly_salary or p.daily_rate):
            rows.append([_name(p.user), "On payroll with no salary", "Set a monthly salary or daily rate on the profile"])
        if p.is_on_payroll and uid not in paid:
            rows.append([_name(p.user), "On payroll but no payslip", f"Missing from {run.label}"])
    rows += [[_name(p.user), "Payslip is zero", f"Gross 0 in {run.label}"] for p in paid.values() if not p.gross]
    for m in Membership.objects.filter(company=ctx.company).select_related("user"):
        if m.user_id not in current:
            rows.append([_name(m.user), "Member with no payroll profile", "Add a profile, or leave them off payroll on purpose"])
    return Result(["Person", "Problem", "Detail"], rows, [("Checked run", run.label), ("Problems", f"{len(rows):,}")])
