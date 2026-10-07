# context.md

The project's memory: **what was done, how it works, and why.** Written for the
next session — including an AI agent landing cold.

**How to use this file**

| If you want to… | Go to |
|---|---|
| find the code for an area | [Quick reference](#quick-reference--where-things-live) |
| know why something is the way it is | the date section for that area |
| check a decision is not being re-litigated | [Open questions](#open-questions--still-unanswered) |
| see what changed on a day | [Change log by date](#change-log-by-date) |

Rules for keeping it current are in `AGENTS.md`, under *"`context.md` is the
project's memory"*. **Update it at the end of every change** — a change with no
entry here is unfinished.

---

## Quick reference — where things live

| Area | Where it lives | The one thing to know |
|---|---|---|
| App shell / nav | `templates/core/base.html`, `templates/core/_sidebar.html` | One `<style>` block, htmx + Alpine from CDN, **no build step** |
| Toasts | `templates/core/base.html`, `apps/core/templatetags/toast_tags.py` | Seed must sit **above** `#toast-container`; every mutation must call `messages.*` |
| Multi-tenancy | `apps/products/access.py`, `apps/core/middleware.py`, `apps/core/mixins.py` | Company isolation **and** per-product access — both required, see `AGENTS.md` |
| Attendance | `apps/attendance/{models,service,views}.py` | `models.punch()` is the only write path; hours never move a payslip |
| Office hours / lateness | `apps/attendance/models.py::WorkShift`, `service.late_*` | Penalties are **derived, never stored**; there is no `LatePenalty` model |
| Leave | `apps/leave/{models,service,views,forms}.py` | The paid/unpaid split is **stored** on the request; payroll trusts it |
| DSR | `apps/dsr/{service,views,forms,models}.py` | A day is submitted **on the day** — `service.submission_window` is the only rule; `auto_log_ticket_dsr` writes **unvalidated** |
| Sign-in | `apps/accounts/{views,forms}.py`, `templates/accounts/login.html`, `apps/core/redirects.py` | `base.html` owns `.auth-shell`; `?next=` must go through `safe_next`; `{# #}` is **line-scoped** |
| Icons | `apps/core/icons.py`, `apps/core/templatetags/icon_tags.py` | `render_icon()` emits **no** `width`/`height` — every `{% icon %}` consumer needs a CSS size rule or it renders 300x150 |
| Payroll | `apps/payroll/service.py` | Pay = payable days × daily rate. No overtime, no hours input |
| Dashboard | `apps/dashboards/service.py` | Personal-first; company-wide numbers gated behind `is_privileged` |
| Tickets / errors | `apps/tickets/`, `apps/errors/`, `apps/products/views.py` | Same logic **twice**: global + product-scoped. Both must stay in sync |
| Ingestion API | `apps/ingestion/` at `/api/v1/` | `Bearer` API key; `request.user` is `None` |
| Serop integration | `apps/serop/`, `apps/accounts/views.py` | Teams **are** `Company`/`Membership`. See `AGENTS.md` §Serop |
| Changelog | `apps/core/changelog.py`, `CHANGELOG.md` | A runtime asset, not docs. Parser-driven format — see `AGENTS.md` |
| Version | `core/settings.py::APP_VERSION` | Env override `DJANGO_APP_VERSION`; served at `/api/v1/version/` |

---

## Current state

- Branch `main`, **47 uncommitted paths** (many untracked). The 2026-10-02 work is
  real and uncommitted — do not assume a clean tree, and do not discard untracked
  files without checking this file first.
- Release **1.0.1**. Full suite **768 tests, 2 failures**, both pre-existing and
  unrelated to any recent work: `test_signup_creates_user` (`accounts:signup`
  route no longer exists — a product question, see Q6) and
  `test_attendance_reflects_only_my_own_punches` (time-of-day dependent; it
  only fails when the suite runs late in the day).
- Sign-in: `/login/` renders as two columns on desktop, form only under 860px;
  brand panel is decorative and collapses first.
  `apps/accounts/tests/test_login.py` is the net — 34 tests.
- Suite takes ~3.5 min. Background it.
- No CI, no lint, no typecheck. `manage.py check` (expect only
  `staticfiles.W004`) plus the suite is the whole gate.

---

## Change log by date

> Only one archived long-form diary exists: `changes-2026-09-30.md`, kept because
> that day's reasoning was too large to compress without loss. **`context.md` is
> the working memory** — a new day gets a section *here*, not a new `changes-`
> file. Do not create another one unless a day's detail genuinely cannot fit;
> that duplication is what this file replaced.

### 2026-10-03 (sign-in) — the login page rebuilt, and `{# #}` is line-scoped

**What changed.** `templates/accounts/login.html` was rewritten around a
two-column layout (brand panel + form) with `apps/accounts/forms.py`,
`apps/accounts/views.py` and the auth CSS in `templates/core/base.html`.
New `apps/core/redirects.py::safe_next` now backs both login's `?next=` and
`apps/attendance/views.py::_safe_next`. Coverage lives in
`apps/accounts/tests/test_login.py` (31 tests).

**Four real bugs, all of the same shape: a thing that looked right in the
template and was wrong in the rendered HTML.**

1. **Multi-line `{# … #}` comments are not comments.** Django's `{# #}` is
   *line-scoped*; a second line is ordinary text. Three multi-line comments in
   `login.html` rendered verbatim, so developer notes about the form appeared
   in the visitor's browser as body copy. `{% comment %}` is the multi-line
   form. **`test_no_template_comment_reaches_the_page` now pins this** — it was
   the single highest-value test in the file.
2. **`.auth-shell` was doubled.** `base.html` already wraps
   `{% block content_full_only %}` in `.auth-shell` (that's how the logged-out
   branch works), and the template added its own. Nested, it is two
   `min-height:100vh` grids, so the page centred twice and scrolled. The
   template now supplies only `.auth-wrap`.
3. **The password toggle carried `tabindex="-1"`** — invisible to every
   keyboard user while plainly visible on the page. It is now a real
   `type="button"`, reachable, with `aria-pressed`/`aria-controls`.
   `test_the_password_toggle_is_reachable_by_keyboard` splits the markup on
   the button's own tag and asserts `tabindex` is absent, so the assertion
   can't drift onto some other element.
4. **The only heading on the page was an `<h2>`.** It is now the single
   `<h1>Sign in</h1>`, and the brand tagline is a `<p>` — a tagline above the
   `<h1>` is decoration, and promoting it put a subheading before the title.
   The CSS selector changed with it (`.auth-brand h2` → `.auth-brand
   .brand-line`); a selector left behind would have silently killed the style.

**Two test lessons worth more than the code.** `base.html` inlines the whole
stylesheet into every page, so `aria-invalid`, `<svg` and `h2` all appear in the
response **as CSS selectors**. Six of the first nine tests failed for that
reason alone — the clean-form test "found" `aria-invalid` in
`.auth-input[aria-invalid="true"]`, and `test_no_hand_written_svg_survives`
demanded zero `<svg>` from a page whose whole icon system renders `<svg
class="ic">`. The `body()` helper strips `<style>`/`<script>` and slices from
`<body>`; assertions now target markup. Also: `id_for_label` is on the
**BoundField**, not the Field — `form[name].id_for_label`, not
`field.id_for_label`.

**Security.** `safe_next` uses `url_has_allowed_host_and_scheme` with no
allowed hosts, so only relative paths survive; `//host/`, `/\host/` and
absolute URLs (including our own host) are dropped. `?next` is validated on
GET, carried in a hidden input, re-validated on POST, and ignored if invalid.
The failure message is now "Incorrect username or password." rather than
"Invalid credentials.", so the form no longer distinguishes a wrong password
from a nonexistent account.

**A DEBUG-gated demo-credentials panel was built, then removed.** The seeded
logins are printed by `seed_data` for whoever is setting the app up; putting
them on the login page as well was judged a bad trade and was deleted rather
than switched off — `DEMO_LOGIN_HINT`, the `demo_users` context value and the
`.auth-demo` CSS are all gone. `NoCredentialsOnTheLoginPageTest` now pins the
absence instead, in DEBUG *and* production, and asserts `DEMO_LOGIN_HINT` is no
longer a setting. The reasoning: the gate is one settings flip from being
wrong, and the seeded accounts are exactly the ones someone would try against a
real deployment.

**Visual register: deliberately plain.** The background is a 22px dot grid
(`--border` dots on `--panel`) rather than coloured radial blobs, and the brand
panel is flat `#182b4d` rather than a blue gradient. The panel copy was also cut
down — it had been written as landing-page copy ("Every product signal, in one
place", "before it becomes a customer call") and now only states which parts of
the app are covered. **Do not reintroduce gradient blobs or marketing register
on this page**; it is a login form for an internal tool, and the `.brand-line`
was dropped from 27px to 15px for the same reason.

**Deliberately not changed.** No password-reset link — there is no such route
anywhere in the project, and a dead link is worse than none. No change to the
`accounts:dashboard` default redirect, which the dashboard test depends on.
No per-page `<style>` and no second stylesheet: the auth CSS still lives in
`base.html`'s single block, per `AGENTS.md`.

**Verification.** `venv/bin/python manage.py test apps.accounts.tests.test_login`
→ **31 tests, OK**. `apps.accounts apps.core apps.dashboards apps.attendance`
→ 329 tests, only the two known pre-existing failures. `apps.leave` → 124 OK,
which includes `PolicyScreenTest.test_every_vendored_icon_is_inert` over the
two new `eye` / `eye-off` icons. Checked visually via `Client().get('/login/')`
under `override_settings(ALLOWED_HOSTS=['testserver'])` — a bare `Client()` in
`manage.py shell` raises `DisallowedHost` because it bypasses the test runner's
`setup_test_environment`.

Re-verified after the demo-panel removal and the visual pass: login suite still
**31 tests OK**; `apps.accounts apps.leave apps.core` → 268 tests with only the
known `test_signup_creates_user` error. Full suite was **765 tests, 2 known
failures** immediately before those edits.

**Open, and found while working.** Twelve **pre-existing** multi-line `{# #}`
comments in ten other templates leak the same way (`my_attendance.html:128`,
`base.html:1129`, `my_leave.html:37,80`, `_apply_form.html:24`,
`_split_preview.html:26`, `_approval_list.html:26,44`, `_team_body.html:143`,
`_month_grid.html:19,31`, `_record_edit_form.html:22`). Not touched — out of
scope for the sign-in work, and each renders only when its branch is taken. They
are the next candidate sweep.

#### Same day, later: the eye icon, and two silent regressions it exposed

**What changed.** `apps/core/icons.py` gained vendored Aria/Lucide `eye` and
`eye-off` (Lucide collection, geometry checked against local `lucide-react`
0.460.0 — `AGENTS.md`'s suggested `GET /api/v1/icon?id=lucide:<name>` endpoint
does not exist in this repo). `templates/accounts/oauth_authorize.html` dropped
its two hand-written Feather-style SVGs and `tabindex="-1"` for `{% icon %}`, and
its `<h2>`/unlabelled password label became `<h1>`/`for="id_password"`.

**Why the icon looked wrong: size, not path.** `render_icon()` emits a `viewBox`
and no `width`/`height`, so an SVG falls back to the CSS replaced-element default
of **300x150px** and bursts out of the 30px `.pw-toggle` button. The path data was
correct all along. Every `{% icon %}` consumer therefore needs a CSS size rule;
`base.html` now has `.pw-toggle .ic{width:16px;height:16px;flex-shrink:0;}`.

**Two regressions found while verifying, both mine, both silent.**

1. **`.auth-card` was deleted from `base.html` during the auth rewrite, and
   `oauth_authorize.html` still uses it** — the whole Serop sign-in screen came
   back as unstyled bare text. **No test failed, because no test rendered that
   page.** The rules are restored, deliberately kept separate from `.auth-wrap`,
   and `LoginPageMarkupTest.test_every_auth_class_used_is_actually_styled` now
   walks the `auth-*` classes both auth templates use and asserts each has a rule
   in `base.html`. That is the general form of the bug: **class names are the
   contract between templates and the single stylesheet, and nothing checked it.**
2. **The password `<label>` was moved inside `.pw-wrap`**, which broke the
   toggle's alignment. `.pw-toggle` is `top:50%` of `.pw-wrap`, so the wrapper
   must hold only the input; with the label inside, the wrapper grew to
   label+input and the button centred across both, landing on the label about
   12px too high. At `HEAD` the label was a sibling, as on the OAuth page. Fixed,
   and pinned by
   `test_the_password_label_sits_outside_the_toggle_wrapper`.

**Verification.** Both new tests were confirmed to **fail with the regression
reintroduced** and pass with it fixed — a test that passes on broken code is
worthless. Reintroducing `.auth-card`'s removal produces
`templates/accounts/oauth_authorize.html uses .auth-card but base.html never
styles it`. `apps.accounts.tests.test_login` → **34 tests OK**; `apps.accounts`
→ 53 tests with only the known `test_signup_creates_user` error. `apps.core`
(changelog parser + history) → 94 OK. **Full suite → 768 tests, the same 2 known
pre-existing failures** — `test_signup_creates_user` and
`test_attendance_reflects_only_my_own_punches`. 768 is 765 plus the three tests
added here.

**Asserting on these pages.** Use the `body()` helper in `test_login.py`: it
strips `<style>`/`<script>`, because `base.html` inlines the whole stylesheet and
a naive `'pw-wrap' in html` or `'<h2' not in html` matches **CSS selectors, not
markup**. Likewise `{% icon %}` *emits* `<svg>`, so "no hand-written SVG" is
asserted as `'<svg' not in html.replace('<svg class="ic"', '')` — never as
"no `<svg`".

### 2026-10-02 (DSR) — long-running tickets no longer break the dashboard

**What changed.** Two unrelated-looking fixes to the DSR area, found together.

1. `hours_spent` was widened from `max_digits=5` to `max_digits=8`
   (migration `apps/dsr/migrations/0002_alter_dsrentry_hours_spent.py`).
2. A DSR day is now **submitted on the day and read-only afterwards**:
   `apps/dsr/service.py::submission_window`.

**The crash, and why it took so long to find.** Production `/dashboards/` was
500-ing with `decimal.InvalidOperation`. `DSREntry.hours_spent` was
`DecimalField(max_digits=5, decimal_places=2)`, so the largest storable value is
`999.99`. `auto_log_ticket_dsr` (`apps/dsr/service.py`) writes
`now - ticket.created_at` as hours with a floor of `0.25` and **no ceiling**,
through `update_or_create` — which runs **no validators**. A ticket open **42+
days** therefore wrote `>=1000.00`, SQLite stored it as REAL without complaint,
and the read-back died in `create_decimal_from_float(...).quantize(0.01,
context=expression.output_field.context)`, whose precision **is** `max_digits`.

Three things hid it, and all three are worth not repeating:

- `Ticket.transition_to` (`apps/tickets/models.py`) wraps the auto-log call in
  `except Exception: pass`, so any write failure is discarded silently. **Still
  not fixed** — it was outside the scope chosen. It is why this was invisible.
- SQLite enforces nothing about DECIMAL, so the write succeeded with no error.
- The old test only asserted `hours_spent > 0`, which passes for `99999999`.

**Widening alone fixes the existing bad rows** — no repair command, no raw SQL,
no downtime — because `prec` goes 5→8, so the already-stored values read back.
Verified: with `max_digits=8`, `1000.0` / `1500.0` / `24000.0` / `99999.99` /
`999999.99` all quantize cleanly. The user asked for up to ~99999h; the field now
holds 1000000.00 (114 years).

**Deliberately NOT capped** (user's decision, 2026-10-02). A 60-day ticket reads
`1440h`. Safe because `time_taken_formatted` prefers
`completed_time - created_time`, so display is right regardless, and **payroll
never reads DSR hours** (verified — no money impact). Do not "tidy" this by
re-adding a cap without asking.

**One non-obvious consequence of widening.** `DSREntryUpdateView` re-validates
*every* posted field, so an unconditional `hours > MAX_HOURS` check made each
wide row **permanently uneditable** — editing its status alone failed on hours.
`DSREntryForm.clean_hours_spent` now tests `"hours_spent" in self.changed_data`,
so keeping a wide value passes while *typing* a big number is still refused. Note
`self.has_changed()` is **form-wide** and would have fired on a status-only edit
— use `changed_data`, not `has_changed()`. It is populated before field cleans
run, so the check is safe inside `clean_hours_spent`. The `max="24"` literal in
`templates/dsr/partials/_dsr_row.html` was removed for the same reason; the
server is the real authority.

**The DSR submission window.** `submission_window(day, is_privileged)` returns
`(can_submit, reason)`. A day is open while `timezone.localdate() == day`, so a
sheet is still writable at 23:59 and read-only at 00:00 — the "submit by
11:59pm" boundary is derived from the local date, **not** a stored cutoff, so it
cannot drift from the timezone. Future days are closed to **everyone**, including
admins: hours cannot be worked yet, and an override there would only admit bad
data. Past days are read-only, with an **owner/admin override** (the user's
choice) so a forgotten or mistyped sheet stays correctable.

**Enforced server-side before any mutation** in `DSREntryAddView`,
`DSREntryUpdateView` and `DSREntryDeleteView` — `date` arrives from the query
string, so the UI is not a boundary. `_get_dsr_context` publishes `can_submit`
/ `locked_reason`, and the templates render a read-only sheet (plain spans, no
`hx-post`) rather than controls that would 403. `next_date` is clamped to today
and the date picker is capped, so `→` stops at today.

**Unaffected:** viewing any date already worked (date picker, ←/Today/Yesterday/→,
`?date=`), and `auto_log_ticket_dsr` writes straight to the ORM so it is not
gated by the window — correct, since an auto entry is always dated today.

**Verified.** `apps.dsr` 37 tests pass. Both new groups were checked against the
unfixed code: reverting `max_digits` to 5 fails all 4 wide-value tests with the
production `decimal.InvalidOperation`, and neutering the window fails 4 lock tests.
`apps.dsr apps.dashboards apps.tickets` = 151 tests, 1 failure — the known
time-dependent attendance one (see Q10), not this change.

### 2026-10-02 (later) — one dropdown everywhere

**What changed.** Every visible native `<select>` in the project was replaced by
one shared component, so no screen shows a browser-default dropdown any more.

**How it works now.** `{% dropdown %}` in
`apps/core/templatetags/dropdown_tags.py` renders
`templates/core/partials/_dropdown.html`: a native `<details>` holding radio or
checkbox inputs — the same idiom as the leave icon picker. The value still posts
with the form when JavaScript is off, and a change still fires a native `change`
event, so `hx-trigger="change"` filtering and the HTMX quick-edit forms were not
rewritten. `.dd-*` CSS and the Alpine `dd` component live in the single
`<style>` block in `templates/core/base.html`; Alpine only relabels the closed
trigger and calls `buildUrl` / `requestSubmit`.

Modes are distinct on purpose: `navigate=True` for a filter outside a form,
`submit=True` for a control that posts its form on change, and neither for an
ordinary form field.

**Two things the rollout had to get right, and did not at first.**

1. **A hand-written choice list is not the same set as the queryset it replaced.**
   The ticket assigned filter became just `me` / `unassigned`, silently dropping
   every member — while `TicketListView` still resolved `assignees__id=<pk>`.
   A template cannot concatenate two iterables into one tag argument, so
   `extra_choices` was added instead of duplicating a context block per view.
2. **`obj_pairs` was stringifying a bound method.** `str(getattr(user,
   "get_full_name"))` renders `<bound method AbstractUser.get_full_name of
   <User: bob>>`, which put a Python repr in front of every person in the ticket
   assignee filter, the audit-log actor filter, the DSR employee picker and both
   `assign_to` pickers. A callable label is now called. Caught by a new test, not
   by reading the diff.

**Also fixed while converting:** `{% load %}` had been prepended *above*
`{% extends %}` in three templates, which is a `TemplateSyntaxError` — `extends`
must be the first tag. Four dropdowns rendered their "All" option twice (an
inline spec starting with `":All …"` plus `empty_value=""`), and two error-list
filters had no "All" option at all, so a chosen filter could not be cleared.

**Deliberately not changed.** The ticket assignee multiselect
(`templates/tickets/partials/_assignee_multiselect.html`) is already a richer
custom dropdown with search and chips, so it was left alone; its `<select>` is
`display:none` and exists to carry the form value, which is the same progressive
enhancement approach taken here. It is the only `<select>` left in `templates/`.

**How it was verified.** `venv/bin/python manage.py test apps` — **721 tests,
1 failure + 1 error, both pre-existing** (see below). Targeted: 25 dropdown and
ticket-filter tests, 187 across dashboards/leave/dsr/errors.

#### Two failures that are NOT the dropdown's doing

Both predate this work and are still open; do not "fix" them as part of a UI
change.

- `accounts.tests.test_tenant_isolation…test_signup_creates_user` —
  `NoReverseMatch: Reverse for 'signup' not found`. `accounts:signup` does not
  exist as a route; allauth is installed but not wired up. A product question.
- `dashboards.tests.test_dashboards.PersonalDashboardTest.test_attendance_reflects_only_my_own_punches`
  — **time-of-day dependent.** It asserts
  `assertLess(expected, colleague_minutes)` where `colleague_minutes` is 480 and
  `expected` is `attendance_service.effective_span_for(...)` for an *unclosed*
  punch, which is capped at `shift.worked_minutes_per_day` = 480. So it passes
  only while the suite runs within 8h of the punch's check-in and fails later in
  the day. The same clause as the cap in `Q…`/attendance notes: this is the
  "never assert a today-timestamp against a literal" trap, in a second disguise.
  **Not fixed here** — deciding what an isolation test should assert is a
  separate call, so it is recorded rather than rewritten.

### 2026-10-02 — released as 1.0.1

User-facing version: the `## [1.0.1]` block in `CHANGELOG.md`.

#### The timezone was costing money

**What.** `TIME_ZONE` changed `"UTC"` → `"Asia/Kolkata"` in `core/settings.py`.

**How.** Storage was always right (`USE_TZ = True` keeps UTC). `TIME_ZONE` is
what decides *display* and *day boundaries*: `timezone.localtime()`,
`timezone.localdate()`, every `|date:` filter, and `service.lateness_for`, which
compares `timezone.localtime(record.check_in).time()` to `WorkShift.start_time`.

**Why it was wrong.** `service.lateness_for` reduces to:

```python
scheduled = timezone.localtime(record.check_in).time()
return max(0, scheduled_minutes - shift.start_time_minutes)
```

| Arrival (IST) | Stored | Read back as | vs 10:00 start | Penalty |
|---|---|---|---|---|
| 10:45 | `05:15Z` | `05:15` | −4h45m → `max(0, −285)` | **0** |
| 10:45 | `05:15Z` | `10:45` | +45m | major, Rs 100 |

A 10:45 IST arrival was read as 05:15, and the `max(0, …)` — which is correct for
arriving early — turned the negative into **zero**. Nobody was ever charged a
late penalty, and the punch panel printed "Checked out 05:15 AM".

**Why it stayed a one-line fix.** `grep -rn "timezone.utc\|utcnow" apps/` was
already empty outside tests. **Keep it empty.** It only became *visible* after the
panel started printing real arrival times — a rule that is quietly always zero has
no symptom until it is rendered.

**Files.** `core/settings.py`, `apps/core/management/commands/seed_data.py`.

#### Punch panel and forgotten check-outs

**What.** The punch panel shows arrival time, shift window, live elapsed time and
**immediate** lateness. Any unclosed day is fixable from wherever it is shown.

**How.**
- `_punch_context(request, record, message, person)` in `apps/attendance/views.py`
  builds the panel for **both** the page load (`MyAttendanceView`) and the htmx
  punch (`AttendancePunchView`), so the DOM cannot disagree with the server. It
  takes `person` **explicitly** — never infer it from `record.user`, or an admin
  reading a colleague's page gets the *admin's* forgotten days.
- Three screen states are distinguished by `is_complete` → `is_open_today` →
  neither. `is_open` cannot separate them: it is true both for someone working
  now and for a punch nobody closed.
- Lateness comes from `service.late_penalty_for` — the **same call the payslip
  line is built from**, so the warning cannot quote a different number from the
  charge.
- `service.effective_span_for(record, shift)` credits an unclosed day as elapsed
  time **capped at `shift.worked_minutes_per_day`**. The cap is not optional:
  elapsed runs to *now*, so one forgotten punch from last month reports 300h.
- `service.unclosed_days(company, user)` lists **every** unclosed day (all months,
  not the month on screen), excluding today's legitimately-open record.
- `AttendanceEditView` takes GET as well as POST so any day can link to
  `/attendance/<pk>/edit/`. The shared form partial
  (`templates/attendance/partials/_record_edit_form.html`) prefills a missing
  check-out with the shift's `end_time`, because the cap assumes they left at
  closing.

**Why it matters.** This cannot move anyone's pay — payslips price payable
*days* and `late_penalties_in_period` reads only `check_in`.

**Files.** `apps/attendance/{models,service,views}.py`,
`templates/attendance/{my_attendance,edit_record}.html`,
`templates/attendance/partials/_punch_{form,button}.html`,
`templates/attendance/partials/_late_note.html`,
`templates/attendance/partials/_record_edit_form.html`, `apps/attendance/tests.py`.

#### Leave: over-cap is charged, not refused

**What.** A request past the allowance now succeeds — days up to the limit are
paid, the rest unpaid.

**How.**
- `service.auto_split(company, user, policy, start, end, days)` returns
  `{paid, unpaid, reasons}` and allocates paid days from the **start** of the
  span, so the unpaid tail is what falls past the cap.
- `service.working_days(start, end)` counts **Mon–Fri only** (Fri→Mon = 2 days,
  not 4). It returns a plain `int`, so anything rendering a day count must go
  through `service.format_days`, which coerces.
- **The split is stored** on `LeaveRequest` (`paid_days`, `unpaid_days`,
  `split_mode`) and **payroll trusts it** — including an approver who marks days
  from an unpaid type as paid. Payroll must never re-derive it, or a later policy
  edit restates an issued payslip.
- Migration `0003` backfills historical rows from the policy **in force at
  migration time**, for the same reason.
- The applicant sees the split **before** submitting: `LeaveSplitPreviewView`
  (`leave:split_preview`) re-runs `auto_split` live. The panel is empty by design
  while dates are incomplete, rather than claiming "0 paid" mid-typing.

**Why.** Refusing an over-cap request meant applicants had to guess how much to
ask for and get it turned away.

**Files.** `apps/leave/{models,service,views,forms}.py`,
`apps/leave/migrations/0003_*.py`, `apps/payroll/service.py`,
`templates/leave/partials/{_split_preview,_decision_dialog}.html`.

#### Toasts were dead everywhere

**What.** Every confirmation and error message in the app rendered nothing,
**while the actions themselves worked** — so the UI looked broken for precisely
the things it reported as succeeding. Then, auditing the handlers, **three flows
turned out never to ask for a toast at all**.

**How.** `{% if messages %}` in `templates/core/base.html` emits
`<script id="toast-seed" type="application/json">` via the `toast_payload` tag
(`apps/core/templatetags/toast_tags.py`), and it must sit **above**
`#toast-container`, whose own `x-init` looks it up by id.

**Why it was broken.** The queue used to be dispatched on `alpine:init`, which
Alpine fires **before** it walks the DOM — so the container's `x-data` did not
exist yet and the guard silently did nothing. The action worked, the app said
nothing.

**Three flows that never asked:** `DSREntryDeleteView`,
`ProductMilestoneDeleteView`, `ProductMilestoneToggleView`. Clicking through the
app does not visit every handler — that is why the fix was an `ast` scan of
`apps/*/views.py`, not a manual pass. `ingestion/*` and the OAuth views are
correctly silent: they return JSON, and there is no page shell to host a toast.

**Files.** `templates/core/base.html`,
`apps/core/templatetags/toast_tags.py`, `apps/core/tests_toast.py`,
`apps/products/tests/test_toasts.py`, `apps/dsr/views.py`,
`apps/products/views.py`.

#### The changelog was not in the production image

**What.** `.dockerignore` had `*.md`, which dropped `CHANGELOG.md` from the
image, so the sidebar "What's new" dialog was empty in production.

**Why it went unnoticed.** A missing changelog renders as an **empty dialog, not
an error** — `/api/v1/changelog/` returns `200` with no releases, so nothing
logged and every local check passed because the file was on disk. `Dockerfile`
does `COPY . .`, so `.dockerignore` alone decides it.

> **The class of bug, not just this instance:** every changelog test reads the
> file from the **working tree**, where it exists. The suite was green on the host
> and empty in the container. No unit test can see that difference — only a test
> that inspects the image, or a real `docker build` probe. Keep that in mind for
> any other file the app reads at runtime.

`!CHANGELOG.md` must stay **after** `*.md`; Docker applies patterns in order and
the last match wins. `AGENTS.md`, `README.md` and `changes-*.md` stay excluded —
they are not read at runtime. Verified against a real image, not by reading the
file: a probe build showed `CHANGELOG.md` and only that one, and
`manage.py shell` in the image reported 4 releases.

**Also.** "Never delete or rewrite an existing release entry" is a standing user
requirement. Add a new release at the top; a test compares the older blocks
against `HEAD`.

**Files.** `.dockerignore`, `apps/core/changelog.py`, `apps/core/tests.py`.

#### Verification

Full suite **694 tests, 1 failure** (`test_signup_creates_user`, pre-existing).
`manage.py check` clean apart from expected `staticfiles.W004`;
`makemigrations --check --dry-run` clean (every attendance addition is a
property, so there is no schema to migrate).

---

### 2026-09-30 — office hours, lateness in payroll, sidebar

Long record: archived as [`changes-2026-09-30.md`](changes-2026-09-30.md) — the
one day whose detail was too large to compress without loss. Read it for the
full reasoning on lateness policy, the sidebar rebuild, and the ~90-instance label
bug; the summary below is the finding layer.

- **Lateness became a payroll fact.** `WorkShift` holds both the hours and the
  bands (Rs 50 / Rs 100 / half day). `service.shift_for` is a `get_or_create`,
  deliberately not a required FK — the defaults *are* the policy.
- **Pay = payable days × daily rate.** Only *unpaid* leave and *lateness* deduct.
  Two mechanisms, deliberately not conflated: cash bands subtract from `gross`;
  a half day reduces `payable_days`. `service.late_pay_in_period` splits them, and
  `preview` / `generate_run` share it so the estimate and the issued run can never
  quote different numbers.
- **Leave policy became per-type, per-company.** Both caps optional; blank means
  **"No cap"**, never "Unlimited", because `0` is a real setting.
- **The sidebar was rebuilt**, and a label sweep fixed ~90 instances of one bug.
- **A committed plaintext API token** was found in `test_api.py` — see Q8.

**Files.** `apps/attendance/`, `apps/payroll/`, `apps/leave/`,
`templates/core/_sidebar.html`, `apps/core/context_processors.py`.

**Verification.** 577 tests, 3 failures — 1 pre-existing signup, 2 from scratch
scripts being imported by test discovery.

---

### 2026-09-04 and earlier

- Dashboard reworked; ticket boards unified and htmx-ified — `5b97709`.
- Serop integration (OAuth-ish loopback sign-in, teams/shared-servers/inbox) —
  `80127d7`.
- Attendance, leave and payroll added — `4653907`.

No `changes-*.md` exists for these; the two `## [Unreleased]` blocks in
`CHANGELOG.md` are the record.

---

### 2026-10-07 — DSR API for the dsr-mcp server

- New JSON API at `/api/v1/` (`apps/dsr/api.py`, `api_urls.py`): `users/me/`, `projects/`, `activities/today/`, `dsr/today/`, `POST dsr/`, `PUT|PATCH dsr/<id>/`. Used by the separate repo `RandomKid24/dsr-mcp` (not built yet).
- Auth reuses `ExternalAccessToken` with `client_id="dsr-mcp"` (get one through the existing loopback `/oauth/authorize` flow). `DSRTokenAuthentication` accepts only that client id, and Serop's `ExternalTokenAuthentication` now rejects it, so an MCP token cannot read Serop teams or shared-server credentials.
- Writes reuse `DSREntryForm`, `submission_window` and `suggestions`, so the API follows the web sheet's rules (hours cap, today only for non-admins, accessible products only). A DSR is still one `DSREntry` row per task; there is no single "report" object.
- Duplicates answer 409 with the existing entry (same ticket, same `source`+`source_id`, or same task name that day); the client then uses PUT. Entries have `source` / `source_id` (migration 0005) as the audit trail.
- Company is the user's first membership unless `?company=<id>`. API users can only edit their own entries (web admins can still override).
- Not done: no DELETE, no CHANGELOG entry (internal API, would need an `APP_VERSION` bump), hours still come from the client.

## Deliberately not changed

A rejected approach with a reason, so it is not re-proposed.

| Not done | Why |
|---|---|
| Overtime / hours-based pay | Would need deciding how it prices; nothing in attendance is allowed to move a payslip |
| A `LatePenalty` model | Penalties are derived on every call, so editing a `check_in` cannot leave a stale charge behind |
| Backfilling historical attendance timestamps | That is data written under the old zone, not schema. A migration would restate punches |
| `balance_for` subtracting only approved leave | Pending leave must reserve balance, or two people book the same last days |
| "Unlimited" on the leave policy | A cap of `0` is real (nobody may take that type) |
| Non-salaried "half a Saturday for lateness" | Not on this payroll — `PayrollProfile` has no employment-type field. Adding it needs a prior decision on how a make-up day prices |
| A `WorkShift` admin screen | One global value; not obviously worth the surface area |

---

## Open questions — still unanswered

An unanswered decision is more valuable than a settled one: it is what a session
would otherwise re-ask or quietly contradict. **When one is answered, note who
decided what and strike the item** rather than deleting it.

| # | Question | Why it is still open |
|---|---|---|
| Q1 | Should historical attendance rows be backfilled? | Demo was re-seeded. A real deployment needs a decision per row; no script guesses at it. |
| Q2 | Should the unclosed-day cap credit up to `shift.end_time`? | That is the generous reading. The alternative punishes the employee for an admin not closing the row. |
| Q3 | Is the Rs 100 band right for 31–60 minutes? | Carried over from existing policy, never re-examined. Band boundaries are **inclusive-at-top on purpose** (10:30 = Rs 50, 11:00 = Rs 100) — flip it with its test, not by editing the comparison. |
| Q4 | Should over-cap leave go to a second approver? | It currently succeeds, with the approver able to override the split. |
| Q5 | Should `TZ=Asia/Kolkata` be set in the image/compose file? | Code is zone-agnostic, but the seeded demo needs the *host clock* on IST. |
| Q6 | Should self-signup exist? | `accounts:signup` is not wired up, so `test_signup_creates_user` is red. A product question, not a stale test. |
| Q7 | How should htmx-swapped actions show an instant toast? | A view returning a `partials/` fragment never renders `base.html`, so its message lands on the **next full page load**. Offered, not built. |
| Q8 | Should the committed API token in `test_api.py` be rotated? | Found 2026-09-30, unfixed. Re-verified 2026-10-02: the key is present in plaintext in `test_api.py` and `test_api10.py`, committed since July. It returns `403 Invalid or revoked API key` everywhere, so **nothing is being written** — but it must be **rotated, not edited in place**, in case it was ever valid elsewhere. Separately, importing either file fires ~45 real `POST`s to `localhost:8000`; discovery skips them under `manage.py test apps` but **not** under bare `manage.py test` from the repo root. |
| Q9 | Should `Ticket.transition_to` stop swallowing auto-log failures? | `apps/tickets/models.py` wraps `auto_log_ticket_dsr` in `except Exception: pass`, which is **why the decimal crash went unnoticed** for so long. Deliberately left alone on 2026-10-02 (scope was the crash only). The obvious replacement is `logger.exception`, but a ticket status change then risks a visible error where the DSR write was merely best-effort. |
| Q10 | Should the attendance dashboard test stop depending on wall-clock time? | `PersonalDashboardTest.test_attendance_reflects_only_my_own_punches` asserts one punch is shorter than another, so it passes early in the day and fails late (`AssertionError: 480 not less than 480`). Long-standing, unrelated to any recent change. The fix is to derive the expectation from `apps/attendance/service.py` rather than comparing two live values. |