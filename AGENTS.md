# AGENTS.md

This file provides guidance to coding agents working in this repository. It is
authoritative for *how to work here*; **`context.md` is authoritative for *what
was done and why*** — read it before changing any area. `CLAUDE.md` is an older,
much shorter draft kept only for the **Serop integration** section, which is
folded in here too.

## Commands

The virtualenv lives at `venv/`. Prefix commands with `venv/bin/python` or activate it first.

```bash
venv/bin/pip install -r requirements.txt          # install deps
venv/bin/python manage.py migrate                 # apply migrations
venv/bin/python manage.py runserver 8010          # dev server
venv/bin/python manage.py seed_data               # wipe + reseed the "Acme Corp" demo workspace
                                                  #   logins: owner|admin|dev1|dev2|support|viewer / testpass123
venv/bin/python manage.py evaluate_rules [--dry-run]   # run the auto-ticket rule engine (see Automation below)
venv/bin/python manage.py test apps.attendance          # employee check-in/out suite
venv/bin/python manage.py test apps.payroll              # payroll suite (monthly salary, cycles, payslips)
./bootstrap.sh                                         # migrate + superuser + demo data in one go
```

Tests use Django's runner (not pytest, despite `.pytest_cache` in `.gitignore`):

```bash
venv/bin/python manage.py test apps                                   # whole suite
venv/bin/python manage.py test apps.tickets                           # one app
venv/bin/python manage.py test apps.tickets.tests.test_tickets.TicketProductAccessTest.test_cannot_open_inaccessible_ticket   # one test
```

One test in `apps.accounts.tests.test_tenant_isolation` fails on a clean checkout: `test_signup_creates_user`. `accounts:signup` no longer exists as a route (allauth is installed but signup is not wired up), so it is a product question — *should* self-signup exist — rather than a stale test. Not a regression; left alone deliberately.

**The full suite takes ~3.5 minutes**, so background it (`nohup … &`) and poll the log rather than watching a foreground command time out. There is no CI, no `.github/`, and no lint or typecheck step configured — `manage.py check` (expect only `staticfiles.W004`) plus the suite is the whole gate.

`test_request_has_company_after_login` used to fail here too, and the note above used to blame `LOGIN_REDIRECT_URL = "/dashboard/"` pointing at a route that did not exist. That was half right: the dead path was real (every login 302'd to a 404) and is now fixed, but the test's actual cause was different — `accounts:dashboard` (`/`) has always been a bare `redirect("dashboards:index")`, so it can never return 200. The test now follows the redirect.

Docker: `docker-compose up` builds and serves on `:8011` via `entrypoint.sh` (migrate + runserver), bind-mounting `db.sqlite3`. **The container builds its own copy of the source, so a fix in your working tree is not in a running container** — rebuild before concluding a change "doesn't work" in Docker. That is how a correct fix can look broken: check `docker compose build --no-cache && docker compose up` before debugging your own code.

There is no frontend build step. Templates render server-side; htmx and Alpine.js load from CDN in `templates/core/base.html`. All CSS is a single `<style>` block in `base.html` driven by CSS custom properties (`--accent`, `--panel`, `--border`, …). `static/` does not exist, so the `staticfiles.W004` check warning is expected.

Root-level `test_api*.py`, `check_db*.py`, `check_serializer.py` are ad-hoc throwaway scripts, not part of the test suite.

## Working loop — evidence, not assumption

Work one goal at a time, and let the *result of each action* decide the next one.
Most of the real work in a session comes from a step returning something
unexpected, so the loop is driven by evidence rather than by a plan made up front.

- **Read the actual failure text.** Do not infer what went wrong from the test
  name or from memory. The specific message is the cheapest information available,
  and guessing at it burns whole cycles. Copy the error out of the log rather than
  paraphrasing it.
- **When reality contradicts your expectation, your model of the code is probably
  wrong — re-read the source, do not patch the test.** Wrong guesses about form
  fields, choice values, URL kwargs and required columns are the single largest
  source of wasted iterations in a Django repo. Look the field up
  (`_meta.get_field(...).choices`, the `Meta.fields` list, the `path(...)` entry)
  instead of recalling it.
- **Prove each claim before reporting it.** "The fix works" is a claim; the
  command you ran and its output are the proof. Prefer an executable check over a
  plausible explanation: hit the page, post to the URL, run the suite.
- **Distinguish what you verified from what you believe.** Say which is which. An
  unverified guess presented as a finding is worse than an honest "not checked".
- **A failing test is the most useful thing in the loop** — it hands you the next
  fact for free. Do not weaken or delete a test to get to green; find out what the
  test was protecting.
- **One goal at a time.** Interleaving two changes makes a confusing half-state
  that is hard to reason about and hard to revert.

### If the request lists several things

Multi-item requests are where work gets silently skipped, because quality decays
across a long request: the early items are driven by fresh evidence, the late ones
by the plan you made before you knew anything. The classic failure is not a
refusal — it is reporting all six items done when item five was never verified.

- **Track the items as a list.** If a task-tracking tool is available, record the
  request as items and update it as you go. An item that is not on the list does
  not get reported on.
- **Do them in the order given, one at a time, fully** — code plus its own check.
  Do not interleave, and do not start item N+1 until item N is verified. Interleaving
  leaves a half-state that is hard to reason about and hard to revert.
- **Make your final report a count.** One line per requested item, each citing the
  command you ran or the page you hit. If the number of lines does not match the
  number of items asked for, you are not finished — go and find the gap.
- **Never mark an item done on intent.** "I added the message" is not evidence;
  the request that queued it is. If you cannot produce the check, the item is
  partial, and partial is reported as partial.
- **If an item needs a decision you do not have, stop and ask.** Guessing mid-list
  is worse than pausing: it produces an answer to the wrong question and every
  later item inherits it.
- **If the loop shows your plan was wrong, re-plan and say so** rather than pushing
  through the original sequence.
- **Report honestly when you do not finish.** "Items 1–3 verified, 4 not started,
  5 blocked on X" is a useful answer. "All done" when three were skipped is the
  failure this section exists to prevent.

## `context.md` is the project's memory — read it, then keep it current

**`context.md` is where the answers live.** It is written to be read by the next
agent, and it is the only file that answers "what was done, how does it work, and
why". Consult it **before** you touch an area, not just afterwards.

- **Look up code location in its *Quick reference* table** rather than grepping
  the tree — it maps each area to the files and functions that implement it.
- **Read the relevant date section before changing an area.** It records what was
  already tried, what was *deliberately not* changed and why, and which open
  questions touch your area. Skipping it is how a session re-proposes a rejected
  approach, or quietly contradicts a decision the user already made.
- **Check *Open questions — still unanswered* for your area.** If one is still
  open, say so before implementing rather than deciding it silently. If you are
  the reason it got answered, record who decided what.

**Then update it at the end of every change.** A change that alters behaviour, a
rule or a decision gets an entry — a change with no entry is unfinished, in the
same way a mutation with no `messages.success` is unfinished. Add to today's
`## YYYY-MM-DD` section (newest first); do not start a second section for one day.

Each entry records **what changed**, **how it works now** (naming the functions
and files), **why it was wrong**, **how it was verified** (test counts), and
**what is still undecided**. Keep it to the finding layer — inline the reasoning
you need, and do not create a third file to hold it:

| File | Audience | Rule |
|---|---|---|
| `CHANGELOG.md` | the user reading "what's new" | **Never** edit or delete an existing release entry; add a new release at the top |
| `context.md` | a future session finding context fast | **append to today's section every change — this is the memory** |
| `changes-2026-09-30.md` | one archived day, committed | **Do not add to this pattern.** It exists because that day's detail was too large to compress; its findings are already summarised in `context.md`. A new day gets a `context.md` section, not a new file. |

- **Carry open questions forward**, and number them (`Q1`, `Q2`, …) so they can be
  referred to and struck when answered. An unanswered decision is the most
  valuable thing in the file. When one is resolved, note **who decided what** and
  strike the old item rather than deleting it.
- **Record "deliberately not changed" too.** A rejected approach with a stated
  reason stops the next session from re-proposing it.
- **Name functions and files in every entry.** "Attendance changed" is useless to
  a later session; `service.effective_span_for` is findable.
- If you introduce a new invariant, it goes in **this file** (how to work); if it
  is a one-off decision, it goes in `context.md` (what happened and why).

## Architecture

Django 6 + SQLite, server-rendered (class-based `View`s with `get`/`post`, not DRF for the web UI). `apps/` is on `sys.path` (see `core/settings.py`), so apps import as `apps.tickets`, `apps.products`, etc. The Django project package is `core/`.

### Timezone — `TIME_ZONE = "Asia/Kolkata"`, and it is not cosmetic

The company runs on Indian time. `USE_TZ = True` still stores UTC; `TIME_ZONE` decides what every **display and every day-boundary calculation** means. It was `"UTC"`, and that was quietly wrong in a way that cost money:

- `WorkShift.start_time` is 10:00 and `lateness_for` compares `timezone.localtime(record.check_in).time()` against it. Under a UTC default, an employee arriving at **10:45 IST** was stored as `05:15Z`, read back as `05:15`, compared to 10:00, and `max(0, negative)` made it **zero lateness**. Nobody was ever charged a late penalty, and the punch panel printed "Checked out 05:15 AM".
- With `Asia/Kolkata` the same punch reads 10:45, lands in the `major` band, and costs Rs 100.

Consequences to keep in mind:

- **Never hardcode an offset or call `datetime.utcnow()`.** Everything already goes through `timezone.get_current_timezone()` / `timezone.localtime()` / `timezone.localdate()`, which is why this was a one-line fix. `grep -rn "timezone.utc\|utcnow" apps/` should stay empty outside tests.
- **Tests that build a punch use `timezone.make_aware(..., timezone.get_current_timezone())`**, never a literal `+05:30` and never a bare `replace(tzinfo=utc)`. They then stay correct in any zone and assert against wall-clock that matches the shift.
- **Never assert a "today" timestamp against a literal.** The dashboard test once asserted `worked_minutes == 0` for an unclosed day and only passed because the suite ran before 09:00. Derive the expectation from the service instead.
- **Existing rows do not migrate.** Timestamps already in the database were written under the old zone and will read 4h30m/5h30m off. That is data, not schema: `venv/bin/python manage.py seed_data --reset` regenerates the demo workspace correctly, and real deployments need a one-off backfill. Do not "fix" it with a migration.
- `seed_data` derives today's arrivals from the shift start ±15/35 minutes so the demo exercises on-time, Rs 50, Rs 100 and half-day bands. It previously subtracted up to **four hours** before the start, which avoided late penalties by inventing 06:30 arrivals for a 10:00 shift — and the punch panel made that obvious the moment it started printing real arrival times.
- The server's own clock is whatever the host is set to. `docker-compose` and a bare `runserver` therefore need the container/host on IST for the seeded demo to look right; the code itself is zone-agnostic.

### Multi-tenancy and access control

Two independent layers — **both** must be enforced on every view that touches tenant data:

1. **Company isolation.** `Company` + `Membership` (roles: owner, admin, developer, support, viewer). `apps/core/middleware.CurrentCompanyMiddleware` sets `request.company` and `request.company_role` on each request from the active-company id in the session (`settings.ACTIVE_COMPANY_SESSION_KEY`); the company switcher (`accounts:company_switch`) rewrites that key. `apps/core/models.TenantScopedModel` is the base for tenant-owned models (adds a `company` FK); most views filter `Model.objects.filter(company=request.company)` explicitly rather than relying on the manager.

2. **Per-product access.** `apps/products/access.py` is the source of truth: `accessible_products(user, company)`, `user_has_product_access(...)`, `require_product_access(request, product)`, plus `accessible_tickets` / `require_ticket_access` and `accessible_error_groups` / `require_error_group_access`. Owners and admins see every product; other roles need a `ProductAccess` row. **Any company-wide list, detail, or mutation view for a product-owned model (Ticket, ErrorGroup, surveys, milestones, rules) must scope its queryset to `accessible_products` and guard each object with the matching `require_*` helper** — filtering by `company` alone leaks and allows mutation across products. `apps/dashboards/service.py` follows the same rule (`get_user_dashboard_data`, `get_summary_report` scope by role).

Access checks live in the view/mixin layer. `apps/core/mixins.py`: `CompanyMemberRequiredMixin` (redirects to company setup if no company), `CompanyAdminRequiredMixin` (403 unless owner/admin), plus `LeaveApproverRequiredMixin` in `apps/leave/views.py` (403 unless an approver). A mixin must answer the permission question **before** calling `super().dispatch()`; deciding after the fact cannot stop a mutation.

### App layout — global vs product-scoped views

The same domain logic exists in two places and both must be kept in sync:

- **Global views:** `apps/tickets/`, `apps/errors/`, `apps/dashboards/`, `apps/feedback/`, `apps/automation/`, `apps/dsr/`, `apps/attendance/` — mounted at `/tickets/`, `/errors/`, etc. Operate across all products the user can access.
- **Product-scoped views:** `apps/products/views.py` + `apps/products/urls.py`, mounted at `/products/<pk>/tickets/`, `/products/<pk>/errors/`, etc. Re-implement the list/detail/create flows against `product.tickets` / `product.error_groups`, and always call `require_product_access` first.

### Ingestion API (`/api/v1/`)

`apps/ingestion/` — DRF `APIView`s for external SDKs. Auth is `APIKeyAuthentication` (`Authorization: Bearer <key>`); keys are per-`Product`, stored hashed (`APIKey.key_hash`), validated by `APIKey.validate_key`. `request.auth` is the `APIKey`, `request.user` is `None`.

- `errors/capture/` dedups by `sha256` fingerprint into `ErrorGroup` (+ one `ErrorOccurrence` per hit), bumping `occurrence_count`.
- `feedback/`, `tickets/`, `tickets/<id>/status/` — see `apps/ingestion/serializers.py`, where all the create logic lives (`serializer.create` / `.save`).

### Cross-cutting side effects

- **Discord notifications:** `apps/products/webhook.py`. `notify_ticket_created`, `notify_error_captured`, `notify_ticket_status_changed`, etc. POST an embed to the product's `discord_webhook_url` (best-effort, 5s timeout). Users with a `discord_id` get `@`-mentioned. Call these after the relevant state change.
- **Activity log:** `apps/dashboards/service.log_activity(company, event_type, title, ...)` writes an `ActivityLog` row (with a `metadata` JSON blob, typically `{"product_id": ..., "from": ..., "to": ...}`). Call it after every user-driven state change — the summary reports (`get_summary_report`) are reconstructed from `ActivityLog`, not the domain tables.
- **DSR auto-logging:** `Ticket.transition_to()` calls `apps/dsr/service.auto_log_ticket_dsr` when a ticket moves to `resolved`/`closed`, creating/updating a `DSREntry` timesheet row for each assignee.
- **Attendance:** `apps/attendance/` is the employee clock. `AttendanceRecord` is **one row per company+user+date** (enforced by `unique_together`), holding a single `check_in`/`check_out` pair — there is no break or multi-session tracking, so `worked_minutes` is always the raw span `check_out - check_in`. Reports show `service.net_minutes_for`, which is the span less the shift's unpaid break (see **Office hours and lateness**). `models.punch(company, user)` is the only write path; it returns `(record, action)` where action is `checked_in` / `checked_out` / `unchanged`, and a third punch on the same day is a deliberate no-op. Any company member can punch, whatever their role. Reports live in `apps/attendance/service.py` (`get_who_is_in`, `get_monthly_rows`, `get_month_grid`, `parse_month`); `worked_minutes` is a property, so it is summed in Python rather than with `Sum()`. `get_monthly_rows` seeds a row for **every** company member (`_company_members`) rather than only those with records, so someone who never clocked in shows as `0h` with a "never punched" pill instead of silently vanishing from the report — keep it consistent with `get_team_today`, which lists absentees too. `team_attendance` and `timesheet` are `CompanyAdminRequiredMixin`; the self-service views pin to `request.user` and 403 if a non-admin passes someone else's `user_id`, while an admin may pass `user_id` for a colleague in their own company (404 otherwise). When an admin views a colleague the page sets `focus_user`, hides the punch panel (its button renders the *target's* state but would punch the *viewer*), and retitles itself. Month-scoped views pass both `current_month` (the month being *viewed*) and `today_month` (the real present) to the template — the nav "This month" button links to the URL with **no** `month` param, so never point it at `?month={{ current_month }}`, which is a no-op that keeps the user on the month they are already viewing.

  - **`is_open` is not a screen state.** It is true both for somebody working right now and for a punch nobody ever closed, and both used to render as "On clock" with a counter that kept ticking — so a forgotten check-out was invisible everywhere except the team view, which computed `is_stale` privately. Use **`is_open_today` / `is_stale`**, both on the model, and `service.get_who_is_in` reads `record.is_stale` instead of recomputing it. Two definitions of one fact is how the other screens could not tell the cases apart.
  - **An unclosed day is counted, not zeroed — and capped.** `worked_minutes` stays 0 for an unclosed day (the punches say nothing about when the person left); `service.effective_span_for` is what puts a number on it: elapsed time from check-in, **capped at `shift.worked_minutes_per_day`**. The cap is not optional — elapsed time runs to *now*, so an uncapped forgotten punch accrues hours forever and one record from last month reports 300h in a 22-day month. `net_minutes_for` is the single funnel and the cap lands *below* its break-deduction threshold on purpose (`worked_minutes_per_day` is already net of the break), so do not change that comparison to `<=`. **This cannot move anyone's pay**: payslips price payable *days*, and `late_penalties_in_period` reads only `check_in`.
  - `open_days` counts days *since* the punch date, not days open-for. A punch 3 days ago reads "3d" and "checked in 3 days ago"; counting today's open day too would call it 4 days old.
  - **A forgotten check-out is fixable from wherever it is shown.** `AttendanceEditView` takes GET as well as POST, so any day can link to `/attendance/<pk>/edit/` — the calendar grid has no room for an inline form but has room for a link. The inline rows share one form partial (`partials/_record_edit_form.html`), which **prefills a missing check-out with the shift's `end_time`**: the cap assumes they left at closing, so making the admin retype it defeats the point, and clearing the box deliberately leaves the day open. `?next=` returns the admin to where they started editing and is validated by `_safe_next` (single leading slash, not `//` or `/\`) — it is a redirect target from user input. The inline Edit is gated on **privilege, not ownership**: an admin reading a colleague's page still needs it, and an employee never sees a button that would 403.
  - **The punch control is `_punch_context` + `_punch_button.html`, rendered twice and never derived twice.** `MyAttendanceView` (page load) and `AttendancePunchView` (htmx punch) both build the panel's context through `_punch_context`; the POST returns `partials/_punch_button.html` re-rendered against fresh state, so the DOM cannot disagree with the server. Do not compute shift/lateness/missing-checkouts in a template or in a view that only has one of the two paths.
  - **`_punch_context` takes `person` explicitly.** It is *not* inferred from `record.user`, because an admin reading a colleague's page gets `person=<colleague>` with `record=None` on any day that colleague has not punched — inferring from the record reported the **admin's** forgotten days on somebody else's page. A warning about the wrong person is worse than no warning. `PunchPanelTest.test_the_read_only_panel_reports_the_colleagues_days_not_the_admins` pins this.
  - **The panel shows three states and needs `is_complete` / `is_open_today` to tell them apart.** `is_open` cannot: it is true both for somebody working right now and for a day already closed. `is_complete` (done) → `is_open_today` (on the clock) → neither (not in yet). Every state carries the shift hours **and** the lateness, because a punch used to swap "on the clock, late 45m" for "checked out" and lose both. The elapsed counter is `x-text` over a server-rendered first value (Alpine only ticks it between requests) and is deliberately **not** in an `aria-live` region — it refreshes every 30s and would interrupt constantly; only the punch result is announced.
  - **The panel says "late" the moment it happens**, from `late_penalty_for` — the same call the payslip line is built from, so the warning cannot quote a different number from the charge. Before you arrive there is no arrival time, so no lateness is shown at all.
  - **The forgotten-check-out warning lists every unclosed day, not the month on screen.** It comes from `service.unclosed_days`, and today's legitimately-open record is excluded — reporting it would put the warning on every working day and stop it meaning anything. It renders **read-only for a colleague** (`punch_readonly`): the button would punch the *viewer*, so it is suppressed, but the panel stays so the warning survives, which is why the old "hide the whole panel when focused on someone else" behaviour was wrong.
  - **`hx-disabled-elt="this"` on the punch form is a correctness fix.** The panel re-renders in place, so a double-click sent two POSTs and the second — which `punch` correctly answers with its `unchanged` no-op — replaced "Checked in at 10:02 AM." with "already checked in and out". The form also carries `method`/`action` so the button works without htmx. Both punch buttons use `.punch-btn-in` / `.punch-btn-out`, which the stylesheet defines (they were previously used but had no rules, so both rendered as the same plain `.btn`).
- **Leave:** `apps/leave/` is the employee leave tracker, mounted at `/leave/`. `LeavePolicy` is a company's rules for one leave type (casual, sick, unpaid…); **both** limits are optional — `max_days_per_year=None` means uncapped and `max_consecutive_days=None` means long spells are allowed. `LeaveRequest` holds the span plus the *charged* `days`, computed once at creation by `service.validate_request`. All rules live in `apps/leave/service.py` and must be reused rather than re-derived in a view or template:
  - `working_days(start, end)` counts **Mon–Fri only**, so Fri→Mon costs 2 days, not 4. A weekend-only range costs 0 and is rejected. It returns a plain **`int`**, not a `Decimal`, so anything that renders a day count must go through `format_days`, which coerces — it used to call `.normalize()` on whatever arrived and raised `AttributeError` from inside a reason string.
  - A half day (`is_half_day=True`) must cover a single date and charges `Decimal("0.5")`.
  - **An over-cap request is accepted, not refused: the excess is charged unpaid.** The annual allowance and the per-spell cap decide the **paid** portion only. `service.auto_split` returns `{paid, unpaid, reasons}` and allocates paid days from the **start** of the span, so the unpaid tail is what falls past the cap. There is no longer any rejection for exceeding either limit, and the approver can override the split (see **the approver dialog** below).
  - **The split is stored, not recomputed.** `LeaveRequest.paid_days` / `unpaid_days` / `split_mode` are the record, and **payroll trusts them** — including an approver who marks days from an unpaid type as paid. Payroll must not re-derive the split from the current policy, or a later policy edit would restate a payslip. Migration `0003` backfills historical rows from their policy **at migration time** for exactly this reason, so a re-applied migration re-prices from the policy in force when it runs, not from today's.
  - **Pending leave reserves balance.** `balance_for` subtracts pending *and* approved, so two people cannot book the same last remaining days; the allowance is per **calendar year of the request's start date**, so January starts fresh even if the previous year was exhausted.
  - **Payroll consumes a request's whole span across the cycle boundary.** A request can straddle two cycles (25 Oct – 4 Nov), and each cycle cannot independently be entitled to the full paid allowance, so `payroll/service` walks the request in order and consumes the paid bucket once, spilling the remainder into the next cycle. Holidays inside a request's span are skipped for the *whole* request.
  - Requests may not start in the past and may not overlap another open (pending/approved) request from the same person.
  - Approvers are **company-level**, not per request: `Membership.is_leave_approver` (toggleable from the team edit form) plus owners/admins, via `is_approver(user, company)`. `LeaveApproverRequiredMixin` checks **before** `super().dispatch()` — deciding a request is a mutation, so a check that ran afterwards would let a non-approver's POST take effect and still return a 302 that looks like success in the browser.
  - Attendees see approved leave as **leave, not absence**: `service.approved_leave_map(company, start, end)` returns `{user_id: {dates}}` in one query and feeds `get_team_today`, `get_monthly_rows` and `get_month_grid`, so the team "on leave" count, the timesheet `leave_day_count` pill and the `att-leave` calendar cells all stay in sync. Leave days are excluded from the absent totals.
  - **The approver dialog is where the split is actually decided.** One shared dialog (`templates/leave/partials/_decision_dialog.html`) serves both the queue and an individual request, and its payload arrives as **`json_script`**, never hand-serialized into an attribute — the `leave_json` tag emits the complete `<script>` element, so there is no escaping question left to get wrong. It exposes the dates (editable — an approver may correct a request that was applied for wrongly), half-day, auto/manual switch, paid and unpaid boxes, and a note. **A decision always submits a date range and a split**, so a bare POST is now invalid (`test_a_decision_without_dates_is_refused`): approving is a mutation that stores a priced split, and a submission with no dates could not store one. **Rejection validates the form but discards the split** — there is nothing to pay for a rejected request, and letting a rejection write `paid_days` would put a number on a row payroll must ignore anyway. The applicant's own view shows the stored split as a read-only pill; it is a consequence of the request, not a field they set.
  - **The apply screen prices the split before submission, not after.** `LeaveSplitPreviewView` (`leave:split_preview`) re-runs `service.auto_split` over the four live inputs and returns `_split_preview.html`, so an applicant learns which days become unpaid *before* the approver does. The panel is **empty by design** when the dates do not parse, are unset, or contain no working days — rendering "0 paid" while somebody is still typing would be a false statement. Its prices must match what the apply view stores, because both call `auto_split`; `SplitPreviewTest.test_the_preview_agrees_with_what_is_actually_stored` pins that agreement, since a preview that disagrees with the queue row is worse than none. The four input ids are declared in `LeaveRequestForm`'s widget `attrs` and named in `hx-include`, so a renamed field cannot silently drop itself from the POST and leave the panel pricing a stale span; a test walks the form's `id_for_label` values and fails if any is missing from the page or from `hx-include`.
  - `hx-trigger="change"`, not `keyup`, on the preview inputs: a date input fires `change` when the browser has a complete date, which is the first moment there is anything meaningful to price. Keying on keystrokes re-prices a half-typed `2026-1` and flashes the panel in and out.
  - **The preview endpoint takes no user id and prices the viewer.** It resolves the policy through `service.get_policy(request.company, ...)` so another company's policy is invisible, and it prices `request.user`'s own balance, so a colleague's approved leave cannot lower the number quoted to the applicant. It is still an ordinary CSRF-protected POST — the global `htmx:configRequest` hook in `core/base.html` attaches the token to every htmx request, so it needs no `hx-headers` of its own, and a test posts with `enforce_csrf_checks=True` to keep it that way.
  - **The policy editor is a labelled grid of four fields, never a `<table>` with a `<thead>`.** It used to be a table whose header advertised `Leave type | Days / year | Max per spell | Paid` while every body row was a single `<td colspan="5">` wrapping a `<form>` that held its own CSS grid. The header was structurally unrelated to the inputs it claimed to label, so there was no way to tell which number box was the annual allowance — the page was functionally unlabelled and the limit was unfindable. This is the same failure the payroll setup screen had; `PolicyScreenTest` pins the fix (no `<th>`, every input has a `<label for>` matching its `id`).
  - **Keep that page to settings only.** It is one row per type: name, days per year, max per spell, paid, Save — plus a single "Add" row. Do not add usage columns, progress bars, per-field hint text or multi-column headings to it. What is left of an allowance is an *employee* question and belongs on `/leave/` and the dashboard, which already show it per person via `balances_for`; a settings form that also tries to answer it becomes the same unlabelled sprawl it replaced.
  - **The sidebar marks the current page by comparing `request.resolver_match.url_name` against an explicit list — never with `'x' in request.path`.** The old substring tests lit up every item whose fragment appeared anywhere in the path: `/attendance/team/` highlighted "My attendance", "Team attendance" *and* "Team" simultaneously, and `/attendance/timesheet/` highlighted two. `{% with u=request.resolver_match.url_name %}` holds the name once for the whole template. `SidebarActiveStateTest` asserts exactly one `.side-item.active` and exactly one `aria-current="page"` per page, and that a typo in a `{% icon %}` name fails the suite (a bad name renders nothing at all, silently).
  - **Every reachable page must resolve to exactly one nav item, so adding a route means adding it to the conditions.** Auditing the whole URLconf (rather than the pages that happened to be visited) found seven that rendered a sidebar with *nothing* marked: `/leave/apply/` — the condition said `leave:leave_create`, a route that has never existed, the real name is `apply` — plus `/feedback/`, `/feedback/create/`, `/automation/`, `/automation/create/` and `/payroll/holidays/`. Automation and the company-wide survey list had **no nav entry at all** and were reachable only by typing the URL. `SidebarActiveStateTest.test_no_page_is_left_with_nothing_highlighted` pins the full list. The invariant is exactly **one `aria-current="page"` per page**; a page with none reads as "you are nowhere", which is how the orphans were found. `/profile/` has no nav item by design, so the *user menu's* Settings link carries the state instead.
  - **The global nav lists use an "All" prefix precisely because the product block below has the same concepts unscoped** — "All tickets" vs the product's "Tickets", "All errors" vs "Errors", and now "All feedback" and "All automation". A global item named plainly "Feedback" next to a product "Feedback" is two different destinations with one name. Keep the prefix when adding a global list.
  - **`.side-item` must never carry `overflow:hidden`.** Its own `::before` (the active bar) and `::after` (the collapsed hover tooltip) are positioned *outside* the item's box — `left:-8px` and `left:calc(100% + 12px)` — so clipping swallowed both: the bar disappeared exactly when the sidebar was collapsed, and the tooltip never rendered at all, leaving a collapsed nav of unlabelled icons. The label ellipsises through `.side-label` (`flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis`), which is where the clipping belongs.
  - **`data-label` is the only tooltip source on a nav link.** It feeds the styled collapsed tooltip; a `title` alongside it makes the browser draw a second native tooltip on top. Buttons (collapse, switchers) still use `title` + `aria-label`.
  - **Section rules are state-independent.** `.nav-section + .nav-section` draws a hairline in *both* states: expanded, the "Operations"/"Admin" labels are not enough to group 5 and 8 items; collapsed, the labels are `display:none` and the rule is the only grouping left. The four `<nav>` landmarks each carry an `aria-label` (Main / Current product / Operations / Admin) so a screen reader's landmark list is not four identical "navigation" entries.
  - **Every sidebar glyph is `{% icon 'name' %}` from `apps/core/icons.py`** — there are no hand-written `<svg>` bodies left in `_sidebar.html`, so the whole nav shares one stroke set. Sidebar links carry both `data-label` (the collapsed-state hover tooltip) and visible label text, and the collapsed state hides that text with `clip` rather than `display:none` so the link keeps an accessible name.
  - **Icons live in `apps/core/icons.py`, vendored from [Aria Icons](https://icons.leularia.com/) (`lucide-icons` collection) and inlined.** That is the whole mechanism: no font, no CDN, no build step, no `static/` directory. To add one, fetch `GET /api/v1/icon?id=lucide:<name>`, keep only the body between `<svg>` and `</svg>`, add it to `ICONS`, and **audit it for `url(`, `javascript:`, `<script`, `on*=` handlers and external refs before committing** — `PolicyScreenTest.test_every_vendored_icon_is_inert` does exactly that, so a dirty import fails the suite. `render_icon` renders `""` for a blank or unknown name (a policy with no icon must show no glyph, not a placeholder box) and is the only thing that calls `mark_safe`. `{% icon name %}` and `{% icon_choices %}` in `core/templatetags/icon_tags.py` are how templates reach it.
  - The picker is a native `<details>` (`leave/partials/_icon_picker.html`) holding **radio** tiles, not a `<select>`: a select cannot render SVG, and a collapsed `<details>` costs one glyph of row height instead of a 21-option dropdown. Radios inside a closed `<details>` are still submitted, so the choice posts with the row.
  - `LeavePolicy.icon` is validated against the same kind of closed set as colour (`clean_icon` vs `ICON_NAMES`). It is not free text, for the same reason `color` is not: the name reaches a template lookup, and a lookup fed a crafted string is how you turn a string into markup.
  - `LeavePolicy.color` is a **closed set of tokens** (`LeavePolicy.COLOR_TOKENS`: green, amber, red, blue, purple, grey, or blank), not free text, and `LeavePolicyForm.clean_color` rejects anything else. That is deliberate: the value is interpolated into a **class name** (`lp-dot-{{ policy.color }}`), so free text would be a style-injection vector via `url(...)`, quotes or braces. Keep the rendering class-based; do not "simplify" it to `style="background:{{ policy.color }}"`. The same dot appears on `/leave/` so a type looks the same on the settings and employee screens.
  - **Paid is a switch, not a bare checkbox.** It silently changes someone's salary, so it is rendered as a labelled `.lp-switch` rather than a filter-style tick, and unchecked submits an absent key (see the create-view note below).
  - Blank in either days box means **"No cap"**, never "Unlimited" — a cap of `0` is a real setting (nobody may take that type) and "Unlimited" reads as though 0 were impossible. The `placeholder="No cap"` is the whole affordance; `PolicyScreenTest` asserts the word "Unlimited" appears nowhere on the page.
  - `LeavePolicyCreateView` (`leave:policy_add`) exists because the empty state always said "add a leave type" with no route able to do it — the Add row is permanent, not an empty state. A checkbox is submitted as an **absent** key when unchecked, so a new type is only paid if the request carries `is_paid`; the create form pre-ticks it.
  - `LeaveRequest.policy` is `CASCADE`, **not** `PROTECT` — `PROTECT` breaks company deletion (and `seed_data --reset`), which cascades through `LeavePolicy`.
  - Days are `Decimal`, so render them with `service.format_days`, which strips trailing zeros (`12.0` → `12`, `11.5` → `11.5`). Raw `str()` on a `Decimal` emits exponent notation whenever the exponent is positive (`Decimal("1E+4")` renders as `1E+4`), which is what the helper exists to prevent.
- **Office hours and lateness:** `WorkShift` (`apps/attendance/models.py`) is **one row per company**, holding the office hours *and* the lateness rules: `start_time` 10:00, `end_time` 19:00, `break_minutes` 60, `grace_minutes` 15, `minor_penalty` Rs 50, `major_penalty` Rs 100, `penalty_currency` INR. `service.shift_for(company)` is a `get_or_create`, deliberately **not** a required FK: a company with no shift row must still be able to run payroll, and the defaults *are* the policy.
  - The bands are stored as **minutes after `start_time`**, not as clock times, so each boundary is a single number: `<= grace` on time, `<= 30` minor, `<= 60` major, beyond that a half day. `WorkShift.band_for_late_minutes` is **inclusive at the top of each band** — 10:30 exactly is still Rs 50, 11:00 exactly is still Rs 100, and 11:01 is the half day. That reading of the policy is deliberate; if it is ever changed, change `LatePenaltyTest.test_the_band_boundaries` with it rather than editing the comparison.
  - `service.lateness_for` measures `check_in` against `start_time` in whole minutes. **A missing punch is never a penalty** (`late_penalty_for` returns `None`): someone who never clocked in has no arrival time to be late with, and inventing one costs them money on a guess.
  - **Hours are shown net of the break, but `worked_minutes` stays the raw span.** `net_minutes_for(record, shift)` subtracts `break_minutes` **only from a day long enough to contain it** (span >= `worked_minutes_per_day + break_minutes`). A full 10:00–19:00 day reports 8h, not 9h; someone who leaves at 11:00 has not sat out a 60 minute break, and deducting one anyway would under-report a short day that is already short.
  - **Penalties are derived, never stored.** `late_penalty_for` recomputes from the punch on every call, so an admin editing a `check_in` cannot leave a stale penalty row behind — the only write path stays `models.punch` plus a normal record edit. There is deliberately no `LatePenalty` model.
  - **Two different mechanisms, deliberately not conflated.** Payroll's `late_pay_in_period` splits them: `cash_penalty` (the Rs 50 / Rs 100 bands) is a flat charge **subtracted from `gross`**, because it is not a fraction of a day's pay; and `half_days` / `half_day_loss` is half a working day at half the daily rate, so it **reduces `payable_days`** exactly like unpaid leave and is also reported in `deduction`. Do not fold the cash bands into a day count.
  - `Payslip.late_penalty` and `Payslip.late_half_days` are **snapshot columns** like the rest of the slip, and `breakdown["late_events"]` carries every event as `{date, late_minutes, band, amount, currency, reason}`. The `reason` string **includes the date and time** (`"Checked in at 2026-11-02 10:20, 20 min after the 10:00 shift start."`) on purpose: a payslip line has to stand on its own as the record of why someone was charged, months later. A silent deduction from a salary is a bug — `LatenessOnScreenTest` pins that both the admin slip and the employee's own `/payroll/me/` slip name the date, the lateness and the cost, and that an on-time slip shows **no** late section at all.
  - The calendar grid's `att-flag-late` label is deliberately terse (`late 45m`, `late 90m · half day`) and is **not** uppercased like the other flags, because the cell is ~30px wide. The reason for any charge lives on the payslip, not squeezed into a cell.
  - **Everybody on this payroll is salaried.** `PayrollProfile` has no employment-type field, so the late rules apply to everyone it pays. The non-salaried "over 45 minutes late in a week earns half a Saturday" rule is **not implemented** and has no payroll effect; do not add a Saturday-makeup column without also deciding how it prices.
  - `service.preview` and `service.generate_run` share `late_pay_in_period`, so the setup screen's estimate and the issued run can never quote different numbers for the same person. The daily rate is passed *in* rather than recomputed for the same reason.

- **DSR manual entries:** `apps/dsr/forms.py::DSREntryForm` is the only write path for hand-logged work (auto-logged rows come from `Ticket.transition_to`). `task_name` is required and `hours_spent` must be `> 0` and `<= 24`, so the old bare "Add Entry" button — which silently created a `"New Task"` / `OTHER` / `1.00`h / `COMPLETED` row — now renders real fields (`dsr/partials/_add_fields.html`) and rejects empty input instead of inventing a task. `DSREntryUpdateView` validates `category`/`status` against the model choices and range-checks hours; invalid input is ignored with a message rather than saved.
- **Payroll:** `apps/payroll/` is a **monthly-salary** calculator, mounted at `/payroll/`. Admin views are `CompanyAdminRequiredMixin` — *other people's* payslips are salary data, not something a developer or viewer can read. The one exception is `/payroll/me/`, which shows a member their own payslips and nothing else. There is no overtime model and no hours input; pay is `payable days × daily_rate`.
  - The pay cycle is the **27th through the 26th** of the next month (`service.cycle_bounds`). Ending on the 26th is deliberate: a 27→27 cycle either overlaps by a day or double-pays one. Consecutive cycles must satisfy `end + 1 day == next start`, so any change here needs a new test rather than an edit.
  - `PayrollProfile` is a dated rate history, unique per `(company, user, effective_from)`, and `is_on_payroll` is the **only** thing that decides who appears in a run — that is what keeps bots and service accounts out. `service.payable_people` takes the *latest* profile as of the cycle start and honours that row's flag, so unticking someone drops them from later cycles while earlier runs keep the old figure. Re-saving the same `effective_from` **edits** that row in place (`PayrollProfileListView.post`) rather than adding a second one; do not re-add a duplicate-date check to `PayrollProfileForm`, it would break the upsert.
  - Only **unpaid** leave and **lateness** deduct. `service.leave_days_in_period` recomputes days from the date range instead of reading `LeaveRequest.days`, because a request can straddle two cycles (25 Oct – 4 Nov) and `days` charges the whole span at once. It skips weekends **and company holidays** — a holiday inside a leave span is already free, so charging it would deduct pay for a day nobody was ever owed for. Casual/sick are `is_paid=True` and are reported but never deducted. Pending leave does not reduce pay; an absent day is not a deduction.
  - `Holiday` is per company and unique per date; holidays only remove days from the cycle's denominator, they do not change anyone's rate.
  - Pay is a **monthly salary**, entered as one number per person; `service.effective_rate` is the only place allowed to turn it into a day rate, by dividing by `working_days` for that cycle. That count already excludes Sat, Sun and company holidays, so the divisor is real and a person is paid their whole salary every cycle — adding a holiday *raises* the day rate instead of silently cutting pay. There is deliberately **no** alternative basis: an earlier `salary_basis`/`fixed_divisor` pair offered a "divide by a fixed 26" option, which pays short in any cycle that is not exactly 26 days, and nobody could say which was in force. One rule, one field. `daily_rate` remains on the model purely as the fallback for a profile with no salary (and for rows predating it); `PayrollProfileForm.clean` zeroes it whenever a salary is present so a leftover value can never outrank the salary. `Payslip.breakdown` records `monthly_salary`/`working_days`/`daily_rate` so a slip explains itself, as raw quantized strings rather than display text.
  - A rate change applies from the **cycle that starts on or after** its `effective_date`. A raise dated mid-cycle prices that whole cycle at the old rate rather than pro-rating; keep the test that pins this.
  - `templates/payroll/base.html` is the shell for all six `/payroll/` pages: it owns the single `<style>` block, the shared breadcrumbs and the Runs/Salaries/Holidays tabs, and a page supplies `pay_name`/`pay_subtitle`/`pay_actions`/`pay_body` plus a `pay_section`. `PayrollPageMixin.page()` injects `pay_section`. Do not add per-page `<style>` or hand-rolled breadcrumbs — that per-page duplication is what made the six pages drift apart.
  - The setup screen's salary box is hand-rendered rather than `{{ form.monthly_salary }}`, so it **must** keep its server-side `value` attribute. `x-model` only fills the box in after Alpine boots; without the `value` a no-JS browser would post an empty salary.
  - `Payslip` rows are an **immutable snapshot** of rate, day counts, deduction and gross. Regenerating a run rewrites them (unless `is_locked`), but a later rate change or a cancelled leave must never retroactively alter an already-issued payslip.
  - `PayrollProfileListView` renders the **estimate** column from `service.preview` for the cycle containing today — do not re-derive day counts or totals in the template or view, or the setup screen and the run screen will disagree. The page is a grid of one `<form>` per person, not a `<table>`: a form cannot legally wrap a `<tr>`, and an earlier `<thead>`/grid hybrid drifted out of alignment with the columns under it.
  - `_initial` prefills `effective_from` with the **latest profile's own date**, not today. That is what makes saving a corrected rate edit that row (the upsert keys on the date) instead of quietly opening a new rate row; recording a raise means changing the date on purpose.
  - **The home page is personal-first, and the only view that mixes both audiences.** `get_personal_dashboard_data(user, company)` in `apps/dashboards/service.py` feeds `DashboardView`. It replaced a dashboard that opened on company-wide error and ticket counts, which told an employee nothing about their own week. Every card is now either "mine" (attendance, pay, leave balances, DSR, my tickets) or a company number an owner/admin is actually responsible for (pending leave approvals, member/ticket/error totals) gated behind `is_privileged`. Two rules keep it honest:
  - **Payroll "on payroll" is a profile fact, not a payslip fact.** `_personal_payroll` reads the latest `PayrollProfile` with `is_on_payroll=True` when there is no `Payslip` yet, so somebody whose admin simply has not run payroll is told "no payslip has been generated" instead of "you're not on payroll". Do not derive it from the payslip. Note `is_on_payroll` defaults to **False** — a profile row that is not explicitly ticked is not on payroll, so tests must pass `is_on_payroll=True`.
  - **Tickets go through `accessible_tickets(user, company)`, not `company=company`.** A ticket is product-owned; filtering by company alone would surface a ticket in a product the developer cannot otherwise see. The old dashboard's product-card panel is gone, so `my_tickets` is the only product-scoped surface left and it is the one place the scoping has to hold.
  - `/dashboard/` (singular) is a `RedirectView` to `dashboards:index`, declared in `core/urls.py`. Do **not** add a second `path("dashboard/", include("apps.dashboards.urls"))` to "fix" it: including the same module twice registers the `dashboards` namespace twice (`urls.W005`) and makes `reverse()` ambiguous about which prefix it produces. `LOGIN_REDIRECT_URL` is the URL **name** `dashboards:index`, not a path, so it cannot drift out of sync with the routes again.
  - The `amount` / `hours` / `days` filters in `dashboard_extras` all tolerate `None` on purpose — a filter that raises on empty data turns "no payslip" into a 500 instead of an honest empty state. `worked_minutes` is a property, so month totals are summed in Python.
- **Employees can read their own payslips, nobody else's.** `MyPayslipListView`/`MyPayslipDetailView` at `/payroll/me/` are `CompanyMemberRequiredMixin`, not `CompanyAdminRequiredMixin` — an employee who has unpaid leave approved needs to see what it cost them. The detail queryset pins `user=request.user` **and** `company=request.company`, and the URL carries no user id, so a colleague's slip is a **404, not a 403** (a 403 would confirm the pk exists). Keep `MyPayslipAccessTest` — it is the only thing stopping this becoming a salary leak. The sidebar's "My payslips" link sits outside the admin-only `{% if %}` in `core/_sidebar.html`; the admin "Payroll" and "Payroll setup" links stay inside it.
  - `generate_run` is idempotent per `(company, period_start, period_end)` and returns `(run, created)`, but it does `run.payslips.all().delete()` and recreates the rows, so a payslip pk captured before a regenerate points at nothing. Tests needing several payslips must generate once per `(company, cycle)` and fetch the rows afterwards. It also returns early on a **locked** run, so unlocking is part of regenerating in a test or a shell. Use `dashboards.service.log_activity` for the audit row — `ActivityLog` has `actor`, not `user`.
- **Automation:** `AutoTicketRule` is **not** evaluated inline. The `evaluate_rules` management command (run on a cron) scans recent `ErrorGroup`s per rule; when `occurrence_count >= threshold_count` within `window_minutes`, it creates an `[Auto]` ticket and records an `AutoTicketLog` (which also dedups re-triggers).

### User-facing feedback — every mutation must say what it happened

A silent success is a bug. The action worked and the screen says nothing, which reads as a dead button — so **every mutating view calls `messages.success` / `.error`**, and a handler with no `messages.*` in it is a hole to fill, not a style choice.

- **How the queue reaches the screen** (`templates/core/base.html`): `{% if messages %}` emits `<script id="toast-seed" type="application/json">` via the `toast_payload` tag (`apps/core/templatetags/toast_tags.py`), and it must sit **above** `#toast-container`, because the container's own `x-init` looks the seed up by id and needs it already in the DOM.
  - That ordering is the entire bug that made every toast in the app invisible: the queue used to be dispatched on `alpine:init`, which Alpine fires **before** it walks the DOM, so the container's `x-data` did not exist and the guard silently did nothing. Do not move the seed read back onto a document-level Alpine hook.
  - `toast_payload` is a **tag, not a filter**: a filter's output gets HTML-escaped a second time (`"` → `&quot;`) and `JSON.parse` chokes. It routes through Django's `json_script`, which also neutralises `</script>` and `<!--` inside message text.
  - An unrecognised level is coerced to `"info"` because `tags` lands in `:class="msg.tags"`. Never pass free text there.
- **htmx views cannot host a toast.** Any view answering `HX-Request` with a `partials/` fragment never renders `base.html`, so no seed is emitted and the message surfaces on the **next full page load**. For instant feedback the fragment must carry the payload or dispatch the `django-message` window event, which the container already listens for (`x-on:django-message.window`).
- **Auditing is not optional.** Clicking through the app misses handlers; parse the POST bodies instead (an `ast` walk over `apps/*/views.py` for `messages.` is ~20 lines). `apps/products/tests/test_toasts.py` is the regression net and shows the shape of the assertion: check the POST *queued* the message **and** that the page rendered after it contains `id="toast-seed"` — a view can pass the first and fail the second, which is precisely what the old bug was.
- Writing one of those tests: send the form's **real** field names and the model's **literal lowercase choice values** (`priority="high"`, DSR `category="other"`), and pass `company=` to tenant-scoped models. A wrong field name re-renders the form with 200 and queues nothing, which is indistinguishable from a broken toast.

### Changelog and version

- `CHANGELOG.md` is a **runtime asset, not documentation**. `apps/core/changelog.py` parses it (memoised against mtime) for the sidebar "What's new" dialog and `/api/v1/changelog/`; `APP_VERSION` (env override `DJANGO_APP_VERSION`) feeds the footer and `/api/v1/version/`.
- **`.dockerignore` contains `*.md`, and `!CHANGELOG.md` must stay *after* it** — Docker applies patterns in order and the last match wins. Losing that negation ships an app whose release notes are missing in production with no error anywhere, because a missing changelog renders as an empty dialog rather than a failure. `_report_missing` logs a warning once per process for that reason, and `apps/core/tests.py` pins both the file's presence in a real image and the parser.
- **Never delete or rewrite an existing release entry.** Add a new release at the top; the full history is required to stay. A test in `apps/core/tests.py` compares the older blocks against `HEAD`.
- The file is parser-driven, so match the format: `## [tag] — YYYY-MM-DD · title`. A tag of `[Unreleased]` sets `released: False`, which is what drives the "unreleased changes" state. `###` headings map through `_SECTION_DISPLAY` (`Added`→New, `Changed`→Improved, `Fixed`, …) and "Known issues" is special-cased. **Top-level bullets are the counted items; an indented bullet is sub-detail and is not counted** — a detail line is free, a new top-level bullet changes the number the dialog and tests display.

### Templates

Project-level `templates/` (plus `APP_DIRS: true`). `core/base.html` is the app shell; the sidebar is `core/_sidebar.html`, fed by the `product_context` and `workspace_context` processors in `apps/core/context_processors.py` (these attach `product` + per-product counts, `nav_products`, and company-wide open counts). Partials are prefixed `_` and live in `<app>/partials/`. For an htmx request (`HX-Request: true` header) a view returns a `partials/` fragment instead of the full page.

- **There is no native `<select>` in `templates/` any more.** Every choice control is `{% dropdown %}` (`apps/core/templatetags/dropdown_tags.py` → `templates/core/partials/_dropdown.html`): a native `<details>` holding radios/checkboxes, styled by `.dd-*` in the single `<style>` block in `base.html`. It is the same idiom as the leave icon picker, and it keeps the two things a hand-rolled dropdown usually loses — the value posts with **no JavaScript**, and a change still fires a native `change`, so `hx-trigger="change"` and the HTMX quick-edit forms work untouched. **Do not add a `<select>` back.** The one exception is the assignee multiselect, which is already a richer custom dropdown and keeps a `display:none` `<select>` solely to carry the form value.
  - **Mode is explicit**, and the three are not interchangeable: `navigate=True` (a filter outside a form, reloads via `buildUrl`), `submit=True` (posts its own form on change), neither (an ordinary form field). Choosing wrongly turns a form field into a page reload.
  - **`empty_value` is not decoration.** An unchecked radio group submits *nothing*, so a filter the user never touches would vanish from the query string instead of arriving as `""`. Any filter with an "everything" state needs `empty_value=""`. Two failure modes to check for when adding one: a spec that already starts with `":All …"` *and* `empty_value=""` renders the option **twice**, and a queryset filter with neither has **no way back to "all"** once chosen.
  - **Replacing a `<select>` with a hand-written list is how options go missing.** The ticket assigned filter kept only `me`/`unassigned` while `TicketListView` still resolved `assignees__id=<pk>`; see `extra_choices` for the fix. When converting, diff the *option set*, not just the markup.
  - **`obj_pairs` calls a callable label.** `get_full_name` is a method, and `str()` on it renders `<bound method …>`. `obj_pairs` calls it, falling back to `username` when a member has no full name. Keep it that way.
  - **`{% extends %}` must stay the first tag** in a template. `{% load dropdown_tags %}` goes *after* it; prepending is a `TemplateSyntaxError`.
  - A dropdown names itself on its `<summary>` (`aria-label`), and its options are wrapped in implicit `<label>`s — so there is **no `<label for>` and no `id`**. Tests that asserted "every input has a matching label" must accept the summary's `aria-label` instead; do not weaken them to pass.

### Serop integration (`apps/serop/`, `apps/accounts` OAuth views)

This repo is the cloud backend for **Server Operator** ("Serop"), a separate Electron app in the parent working directory (`../CLAUDE.md`) — an actual dependent, not just an SDK-ingesting customer. Two things exist purely to serve it:

- **OAuth-ish sign-in** (`apps/accounts/views.py`: `OAuthAuthorizeView` / `OAuthTokenView` / `OAuthMeView`, models `ExternalAuthCode` / `ExternalAccessToken`) is a loopback-redirect flow (`redirect_uri` must be `127.0.0.1` / `localhost`) because there is no self-serve signup here; Serop's Electron main process catches the redirect. `ExternalAccessToken` is the bearer token every `apps/serop/` endpoint authenticates with (`apps/serop/authentication.py::ExternalTokenAuthentication` sets `request.user` to the real CRM `User`).
- **Serop "teams" are this app's `Company` / `Membership` directly.** Adding someone to a Serop team creates a real `Membership` (`defaults={"role": Membership.Role.VIEWER}`) in that company — a deliberate but easy-to-forget cross-product coupling. It grants no ticketing visibility by itself (`accessible_products` only auto-grants owners/admins), but it does mean the Serop team list and the ticketing UI's membership lists are the same data.
- The inbox WebSocket is `apps/serop/consumers.py`, routed by `apps/serop/routing.py` through `core/asgi.py`'s `ProtocolTypeRouter` at `/ws/inbox/?token=…`.
- `SeropSharedServer.encrypted_password` is Fernet-encrypted with `settings.SHARED_SERVER_ENCRYPTION_KEY` — never log or return it undecrypted outside `SharedServerCredentialsView`.
- CORS (`django-cors-headers`) is scoped by `CORS_URLS_REGEX = r"^/(oauth|api/serop)/.*$"`, so the CRM's session-cookie web UI is untouched. Note the token-authenticated Serop views are why some of them legitimately have no `messages.*`: they return JSON, and there is no page shell to host a toast.

### Auth

Custom `accounts.User` (`AbstractUser` + `discord_id`). django-allauth is installed but login/logout/signup are handled by `apps/accounts/views.py` (email + password). A user with no `Membership` is sent to `accounts:company_setup`, which creates a `Company` and an owner `Membership`.
