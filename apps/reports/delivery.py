"""Batch 3: project delivery, planning and capacity."""

import statistics
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum

from apps.attendance import service as att
from apps.dsr.models import DSREntry
from apps.ingestion.models import ErrorGroup
from apps.payroll.models import PayrollProfile
from apps.payroll.service import holiday_dates
from apps.products.lifecycle import LABELS as STAGES
from apps.products.models import CrunchItem, PhasePlan, PodMember, Product, ProductAccess, ProductMilestone, ProductVersion, ProjectLogEntry
from apps.serop.models import SeropSharedServer
from apps.tickets.models import Ticket

from .registry import Result, report
from .work import CLOSED, _bounds, _name

DONE_STAGES = ("live", "close")


def _prods(ctx):
    qs = ctx.products.select_related("lead").order_by("name")
    return qs.filter(pk=ctx.product.pk) if ctx.product else qs


@report("milestones", "Milestone delivery", "projects", "Which milestones were hit or missed, and how many tickets sat behind each.",
        "RPT-011", icon="target", filters=("period", "product"))
def milestones(ctx):
    ms = ProductMilestone.objects.filter(company=ctx.company, product__in=_prods(ctx), target_date__range=(ctx.start, ctx.end)).select_related("product").order_by("target_date")
    tickets = defaultdict(lambda: [0, 0])
    for m, s in Ticket.objects.filter(milestone__in=ms).values_list("milestone", "status"):
        tickets[m][0] += 1
        tickets[m][1] += s in CLOSED
    rows = []
    for m in ms:
        late = None
        if m.completed_at:
            late = (m.completed_at.date() - m.target_date).days
        elif m.is_past_due:
            late = (ctx.today - m.target_date).days
        t, d = tickets[m.pk]
        rows.append([m.product.name, m.title, m.target_date, m.get_status_display() if m.computed_status == m.status else "Overdue",
                     m.completed_at, late, t, round(d * 100 / t) if t else None])
    return Result(["Project", "Milestone", "Target date", "Status", "Completed", "Days late (negative = early)", "Tickets", "Tickets resolved %"], rows,
                  [("Milestones", f"{len(rows):,}"), ("Overdue", f"{sum(r[3] == 'Overdue' for r in rows):,}")])


@report("stage-dwell", "Time spent in each project stage", "projects", "How long projects spend in FE, BE, Deploy, Testing and the other stages.",
        "RPT-031", icon="history", filters=("period", "product"))
def stage_dwell(ctx):
    a, b = _bounds(ctx)
    per, back = defaultdict(list), defaultdict(int)
    order = list(STAGES)
    for p in _prods(ctx):
        prev = p.start_date and p.created_at
        prev = p.created_at
        for e in ProjectLogEntry.objects.filter(product=p, kind="stage").order_by("created_at"):
            if a <= e.created_at <= b and e.from_stage:
                per[e.from_stage].append((e.created_at - prev).total_seconds() / 86400)
                if e.to_stage in order and e.from_stage in order and order.index(e.to_stage) < order.index(e.from_stage):
                    back[e.from_stage] += 1
            prev = e.created_at
    rows = [[STAGES.get(s, s), len(per[s]), round(sum(per[s]) / len(per[s]), 1), round(statistics.median(per[s]), 1), round(max(per[s]), 1), back[s]] for s in order if per.get(s)]
    return Result(["Stage", "Times left", "Average days", "Median days", "Longest (days)", "Moved backward from here"], rows,
                  note="A stay is counted when the project leaves the stage inside the period. The first stage counts from when the project was created.")


@report("plan-vs-actual", "Planned vs logged hours", "projects", "Hours planned for each project against hours logged in the DSR.",
        "RPT-032", icon="clock", admin=True, filters=("product",))
def plan_vs_actual(ctx):
    prods = list(_prods(ctx))
    plan = {r["product"]: r for r in PhasePlan.objects.filter(product__in=prods).values("product").annotate(h=Sum("planned_hours"))}
    done = dict(DSREntry.objects.filter(company=ctx.company, product__in=prods).values_list("product").annotate(h=Sum("hours_spent")))
    rows = []
    for p in prods:
        pl = float(plan.get(p.pk, {}).get("h") or 0)
        ac = float(done.get(p.pk) or 0)
        left = (p.end_date - ctx.today).days if p.end_date else None
        rows.append([p.name, STAGES.get(p.stage, p.stage), pl or None, round(ac, 1), round(ac - pl, 1) if pl else None, round(ac * 100 / pl) if pl else None, p.end_date, left])
    rows.sort(key=lambda r: -(r[5] or 0))
    return Result(["Project", "Stage", "Planned hours", "Logged hours", "Over (+) or under (-) plan", "Plan used %", "Planned end", "Days left"], rows,
                  [("Logged", f"{sum(r[3] for r in rows):,.0f} h")], "Planned hours come from the phase plan. Projects without one show no percentage.")


@report("schedule-slippage", "Schedule slippage", "projects", "Projects past their planned end, how often the plan was changed, and overdue milestones.",
        "RPT-033", icon="triangle-alert", filters=("period", "product"))
def schedule_slippage(ctx):
    a, b = _bounds(ctx)
    prods = list(_prods(ctx))
    changes = dict(ProjectLogEntry.objects.filter(product__in=prods, kind="schedule", created_at__range=(a, b)).values_list("product").annotate(n=Count("id")))
    overdue = dict(ProductMilestone.objects.filter(product__in=prods).exclude(status="completed").filter(target_date__lt=ctx.today).values_list("product").annotate(n=Count("id")))
    rows = []
    for p in prods:
        past = (ctx.today - p.end_date).days if p.end_date and p.end_date < ctx.today and p.stage not in DONE_STAGES else 0
        if past or changes.get(p.pk) or overdue.get(p.pk):
            rows.append([p.name, STAGES.get(p.stage, p.stage), p.end_date, past, changes.get(p.pk, 0), overdue.get(p.pk, 0)])
    rows.sort(key=lambda r: -r[3])
    return Result(["Project", "Stage", "Planned end", "Days past planned end", "Plan changes in period", "Overdue milestones"], rows,
                  [("Projects listed", f"{len(rows):,}")])


@report("crunch-blockers", "Crunch items and blockers", "projects", "Items that must come early and blockers raised on projects.",
        "RPT-034", icon="triangle-alert", filters=("period", "product"))
def crunch_blockers(ctx):
    a, b = _bounds(ctx)
    prods = list(_prods(ctx))
    rows = []
    for c in CrunchItem.objects.filter(product__in=prods).select_related("product", "created_by").order_by("due_date"):
        if c.done and not (c.done_at and a <= c.done_at <= b):
            continue
        rows.append(["Crunch item", c.product.name, c.feature, c.due_date, "Done" if c.done else ("Overdue" if c.due_date < ctx.today else "Open"),
                     (c.done_at.date() - c.due_date).days if c.done_at else (ctx.today - c.due_date).days, c.reason, _name(c.created_by) if c.created_by else ""])
    for e in ProjectLogEntry.objects.filter(product__in=prods, kind="blocker", created_at__range=(a, b)).select_related("product", "author").order_by("-created_at"):
        rows.append(["Blocker", e.product.name, e.body[:200], e.created_at.date(), "Raised", (ctx.today - e.created_at.date()).days, "", _name(e.author) if e.author else ""])
    return Result(["Type", "Project", "What", "Due or raised", "State", "Days late or old", "Why", "Raised by"], rows,
                  [("Open crunch items", f"{sum(r[0] == 'Crunch item' and r[4] != 'Done' for r in rows):,}"), ("Blockers", f"{sum(r[0] == 'Blocker' for r in rows):,}")])


@report("project-people", "Who works on which project", "projects", "Lead, pod and access per person, with hours in the last 28 days.",
        "RPT-037", icon="users", admin=True, filters=())
def project_people(ctx):
    since = ctx.today - timedelta(days=27)
    from apps.accounts.models import Membership

    leads = defaultdict(list)
    for p in Product.objects.filter(company=ctx.company, lead__isnull=False):
        leads[p.lead_id].append(p.name)
    pods, acc = defaultdict(list), defaultdict(int)
    for u, n in PodMember.objects.filter(company=ctx.company).values_list("user", "product__name"):
        pods[u].append(n)
    for u, in ProductAccess.objects.filter(company=ctx.company).values_list("user"):
        acc[u] += 1
    hrs = defaultdict(lambda: defaultdict(Decimal))
    for u, n, h in DSREntry.objects.filter(company=ctx.company, date__gte=since).values_list("user", "product__name", "hours_spent"):
        hrs[u][n or "No project"] += h or 0
    rows = []
    for m in Membership.objects.filter(company=ctx.company).select_related("user").order_by("user__username"):
        h = hrs[m.user_id]
        top = ", ".join(f"{k} ({float(v):.0f}h)" for k, v in sorted(h.items(), key=lambda x: -x[1])[:3])
        rows.append([_name(m.user), m.get_role_display(), ", ".join(leads[m.user_id]), len(pods[m.user_id]), ", ".join(pods[m.user_id]), acc[m.user_id], float(sum(h.values())), len(h), top])
    return Result(["Person", "Role", "Leads", "Pods joined", "Pod projects", "Projects granted access", "Hours, last 28 days", "Projects worked on", "Most time on"], rows)


@report("hosting-inventory", "Hosting and server inventory", "projects", "Which project lives on which server, with stack and environment.",
        "RPT-038", icon="landmark", admin=True, filters=())
def hosting_inventory(ctx):
    rows = [["Project", p.name, p.server.name if p.server_id else "", p.server_path, ", ".join(p.tech_stack or []), p.default_environment, "Yes" if p.discord_webhook_url else "No", STAGES.get(p.stage, p.stage)]
            for p in Product.objects.filter(company=ctx.company).select_related("server").order_by("name")]
    rows += [["Shared server", s.name, s.host, s.project_path or "", "", s.connection_type, "", "Shareable" if s.is_shareable else "Private"]
             for s in SeropSharedServer.objects.filter(company=ctx.company).order_by("name")]
    return Result(["Kind", "Name", "Server or host", "Path", "Tech stack", "Environment or connection", "Discord alerts on", "Stage or sharing"], rows,
                  [("Projects without a server", f"{sum(r[0] == 'Project' and not r[2] for r in rows):,}")], "Passwords and keys are never shown.")


@report("project-risk", "Project delivery risk", "projects", "A 0-100 risk score per live project from overdue work, blockers, plan overrun and late dates.",
        "RPT-042", icon="triangle-alert", admin=True, filters=("product",))
def project_risk(ctx):
    prods = [p for p in _prods(ctx) if p.stage not in DONE_STAGES]
    ids = [p.pk for p in prods]
    ms = dict(ProductMilestone.objects.filter(product__in=ids, target_date__lt=ctx.today).exclude(status="completed").values_list("product").annotate(n=Count("id")))
    cr = dict(CrunchItem.objects.filter(product__in=ids, done=False, due_date__lt=ctx.today).values_list("product").annotate(n=Count("id")))
    bl = dict(ProjectLogEntry.objects.filter(product__in=ids, kind="blocker", created_at__gte=ctx.today - timedelta(days=14)).values_list("product").annotate(n=Count("id")))
    tk = dict(Ticket.objects.filter(product__in=ids, deadline__lt=__import__("django").utils.timezone.now()).exclude(status__in=CLOSED).values_list("product").annotate(n=Count("id")))
    plan = {r["product"]: float(r["h"] or 0) for r in PhasePlan.objects.filter(product__in=ids).values("product").annotate(h=Sum("planned_hours"))}
    done = {k: float(v or 0) for k, v in DSREntry.objects.filter(company=ctx.company, product__in=ids).values_list("product").annotate(h=Sum("hours_spent"))}
    rows = []
    for p in prods:
        f = {
            "Overdue milestones": min(30, 15 * ms.get(p.pk, 0)),
            "Overdue crunch items": min(20, 10 * cr.get(p.pk, 0)),
            "Blockers in last 14 days": min(20, 10 * bl.get(p.pk, 0)),
            "Overdue tickets": min(15, 3 * tk.get(p.pk, 0)),
            "Past planned end": min(30, 2 * (ctx.today - p.end_date).days) if p.end_date and p.end_date < ctx.today else 0,
            "Over planned hours": 20 if plan.get(p.pk) and done.get(p.pk, 0) > plan[p.pk] else 0,
        }
        score = min(100, sum(f.values()))
        top = max(f, key=f.get)
        rows.append([p.name, STAGES.get(p.stage, p.stage), score, "High" if score >= 60 else "Medium" if score >= 30 else "Low", top if f[top] else "Nothing flagged",
                     ms.get(p.pk, 0), cr.get(p.pk, 0), bl.get(p.pk, 0), tk.get(p.pk, 0)])
    rows.sort(key=lambda r: -r[2])
    return Result(["Project", "Stage", "Risk score", "Risk", "Biggest factor", "Overdue milestones", "Overdue crunch items", "Blockers (14 days)", "Overdue tickets"], rows,
                  [("High risk", f"{sum(r[3] == 'High' for r in rows):,}")],
                  "Score adds points: 15 per overdue milestone, 10 per overdue crunch item or recent blocker, 3 per overdue ticket, 2 per day past planned end, 20 if over planned hours. Capped at 100.")


@report("client-status", "Client project status", "projects", "A one-line-per-project status you can share with a client.",
        "RPT-041", icon="package", filters=("period", "product"))
def client_status(ctx):
    a, b = _bounds(ctx)
    prods = list(_prods(ctx))
    ids = [p.pk for p in prods]
    mil = defaultdict(lambda: [0, 0])
    for p, s in ProductMilestone.objects.filter(product__in=ids).values_list("product", "status"):
        mil[p][0] += 1
        mil[p][1] += s == "completed"
    tk = defaultdict(lambda: [0, 0])
    for p, s, u in Ticket.objects.filter(product__in=ids).values_list("product", "status", "updated_at"):
        if s in CLOSED:
            tk[p][0] += a <= u <= b
        else:
            tk[p][1] += 1
    err = dict(ErrorGroup.objects.filter(product__in=ids, severity__in=("critical", "high"), status__in=("open", "investigating")).values_list("product").annotate(n=Count("id")))
    last = {}
    for e in ProjectLogEntry.objects.filter(product__in=ids, kind__in=("update", "decision", "stage")).order_by("created_at"):
        last[e.product_id] = e
    rows = []
    for p in prods:
        m, t, e = mil[p.pk], tk[p.pk], last.get(p.pk)
        rows.append([p.name, STAGES.get(p.stage, p.stage), p.end_date, f"{m[1]} of {m[0]}" if m[0] else "", t[0], t[1], err.get(p.pk, 0),
                     e.created_at if e else None, (e.body[:160] if e and e.body else "")])
    return Result(["Project", "Stage", "Planned end", "Milestones done", "Tickets resolved in period", "Open tickets", "Open critical or high errors", "Last update", "Latest note"], rows,
                  [("Projects", f"{len(rows):,}")], "Leaves out blockers and corrections. Check the latest note before sharing.")


@report("capacity-plan", "Capacity vs planned hours", "projects", "Hours the team has available each month against hours planned in project phases.",
        "RPT-097", icon="chart-column", admin=True, filters=())
def capacity_plan(ctx):
    shift = att.shift_for(ctx.company)
    cur = {}
    for p in PayrollProfile.objects.filter(company=ctx.company, effective_from__lte=ctx.today).order_by("user_id", "-effective_from"):
        cur.setdefault(p.user_id, p)
    people = sum(p.is_on_payroll for p in cur.values())
    first = ctx.today.replace(day=1)
    months = []
    for i in range(3):
        y, m = divmod(first.month - 1 + i, 12)
        months.append(first.replace(year=first.year + y, month=m + 1))
    months.append(months[-1].replace(year=months[-1].year + (months[-1].month // 12), month=months[-1].month % 12 + 1))
    plans = list(PhasePlan.objects.filter(company=ctx.company, planned_hours__isnull=False, start_date__isnull=False, end_date__isnull=False))
    rows = []
    for s, e in zip(months, months[1:]):
        e = e - timedelta(days=1)
        hol = holiday_dates(ctx.company, s, e)
        wd = [d for d in (s + timedelta(n) for n in range((e - s).days + 1)) if not shift.is_weekly_off(d) and d not in hol]
        avail = len(wd) * people * shift.worked_minutes_per_day / 60
        need = 0.0
        for ph in plans:
            span = (ph.end_date - ph.start_date).days + 1
            ov = (min(e, ph.end_date) - max(s, ph.start_date)).days + 1
            if span > 0 and ov > 0:
                need += float(ph.planned_hours) * ov / span
        rows.append([f"{s:%b %Y}", len(wd), people, round(avail), round(need), round(avail - need), round(need * 100 / avail) if avail else None])
    return Result(["Month", "Working days", "People on payroll", "Hours available", "Hours planned", "Spare hours", "Planned as % of available"], rows,
                  note="Available hours ignore leave and part-time. Planned hours spread each phase evenly over its dates.")
