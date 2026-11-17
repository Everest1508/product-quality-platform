"""Batch 2: money, salary history, quotes, API keys and product access. Owner/admin only."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count

from apps.accounts.models import Membership
from apps.costing.models import Estimate
from apps.costing.views import compute as quote_compute
from apps.expenses.models import Expense
from apps.payroll.models import PayrollProfile, Payslip
from apps.products.models import APIKey, PodMember, ProductAccess

from .money import _inr
from .registry import Result, report
from .work import _name


@report("expense-exceptions", "Expense exceptions", "money", "Unusually large expenses, possible duplicates, late entries and entries made for someone else.",
        "RPT-055", icon="triangle-alert", admin=True, filters=("period",))
def expense_exceptions(ctx):
    es = list(Expense.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end)).select_related("paid_by", "created_by").order_by("date"))
    amounts = sorted(e.amount_paise for e in es)
    big = amounts[int(len(amounts) * 0.95)] if len(amounts) >= 20 else None
    seen, rows = defaultdict(list), []
    for e in es:
        seen[(e.paid_by_id, e.category, e.amount_paise)].append(e)
    for e in es:
        flags = []
        if big and e.amount_paise >= big:
            flags.append("Among the largest 5%")
        if any(o.pk != e.pk and abs((o.date - e.date).days) <= 3 for o in seen[(e.paid_by_id, e.category, e.amount_paise)]):
            flags.append("Same amount, person and category within 3 days")
        if (e.created_at.date() - e.date).days > 7:
            flags.append("Entered more than a week late")
        if e.created_by_id != e.paid_by_id:
            flags.append("Entered by someone else")
        if flags:
            rows.append([e.date, e.category_label, _name(e.paid_by), _name(e.created_by), _inr(e.amount_paise), e.note, "; ".join(flags)])
    return Result(["Date", "Category", "Paid by", "Entered by", "Amount (INR)", "Details", "Why listed"], rows,
                  [("Expenses checked", f"{len(es):,}"), ("Listed", f"{len(rows):,}")])


@report("deductions", "Pay deductions by person", "money", "Money withheld for unpaid leave and lateness in each payroll cycle.",
        "RPT-058", icon="percent", admin=True, filters=("period", "person"))
def deductions(ctx):
    qs = Payslip.objects.filter(company=ctx.company, run__period_end__range=(ctx.start, ctx.end)).select_related("user", "run").order_by("run__period_start", "user__username")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    rows = []
    for p in qs:
        unpaid = p.unpaid_leave_days * p.daily_rate
        half = p.late_half_days * p.half_day_value
        rows.append([p.run.label, _name(p.user), float(p.unpaid_leave_days), float(unpaid), float(p.late_half_days), float(half), float(p.late_penalty),
                     float(unpaid + half + p.late_penalty), float(p.gross)])
    return Result(["Cycle", "Person", "Unpaid leave days", "Withheld for unpaid leave", "Late half-days", "Withheld for late half-days", "Late penalties", "Total withheld", "Gross paid"], rows,
                  [("Total withheld", f"{sum(r[7] for r in rows):,.2f}")], "Calculated from each payslip's own day counts and rate.")


@report("quote-margins", "Quote margins vs target", "money", "Each quote's cost, price, discount from the computed price and margin against target.",
        "RPT-049", icon="percent", admin=True, filters=("period",))
def quote_margins(ctx):
    rows = []
    for e in Estimate.objects.filter(company=ctx.company, quote_date__range=(ctx.start, ctx.end)).order_by("-quote_date"):
        r = quote_compute(ctx.company, e.inputs())
        cost, calc = r["total"], r["price"]
        price = r["pitch"] if r["has_pitch"] else calc
        margin = (price - cost) / price * 100 if price else Decimal("0")
        target = Decimal(e.margin_percent or 0)
        rows.append([e.quote_date, e.name, e.client_name, float(cost), float(calc), float(price) if r["has_pitch"] else None,
                     float((calc - price) / calc * 100) if r["has_pitch"] and calc else None, round(float(margin), 1), float(target),
                     "Yes" if e.margin_mode == "margin" and margin < target else ""])
    return Result(["Quoted on", "Project", "Client", "Our cost", "Computed price", "Pitched price", "Discount %", "Margin on price %", "Target margin %", "Below target"], rows,
                  [("Quotes", f"{len(rows):,}")], "Target is only compared when the quote is set to margin mode; a markup target is a different number.")


@report("api-key-hygiene", "API key hygiene", "audit", "Keys that are unused, expiring, expired or revoked.",
        "RPT-039", icon="eye", admin=True, filters=("product",))
def api_key_hygiene(ctx):
    from django.utils import timezone

    now = timezone.now()
    qs = APIKey.objects.filter(product__in=ctx.products).select_related("product").order_by("product__name", "-created_at")
    if ctx.product:
        qs = qs.filter(product=ctx.product)
    rows = []
    for k in qs:
        flags = []
        if k.state == "revoked":
            flags.append("Revoked")
        elif k.state == "expired":
            flags.append("Expired")
        else:
            if k.expires_at and k.expires_at <= now + timedelta(days=14):
                flags.append("Expires within 14 days")
            if not k.last_used_at and (now - k.created_at).days > 7:
                flags.append("Never used")
            elif k.last_used_at and (now - k.last_used_at).days >= 30:
                flags.append("Unused for 30+ days")
        rows.append([k.product.name, k.name, k.prefix, k.state.title(), k.created_at, k.last_used_at, (now - k.last_used_at).days if k.last_used_at else None, k.expires_at, "; ".join(flags)])
    return Result(["Project", "Key name", "Starts with", "State", "Created", "Last used", "Days since use", "Expires", "Attention"], rows,
                  [("Keys", f"{len(rows):,}"), ("Need attention", f"{sum(bool(r[8]) for r in rows):,}")], "The key itself is never stored or shown, only its first characters.")


@report("access-matrix", "Who can see which project", "audit", "A person-by-project grid showing how each person gets access.",
        "RPT-040", icon="users", admin=True, filters=())
def access_matrix(ctx):
    from apps.products.models import Product

    prods = list(Product.objects.filter(company=ctx.company).order_by("name"))
    explicit = set(ProductAccess.objects.filter(company=ctx.company).values_list("user_id", "product_id"))
    pods = set(PodMember.objects.filter(company=ctx.company).values_list("user_id", "product_id"))
    rows = []
    for m in Membership.objects.filter(company=ctx.company).select_related("user").order_by("user__username"):
        full = m.role in ("owner", "admin")
        cells = ["All (role)" if full else ("Access + pod" if (m.user_id, p.pk) in explicit and (m.user_id, p.pk) in pods else "Access" if (m.user_id, p.pk) in explicit else "Pod only (no access)" if (m.user_id, p.pk) in pods else "") for p in prods]
        rows.append([_name(m.user), m.get_role_display(), sum(bool(c) and "no access" not in c for c in cells), *cells])
    return Result(["Person", "Role", "Projects they can open", *[p.name for p in prods]], rows, [("People", f"{len(rows):,}"), ("Projects", f"{len(prods):,}")],
                  "Owners and admins see every project. Others need an explicit access grant; pod membership alone does not give access.")
