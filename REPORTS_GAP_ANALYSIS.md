# Reports Gap Analysis

*Read-only audit of this repository; no source code was changed. Generated 2026-11-16.*

## A. Executive summary

- **Stack:** Django 6 + SQLite, server-rendered (htmx/Alpine), DRF only for the ingestion and Serop APIs, Channels for live feeds.
- **Domain:** internal operations platform for a software studio: ticketing, error monitoring, project lifecycle, leads and quotes, plus the studio's own attendance, leave, payroll, daily status reports and expenses. There is **no invoicing, receivables or customer-billing data**, so revenue/AR reports are out of scope until that exists.
- **Existing report surfaces:** 19 (section C); only 5 export anything (CSV for timesheet, payroll run, DSR, expenses, costing) and none is scheduled or e-mailed.
- **Candidate reports found missing or partial:** **99** (78 MISSING, 21 PARTIAL). 89 are READY on data that exists today; 10 need new fields or tables (section F).
- **Quick wins (READY + S + High):** 25 (section G).
- **Biggest structural gaps:** (1) no duration data on tickets/errors (`resolved_at` is not stored), (2) quotes, expenses and time are not linked to projects, so profitability cannot be computed, (3) lead records have no source/owner/lost reason, (4) SDK feedback, browser/OS/device and version data are stored but never shown.

### Top 10 highest-value gaps
Ranked by business value, then lowest effort, among reports whose data exists today.

| ID | Report | Status | Audience | Value | Effort | Score |
|---|---|---|---|---|---|---|
| RPT-002 | Ticket ageing (open backlog by age bucket) | MISSING | Ops | High | S | 3.0 |
| RPT-003 | Overdue and due-soon deadlines | PARTIAL | Ops | High | S | 3.0 |
| RPT-006 | Created vs resolved trend and backlog burn | PARTIAL | Owner | High | S | 3.0 |
| RPT-009 | Unassigned and stale tickets | MISSING | Ops | High | S | 3.0 |
| RPT-014 | Error trend by severity and product | PARTIAL | Ops | High | S | 3.0 |
| RPT-015 | Top errors by occurrences and users affected | PARTIAL | Ops | High | S | 3.0 |
| RPT-022 | Untriaged error queue ageing | MISSING | Ops | High | S | 3.0 |
| RPT-024 | NPS / CSAT / CES trend and distribution | PARTIAL | Owner | High | S | 3.0 |
| RPT-026 | In-app feedback ratings report | MISSING | Owner | High | S | 3.0 |
| RPT-030 | Project portfolio status | PARTIAL | Owner | High | S | 3.0 |

Highest-value reports that are blocked on new data (worth scheduling the data work for): RPT-036 project profitability, RPT-047 lead source/owner/lost reason, RPT-051 quote win/loss, RPT-063 statutory summary, RPT-025 detractor follow-up.

---

## B. System map

**Stack.** Django 6 on SQLite (`db.sqlite3`), server-rendered class-based views, htmx + Alpine.js from CDN, one CSS bundle built from `templates/core/css/*.css`. DRF only for the ingestion API (`/api/v1/`, `apps/ingestion/`) and the Serop API (`/api/serop/`). Django Channels/Daphne for WebSockets (presence, live inbox), Redis optional. No ORM other than Django's. Clients: the browser app, the **Server Operator ("Serop")** Electron desktop app (OAuth-style loopback sign-in, `apps/accounts/views.py`, `apps/serop/`), customer apps that push errors/feedback/tickets through SDK keys, a website lead webhook (`/api/v1/leads/<token>/`), and a PWA shell (`apps/core/pwa.py`). Integrations: Discord webhooks per product (`apps/products/webhook.py`), web push (VAPID) in `apps/notifications`. No payment, tax, email-digest or invoicing integration exists. Scheduled work is cron-driven management commands: `evaluate_rules`, `send_attendance_reminders`, `notify_todos`.

**Domain.** An internal operations platform for a small software studio / agency: ticketing and error monitoring for customer products, project lifecycle tracking, lead intake and quoting, plus the studio's own HR (attendance, leave, payroll, daily status reports) and expense tracking. Real buyers/users: **Owner** (portfolio, margin, people cost), **Admin/Ops** (queues, access, data hygiene), **Finance/HR** (payroll, leave, reimbursements), **Developers/Support** (tickets, errors, DSR), **Sales** (leads, quotes), **Auditor** (who-changed-what) and **Client** (status and feedback shared out).

**Entities and relationships.**

```
Company ─┬─ Membership(role, is_leave_approver, late_exempt) ── User
         ├─ Product(=Project; stage, key, lead, server, dates) ─┬─ Ticket ── TicketComment / TicketAttachment / assignees
         │                                                      ├─ ErrorGroup ── ErrorOccurrence   (ingestion API)
         │                                                      ├─ Feedback / IngestedTicket       (ingestion API)
         │                                                      ├─ Survey ── SurveyResponse ; SentimentRecord
         │                                                      ├─ ProductMilestone, ProductVersion, APIKey
         │                                                      ├─ PhasePlan, ProjectLogEntry, CrunchItem, PodMember, ProductAccess
         │                                                      └─ AutoTicketRule ── AutoTicketLog
         ├─ Lead ── LeadLog ──(convert)──► Product
         ├─ Estimate (quote; people/others as JSON)           [no link to Lead or Product]
         ├─ Expense ── ExpenseComment ──(to_salary/paid_in_run)──► PayrollRun
         ├─ WorkShift(1 per company), Holiday
         ├─ AttendanceRecord ── AttendanceCorrection
         ├─ LeavePolicy ── LeaveRequest(paid_days/unpaid_days)
         ├─ PayrollProfile(dated) ─► PayrollRun ── Payslip(snapshot)
         ├─ DSREntry(user,date,ticket?,product?,hours_spent)
         └─ ActivityLog (audit trail; event_type + metadata JSON), Notification, PresenceSession(live only)
```

**User roles.** `Membership.Role`: owner, admin, developer, support, viewer; plus flags `is_leave_approver` and `late_exempt`. Per-product visibility through `ProductAccess` (`apps/products/access.py`); owners/admins see all. Payroll and attendance admin views require owner/admin; `/payroll/me/` is member-only.

**Main business flows.**
1. *Support loop:* SDK error → `ErrorGroup` (dedup by fingerprint) → rule or person creates `Ticket` → status moves (open → assigned → in progress → testing → resolved → closed) → resolution auto-logs a `DSREntry` → resolved error that returns is flagged as a regression.
2. *Sales loop:* website form → `Lead` → notes/status in `LeadLog` → convert → new `Product` (project) → stage moves through nine phases (`products/lifecycle.py`).
3. *Quote loop:* `Estimate` computed from people, rent, AI cost and margin → printable quote (not linked to the lead or project).
4. *People loop:* punch in/out → lateness derived from `WorkShift` → leave split paid/unpaid → payroll run 27th-26th → locked `Payslip` snapshot; expenses flagged "to salary" are repaid in the run; DSR records the work.
5. *Feedback loop:* surveys and SDK ratings per product → CS hub averages and NPS.

---

## C. Existing reports inventory

| # | Name | Module | Where it lives | Filters supported | Export | Gaps |
|---|---|---|---|---|---|---|
| 1 | Summary report ("Reports") | dashboards | `apps/dashboards/views.py:191`, `service.get_summary_report` (409), template `dashboards/reports.html` | date range, presets; role-scoped | none | counts come only from `ActivityLog`; no weekly/monthly view, no export, no schedule, no durations (RPT-004/006) |
| 2 | Admin / product / personal dashboards | dashboards | `service.get_admin_dashboard_data`, `get_product_dashboard_data`, `get_personal_dashboard_data` | role, product | none | live snapshot only; no history |
| 3 | Audit log | dashboards | `dashboards/views.py:95` | category, type, actor, from/to, preset, text | none | cannot hand to an auditor (RPT-086/087) |
| 4 | Ticket list and Kanban | tickets / products | `tickets/views.py:63-123`, `products/views.py` (`ProductTicket*`) | text, type, priority, product, assignee, overdue, status, sort | none | no export, no ageing, no durations |
| 5 | Error list and detail | errors | `errors/views.py:42-64` | product, status, severity, text, regressed, sort | none | no trends, no breakdowns, no impact ranking |
| 6 | CS hub and survey detail | feedback | `feedback/views.py:215-270`, `Survey.compute_nps` | product | none | no trend, no export; SDK `Feedback` not shown at all |
| 7 | Attendance timesheet | attendance | `attendance/views.py:662` | month | **CSV** (`?export=csv`) | present/absent/late counts only; no minutes or penalty |
| 8 | Attendance team today / week; who-is-in | attendance | `service.get_team_today`, `get_team_week`, `get_who_is_in` | date | none | live view; no history report |
| 9 | Timesheet detail grid | attendance | `attendance/views.py` `TimesheetDetailView`, `service.get_month_grid` | month, person | none | one person at a time |
| 10 | Correction queue | attendance | `attendance/corrections.py`, `CorrectionQueueView` | status | none | no proof or risk flags, no analytics |
| 11 | Leave balances, calendar, approvals | leave | `leave/views.py:113,323,639`, `service.balances_for` | year, status, month | none | own balance only; no company register |
| 12 | Payroll run list / detail / preview | payroll | `payroll/views.py:164`, `service.preview` | cycle | **CSV** (run) + printable payslip (`templates/payroll/payslip.html`) | one run at a time; no trends or variance |
| 13 | DSR log | dsr | `dsr/views.py:455-490` | date range, person, text | **CSV** | rows only; no pivot, no compliance view |
| 14 | Expenses list with totals | expenses | `expenses/views.py:81-151` | month (+person/category) | **CSV** (`export.csv`) | single month; no ageing or reconciliation |
| 15 | Project costing report | costing | `costing/views.py:56-110` | month | **CSV** (`export.csv`), printable quote (`costing/quote.html`) | no target-vs-actual or pipeline |
| 16 | Projects board and lifecycle | products | `products/project_views.py`, `lifecycle.py` | stage | none | no portfolio table, dwell or plan-vs-actual |
| 17 | Lead list | leads | `leads/views.py:56` | none (paginated) | none | no counts, funnel, or filters |
| 18 | Global search | core | `apps/core/search.py` | text | none | search only |
| 19 | API docs (generated) | ingestion | `ingestion/docs.py` | product | none | documentation, not a report |

**Scheduled/e-mail reports:** none. Cron commands only send in-app/push reminders (`send_attendance_reminders`, `notify_todos`) or create tickets (`evaluate_rules`). **Count of existing report-like surfaces: 19** (5 with CSV export, plus print views for payslips and quotes).

---

## D. Missing / Partial report catalogue

Format: each report has a meta line (`Status · Audience · Value · Effort · Data · Freq · Score`). **Score = value ÷ effort** with High=3, Medium=2, Low=1 and S=1, M=2, L=3 (so 3.0 is the best possible). Paths are relative to the repo root. "Derived from ActivityLog" means the duration is rebuilt from `ActivityLog.created_at` + `metadata.from/to` + `target_object_id` (written by `apps/tickets/views.py:379-387` and `apps/errors/views.py:152`), because neither `Ticket` nor `ErrorGroup` has a `resolved_at` column; see section F.

### D1. Tickets (`apps/tickets/models.py`, `apps/dashboards/models.py`)

### RPT-001 · Ticket register export (CSV/Excel)
Status: PARTIAL · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: on-demand · Priority score: 2.0
- **Question:** Give me the filtered ticket list as a spreadsheet I can sort, share or attach to a client mail.
- **Sources:** `Ticket` (`number`, `title`, `ticket_type`, `status`, `priority`, `source`, `deadline`, `created_at`, `updated_at`, `product`, `assignees`, `created_by`, `milestone`, `linked_error_group`). The list already filters in `apps/tickets/views.py:63-100` (q, type, priority, product, assigned, overdue, status) but has no export route (`apps/tickets/urls.py`).
- **Filters & grouping:** same as list, plus created/updated date range.
- **Columns:** Key (`product.key`-`number`), title, type, status, priority, assignees, deadline, overdue flag, age in days.
- **Viz / Export:** table · CSV (reuse `apps/core/csvx.csv_response`) / Excel.

### RPT-002 · Ticket ageing (open backlog by age bucket)
Status: MISSING · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: weekly · Priority score: 3.0
- **Question:** How old is the open backlog, and which products or people are sitting on the oldest tickets?
- **Sources:** `Ticket.created_at`, `status` (open = not resolved/closed), `priority`, `product`, `assigned_to`.
- **Filters & grouping:** product, priority, assignee; buckets 0-2d, 3-7d, 8-14d, 15-30d, 30d+.
- **Metrics:** count per bucket; median and oldest age; % of open tickets older than 14 days.
- **Viz / Export:** stacked bar by product + table · CSV · weekly email.

### RPT-003 · Overdue and due-soon deadlines
Status: PARTIAL · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: daily · Priority score: 3.0
- **Question:** Which tickets are past their deadline or due in the next 3 / 7 days, and who owns them?
- **Sources:** `Ticket.deadline`, `status`, `assignees`, `priority`; `Ticket.is_overdue` (`models.py`). Only an `overdue` filter exists in the list (`tickets/views.py:92`).
- **Filters & grouping:** product, assignee, days-to-deadline window; group by assignee.
- **Metrics:** overdue count, days overdue, due-soon count, % of deadline-bearing tickets that are overdue.
- **Viz / Export:** table with red/amber chips · CSV · daily digest.

### RPT-004 · Ticket resolution time (TAT) by product, priority and assignee
Status: MISSING · Audience: Ops · Value: High · Effort: M · Data: READY · Freq: monthly · Priority score: 1.5
- **Question:** How long do tickets take from creation to resolved, and is it getting better?
- **Sources:** `Ticket.created_at`; resolved time derived from `ActivityLog` where `event_type='ticket_status_changed'`, `metadata.to in (resolved, closed)`, `target_object_id=ticket.pk`; `Ticket.priority`, `ticket_type`, `product`, `assignees`.
- **Filters & grouping:** period, product, type, priority, assignee; MoM comparison.
- **Metrics:** median / P90 hours to resolve; count resolved; % resolved within 3 / 7 days.
- **Viz / Export:** line (monthly median) + box-style table · CSV/PDF.
- **Caveat:** tickets changed through the SDK endpoint (`apps/ingestion/views.py:105`) may not write an ActivityLog row; verify before trusting, or add `resolved_at` (section F).

### RPT-005 · Time-in-status / bottleneck report
Status: MISSING · Audience: Ops · Value: High · Effort: M · Data: READY · Freq: monthly · Priority score: 1.5
- **Question:** Where do tickets wait: open, assigned, in progress, or testing?
- **Sources:** `ActivityLog` ticket status events (`metadata.from`, `metadata.to`, `created_at`), `Ticket.Status` choices (open, assigned, in_progress, testing, resolved, closed).
- **Filters & grouping:** product, priority, period; group by status.
- **Metrics:** average and P90 hours spent in each status; share of total lead time per status.
- **Viz / Export:** horizontal stacked bar (one bar per product) · CSV.

### RPT-006 · Created vs resolved trend and backlog burn
Status: PARTIAL · Audience: Owner · Value: High · Effort: S · Data: READY · Freq: weekly · Priority score: 3.0
- **Question:** Are we closing tickets faster than they arrive?
- **Sources:** `ActivityLog` `ticket_created` / `ticket_status_changed`; `get_summary_report` (`apps/dashboards/service.py:409`) already has day-level created/resolved, but only daily, no weekly/monthly roll-up, no previous-period overlay on the chart, and no export.
- **Filters & grouping:** week / month, product, type, priority.
- **Metrics:** created, resolved, net backlog change, resolution rate = resolved ÷ created.
- **Viz / Export:** dual line + net bars · CSV/PDF · scheduled weekly.

### RPT-007 · Ticket mix by type, source and priority
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** How much of our load is bugs vs features vs questions, and how much arrives automatically or from the customer portal?
- **Sources:** `Ticket.ticket_type`, `source` (manual / auto / customer_portal), `priority`, `product`, `created_at`.
- **Filters & grouping:** period, product; group by type × source.
- **Metrics:** counts and share; critical share; auto-created share.
- **Viz / Export:** stacked bars + pie · CSV.

### RPT-008 · Reopened tickets (quality exception)
Status: MISSING · Audience: Ops · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Which tickets were marked resolved/closed and then moved back, and who resolved them?
- **Sources:** `ActivityLog` ticket status events where `metadata.from in (resolved, closed)` and `metadata.to` is anything else; `actor`.
- **Filters & grouping:** product, assignee, period.
- **Metrics:** reopen count; reopen rate = reopened ÷ resolved; time resolved→reopened.
- **Viz / Export:** table + bar by assignee · CSV.

### RPT-009 · Unassigned and stale tickets
Status: MISSING · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: daily · Priority score: 3.0
- **Question:** Which open tickets have no owner, or have not been touched in N days?
- **Sources:** `Ticket.assignees` (empty), `Ticket.updated_at`, `status`, `priority`, last `TicketComment.created_at`.
- **Filters & grouping:** product, priority, stale threshold (default 7 days).
- **Metrics:** count unassigned; days since last update; critical/high unassigned count.
- **Viz / Export:** table · CSV · daily digest to owners/admins.

### RPT-010 · First-response and comment activity
Status: MISSING · Audience: Ops · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** How quickly does someone first comment on a new ticket, and who answers most?
- **Sources:** `TicketComment` (`created_at`, `author`, `ticket`), `Ticket.created_at`, `created_by`.
- **Filters & grouping:** product, author, period.
- **Metrics:** median time to first comment by someone other than the creator; comments per ticket; comments per author.
- **Viz / Export:** bar by author + trend line · CSV.

### RPT-011 · Milestone delivery report
Status: PARTIAL · Audience: Owner · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** Which milestones were hit, missed or slipped, and how many tickets sat behind each?
- **Sources:** `ProductMilestone` (`title`, `target_date`, `status`, `completed_at`, `order`, `computed_status`), `Ticket.milestone`.
- **Filters & grouping:** product, status, period.
- **Metrics:** days early/late = `completed_at` − `target_date`; on-time %; tickets per milestone and % resolved.
- **Viz / Export:** timeline/Gantt-style bar + table · PDF/CSV.
- **Note:** milestones are managed in the product page (`apps/products/urls.py` `milestone_*`); there is no cross-product view or export.

### RPT-012 · Auto-ticket rule effectiveness
Status: MISSING · Audience: Admin · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** Which automation rules fire, how many tickets they create, and are those tickets ever fixed or just noise?
- **Sources:** `AutoTicketRule` (`trigger_type`, `threshold_count`, `window_minutes`, `is_active`, `trigger_count`, `last_triggered_at`), `AutoTicketLog` (`matched_count`, `action_taken`, `ticket`), `Ticket.status` of the created ticket.
- **Filters & grouping:** product, rule, period.
- **Metrics:** fires per rule, tickets created, % of those tickets resolved, median time to resolve, rules never fired in 30 days.
- **Viz / Export:** table + sparkline · CSV.

### RPT-013 · Errors without a ticket / tickets without an error (linkage gap)
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** Which high-severity open error groups have nobody working on them?
- **Sources:** `ErrorGroup` (`severity`, `status`, `occurrence_count`, `last_seen`), `Ticket.linked_error_group` (null = no ticket).
- **Filters & grouping:** product, severity, min occurrences.
- **Metrics:** untracked error groups, occurrences they account for, days since `first_seen`.
- **Viz / Export:** table · CSV.

### D2. Errors and ingestion (`apps/ingestion/models.py`, `apps/errors/`)

### RPT-014 · Error trend by severity and product
Status: PARTIAL · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: daily · Priority score: 3.0
- **Question:** Is the error volume rising or falling, by product and severity?
- **Sources:** `ErrorOccurrence.created_at` joined to `ErrorGroup.severity`, `product`. The summary report counts `error_captured` ActivityLog events (first sighting only), not occurrences (`dashboards/service.py:460-500`).
- **Filters & grouping:** period, product, severity, environment (`ErrorOccurrence.environment`).
- **Metrics:** occurrences per day/week, new groups per day, MoM change.
- **Viz / Export:** stacked area · CSV/PDF.

### RPT-015 · Top errors by occurrences and users affected
Status: PARTIAL · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: weekly · Priority score: 3.0
- **Question:** Which 20 error groups hurt the most customers right now?
- **Sources:** `ErrorGroup.occurrence_count`, `affected_user_count`, `severity`, `status`, `last_seen`; the list sorts (`errors/views.py:64`) but has no impact score or export.
- **Filters & grouping:** product, status, period (needs `ErrorOccurrence.created_at` for period-bound counts).
- **Metrics:** occurrences in period, distinct `ErrorOccurrence.user_ref`, impact score = occurrences × severity weight.
- **Viz / Export:** ranked bar + table · CSV · weekly email.

### RPT-016 · Release quality scorecard
Status: MISSING · Audience: Owner · Value: High · Effort: M · Data: READY · Freq: per release · Priority score: 1.5
- **Question:** Did the last release make things better or worse?
- **Sources:** `ProductVersion` (`version_string`, `released_at`, `is_current`), `ErrorGroup.first_version`, `ErrorOccurrence.version`, `ErrorGroup.regressed_at` / `regression_count`, `Feedback.version`, `Feedback.rating`.
- **Filters & grouping:** product; one row per version.
- **Metrics:** new error groups introduced; occurrences per day since release; regressions; avg feedback rating; tickets opened in the 7 days after `released_at`.
- **Viz / Export:** table + sparkline per version · PDF/CSV.

### RPT-017 · Regression report
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** Which "fixed" errors came back, how often, and which release did it?
- **Sources:** `ErrorGroup.regressed_at`, `regression_count`, `first_version`, `status`; `ActivityLog` `error_resolved`; the list has only a `regressed=1` filter (`errors/views.py:60`).
- **Filters & grouping:** product, period, version.
- **Metrics:** regressed groups, repeat regressions (count ≥ 2), days between resolve and regression.
- **Viz / Export:** table · CSV.

### RPT-018 · Error resolution time (MTTR) and triage lag
Status: MISSING · Audience: Ops · Value: High · Effort: M · Data: READY · Freq: monthly · Priority score: 1.5
- **Question:** How long from first sighting to first human touch, and to resolved?
- **Sources:** `ErrorGroup.first_seen`; `ActivityLog` `error_status_changed` / `error_resolved` / `error_ignored` (`metadata.to`, `created_at`, `actor`).
- **Filters & grouping:** product, severity, period.
- **Metrics:** median time to first status change (triage lag); median to resolved; % resolved in 24h by severity.
- **Viz / Export:** bar by severity + trend · CSV.

### RPT-019 · Environment / OS / browser / device breakdown
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: on-demand · Priority score: 2.0
- **Question:** Is this error specific to one browser, OS, device, or environment (staging vs production)?
- **Sources:** `ErrorOccurrence.environment`, `os`, `browser`, `device`, `page`. These are written by `apps/ingestion/serializers.py:126-132`. `environment` and `page` appear only as per-occurrence rows (`templates/errors/partials/_occurrence_list.html:8`) and in the Discord embed (`apps/products/webhook.py:127-130`), never aggregated; `os`, `browser` and `device` are not read by any view or template (see section E).
- **Filters & grouping:** error group or product; group by each dimension.
- **Metrics:** occurrences and share per value; top 5 with "other".
- **Viz / Export:** donut/bar per dimension, on the error detail page and as a product report · CSV.

### RPT-020 · Page / URL hotspots
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** Which pages produce the most errors?
- **Sources:** `ErrorOccurrence.page`, `error_group`, `created_at`.
- **Filters & grouping:** product, period, severity.
- **Metrics:** occurrences and distinct error groups per page (normalised path).
- **Viz / Export:** ranked bar + table · CSV.

### RPT-021 · Customer impact: affected users per product
Status: MISSING · Audience: Owner · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** How many distinct end users hit an error, per product and week?
- **Sources:** `ErrorOccurrence.user_ref` (distinct), `created_at`, `ErrorGroup.product`; `ErrorGroup.affected_user_count` is a stored counter shown only on the detail page (`templates/errors/error_detail.html:41`).
- **Filters & grouping:** product, period, severity.
- **Metrics:** distinct users affected, errors per affected user, repeat-victim list (top user_refs).
- **Viz / Export:** line + table · CSV.

### RPT-022 · Untriaged error queue ageing
Status: MISSING · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: daily · Priority score: 3.0
- **Question:** Which error groups are still `open` (nobody investigating) and how long have they been?
- **Sources:** `ErrorGroup.status`, `severity`, `first_seen`, `last_seen`, `occurrence_count`.
- **Filters & grouping:** product, severity; ageing buckets on `first_seen`.
- **Metrics:** open count, oldest age, critical/high open > 24h.
- **Viz / Export:** table + bucket bars · CSV · daily digest.

### RPT-023 · Error spike early warning
Status: MISSING · Audience: Ops · Value: High · Effort: M · Data: READY · Freq: real-time/hourly · Priority score: 1.5
- **Question:** Is any error group suddenly running far above its normal rate?
- **Sources:** `ErrorOccurrence.created_at` hourly series per `error_group`; compare to trailing 7-day hourly average. Today only `evaluate_rules` thresholds fire (`apps/automation/management/commands/evaluate_rules.py`).
- **Filters & grouping:** product, severity.
- **Metrics:** ratio = last-hour count ÷ trailing average; z-score flag ≥ 3.
- **Viz / Export:** spark-lines + alert list · notification via `apps/notifications/service.notify`.

### D3. Customer feedback and success (`apps/feedback/`, `apps/ingestion/models.py`)

### RPT-024 · NPS / CSAT / CES trend and distribution
Status: PARTIAL · Audience: Owner · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** Is customer sentiment improving, and what is the promoter / passive / detractor split over time?
- **Sources:** `SurveyResponse.score`, `created_at`, `survey.survey_type`, `survey.product`; `Survey.compute_nps()` and `score_label()` (`feedback/models.py`). The CS hub (`feedback/views.py:215-270`) shows a current average per product and the survey page a single NPS number, with no time series and no export.
- **Filters & grouping:** product, survey, period; month-by-month.
- **Metrics:** NPS = %promoters (9-10) − %detractors (0-6); CSAT = % scoring 4-5; CES average; response count.
- **Viz / Export:** line + stacked 100% bar · PDF/CSV.

### RPT-025 · Detractor follow-up list
Status: MISSING · Audience: Sales · Value: High · Effort: S · Data: NEEDS NEW DATA (follow-up status) · Freq: weekly · Priority score: 3.0
- **Question:** Who gave a low score and left contact details, and has anyone called them back?
- **Sources:** `SurveyResponse.score`, `comment`, `contact_name`, `contact_email`, `user_ref`, `created_at`. Missing: `followed_up_at`, `followed_up_by`, `follow_up_note` on `SurveyResponse`.
- **Filters & grouping:** product, survey, score ≤ 6 (NPS) / ≤ 2 (CSAT).
- **Metrics:** detractors, days since response, % followed up.
- **Viz / Export:** action list · CSV.
- **Note:** the list itself is READY; only the "followed up" column needs new data.

### RPT-026 · In-app feedback ratings report
Status: MISSING · Audience: Owner · Value: High · Effort: S · Data: READY · Freq: weekly · Priority score: 3.0
- **Question:** What do users rate us (1-5) through the SDK, by product and version, and what do they say?
- **Sources:** `ingestion.Feedback` (`rating`, `comment`, `version`, `user_ref`, `screenshot_url`, `created_at`). Nothing reads this table except search (`apps/core/search.py:212`) and a webhook message; there is no list or report page.
- **Filters & grouping:** product, version, rating, period.
- **Metrics:** average rating, rating distribution, volume per week, % with comment, low-rating list with screenshots.
- **Viz / Export:** histogram + trend + comment table · CSV.

### RPT-027 · Survey performance and response rate
Status: PARTIAL · Audience: Ops · Value: Low · Effort: S · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Which surveys collect responses and which are dead?
- **Sources:** `Survey` (`status`, `survey_type`, `created_at`), `Survey.response_count`, `SurveyResponse.created_at`.
- **Filters & grouping:** product, status.
- **Metrics:** responses per survey, responses per week since launch, days since last response, active surveys with 0 responses.
- **Viz / Export:** table · CSV.
- **Note:** denominators (survey invites sent) are not stored, so a true response rate is **NEEDS NEW DATA** (`Survey.invited_count`).

### RPT-028 · Sentiment score trend
Status: PARTIAL · Audience: Owner · Value: Low · Effort: S · Data: NEEDS NEW DATA (a writer) · Freq: monthly · Priority score: 1.0
- **Question:** What is the −1…+1 sentiment trend per product, by source (survey, feedback, support, manual)?
- **Sources:** `SentimentRecord` (`score`, `source`, `recorded_at`, `summary`, `product`). Rows are only created by admin/seed; no code derives one from a survey or feedback, so a real report would be empty.
- **Filters & grouping:** product, source, period.
- **Metrics:** average score per month, count per source.
- **Viz / Export:** line · CSV.

### RPT-029 · SDK ticket intake log
Status: MISSING · Audience: Ops · Value: Low · Effort: S · Data: READY · Freq: weekly · Priority score: 1.0
- **Question:** What tickets do customer apps push to us through the API, and what became of them?
- **Sources:** `IngestedTicket` (`external_id`, `title`, `ticket_type`, `user_ref`, `metadata`, `created_at`, `product`); read today only by the status endpoint (`apps/ingestion/views.py:109`).
- **Filters & grouping:** product, type, period.
- **Metrics:** intake per week, per product; repeat reporters (`user_ref`).
- **Viz / Export:** table · CSV.

### D4. Projects and products (`apps/products/models.py`, `apps/products/lifecycle.py`)

### RPT-030 · Project portfolio status
Status: PARTIAL · Audience: Owner · Value: High · Effort: S · Data: READY · Freq: weekly · Priority score: 3.0
- **Question:** All projects on one page: stage, lead, planned dates, overdue or not, last update.
- **Sources:** `Product` (`stage`, `stage_changed_at`, `start_date`, `end_date`, `lead`, `server`), `ProjectLogEntry.created_at` (last update), `CrunchItem.done`, `ProductMilestone.computed_status`. The board (`products/project_views.py`) shows cards only; no export or overdue column.
- **Filters & grouping:** stage, lead, overdue; group by stage.
- **Metrics:** days in stage, days past `end_date`, open crunch items, open tickets.
- **Viz / Export:** table + stage funnel · PDF/CSV · weekly email.

### RPT-031 · Stage dwell time and project cycle time
Status: MISSING · Audience: Owner · Value: High · Effort: M · Data: READY · Freq: monthly · Priority score: 1.5
- **Question:** How long does a project spend in FE, BE, Deploy, Testing, UAT, and where do we get stuck?
- **Sources:** `ProjectLogEntry` where `kind='stage'` (`from_stage`, `to_stage`, `created_at`, `author`) — append-only by design (`lifecycle.py` docstring); `Product.start_date`; the nine stages in `lifecycle.STAGES`.
- **Filters & grouping:** stage, project, period; presets (`PRESETS` skip stages).
- **Metrics:** average days per stage; total days creation→live; stage skips and backward moves.
- **Viz / Export:** stacked horizontal bar per project · CSV.

### RPT-032 · Planned vs actual hours per project
Status: MISSING · Audience: Owner · Value: High · Effort: M · Data: READY · Freq: monthly · Priority score: 1.5
- **Question:** Are projects burning more hours than planned?
- **Sources:** `PhasePlan.planned_hours` (per product and phase) vs `DSREntry.hours_spent` summed by `product`. Per-phase actuals are not possible because `DSREntry` has no phase column (see section F).
- **Filters & grouping:** product, period, person.
- **Metrics:** planned total, actual total, variance = actual − planned, % burned, projected finish if burn rate continues.
- **Viz / Export:** bullet bar per project · CSV/PDF.

### RPT-033 · Schedule slippage
Status: MISSING · Audience: Owner · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Which projects moved their dates, how often, and by how much?
- **Sources:** `ProjectLogEntry` `kind='schedule'` (`meta` JSON, `body`), `Product.end_date`, `PhasePlan.end_date`, overdue `ProductMilestone`.
- **Filters & grouping:** product, period.
- **Metrics:** reschedule count; days slipped (from `meta`); projects past `end_date` and not in `live`/`close`.
- **Viz / Export:** table + timeline · CSV.

### RPT-034 · Crunch and blocker register
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** What is blocking or crunching each project, how old is it?
- **Sources:** `CrunchItem` (`feature`, `due_date`, `done`, `done_at`, `reason`), `ProjectLogEntry` `kind in ('blocker','crunch')`.
- **Filters & grouping:** product, done/open, overdue.
- **Metrics:** open items, overdue count, average days to done, blockers per project.
- **Viz / Export:** table · CSV.

### RPT-035 · Project hours by person and category
Status: PARTIAL · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** Who spent how many hours on which project, and on what kind of work?
- **Sources:** `DSREntry` (`hours_spent`, `product`, `user`, `category`, `date`). The DSR log lists rows with a CSV (`apps/dsr/views.py:467`) but offers no pivot or totals by project × person.
- **Filters & grouping:** period, product, person; pivot product × person, product × category.
- **Metrics:** hours, share of total, hours per ticket resolved.
- **Viz / Export:** stacked bar + pivot table · CSV/Excel.

### RPT-036 · Project profitability (quote vs actual cost)
Status: MISSING · Audience: Finance · Value: High · Effort: L · Data: NEEDS NEW DATA (`Estimate.product` link) · Freq: monthly · Priority score: 1.0
- **Question:** Did the project make the margin we quoted?
- **Sources:** quoted `price` / `cost` from `costing.views._figures` (from `Estimate.people`, `others`, `margin_percent`, `pitch_price`); actual cost = `DSREntry.hours_spent` × `payroll.service.effective_rate`; plus `Expense` for the project. Missing: `Estimate.product` (or `Product.estimate`) and `Expense.product`.
- **Filters & grouping:** project, client, period.
- **Metrics:** Margin % = (Price − Actual cost) ÷ Price; variance to quoted margin; hours overrun.
- **Viz / Export:** waterfall + table · PDF/CSV.

### RPT-037 · Project team allocation
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** Who is on which projects, and who is spread too thin?
- **Sources:** `PodMember` (`product`, `user`), `ProductAccess`, `Product.lead`, DSR hours last 4 weeks.
- **Filters & grouping:** person, product.
- **Metrics:** projects per person, hours per project last 28 days, projects with no pod member.
- **Viz / Export:** person × project heat-grid · CSV.

### RPT-038 · Hosting and server inventory
Status: MISSING · Audience: Admin · Value: Low · Effort: S · Data: READY · Freq: on-demand · Priority score: 1.0
- **Question:** Which project lives on which server, path and stack?
- **Sources:** `Product.server`, `server_path`, `tech_stack`, `default_environment`, `discord_webhook_url` (configured yes/no); `serop.SeropSharedServer` (`name`, `host`, `connection_type`, `is_shareable`, `owner`). Never show `encrypted_password`.
- **Filters & grouping:** server, stack.
- **Metrics:** projects per server, projects with no server, servers with no project.
- **Viz / Export:** table · CSV.

### RPT-039 · API key hygiene
Status: MISSING · Audience: Auditor · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** Which API keys are stale, expiring, revoked, or never used?
- **Sources:** `APIKey` (`product`, `name`, `prefix`, `is_active`, `created_at`, `revoked_at`, `last_used_at`, `expires_at`, `state`); `ActivityLog` `api_key_created` / `api_key_revoked` for who.
- **Filters & grouping:** product, state.
- **Metrics:** days since `last_used_at`, days to `expires_at`, never-used keys older than 7 days.
- **Viz / Export:** table with flags · CSV.

### RPT-040 · Product access matrix
Status: MISSING · Audience: Auditor · Value: Medium · Effort: S · Data: READY · Freq: quarterly · Priority score: 2.0
- **Question:** Who can see which product, and through which route (owner/admin, `ProductAccess`, pod)?
- **Sources:** `Membership.role`, `ProductAccess`, `PodMember`; rule in `apps/products/access.py`.
- **Filters & grouping:** user, product, role.
- **Metrics:** user × product matrix; people with access to everything; products with only one person.
- **Viz / Export:** matrix · PDF/CSV (signed-off access review).

### RPT-041 · Client project status report
Status: MISSING · Audience: Client · Value: High · Effort: M · Data: READY · Freq: weekly/on-demand · Priority score: 1.5
- **Question:** One shareable page per project: stage, milestones, last updates, open issues.
- **Sources:** `Product.stage`, `end_date`, `ProductMilestone`, `ProjectLogEntry` (`kind in update/decision/stage`), `Ticket` counts by status, `ErrorGroup` open count. Exclude `blocker`/`correction` text and internal notes by default.
- **Filters & grouping:** product, date range.
- **Metrics:** % milestones done, tickets resolved this period, open critical items.
- **Viz / Export:** progress bar + timeline · PDF · scheduled email.

### RPT-042 · Project delivery risk score
Status: MISSING · Audience: Owner · Value: High · Effort: M · Data: READY · Freq: weekly · Priority score: 1.5
- **Question:** Which projects are most likely to miss their date?
- **Sources:** overdue milestones, open `CrunchItem`, `blocker` log entries, overdue tickets (`Ticket.deadline`), days past `Product.end_date`, hours burn vs `PhasePlan.planned_hours`.
- **Filters & grouping:** stage, lead.
- **Metrics:** weighted score 0-100 (weights editable); top contributing factor per project.
- **Viz / Export:** ranked table with traffic lights · email to owners.

### D5. Leads / sales (`apps/leads/models.py`)

### RPT-043 · Lead funnel and conversion
Status: MISSING · Audience: Sales · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** How many leads reach contacted → qualified → converted, and how many are lost?
- **Sources:** `Lead.status` (new/contacted/qualified/converted/lost), `created_at`, `converted_at`, `LeadLog` `kind='status'`. The lead list (`leads/views.py:56`) has no filters, counts or export.
- **Filters & grouping:** period, `need`, company.
- **Metrics:** leads per month; stage-to-stage % ; conversion % = converted ÷ total; lost %.
- **Viz / Export:** funnel + monthly bars · CSV/PDF.

### RPT-044 · Speed to first contact
Status: MISSING · Audience: Sales · Value: High · Effort: S · Data: READY · Freq: weekly · Priority score: 3.0
- **Question:** How long does a new website lead wait before someone touches it?
- **Sources:** `Lead.created_at`, first `LeadLog.created_at` (`author`), `Lead.status`.
- **Filters & grouping:** period, author.
- **Metrics:** median / P90 hours to first log; leads untouched > 24h.
- **Viz / Export:** histogram + untouched list · CSV · daily alert.

### RPT-045 · Stale leads
Status: MISSING · Audience: Sales · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** Which open leads have not moved for N days?
- **Sources:** `Lead.status` not in converted/lost, latest `LeadLog.created_at`, `created_at`.
- **Filters & grouping:** status, need, idle days.
- **Metrics:** days idle, count by status.
- **Viz / Export:** table · CSV.

### RPT-046 · Demand by need and lead-to-project time
Status: MISSING · Audience: Owner · Value: Medium · Effort: S · Data: READY · Freq: quarterly · Priority score: 2.0
- **Question:** What do prospects ask for most, which kinds convert, and how long does conversion take?
- **Sources:** `Lead.need`, `company_name`, `status`, `converted_at − created_at`, `Lead.product` (the project created).
- **Filters & grouping:** period; group by `need`.
- **Metrics:** leads and conversion % per need; median days to convert.
- **Viz / Export:** bar + table · CSV.

### RPT-047 · Lead source, owner and lost reason
Status: MISSING · Audience: Sales · Value: High · Effort: M · Data: NEEDS NEW DATA (`Lead.source`/utm, `Lead.owner`, `Lead.lost_reason`, `Lead.expected_value`) · Freq: monthly · Priority score: 1.5
- **Question:** Which channel brings leads that convert, who owns them, and why do we lose them?
- **Sources:** none of these fields exist on `Lead`; the closest are `LeadLog.author` and free-text log lines.
- **Filters & grouping:** source, owner, period.
- **Metrics:** conversion by source; pipeline value; loss reasons.
- **Viz / Export:** bar + table · CSV.

### RPT-048 · Duplicate and repeat leads
Status: MISSING · Audience: Sales · Value: Low · Effort: S · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Same email or phone submitted more than once?
- **Sources:** `Lead.email`, `phone`, `company_name`, `created_at`.
- **Filters & grouping:** period.
- **Metrics:** duplicate groups, repeat count, days between submissions.
- **Viz / Export:** table · CSV.

### D6. Costing / quotes (`apps/costing/`)

### RPT-049 · Quote margin analysis (realised vs target)
Status: PARTIAL · Audience: Finance · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** Are our pitched prices leaving the margin we aim for, and how much do we discount?
- **Sources:** `Estimate.margin_percent`, `margin_mode`, `pitch_price`, computed `price`/`cost` (`costing/views.py:56-65`). The list shows totals, by client and by month, plus a CSV (`EstimateExportView`); it does not compare pitch to computed price or margin to target.
- **Filters & grouping:** month, client, margin_mode.
- **Metrics:** Discount % = (computed price − pitch) ÷ computed price; realised margin vs `margin_percent`; quotes below target.
- **Viz / Export:** scatter (cost vs price) + table · CSV.

### RPT-050 · Quote cost composition
Status: MISSING · Audience: Finance · Value: Medium · Effort: S · Data: READY · Freq: quarterly · Priority score: 2.0
- **Question:** What share of our quoted cost is people, rent, AI subscriptions and others?
- **Sources:** `Estimate.people` (JSON rows), `others`, `rent_monthly`, `ai_per_person_month`, `dedicated_days`, `client_days`.
- **Filters & grouping:** period, client.
- **Metrics:** people %, rent %, AI %, other %; average cost per person-day.
- **Viz / Export:** stacked bar · CSV.
- **Note:** numbers are strings and JSON, so aggregation must reuse `costing.service.compute`.

### RPT-051 · Quote pipeline win/loss
Status: MISSING · Audience: Sales · Value: High · Effort: M · Data: NEEDS NEW DATA (`Estimate.status` draft/sent/won/lost, `Estimate.lead` FK) · Freq: monthly · Priority score: 1.5
- **Question:** How many quotes become projects, and what do the lost ones look like?
- **Sources:** `Estimate` has no status or link to `Lead`/`Product`.
- **Filters & grouping:** client, month.
- **Metrics:** win rate; value won vs lost; quote-to-project time.
- **Viz / Export:** funnel · CSV.

### D7. Expenses (`apps/expenses/models.py`)

### RPT-052 · Monthly expense trend by category
Status: PARTIAL · Audience: Finance · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** How is spend moving month on month — tea, milk, AI, server, trips?
- **Sources:** `Expense.amount_paise`, `date`, `category`, `category_other`. The list has one month at a time with totals by person and category (`expenses/views.py:81-124`).
- **Filters & grouping:** 12-month window, category, person.
- **Metrics:** monthly total, MoM %, 3-month average, recurring (AI, server) commitments.
- **Viz / Export:** stacked column + table · CSV/PDF.

### RPT-053 · Reimbursement ageing
Status: MISSING · Audience: Finance · Value: High · Effort: S · Data: READY · Freq: weekly · Priority score: 3.0
- **Question:** Who has paid out of pocket and is still waiting to be repaid, for how long?
- **Sources:** `Expense.paid_by`, `amount_paise`, `date`, `to_salary`, `repaid_on`, `paid_in_run`.
- **Filters & grouping:** person; buckets 0-30, 31-60, 60+ days since `date`.
- **Metrics:** outstanding ₹ per person, count, oldest item; sent to salary but not yet in a locked run.
- **Viz / Export:** table + bucket bars · CSV · monthly email to finance.

### RPT-054 · Expense ↔ payroll reconciliation
Status: MISSING · Audience: Finance · Value: Medium · Effort: M · Data: READY · Freq: per payroll run · Priority score: 1.0
- **Question:** Do the expenses marked "to salary" match the reimbursement lines on each payslip?
- **Sources:** `Expense.to_salary`, `paid_in_run`, `amount_paise` (÷100) vs `Payslip.reimbursement`, `Payslip.run`, `user`.
- **Filters & grouping:** run, person.
- **Metrics:** difference per person per run; expenses flagged but no run; run reimbursement with no expense.
- **Viz / Export:** reconciliation table · CSV.

### RPT-055 · Expense exceptions and possible duplicates
Status: MISSING · Audience: Auditor · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** Large single items, repeated identical amounts, or entries recorded long after the date?
- **Sources:** `Expense.amount_paise`, `date`, `category`, `paid_by`, `created_by`, `created_at`; `ExpenseComment` queries.
- **Filters & grouping:** period, person, category.
- **Metrics:** items above P95; same amount + category + person within 3 days; `created_at` − `date` > 7 days; `created_by ≠ paid_by` count.
- **Viz / Export:** exception table · CSV.

### RPT-056 · Spend per project
Status: MISSING · Audience: Finance · Value: Medium · Effort: M · Data: NEEDS NEW DATA (`Expense.product`) · Freq: monthly · Priority score: 1.0
- **Question:** How much non-payroll money does each project consume?
- **Sources:** `Expense` has no project link.
- **Filters & grouping:** product, category, month.
- **Metrics:** spend per project, per head.
- **Viz / Export:** bar · CSV.

### D8. Payroll (`apps/payroll/models.py`, `apps/payroll/service.py`)

### RPT-057 · Payroll cost trend per cycle
Status: PARTIAL · Audience: Finance · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** What did payroll cost each cycle, and how are gross, deductions and headcount moving?
- **Sources:** `PayrollRun` (`period_start`, `period_end`, `working_days`, `is_locked`), `Payslip` (`gross`, `deduction`, `late_penalty`, `reimbursement`). `run_list` and the run CSV show one run at a time (`payroll/views.py:164-176`).
- **Filters & grouping:** 12 / 24 cycles, locked only.
- **Metrics:** total gross, total deduction, headcount, gross per head, MoM %.
- **Viz / Export:** line/column + table · CSV/PDF.

### RPT-058 · Deduction analysis (leave vs lateness)
Status: MISSING · Audience: Finance · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** How much money is withheld for unpaid leave, late half-days and late penalties, and from whom?
- **Sources:** `Payslip.deduction`, `unpaid_leave_days`, `late_half_days`, `late_penalty`, `daily_rate`, `half_day_value`, `user`, `run`.
- **Filters & grouping:** run/period, person.
- **Metrics:** ₹ from unpaid leave = `unpaid_leave_days × daily_rate`; ₹ from late half-days = `late_half_days × half_day_value`; late penalties; share of gross.
- **Viz / Export:** stacked bar by person + table · CSV.

### RPT-059 · Payroll variance run-over-run
Status: MISSING · Audience: Finance · Value: High · Effort: S · Data: READY · Freq: per run · Priority score: 3.0
- **Question:** Whose pay changed since last cycle, and why?
- **Sources:** `Payslip.gross`, `payable_days`, `unpaid_leave_days`, `late_penalty`, `reimbursement`, `profile`; two consecutive `PayrollRun`s.
- **Filters & grouping:** run vs previous run; threshold (default ±5%).
- **Metrics:** Δ gross ₹ and %; flagged cause (rate change, leave, lateness, reimbursement, joiner/leaver).
- **Viz / Export:** variance table · CSV; run before locking.

### RPT-060 · Salary revision history
Status: MISSING · Audience: HR · Value: Medium · Effort: S · Data: READY · Freq: yearly/on-demand · Priority score: 2.0
- **Question:** When did each person's salary change, by how much?
- **Sources:** `PayrollProfile` (`user`, `monthly_salary`, `daily_rate`, `effective_from`, `is_on_payroll`, `notes`) — dated rows are kept on purpose.
- **Filters & grouping:** person, period.
- **Metrics:** raise % between consecutive rows; months since last revision; current salary distribution.
- **Viz / Export:** step line per person + table · CSV (restricted to owner/admin).

### RPT-061 · Payroll completeness exceptions
Status: MISSING · Audience: Finance · Value: High · Effort: S · Data: READY · Freq: per run · Priority score: 3.0
- **Question:** Is anyone who should be paid missing from the run, or paid a zero slip?
- **Sources:** `PayrollProfile.is_on_payroll`, `monthly_salary` / `daily_rate` null or 0, `Membership` (active members), `Payslip` for the run.
- **Filters & grouping:** run.
- **Metrics:** on-payroll people without a payslip; slips with `gross = 0`; members with no profile; profile with no salary.
- **Viz / Export:** exception list · CSV.

### RPT-062 · Employee annual earnings statement
Status: MISSING · Audience: Client (employee) · Value: Medium · Effort: M · Data: READY · Freq: yearly · Priority score: 1.0
- **Question:** A person's total pay, deductions and reimbursements for a financial year, in one document.
- **Sources:** all `Payslip` rows per `user` joined to `PayrollRun.period_end`; month-wise `gross`, `deduction`, `late_penalty`, `reimbursement`, `currency`. The member-only slip view exists (`payroll/urls.py` `my_payslips`).
- **Filters & grouping:** FY (April-March), person.
- **Metrics:** totals and monthly table.
- **Viz / Export:** table · PDF (employee self-serve + admin).

### RPT-063 · Statutory deduction summary (PF / ESI / TDS)
Status: MISSING · Audience: Finance · Value: High · Effort: L · Data: NEEDS NEW DATA (`Payslip` PF/ESI/TDS/professional-tax fields, tax identifiers on profile) · Freq: monthly · Priority score: 1.0
- **Question:** What do we owe the authorities this month?
- **Sources:** nothing in `Payslip` or `PayrollProfile` (only `gross`, `deduction` for leave). `Payslip.breakdown` is a JSON of the calculation, not statutory lines.
- **Filters & grouping:** run, person.
- **Metrics:** employee + employer share per head; challan totals.
- **Viz / Export:** table · CSV in the portal format.

### D9. Attendance (`apps/attendance/models.py`, `apps/attendance/service.py`)

### RPT-064 · Lateness and penalty ledger
Status: PARTIAL · Audience: HR · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** Who is late, how often, how many minutes, and what does it cost?
- **Sources:** `AttendanceRecord.check_in`, `WorkShift` bands (`grace_minutes`, `minor_band_end_minutes`, `major_band_end_minutes`, `minor_penalty`, `major_penalty`), `service.lateness_for`, `late_penalty_for`, `late_penalties_in_period`, `Membership.late_exempt`. The timesheet CSV has only a count of late days (`attendance/views.py:676`).
- **Filters & grouping:** month/cycle (27th-26th), person.
- **Metrics:** late days, total late minutes, average lateness, ₹ penalty per person, exempt people listed.
- **Viz / Export:** table + bar · CSV/PDF.

### RPT-065 · Arrival-time and punctuality pattern
Status: MISSING · Audience: HR · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** When do people really arrive, by weekday and by person?
- **Sources:** `AttendanceRecord.check_in` (local time), `WorkShift.start_time`.
- **Filters & grouping:** month range, person; weekday × week grid.
- **Metrics:** minutes after shift start; share on time; Monday/Friday late share.
- **Viz / Export:** heatmap (weekday × person) · PNG/CSV.

### RPT-066 · Overtime and short-hours
Status: MISSING · Audience: HR · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** Who works above or below the standard day?
- **Sources:** `service.net_minutes_for(record, shift)` (net of `break_minutes`) vs `WorkShift.worked_minutes_per_day`; `AttendanceRecord.date` (not weekly off).
- **Filters & grouping:** month, person.
- **Metrics:** net hours per day; overtime = net − standard; days short by > 30 min; average per day.
- **Viz / Export:** diverging bar per person · CSV.

### RPT-067 · Missing check-out / unclosed days exception
Status: PARTIAL · Audience: HR · Value: High · Effort: S · Data: READY · Freq: daily · Priority score: 3.0
- **Question:** Which days were never closed (no check-out), by whom, and are they still open?
- **Sources:** `AttendanceRecord.check_in`, `check_out` null, `is_stale`, `service.unclosed_days`, `missing_checkout_label`. Currently per-person reminders only (`management/commands/send_attendance_reminders.py`); admins have no consolidated list.
- **Filters & grouping:** month, person.
- **Metrics:** unclosed day count, oldest, repeat offenders; corrections pending for those days.
- **Viz / Export:** table · CSV · daily digest.

### RPT-068 · Manual attendance edit audit
Status: MISSING · Audience: Auditor · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** Which attendance rows were edited by hand, by whom, and what changed?
- **Sources:** `AttendanceRecord.is_edited`, `updated_at`; `ActivityLog` `attendance_edited` (`actor`, `description`, `created_at`); original times only exist for corrections (`AttendanceCorrection.original_check_in/out`).
- **Filters & grouping:** month, person, editor.
- **Metrics:** edit count per person and per editor; edits that remove lateness; edits by someone for themselves.
- **Viz / Export:** table · CSV/PDF.
- **Note:** direct admin edits keep no "before" value (see section F).

### RPT-069 · Attendance correction analytics and risk flags
Status: MISSING · Audience: Auditor · Value: High · Effort: M · Data: READY · Freq: weekly · Priority score: 1.5
- **Question:** Who asks for the most corrections, how big are they, and which ones look unusual?
- **Sources:** `AttendanceCorrection` (`requested_check_in/out`, `original_check_in/out`, `reason`, `status`, `decided_by`, `decided_at`, `created_at`), `WorkShift.start_time`. Ties to the open concern about blind approvals (memory note on corrections).
- **Filters & grouping:** month, person, status, approver.
- **Metrics:** requests per person per month; hours added = requested span − original span; before-shift-start requests; third-in-month flag; approval % and turnaround; self-decided cases.
- **Viz / Export:** table with flags + bar · CSV; weekly digest to owners.

### RPT-070 · Absenteeism and pattern report
Status: MISSING · Audience: HR · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Who is absent without leave, and is there a pattern (Mondays, Fridays, after holidays)?
- **Sources:** working days (`WorkShift.weekly_off_days`, `Holiday.date`), `AttendanceRecord` (none), approved `LeaveRequest` dates (`service.leave_dates`).
- **Filters & grouping:** month/quarter, person.
- **Metrics:** unexplained absent days; absence rate = absent ÷ working days; weekday distribution; Bradford factor = S² × D.
- **Viz / Export:** bar + weekday heat strip · CSV.

### RPT-071 · Work on weekly off / holiday
Status: MISSING · Audience: HR · Value: Low · Effort: S · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Who worked on a Saturday, Sunday or company holiday?
- **Sources:** `AttendanceRecord.date`, `check_in/out`, `WorkShift.is_weekly_off`, `Holiday.date`.
- **Filters & grouping:** month, person.
- **Metrics:** days worked on off-days, hours; candidates for comp-off.
- **Viz / Export:** table · CSV.

### RPT-072 · Attendance vs DSR reconciliation
Status: MISSING · Audience: Ops · Value: High · Effort: M · Data: READY · Freq: weekly · Priority score: 1.5
- **Question:** Does the time people punch match the time they log on work?
- **Sources:** `service.net_minutes_for` per `AttendanceRecord` vs `DSREntry.hours_spent` summed per user per `date`.
- **Filters & grouping:** week/month, person.
- **Metrics:** Utilisation % = DSR hours ÷ net punched hours; days with attendance but no DSR; days with DSR but no punch; gap > 2h.
- **Viz / Export:** scatter + table · CSV.

### RPT-073 · Team presence and app usage hours
Status: MISSING · Audience: Admin · Value: Low · Effort: M · Data: NEEDS NEW DATA (history; `PresenceSession` rows are deleted after 5 min) · Freq: monthly · Priority score: 0.5
- **Question:** When is the team actually in the app?
- **Sources:** `PresenceSession` (`connected_at`, `last_seen`, `path`, `activity`) is purged by `apps/presence/service.py:73` (`PURGE_AFTER = 5 min`), so it is live state, not history. Needs a durable daily roll-up.
- **Metrics:** active minutes per user per day; most used areas.
- **Viz / Export:** heatmap · CSV.

### D10. Leave (`apps/leave/models.py`, `apps/leave/service.py`)

### RPT-074 · Company leave balance register
Status: PARTIAL · Audience: HR · Value: High · Effort: S · Data: READY · Freq: monthly · Priority score: 3.0
- **Question:** For every employee and leave type: allowed, used, pending, remaining.
- **Sources:** `LeavePolicy.max_days_per_year`, `LeaveRequest` (`paid_days`, `unpaid_days`, `status`, `policy`, `start_date`), `service.balance_for`. `balances_for` is shown per person only (`leave/views.py:130`).
- **Filters & grouping:** year, policy, person.
- **Metrics:** paid used, unpaid taken, pending, remaining = cap − paid used.
- **Viz / Export:** person × policy matrix · CSV/PDF.

### RPT-075 · Leave utilisation and seasonality
Status: MISSING · Audience: HR · Value: Medium · Effort: S · Data: READY · Freq: quarterly · Priority score: 2.0
- **Question:** How much leave is taken, when, and for what type?
- **Sources:** `LeaveRequest` (`start_date`, `end_date`, `days`, `is_half_day`, `policy`, `status='approved'`).
- **Filters & grouping:** month, policy, person.
- **Metrics:** days per month; per policy; per head; peak weeks.
- **Viz / Export:** column + calendar heat · CSV.

### RPT-076 · Unpaid-leave cost
Status: MISSING · Audience: Finance · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** How many unpaid days were taken and what did it save?
- **Sources:** `LeaveRequest.unpaid_days`, `split_mode`, `PayrollProfile` rates via `payroll.service.effective_rate`; `Payslip.unpaid_leave_days`.
- **Filters & grouping:** cycle, person.
- **Metrics:** unpaid days, ₹ = days × daily rate.
- **Viz / Export:** bar · CSV.

### RPT-077 · Leave approval turnaround and approver workload
Status: MISSING · Audience: HR · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** How fast are leave requests decided, and by whom?
- **Sources:** `LeaveRequest.created_at`, `decided_at`, `decided_by`, `status`, `decision_note`; `Membership.is_leave_approver`.
- **Filters & grouping:** period, approver.
- **Metrics:** median hours to decision; pending > 48h; approve/reject ratio per approver; requests decided after the leave started.
- **Viz / Export:** bar + table · CSV.

### RPT-078 · Over-cap and auto-split leave exceptions
Status: MISSING · Audience: Auditor · Value: Low · Effort: S · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Which approved requests were split into paid and unpaid parts, and did anyone override the split?
- **Sources:** `LeaveRequest.split_mode` (auto/manual), `paid_days`, `unpaid_days`, `decided_by`, `LeavePolicy` caps.
- **Filters & grouping:** period, policy.
- **Metrics:** requests with `unpaid_days > 0` on a paid policy; manual overrides.
- **Viz / Export:** table · CSV.

### RPT-079 · Capacity outlook (leave + holidays, next 30 days)
Status: PARTIAL · Audience: Ops · Value: Medium · Effort: M · Data: READY · Freq: weekly · Priority score: 1.0
- **Question:** How many people are available each day, and how many planned hours does that cover?
- **Sources:** approved/pending `LeaveRequest`, `Holiday`, weekly off, `PhasePlan.planned_hours`. The leave calendar (`leave/views.py:639`) shows who is off but no headcount per day, no planned vs available hours, and no export.
- **Filters & grouping:** date window, team.
- **Metrics:** available people/day; available hours; planned hours in window.
- **Viz / Export:** line + calendar · CSV.

### D11. DSR / time (`apps/dsr/models.py`)

### RPT-080 · DSR compliance (missing and late reports)
Status: MISSING · Audience: Ops · Value: High · Effort: S · Data: READY · Freq: daily/weekly · Priority score: 3.0
- **Question:** Who did not file a daily status report on a working day?
- **Sources:** `DSREntry.date`, `user`; working days from `WorkShift`, `Holiday`, approved leave; `dsr.service.submission_window`.
- **Filters & grouping:** week/month, person.
- **Metrics:** days without entry; late entries (entry `created_at` after day end); streaks.
- **Viz / Export:** person × day grid · CSV · daily reminder list.

### RPT-081 · Work-type mix
Status: MISSING · Audience: Owner · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** How much time goes to features, bug fixes, reviews, meetings and admin?
- **Sources:** `DSREntry.category` (ticket, bug_fix, feature, code_review, meeting, documentation, administration, other), `hours_spent`, `user`, `product`.
- **Filters & grouping:** period, person, product.
- **Metrics:** hours and % by category; meeting + admin overhead %.
- **Viz / Export:** stacked bar · CSV.

### RPT-082 · DSR data quality (auto-logged, unverified, no time)
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** How much logged time is auto-generated and never confirmed?
- **Sources:** `DSREntry.is_auto_logged`, `source`, `source_id`, `hours_spent` (0), `elapsed_hours`, `status`; model helpers `unverified`, `needs_time`.
- **Filters & grouping:** period, person.
- **Metrics:** entries with 0 hours; auto-logged share; entries where `hours_spent` far from `elapsed_hours`.
- **Viz / Export:** table · CSV.

### RPT-083 · Ticket effort vs elapsed
Status: MISSING · Audience: Ops · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** For resolved tickets, how many hours were logged vs how long they took?
- **Sources:** `DSREntry.ticket`, `hours_spent`, `elapsed_hours`; `Ticket.created_at`, resolved time from ActivityLog; `ticket_type`, `priority`.
- **Filters & grouping:** type, priority, product, assignee.
- **Metrics:** average logged hours by type/priority; logged ÷ elapsed; outliers.
- **Viz / Export:** scatter + table · CSV.

### RPT-084 · Blocked work register
Status: MISSING · Audience: Ops · Value: Medium · Effort: S · Data: READY · Freq: weekly · Priority score: 2.0
- **Question:** Which tasks are logged as `blocked`, for how long, on which project?
- **Sources:** `DSREntry.status='blocked'`, `task_name`, `notes`, `product`, `user`, `date`.
- **Filters & grouping:** product, person, period.
- **Metrics:** blocked entries, repeated blocked task names, days blocked.
- **Viz / Export:** table · CSV.

### RPT-085 · Personal to-do completion
Status: MISSING · Audience: Ops · Value: Low · Effort: S · Data: READY · Freq: weekly · Priority score: 1.0
- **Question:** How many own to-dos are done on time? (self-service only; to-dos are private)
- **Sources:** `dashboards.Todo` (`done`, `due`, `completed_at`, `priority`, `hours_spent`, `user`).
- **Filters & grouping:** period.
- **Metrics:** completion %; overdue; hours per task.
- **Viz / Export:** none/mini bar on home · none.

### D12. Admin, compliance and system (`apps/accounts/`, `apps/dashboards/`, `apps/notifications/`)

### RPT-086 · Audit log export
Status: PARTIAL · Audience: Auditor · Value: High · Effort: S · Data: READY · Freq: on-demand/monthly · Priority score: 3.0
- **Question:** Give an auditor the filtered change log as a file.
- **Sources:** `ActivityLog` (`event_type`, `title`, `description`, `actor`, `target_content_type`, `target_object_id`, `metadata`, `created_at`). `AuditLogView` (`dashboards/views.py:95`) filters by category, type, actor, date, text but renders HTML only.
- **Filters & grouping:** same as view.
- **Metrics:** one row per event with actor name, resolved target.
- **Viz / Export:** table · CSV/PDF · scheduled monthly archive.

### RPT-087 · Access and role change report
Status: PARTIAL · Audience: Auditor · Value: High · Effort: S · Data: READY · Freq: quarterly · Priority score: 3.0
- **Question:** Who joined, left, got a new role or product access, and who approved it?
- **Sources:** `ActivityLog` `member_joined`, `member_removed`, `member_role_changed`, `access_granted`, `access_revoked`; current `Membership`.
- **Filters & grouping:** period, actor.
- **Metrics:** changes per period; admins added; access granted without removal; current owners/admins list.
- **Viz / Export:** table · PDF/CSV (access review sign-off).

### RPT-088 · Sign-in, token and dormant-user report
Status: MISSING · Audience: Admin · Value: Medium · Effort: S · Data: NEEDS NEW DATA (login history table) · Freq: monthly · Priority score: 2.0
- **Question:** Who has not logged in for 30 days; which desktop-app tokens are in use, from which IP?
- **Sources:** `User.last_login`, `ExternalAccessToken` (`client_id`, `created_at`, `last_used_at`, `last_used_ip`, `expires_at`, `revoked_at`) — today only the profile page shows own tokens (`templates/accounts/profile.html:88`). Full history of sign-ins and failures is not stored.
- **Filters & grouping:** role, days inactive.
- **Metrics:** dormant users; active tokens; tokens unused 30 days; tokens expiring in 14 days.
- **Viz / Export:** table · CSV.
- **Note:** the dormant-user and token parts are READY today; per-login history needs `LoginEvent`.

### RPT-089 · Feature adoption by module
Status: MISSING · Audience: Admin · Value: Medium · Effort: S · Data: READY · Freq: monthly · Priority score: 2.0
- **Question:** Which modules does the team actually use?
- **Sources:** `ActivityLog.event_type` grouped by module prefix (ticket_, error_, leave_, attendance_, payroll_, project_, survey_), `actor`, `created_at`.
- **Filters & grouping:** period; user × module.
- **Metrics:** events per module per active user; modules with no events in 30 days.
- **Viz / Export:** heat grid · CSV.

### RPT-090 · Notification engagement
Status: MISSING · Audience: Admin · Value: Low · Effort: S · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Do people read the alerts we send them, and which kinds do they mute?
- **Sources:** `Notification.kind`, `created_at`, `read_at`, `user`; `NotificationMute`; `PushSubscription` count.
- **Filters & grouping:** kind, user, period.
- **Metrics:** read rate, median time to read, mutes per kind, push-enabled users.
- **Viz / Export:** bar · CSV.

### RPT-091 · Integration health (Discord webhooks, ingestion)
Status: MISSING · Audience: Admin · Value: Medium · Effort: M · Data: NEEDS NEW DATA (`WebhookDelivery` log, request counters per key) · Freq: daily · Priority score: 1.0
- **Question:** Are our Discord alerts and SDK feeds actually working?
- **Sources:** `Product.discord_webhook_url` (configured or not), `APIKey.last_used_at`, `ErrorOccurrence.created_at` per product (last seen). Webhook calls are "best-effort, 5s timeout" (`apps/products/webhook.py`) and nothing records failures.
- **Metrics:** products with webhook but no recent send; keys silent > 24h; failure rate.
- **Viz / Export:** status table · alert.

### RPT-092 · Ingestion volume per product and key
Status: MISSING · Audience: Admin · Value: Low · Effort: S · Data: READY · Freq: weekly · Priority score: 1.0
- **Question:** How much data does each SDK send us (storage and fair-use planning)?
- **Sources:** `ErrorOccurrence` rows per product per day (including `request_payload`, `raw_data` size), `Feedback`, `IngestedTicket`.
- **Filters & grouping:** product, period.
- **Metrics:** rows per day; approximate payload bytes; largest groups.
- **Viz / Export:** line · CSV.

### D13. Data quality and exceptions

### RPT-093 · Workspace data-health scorecard
Status: MISSING · Audience: Admin · Value: Medium · Effort: M · Data: READY · Freq: weekly · Priority score: 1.0
- **Question:** Where is the data incomplete or inconsistent?
- **Sources:** tickets with `product` null; products without `key`, `lead`, `end_date`, `server`; members without `PayrollProfile`; `PayrollProfile.is_on_payroll` with no salary; `LeavePolicy` with zero requests; `Product` with no `ProductAccess`/`PodMember`; `Estimate.client_name` blank.
- **Filters & grouping:** module.
- **Metrics:** counts per check, % complete, trend.
- **Viz / Export:** checklist table · CSV.

### RPT-094 · Dormant automation rules
Status: MISSING · Audience: Admin · Value: Low · Effort: S · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** Which active rules never fire, and which fire too much?
- **Sources:** `AutoTicketRule.is_active`, `last_triggered_at`, `trigger_count`, `threshold_count`, `window_minutes`.
- **Filters & grouping:** product.
- **Metrics:** never triggered; triggers per week; rules created > 30 days ago with 0 triggers.
- **Viz / Export:** table · CSV.
- **Note:** distinct from RPT-012 (outcome of tickets created); this one is a hygiene list.

### D14. Forecast and insight

### RPT-095 · Ticket backlog forecast
Status: MISSING · Audience: Owner · Value: Medium · Effort: M · Data: READY · Freq: weekly · Priority score: 1.0
- **Question:** At the current pace, when does the open backlog reach zero (or double)?
- **Sources:** weekly created and resolved counts (ActivityLog), current open count, `Ticket.priority`.
- **Filters & grouping:** product.
- **Metrics:** 4-week average net burn; projected weeks to clear; confidence band.
- **Viz / Export:** projection line · email.

### RPT-096 · Next-cycle payroll and capacity forecast
Status: PARTIAL · Audience: Finance · Value: Medium · Effort: M · Data: READY · Freq: monthly · Priority score: 1.0
- **Question:** What will next cycle's payroll be, given approved and pending leave and holidays?
- **Sources:** `payroll.service.preview` (already computes any cycle), `cycle_bounds`, `PayrollProfile`, `Holiday`, `LeaveRequest` pending/approved in the window, expenses marked `to_salary`.
- **Filters & grouping:** next cycle; best/worst case (pending leave approved/rejected).
- **Metrics:** projected gross, deductions, reimbursements; range.
- **Viz / Export:** table + range bar · PDF.
- **Note:** preview exists for the chosen cycle; the forward-looking range and pending-leave scenarios do not.

### RPT-097 · Hiring/capacity plan vs planned hours
Status: MISSING · Audience: Owner · Value: Medium · Effort: M · Data: READY · Freq: quarterly · Priority score: 1.0
- **Question:** Do we have enough people-hours for the planned project work next quarter?
- **Sources:** `PhasePlan` (`planned_hours`, `start_date`, `end_date`), `WorkShift.worked_minutes_per_day`, headcount from `PayrollProfile.is_on_payroll`, holidays, leave history.
- **Filters & grouping:** month, product.
- **Metrics:** planned hours vs available hours; gap in person-months.
- **Viz / Export:** stacked area · PDF.

### D15. Client-facing

### RPT-098 · Customer feedback summary pack
Status: MISSING · Audience: Client · Value: Medium · Effort: M · Data: READY · Freq: quarterly · Priority score: 1.0
- **Question:** A shareable summary of NPS, CSAT, ratings and quotes per product for a client or board.
- **Sources:** `SurveyResponse` (score, comment), `ingestion.Feedback` (rating, comment, `version`), `Survey`.
- **Filters & grouping:** product, quarter.
- **Metrics:** NPS, average rating, top praised and top complained themes (comment text, with names removed).
- **Viz / Export:** line + quotes · PDF.

### RPT-099 · Client support and reliability summary
Status: MISSING · Audience: Client · Value: High · Effort: M · Data: READY · Freq: monthly · Priority score: 1.5
- **Question:** What did we fix for a client this month and how quickly?
- **Sources:** `Ticket` resolved in period (by product), RPT-004 TAT, `ErrorGroup` resolved/open, regressions, `ProductVersion` released.
- **Filters & grouping:** product, month.
- **Metrics:** tickets resolved, median resolution time, open critical items, errors fixed, releases shipped.
- **Viz / Export:** one-page PDF · scheduled email.
- **Note:** SLA targets (`Ticket` has no `sla_hours`) would allow an "SLA met %" line; that part is NEEDS NEW DATA.

---

## E. Data we capture but never report on

| Table.field | Evidence | Report it could power |
|---|---|---|
| `ErrorOccurrence.os`, `.browser`, `.device` | written in `ingestion/serializers.py:126-130`; zero reads in views/templates | RPT-019 |
| `ErrorOccurrence.environment`, `.page` | only raw rows and Discord text; never aggregated | RPT-019, RPT-020 |
| `ErrorOccurrence.user_ref` | counted into a stored counter only | RPT-021 |
| `ErrorOccurrence.request_payload`, `.raw_data` | written (scrubbed); never read | storage report RPT-092; support drill-down |
| `ingestion.Feedback` (all fields: `rating`, `comment`, `version`, `screenshot_url`) | no list/report; used in search and a Discord embed only | RPT-026, RPT-016, RPT-098 |
| `IngestedTicket` | read once, by the status endpoint (`ingestion/views.py:109`) | RPT-029 |
| `SurveyResponse.contact_name/contact_email/user_ref` | stored, not exposed | RPT-025 |
| `SentimentRecord` | listed in CS hub; no code creates rows | RPT-028 |
| `Ticket.watchers`, `TicketAttachment` (all fields) | `TicketAttachment` only in Django admin | usage in RPT-089 |
| `TicketComment.created_at/author` | shown in thread only | RPT-010 |
| `ErrorGroup.regression_count`, `first_version`, `regressed_at` | list filter and detail only | RPT-016, RPT-017 |
| `ProductVersion.released_at` | shown in the version list only | RPT-016 |
| `ProjectLogEntry.from_stage/to_stage/meta` | shown as log text | RPT-031, RPT-033 |
| `PhasePlan.planned_hours` | project form only | RPT-032, RPT-097 |
| `CrunchItem.done_at` | project page only | RPT-034 |
| `PodMember`, `ProductAccess` | used for permissions only | RPT-037, RPT-040 |
| `APIKey.last_used_at/expires_at/revoked_at` | per-key badge only | RPT-039 |
| `ExternalAccessToken.last_used_ip/last_used_at` | own profile page only | RPT-088 |
| `AutoTicketRule.trigger_count/last_triggered_at`, `AutoTicketLog.matched_count` | admin list only (`automation/admin.py:15`) | RPT-012, RPT-094 |
| `Lead.converted_at`, `Lead.need`, `LeadLog.created_at` | detail page only | RPT-043 to RPT-046 |
| `AttendanceRecord.is_edited`, `AttendanceCorrection.original_*` | flag/queue only | RPT-068, RPT-069 |
| `Membership.late_exempt` | rule input only | RPT-064 |
| `LeaveRequest.decided_at/decided_by/split_mode` | request page only | RPT-077, RPT-078 |
| `Payslip.late_half_days/late_penalty/reimbursement/unpaid_leave_days` | inside the run CSV only | RPT-058, RPT-059 |
| `PayrollProfile.effective_from` history | used to pick the current rate | RPT-060 |
| `Expense.to_salary/repaid_on/paid_in_run` | row badges only | RPT-053, RPT-054 |
| `Estimate.pitch_price/margin_percent/people/others` | one-off quote screen | RPT-049, RPT-050 |
| `DSREntry.category/is_auto_logged/elapsed_hours/status` | day grouping only | RPT-081, RPT-082, RPT-084 |
| `Notification.read_at`, `NotificationMute`, `PushSubscription` | per-user inbox | RPT-090 |
| `ActivityLog.metadata` | only `to`, `product_id` read by summary | RPT-004/005/008/018 |

---

## F. Data we should start capturing (ranked by reports unlocked)

| Rank | Add | Why | Reports unlocked |
|---|---|---|---|
| 1 | `Ticket.resolved_at`, `closed_at`, `first_response_at` (set in `Ticket.transition_to`) and `ErrorGroup.resolved_at`, `first_triaged_at` | durations are currently rebuilt from `ActivityLog` and break when the SDK or admin changes status without logging | RPT-004, 005, 008, 010, 018, 083, 099, 095 |
| 2 | `Estimate.product` (and `Estimate.lead`, `Estimate.status`), `Expense.product` | no cost can be tied to a project or a quote to its outcome | RPT-036, 051, 056 |
| 3 | `DSREntry.phase` (or derive from `Product.stage` at entry time) | plan-vs-actual per phase | RPT-032, 036, 097 |
| 4 | `Lead.source`/`utm_*`, `owner`, `lost_reason`, `expected_value` | marketing and sales attribution | RPT-047, 043, 044 |
| 5 | `SurveyResponse.followed_up_at/by/note`, `Survey.invited_count` | close the loop on detractors; true response rate | RPT-025, 027 |
| 6 | `LoginEvent` (user, time, ip, success) | sign-in history, brute-force, dormancy | RPT-088 |
| 7 | `AttendanceRecord` edit history (before/after, editor) | admin edits keep no old values | RPT-068, 069 |
| 8 | `WebhookDelivery` log and ingestion request counters per `APIKey` | integration health | RPT-091, 092 |
| 9 | `PresenceDaily` roll-up (user, date, active minutes) | live presence rows are purged after 5 min | RPT-073 |
| 10 | Statutory fields on `Payslip`/`PayrollProfile` (PF, ESI, TDS, PT, PAN) | compliance | RPT-063 |
| 11 | `Ticket.sla_hours` (per priority policy) | SLA met % | RPT-099 |
| 12 | A writer for `SentimentRecord` (derive from survey/feedback) | table is empty in practice | RPT-028 |


## G. Quick wins (READY + S effort + High value)

| ID | Report | Status | Audience | Value | Effort | Score |
|---|---|---|---|---|---|---|
| RPT-002 | Ticket ageing (open backlog by age bucket) | MISSING | Ops | High | S | 3.0 |
| RPT-003 | Overdue and due-soon deadlines | PARTIAL | Ops | High | S | 3.0 |
| RPT-006 | Created vs resolved trend and backlog burn | PARTIAL | Owner | High | S | 3.0 |
| RPT-009 | Unassigned and stale tickets | MISSING | Ops | High | S | 3.0 |
| RPT-014 | Error trend by severity and product | PARTIAL | Ops | High | S | 3.0 |
| RPT-015 | Top errors by occurrences and users affected | PARTIAL | Ops | High | S | 3.0 |
| RPT-022 | Untriaged error queue ageing | MISSING | Ops | High | S | 3.0 |
| RPT-024 | NPS / CSAT / CES trend and distribution | PARTIAL | Owner | High | S | 3.0 |
| RPT-026 | In-app feedback ratings report | MISSING | Owner | High | S | 3.0 |
| RPT-030 | Project portfolio status | PARTIAL | Owner | High | S | 3.0 |
| RPT-035 | Project hours by person and category | PARTIAL | Ops | High | S | 3.0 |
| RPT-043 | Lead funnel and conversion | MISSING | Sales | High | S | 3.0 |
| RPT-044 | Speed to first contact | MISSING | Sales | High | S | 3.0 |
| RPT-052 | Monthly expense trend by category | PARTIAL | Finance | High | S | 3.0 |
| RPT-053 | Reimbursement ageing | MISSING | Finance | High | S | 3.0 |
| RPT-057 | Payroll cost trend per cycle | PARTIAL | Finance | High | S | 3.0 |
| RPT-059 | Payroll variance run-over-run | MISSING | Finance | High | S | 3.0 |
| RPT-061 | Payroll completeness exceptions | MISSING | Finance | High | S | 3.0 |
| RPT-064 | Lateness and penalty ledger | PARTIAL | HR | High | S | 3.0 |
| RPT-067 | Missing check-out / unclosed days exception | PARTIAL | HR | High | S | 3.0 |
| RPT-068 | Manual attendance edit audit | MISSING | Auditor | High | S | 3.0 |
| RPT-074 | Company leave balance register | PARTIAL | HR | High | S | 3.0 |
| RPT-080 | DSR compliance (missing and late reports) | MISSING | Ops | High | S | 3.0 |
| RPT-086 | Audit log export | PARTIAL | Auditor | High | S | 3.0 |
| RPT-087 | Access and role change report | PARTIAL | Auditor | High | S | 3.0 |

---

## H. Roadmap

**Phase 1: quick wins (weeks 1-3).** The section G reports, delivered on one shared export helper. Start with the CSV exports that already have a view and a filter bar (RPT-086, 087, and the Medium-value but trivial RPT-001), then the exception lists admins act on daily (RPT-009, 022, 067, 053), then the single-query analytics (RPT-002, 014, 015, 026, 043, 044, 052, 064, 074). The section G reports named under phase 2 (RPT-030, 035, 057, 059, 061, 068, 080) are quick wins too but pair naturally with that phase's related work, so they may be pulled forward or left there.

**Phase 2: core MIS and finance (weeks 4-8).** Add `resolved_at` / `first_response_at` (section F, rank 1) in one migration, back-fill from `ActivityLog`, then ship the duration reports (RPT-004, 005, 010, 018, 083). In parallel: payroll and leave MIS (RPT-057, 058, 059, 061, 076, 077), DSR and attendance reconciliation (RPT-072, 080), project portfolio, plan-vs-actual and hours (RPT-030, 032, 035), release scorecard (RPT-016), correction analytics (RPT-069), expense reconciliation (RPT-054).

**Phase 3: advanced, forecast, compliance (weeks 9+).** Capture the new data in section F ranks 2-12, then ship profitability (RPT-036), quote win/loss (RPT-051), lead attribution (RPT-047), statutory (RPT-063), sign-in history (RPT-088), integration health (RPT-091); forecasting (RPT-023 spike detection, RPT-042 risk score, RPT-095/096/097); and the client-facing packs (RPT-041, 098, 099) once their source reports are trusted.

---

## I. Suggested shared report infrastructure

What exists: `apps/core/csvx.csv_response` (BOM + formula-safe CSV), but three modules still hand-roll `csv.writer` (`expenses/views.py:141`, `costing/views.py:102`) and each view reads `?export=csv` differently. There is no report registry, scheduler, PDF/Excel writer or per-report permission.

1. **Report registry.** One small class per report (`key`, `title`, `audience`, `permission`, `queryset(filters)`, `columns`, `chart`). A single `/reports/` index lists what the user may open. This also gives one place to enforce the rule from CLAUDE.md that every product-owned query goes through `accessible_products`.
2. **Common filter bar** (partial in `templates/components/`): period presets (already in `dashboards/views.py:191`), product, person, status, compare-to-previous-period toggle.
3. **Export service.** Extend `csvx` with `xlsx_response` (openpyxl) and a print-CSS PDF route (the project already uses print views for payslips and quotes), reading the same `columns`. Every report gets CSV, Excel, PDF with no extra code. Keep `_safe()` for formula injection.
4. **Scheduler.** A `send_report_digests` management command on the same cron as `evaluate_rules`, driven by a `ReportSubscription(user, report_key, filters, frequency, last_sent_at)` table; delivers through `notifications.service.notify` first, e-mail later.
5. **Precomputed rollups** for the heavy ones: a nightly `DailyMetric(company, product, date, metric, value)` table (tickets created/resolved/open, error occurrences, DSR hours) so trend reports do not scan `ActivityLog` per day as `get_summary_report` does today (one query per day per metric, `dashboards/service.py:488-505`). Cache rendered results per (report, filters, company) for a few minutes.
6. **Permissions.** Reuse `CompanyAdminRequiredMixin` for people/money reports, `accessible_products` for product data, and mask personal data in client-facing packs.
7. **Report tests.** One generic test per report that runs it against `seed_data` and asserts it returns rows with the declared columns, matching the repo's "one runnable check" habit.
