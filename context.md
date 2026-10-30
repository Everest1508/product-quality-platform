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
| Multi-tenancy | `apps/products/access.py`, `apps/accounts/access.py`, `apps/core/middleware.py`, `apps/core/mixins.py` | Company isolation **and** per-product access — both required, see `AGENTS.md`. A person with no `Membership` is locked out (`has_no_workspace`), not sent to company setup |
| Attendance | `apps/attendance/{models,service,views}.py` | `models.punch()` is the only write path; hours never move a payslip |
| Office hours / lateness | `apps/attendance/models.py::WorkShift`, `service.late_*` | Penalties are **derived, never stored**; there is no `LatePenalty` model |
| Weekly off days | `WorkShift.weekly_off_days`, `shift.is_weekly_off`, `weekly_off_for(company)`, `service.set_weekly_off`, `views.WeeklyOffView` | The one definition of a day nobody is expected in. Never write `weekday() >= 5`; payroll and leave read the same set |
| Expenses | `apps/expenses/{models,service,views}.py` | Owners and admins only; whole paise; each expense has a comment thread (`ExpenseComment`) |
| Leave | `apps/leave/{models,service,views,forms}.py` | The paid/unpaid split is **stored** on the request; payroll trusts it |
| DSR | `apps/dsr/{service,views,forms,models}.py`, `templates/dsr/` | Add form uses hour/minute `<select>` dropdowns; inline row edit and API still accept free text (`"45m"`, `"1h 30m"`); `duration.py` is the shared parser |
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

### 2026-10-12 (audit) — toasts for the silent mutations, audit rows for the unlogged ones

**What changed.** An AST scan of every mutation handler in `apps/*/views.py`
(`/tmp/audit_mutations.py`, throwaway) was classified with a subagent. Two
families of gaps were fixed:

1. **Toasts added where a mutation was silent.** Htmx fragment replies already
   deliver instantly via `HtmxMessagesMiddleware`, and the fetch-based
   bulk-delete UI already toasts client-side — so the only fix needed was
   calling `messages.*` in the silent views:
   - `apps/dashboards/views.py` — all four todo handlers now post messages
     (`TodoListView.post` "Added …" / "To-do text can't be empty.",
     `TodoToggleView.post` "Marked … done." / "Reopened …",
     `TodoDeleteView.post`, `TodoClearDoneView.post` "Cleared N completed
     to-do(s)." only when N > 0). The module previously had **no** `messages`
     import.
   - `apps/products/views.py::APIKeyRotateView.post` — "Key rotated — the old
     key is revoked now." / "… works until {date}." A rotation with no feedback
     was the worst kind of silent success: the old key stops working and
     nothing says why.
   - Bulk-ticket delete (`TicketBulkDeleteView`,
     `ProductTicketBulkDeleteView`) returns JSON that `base.html`'s
     `bulkDeleteTickets` `fetch` turns into a `toast()` itself — **not** a gap.

2. **Audit rows added where a user-driven state change was unlogged**
   (`log_activity`, all new free-form snake_case event types following the
   `ticket_deadline_changed` precedent — no model change, so they appear in
   the audit-log list but are not counted by `get_summary_report`):
   - `apps/accounts/views.py` — `CompanySetupView.post` → `company_created`
     (the first row of the new company); `ProfileView.post` →
     `profile_updated`, only when `form.changed_data` (an unchanged save is
     not an event).
   - `apps/dsr/views.py` — `DSREntryAddView` & `DSRSuggestionAddView` →
     `dsr_entry_added`; `DSREntryUpdateView` → `dsr_entry_updated`;
     `DSREntryDeleteView` → `dsr_entry_deleted`, all with
     `{user_id, date, product_id}` metadata and the sheet facts (date ·
     category · hours · status) in the description. The DSR is company state
     — a work-hours claim on the team sheet — so it belongs in the feed even
     though the sheet is per-person.
   - `apps/products/views.py` — `ProductMilestoneAddView` →
     `milestone_added`; `ProductMilestoneToggleView` → `milestone_toggled`
     (metadata `from`/`to` captured **before** the status change);
     `ProductMilestoneDeleteView` → `milestone_deleted`.
   - `apps/tickets/views.py::TicketFollowView.post` → `ticket_followed` /
     `ticket_unfollowed`, target = the ticket.
   - `apps/attendance/corrections.py::cancel` → `attendance_correction_cancelled`,
     logged inside the service like `request_correction`/`decide` (the rules
     live there), with the same `target_content_type="attendance_correction"`
     shape.

**Deliberately not changed** (classification results): Login (inline form
errors; success redirects to a page), logout / company-switch (session-only,
toasts already present), OAuth / ingestion / Serop / MarkAllRead / push-subscribe
(JSON or fetch APIs — no page shell to host a toast, per AGENTS.md),
`LeaveSplitPreviewView` (a preview, not a mutation), `PublicSurveyView`
(already logs `survey_response` and renders a thank-you page). To-dos get
toasts but **no** audit row: they are a personal scratch list
(`user=request.user`), and "added to-do: ship it" in the company feed would
be noise.

**How verified.** `apps.attendance.test_corrections` +
`apps.dashboards.tests.test_todos` + `apps.dsr.tests` +
`apps.tickets.tests.test_tickets` + `apps.products.tests.test_milestones` +
`apps.accounts.tests.test_tenant_isolation` → 177 tests; the only failure is
the known Q6 `test_signup_creates_user` (`NoReverseMatch: 'signup'`,
deliberately left red). `apps.products.tests.test_api_keys` → 36 OK. New
regression tests pinning the toasts and rows: todo HX-Trigger test in
`test_todos.py`; `test_cancelling_my_request_writes_an_audit_row`;
DSR add/update/delete audit tests; `test_following_and_unfollowing_are_audited`;
`test_milestone_actions_are_audited`; company-setup + ProfileAuditTest;
`test_the_rotation_toast_names_the_grace` (learned: rotating with "now" grace
revokes the key, so the test's second rotate uses a *fresh* key — the old one
400s).

**Still undecided.** Whether to-dos should ever appear in the company audit
feed (currently: no). Whether a rejected DSR update deserves a row (currently:
no — nothing changed, mirroring the leave "rejection discards the split"
rule).

**Released as 1.11.0.** At the user's request, the working-tree changes from
today (punch time/notification fixes + this audit sweep) were cut as
**1.11.0**: a `## [1.11.0] — 2026-10-12 · a toast for every action, and an
audit trail behind it` entry was added at the top of `CHANGELOG.md` (5
top-level bullets across New/Better/Fixed — New: audit rows + to-do toasts +
key-rotation toast; Better: punch notifications with late fee / day tally;
Fixed: UTC→IST punch times), and `core/settings.py::APP_VERSION` default
bumped `"1.10.0"` → `"1.11.0"`. No existing release entries were edited. The
parser pins hold: `apps.core` → 159 tests OK (including bullet-count vs HEAD
and the 700-char longest-item cap), and `get_version_info()` reports
version `1.11.0` / latest_release `1.11.0` / `2026-10-12` with 5 items.

### 2026-10-12 (attendance) — punch toast/notification showed UTC time; a Monday-only test failure

**What changed.**

1. **The punch message, toast and notification now show Indian time.** Both
   server-side formatting sites in `apps/attendance/views.py::AttendancePunchView.post`
   called `record.check_in.strftime("%I:%M %p")` on the raw value, which is
   stored **UTC** — a 10:02 IST punch produced a notification reading
   "Checked in at 04:32 AM." (and the same wrong time in the activity-log
   description). Both now go through `timezone.localtime(record.check_in)`,
   the same pattern `service._penalty_reason` already used. Verified:
   `apps.attendance.tests.PunchPanelTest` → 27 tests OK, including the new
   `test_the_punch_notification_shows_indian_time_not_utc` (asserts the htmx
   panel message *and* the `Notification` title contain the IST time and not
   the UTC strftime).
   - Related but deliberately **not** changed: the presence panel's
     `clock()` (`templates/core/_presence.html`) renders `clocked_in_at` via
     `new Date(iso).toLocaleTimeString()` — *device-local*, not IST. If the
     viewer's machine is on a non-IST zone, "In since …" still shows local
     time. Same for the punch panel's live `clock` getter (epoch ms). Decide
     whether every on-screen clock should force IST before touching these.
   - The templates were never affected: `{{ ...|date:"g:i A" }}` localizes
     via Django's template filter.

2. **`test_an_unclosed_day_does_not_create_a_late_penalty` was Monday-only**
   red: it built its record from "yesterday", and `lateness_for`
   (service.py:329) returns 0 for weekends, so on a Monday (yesterday =
   Sunday) the assertion `0 != 1` failed. Fix: roll the record back to the
   previous weekday when "yesterday" is Sat/Sun. The test still pins what it
   protected — an unclosed day *does* incur its `check_in`-based penalty
   because payroll reads `check_in` alone. Verified: single test and the full
   `apps.attendance` suite (197 tests) both OK.

3. **Punch notifications now carry a `body`** (the bell row and push alert had
   the field but it was always empty for punches). New
   `views._punch_notification_body(record, action, company)`:
   - check-in: the `late_penalty_for` result — `"45 min late — ₹100.00 late
     fee."`, `"… counts as a half day on this cycle's payslip."`, or `"On
     time for the 10:00 AM shift."` — the same call the payslip quotes, never
     a second copy of the rule;
   - check-out: `"{worked} worked today · {delta} short of/over a full {target}
     day"` plus `" · N earlier days still unclosed"` from
     `service.unclosed_days`, mirroring the panel's facts.
   `CURRENCY_SYMBOLS` is now a module constant shared by `_punch_context`'s
   `late_rules` and the helper, so the panel and the notification cannot
   disagree about the currency symbol. Verified:
   `test_the_punch_notification_body_names_lateness_or_the_day` (helper-level,
   deterministic: a live punch lands at "now" so lateness can't be tested
   end-to-end; each band needs its own user because `AttendanceRecord` is
   unique per company+user+date; the end-to-end check-out posts directly
   because the `htmx_panel` helper re-logs-in as `dev`). Full
   `apps.attendance` → 198 tests OK.

**How verified.** `apps.attendance` → 198 tests OK. `test_signup_creates_user`
remains red (Q6, unrelated).

**Open.** Q10 (wall-clock dashboard test) still open. Whether the device-local
JS clocks (`toLocaleTimeString`) should be forced to IST is now noted above —
needs a product decision.

### 2026-10-08 (DSR) — "Administration" category and hour/minute dropdowns

**What changed.** Two changes to the DSR entry form:

1. **New category "Administration"** added to `DSREntry.Category` choices.
   Migration `dsr/0006_add_administration_category.py` alters the `category`
   field. Styled with grey tones in `dsr_sheet.html`
   (`.category-select.administration`).

2. **Hour/minute dropdowns replace the free-text time input** in the add-entry
   form. The old `HoursField` (a `CharField` that parsed `"45m"`, `"1h 30m"`,
   `"1.5"` etc.) is gone from the add form. In its place: two `<select>`s —
   `hours` (0–24 hr, step 1) and `minutes` (0–55 min, step 5). The form's
   `clean()` combines them into `hours_spent` (Decimal). Quick-time chips
   (`15m`, `30m`, `1h`, `2h`, `4h`) now call `dsrTime()` to set both dropdowns.

**Why.** The user requested an explicit Administration task type and a
dropdown-based time selector instead of the text field.

**How it works now.**

- `DSREntryForm` declares `hours` and `minutes` as `ChoiceField`s (not in
  Meta.fields — they are UI-only). Meta.fields still includes `hours_spent`
  but it's rendered as a `HiddenInput` and overridden in `__init__` with a
  `CharField` so text values like `"45m"` (from inline row edits and the API)
  can reach `clean()` without hitting a Decimal validator.
- `clean()` has two paths: **path 1** (add form) reads `hours`/`minutes` from
  the dropdowns; **path 2** (inline row edit / API) reads raw `hours_spent`
  text from `self.data` and parses it via `apps/dsr/duration.parse_hours()`.
  The 24h cap is only enforced when the value actually **changed** from the
  instance, so a wide entry that wasn't touched survives an unrelated edit.
- Inline row editing (`_dsr_row.html`) and the API (`apps/dsr/api.py`)
  continue to use `hours_spent` as a text field — they are **not** changed to
  dropdowns.
- CSS: `.dc-time-row` (flex, gap 6px) and `.dc-time-select` (full width,
  min-width 0) are added to `templates/core/css/_components.css`.

**What was wrong before.** No "Administration" category existed. Time entry
required typing free text like `"1h 30m"` — functional but less discoverable
than explicit dropdowns.

**How verified.** Full suite: 1177 tests, 0 new failures (one pre-existing
`test_signup_creates_user` per AGENTS.md). DSR suite: 119 tests, all pass.

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

### 2026-10-07 (later) — DSR table back, time in minutes, released as 1.5.0

- The work log is a table again (header Task, Project, Category, Time, Status, actions; total row at the bottom). It is CSS grid, not `<table>`, so each row stays one `<form id="dsr-row-N">` (a form cannot wrap a `<tr>`; radios per row stay correct, htmx still swaps the row). `.dsr-grid-wrap` scrolls sideways under ~880px. Dropdown menus are absolutely positioned, so on a phone the scroll wrapper can clip the last row's menu; it scrolls inside the wrapper.
- Time is typed as `45m`, `1h 30m`, `1h30`, `1:30`, `1,5`; a bare number is still hours. `apps/dsr/duration.py` (`parse_hours`, `format_hm`, own tests) is the single parser: `DSREntryForm.hours_spent` is now a `HoursField` (text widget, shows `1h 30m`, compares parsed values so the "cap only when changed" rule still works), the update view and the suggestion add view go through it. DB field and API field names are unchanged. Template filter `hm` is in `time_tags`.
- Quick-pick chips are 15m 30m 1h 2h 4h. The composer is one compact row (task, project, category, time, status, Log it) with the note and chips below. "+ More" is gone.
- Times people read are 12-hour (`apps/core/timefmt.t12`), set earlier today.
- Released as 1.5.0 (`APP_VERSION` bumped, changelog entry added): /dsr in AI tools, "via MCP" pill, minutes, table, 12-hour times, the DSR token being unusable for Serop.

### 2026-10-07 (evening) — ticket and project endpoints for the MCP, released as 1.6.0

- `apps/dsr/api.py`: `GET /api/v1/dsr/tickets/` (`q`, `product`, `status=open|all`, max 20, newest first, through `accessible_tickets`), `POST /api/v1/dsr/tickets/`, `POST /api/v1/projects/` (owner/admin only, else 403). `users/me/` gained `can_create_projects`.
- Ticket create mirrors the web view (`Ticket.save` numbers it, `set_assignees(actor=)`, `notify_ticket_created`, `log_activity`). `assign_to_me` defaults true. Title max 255 here (model allows 500).
- Duplicate guard: an OPEN ticket with the same title (case-insensitive) in the same product answers 409 with `existing`; nothing is created. Resolved or closed tickets do not count.
- `status` resolved/closed: the ticket is created open, assigned, then `transition_to` runs, so the automatic DSR entry for the assignee is created. Intended, not suppressed.
- Project create validates through `ProductCreateForm`; duplicate name, slug or key answers 409 with `existing`. No `ProductAccess` row is made (owners and admins see every product).
- Tests: `apps/dsr/tests_api_tickets.py`.

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
| ~~A `WorkShift` admin screen~~ | One global value; not obviously worth the surface area. **Reversed 2026-10-17 for the weekly off days only**: the user asked to define them in the system, so Team attendance has a small dialog for them. Hours, break and the lateness bands still have no screen |
| A weekly off with its own rules (a make-up day, overtime, "short" hours) | The user wants no rules on those days: work any time, nothing derived. Net hours and the unclosed-day cap are unchanged |

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
| ~~Q9~~ | ~~Should `Ticket.transition_to` stop swallowing auto-log failures?~~ | `apps/tickets/models.py` wraps `auto_log_ticket_dsr` in `except Exception: pass`, which is **why the decimal crash went unnoticed** for so long. Deliberately left alone on 2026-10-02 (scope was the crash only). The obvious replacement is `logger.exception`, but a ticket status change then risks a visible error where the DSR write was merely best-effort. **Answered 2026-10-16:** it still must not block the status change, but the failure is now written with `logger.exception` (test `test_dsr_auto_log_failure_is_logged_not_swallowed`). |
| Q10 | Should the attendance dashboard test stop depending on wall-clock time? | `PersonalDashboardTest.test_attendance_reflects_only_my_own_punches` asserts one punch is shorter than another, so it passes early in the day and fails late (`AssertionError: 480 not less than 480`). Long-standing, unrelated to any recent change. The fix is to derive the expectation from `apps/attendance/service.py` rather than comparing two live values. |
| Q11 | Should Serop sign-in and "create team" be closed to people with no workspace? | `/oauth/authorize/` still signs a removed person in and issues a Serop token, and `TeamsView.post` lets any signed-in account create a team, which is a new `Company` they own: the same side door company setup used to be. Closed for the CRM web UI on 2026-10-16 (1.52.6) and left open for Serop, because its solo use (sign in, then create a team) cannot be seen from this repo. |
| Q12 | On a weekly off, should the Home DSR meter still compare a day with no punch against a full working day? | `_today_work` (`apps/dsr/views.py`) says "0h 00m of 8h 00m in your DSR" on a Saturday with no punch. DSR is not attendance, so 1.52.7 left it; hiding it on a weekly off is one condition. |
| Q13 | Should leave already approved be re-priced when the weekly offs change? | Leave keeps the days it was charged (`LeaveRequest.days` and the stored split), but payroll walks the request's dates on the current calendar, so an unlocked run can price a request approved before the change one day more or less. Locked runs never move. Not guarded in 1.52.7. |
## 2026-10-14 (SDK how-to)
- Package name is `pq-befu` (PyPI, import `pq_sdk`; also npm). The PyPI README itself still says `pip install pq-sdk`: fix there on next release of the SDK.
- API page has a framework-by-framework "Use the SDK" section from `apps/ingestion/docs.py` (`SDK_FRAMEWORKS`, `sdk_guide`); guide at `docs/guides/using-the-sdk.md`. Added on htmx-restyle only; production (main, React) still needs the same section in `ProductApiDocsPage.tsx`. Released as 1.15.0 "Umbrellabird".

## 2026-10-14 (project lifecycle, 1.46.0)
- Product is the project. New fields on Product (stage, stage_changed_at, start/end, lead, tech_stack, srs, phases) and tables PodMember, PhasePlan, ProjectLogEntry (append-only, `save()` refuses edits), CrunchItem. All rules in `apps/products/lifecycle.py` (`move_stage`, `add_entry`, `save_plan`, `set_team`, `add_crunch`); views in `project_views.py`, pages under `/products/projects/` and `/products/<pk>/lifecycle/` + `/project/`.
- Moving always needs a reason; only lead/Pod/owner/admin may move or write. Unused phases are refused and skipped. Existing products start in Creation with `stage_changed_at` empty (falls back to created_at), no lead or Pod.
- Not done / ideas: target-date alerts for late phases (card shows "Nd late" only), a cron to notify when a Crunch date is near, per-person mute per project.
- 1.47.0: removed the /design/ Design kit (vendored befui css/js stay in apps/core/vendor/befui, served at /befui/, not loaded by any page; demos.json dropped). Products and Projects share one sidebar entry ("Projects" → board; List view is the old product list); user-facing "Products" became "Projects", routes and models unchanged. `design-system.md` rewritten as the UI rules (tokens `--space-*`, `--fs-*`, forms, icons); `design.md` is still the PDF style guide.
- befui second drop (2026-10-14): upstream split its HTML build into a tiny ES-module loader plus per-component chunks. Vendored `befui.js`, `befui.css` and `chunks/` (228 files, 1.7 MB in the repo, but a page downloads only the chunks it uses). Served by `apps/core/befui.py` at `/befui/` and `/befui/chunks/<file>.js`; load with `<script type="module">` (see `templates/core/_befui.html`). `apps/core/befui_icons.py` was regenerated from its icons chunk: 390 icons (was 283); only `keyboard` changed shape. Alpine still mangles befui's `:prop='json'` attributes, so set data with `el.props = {...}` on Alpine pages.

## 2026-10-15 (expenses, 1.51.0; break 30 min)
- New `apps/expenses` (`/expenses/`): owners/admins-only simple ledger (title, amount, who paid, date, category, note) with totals and per-payer sums. Amounts are whole paise (`amount_paise`). Splitting/settle-up was built first, then removed by request (migration 0002); not wanted.
- `WorkShift.break_minutes` default 60 -> 30 (migration 0006 moves rows still on 60). Every hours display uses `service.net_minutes_for` (via `annotate_effective`), not the raw punch span.
- Correction decisions now also notify the other owners and admins.
- Not done: per-expense receipts, CSV export, month filter on the list.

## 2026-10-16 (1.52.4, 1.52.5, 1.52.6)
- Custom select and date picker popovers (`templates/core/base.html`) no longer close when the popover itself scrolls: the capture-phase `scroll` listener now ignores scrolls whose target is inside the popover. The kanban and Projects "move to" menus have the same pattern but their lists are short, so they were left.
- DSR log (`templates/dsr/dsr_log.html`): removed the `max-height:70vh` box around the table (it showed ~2 rows on a short window; the page scrolls instead), category and project cells no longer wrap, and task names use the existing `.clamp-2` with the full name in `title`.
- Q9 answered: `Ticket.transition_to` logs a failed DSR auto-log instead of swallowing it; the status change is still not blocked.
- Not done: DSR project mapping (the repo has no matching CRM project, so its entries file under no project), the committed key in `test_api*.py` (Q8).
- 1.52.6, removed members are locked out. `TeamRemoveView` only deletes the `Membership`, and a user with none used to sign in, land on `accounts:company_setup` and open a company of their own. `apps/accounts/access.py::has_no_workspace` is now the one rule: not staff, no `Membership`, and the install already has a `Company` means refused. `LoginView` refuses the sign-in (only after the password checks out, so a wrong password never reveals it) and `CurrentCompanyMiddleware` logs out a session whose membership vanished, both with `NO_WORKSPACE_MESSAGE`. Company setup still works for staff and on an empty install (the first owner: `bootstrap.sh`, `createsuperuser`). Still a member somewhere else: nothing changes, the middleware falls back to the remaining company.
- Decision: no "was removed" marker, no `is_active` flip. No `Membership` is exactly what a removal leaves, and a never-added account gets the same answer (ask an owner or admin), so telling the two apart would only buy the company name in the message. `is_active` would also have to be undone by every re-add path (Serop invite, Django admin). Tests: `apps/accounts/tests/test_removed_member.py`.
- Serop has no remove-member endpoint (only team create, list, detail, invite), so a removal only happens in `TeamRemoveView` or Django admin. Serop loses the person on its own because every Serop query filters by `Membership`; the DSR API refuses a token whose user belongs to no company. Serop sign-in and create-team are untouched (Q11).
- Not done: `PresenceConsumer` checks membership only when the socket opens, so a removed person's already-open tab keeps getting the company's live "who is online" list until it closes or reconnects. Closing it on the next ping is a few lines plus an async test.

## 2026-10-17 (weekly off days, Home punch, expense thread, 1.52.7)
- **Weekly off days are a company setting, default Saturday and Sunday.** `WorkShift.weekly_off_days` (JSON list of weekday numbers, Monday 0; migration `attendance/0007`, existing rows get `[5, 6]`). `shift.is_weekly_off(day)` is the question for a day, `weekly_off_for(company)` the set for code that only reads (payroll, leave; creates no shift row). Default chosen because `lateness_for` already returned 0 for `weekday() >= 5`, payroll's `working_days` already skipped Sat and Sun, and leave's `working_days` was Mon–Fri: the default changes no payslip, leave charge or existing assertion.
- **Why it was wrong.** The rule was hard-coded in eleven places (`lateness_for`, `get_month_grid`, `get_team_week`, three strips in `attendance/views.py`, reminders, `kudos.on_time_streak`, `_dsr_nudge`, payroll and leave day counts, the Home card), and the punch panel and team page did not know about it at all: on a Saturday the panel still showed "Checking in now is 136 min late: half a day", the team page listed everyone as Absent, and Home had no Punch in button (`today.weekday < 5`).
- **How it works now.** `lateness_for` is the one place that returns 0 on a weekly off, so the penalty, the calendar label, the payslip and the notification follow. `punch()` never refused a day. The punch panel (`_punch_context` → `is_weekly_off`, `_punch_button.html`) drops the countdown, the lateness note, "starts in" and "short of the day", keeps `Shift HH:MM–HH:MM`, and the notification body says "Weekly off: ...". Team attendance shows `off` instead of `absent` (`absent_count` counts `state == "absent"`); the month grid skips the day in `absent_days` and drops the `att-absent` hatch; the week views and strips use the shift. Payroll `working_days`/`working_day_list`/`_weekdays` and leave `working_days`/`_weekdays_between`/`month_calendar` take the set (default `WEEKEND`, so a bare call is Mon–Fri as before). Net hours are unchanged on a weekly off. The days are edited from the "Weekly off" dialog on Team attendance (owners and admins; `WeeklyOffView` → `service.set_weekly_off`, which refuses all seven days; none saves an empty list, a seven day week); it writes a `weekly_off_changed` audit row and a toast. A locked run is never regenerated, so a changed calendar cannot restate a payslip.
- **Home Today card (the "is there no punch in on dashboard?" question).** It already had Punch in and Punch out, but hid Punch in on Saturday and Sunday and printed "Weekend", so on a Saturday there was no way to start the day. It now shows on every day (not on approved leave), says "Weekly off · punch in only if you work" on one, shows net hours (`today_minutes`; it used the raw span `worked_hours`, 8.5h for a 10:00 to 6:30 day), and its forms send `next=` Home so `AttendancePunchView` returns there (`safe_next`; without `next` it still lands on Attendance).
- **Expense discussion.** `ExpenseComment` (migration `expenses/0006`), shaped like `TicketComment`: author kept as SET_NULL, no edit, delete only your own (403 for anyone else, owners included). Thread sits under the edit form at `/expenses/<pk>/#discussion`; plain form posts and a redirect back, so the toast arrives with the page. `service.add_comment` notifies the other owners and admins (`Notification.Kind.COMMENT`, url `/expenses/<pk>/#discussion`). The list shows a comment count per row (`comment_count`). Comment text is not copied into the audit log; add and delete write `expense_commented` / `expense_comment_deleted`. "Disbuss" was read as "discuss"; "disburse"/mark as paid was not built (settle-up was built and removed on request, 1.51.0).
- **Old tests that read "today".** Seven tests failed on a Saturday at HEAD (the three `LatePenaltyTest` bands, four lateness assertions in `PunchPanelTest`) because `lateness_for` already returned 0 on weekends; four more would have failed from this change. `LatePenaltyTest.punch_at` now lands on the Friday, and `PunchPanelTest`, `PunchCountdownTest` and `test_team_view_counts_leave_separately` pin a seven day week with `service.set_weekly_off(company, [])`. `WeekendWorkNotLateTest` uses an unsaved `WorkShift` instead of a `SimpleNamespace`, which no longer has `is_weekly_off`. No assertion was weakened.
- **How verified.** New: `apps/attendance/test_weekly_off.py` (27), `apps/dashboards/tests/test_home_punch.py` (7), `apps/leave/test_weekly_off.py` (6), `apps/payroll/test_weekly_off.py` (7), `ExpenseDiscussionTest` (10). `manage.py check` shows only `staticfiles.W004`. Looked at in the browser on a scratch database (never `db.sqlite3`): Home card, punch panel on a weekly off and on a working day, Team attendance and the dialog, the expense thread, at phone width and in the light theme.
- **Found, not fixed.** (1) The `/* Expenses */` CSS block in `_pages.css` (`.ex-stats`, `.ex-grid`, `.ex-form`, `.ex-who`, ...) was deleted by `a4bee33` (1.51.0) while the new ledger markup added classes that never had rules (`.ex-filters`, `.ex-ledger`, `.ex-limit`, `.ex-dlg`), so the Expenses list and edit pages lay out unstyled; `git show 5a9b2c3:templates/core/css/_pages.css` has the old block. The `.dsr-notices` block went in the same commit. (2) The expense delete form uses a bare `data-confirm`, which `base.html` treats as "no confirm" (it needs a title value), so deleting an expense asks nothing. (3) `get_month_grid` still counts future days and company holidays as absent. (4) The punch toast and notification quote the raw span (`worked_formatted`), not net hours. (5) Q12 and Q13 above.

## 2026-10-19 (project costing, 1.53.0)
- **New app `apps/costing/`, owners and admins only** (`CompanyAdminRequiredMixin`, same as expenses). `Estimate` is company-scoped; people and other charges are JSON lists on the row, money is text so Decimals round-trip. Salaries are typed by hand and never read from payroll. Hours are not typed: `service.office_hours` takes hours per day from the `WorkShift` (span less break, 8) and a month is 30 days (owner's choice, matches the estimate sheet), so 240 hours a month; weekly offs are not taken out. The rate follows Attendance settings; the result panel states the numbers used.
- **One copy of the maths** in `costing/service.compute`; the page posts the form to `/costing/calc/` on every change (htmx) and swaps `_result.html`, so there is no JS formula to keep in step. Rent and AI scale by dedicated days / days per month; AI counts only people ticked. Markup (cost x (1+p)) or true margin (cost / (1-p)).
- **Gotcha:** the form has `novalidate`, because htmx refuses to send the live-calc request while a `required` field (the project name) is empty. The server checks the name on Save.
- **Client quote** (`estimate_quote`) shows project, client days and one price (the pitch price if set, else the calculated price). A test fails if a salary or the internal cost reaches it.
- **Open:** the sidebar link sits in the Admin fold; it is not in the palette (`core/search.py`).
- **Reports.** `Estimate.quote_date` (migration `costing/0002`) lets old quotes be filed under their own month; the list page shows totals, a by-client table, a month filter and `export.csv`. Profit and margin there use the quoted price (the typed price if set, else the calculated one); margin is on price. Not built: win/lost status on a quote.
- **Fixed: DSR log (and any `.card-flush` / `.ledger` directly under `.main`) clipped with no scroll.** `.main` is a flex column; a child with `overflow:hidden` has min-height 0 and shrank to the screen height, hiding its rows. `_components.css` now sets `flex-shrink:0` on `.main > .card-flush, .main > .ledger`. 1.52.4 had only removed a `max-height`, which was not the cause.
- **Costing UI follows the owner's reference screens** (Projects table, KPI strip, BeForth quote). Pages are wrapped in `.co-scope`, which sets DM Sans / Manrope; the fonts are loaded only by the costing templates (`costing/_fonts.html`, via `extra_head`), the rest of the app stays on Inter. The KPI strip updates through an htmx out-of-band swap from `_result.html` (`oob` flag; the initial page renders the strip itself so the id is not duplicated). Quote lines (`service.quote_lines`) spread the price over the cost lines in whole rupees, remainder on the last line. The generic HRMS-dashboard prompt the owner pasted (sidebar groups, welcome banner, etc.) was NOT applied: it concerns the Home dashboard, not costing.
- **Speed (1.53.0).** Server time was never the problem (3-11 ms, 11-26 queries a page). Each page carried the five CSS files inline (~232 KB of ~340 KB) and nothing was compressed. Now `apps/core/assets.py` serves them as `/assets/app.<hash>.css` (content hash, `immutable` for a year, pre-gzipped, re-read when a file's mtime changes; an old hash still gets the current CSS with `no-cache`), `base.html` links it via `{% app_css %}`, and `GZipMiddleware` sits right after `SecurityMiddleware`. A test that looked for CSS text inside the page (`test_trigger_is_reachable_by_keyboard`) now reads the CSS file. **If you add CSS, add it to the five files as before; do not inline `<style>` blocks of any size in `base.html`.** Django's CSRF token is masked per response, which is what keeps gzip on HTML acceptable against BREACH; if a secret that is the same on every response is ever put in a page, turn the middleware off for that view.
- **Not done:** htmx still loads from unpkg as a blocking script in `<head>` (making it `defer` would break inline scripts that call `htmx.` early), and both it and Alpine come from CDNs, so a cold cache or a slow CDN still costs time. Self-hosting them needs a static pipeline or a view like `assets.py`.
- **Fonts.** Body is DM Sans (`html,body` in `_app.css`), headings and big figures are Manrope (rule at the end of `_components.css`). Inter is gone, including the datepicker and the 404/500 pages. The costing-only font link and `.co-scope` font rules were removed.
- **Production evidence (owner's Firefox network tab, crm.beforth.in).** `/tickets/` was 1.12 MB (288 tickets, 103 in Testing, every card drawn, ~3 KB each); errors and projects ~350-420 KB each of which ~232 KB was inline CSS; production still ran the Inter/old build; `wss://crm.beforth.in/ws/presence/` failed to connect (proxy not forwarding Upgrade, so presence polls) and `POST /presence/beat/` returned 500 (873 ms). Fixes: kanban shows `KANBAN_CARDS_PER_COLUMN` (30) per column with `?all=1` to show every card (`data-more` keeps the header counts right after a drag); `presence.beat` wraps the channel-layer broadcast in try/except (likely a Redis/layer error, not confirmed without server logs). **Still open on the server side:** `docker-compose.yml` runs with `DJANGO_DEBUG=True`; the proxy must forward WebSocket Upgrade for `/ws/`; SQLite on a bind mount.
- **Expenses CSS restored.** The `.ex-*` block had been deleted from `_pages.css` (a4bee33) while the ledger markup kept using it, so the page rendered unstyled (stacked filters, total and count run together, giant empty-state icon). Re-added at the end of `_pages.css`, adapted to the ledger markup (`.ex-filters` toolbar, `.ex-stats`, `.ex-grid` + `.ex-side`, `.ex-form`, `.ex-dlg`). Firefox draws its own date button, so `_app.css` drops our drawn calendar icon there (`@supports (-moz-appearance:none)`); Chrome/Safari keep ours (the native one is made transparent by the rule above it).
- **Sidebar Admin fold split into three** (People / Money / System) under an `Admin` `.nav-label`, each its own `.nav-fold` with its own localStorage key (`pqFoldPeople`, `pqFoldMoney`, `pqFoldSystem`; the old `pqAdminFold` is unused) and a `.fold-count`. Group card (open = soft panel, current page lifts out), chip and count are CSS at the end of `_pages.css` and apply to the My work fold too; collapsed-sidebar rules strip them. Pending corrections badge sits on People. `SidebarActiveStateTest` still passes (one active item per page).
- **Expenses form fields are block, not flex.** `display:flex` on `.ex-form .field` stretched `input[type=date]` to ~260px tall in some browsers; now block with a 38px date input.
- **Sidebar clipping bug:** `.sidebar` is a flex column with `overflow-y:auto`, so `overflow:hidden` children such as `.nav-label` shrank to nothing once the menu got long (the Admin heading vanished). `.sidebar > *{flex-shrink:0}` fixes it; same class of bug as the DSR table.


## 2026-10-27 (expense to salary)
- "Disbuss" meant disburse. `Expense.to_salary` + `paid_in_run` (expenses/0007), `Payslip.reimbursement` (payroll/0004). `payroll.service.reimbursements` picks marked expenses dated up to the cycle end that no other run took; `_write_run` stamps `paid_in_run`. Reimbursement is inside `gross`, shown as its own payslip line. Once paid, an expense cannot be edited, deleted or unmarked. Payer must be on payroll or it waits. Not done: CHANGELOG entry/version bump, notification when a slip is ready.

## 2026-10-29 (team attendance, past-date leave)
- Team Attendance takes `?date=` (never later than today) in both views, so old days are browsable; "Week" is now "Calendar view". Moving between days/weeks swaps `#team-main` in place (hx-boost) instead of reloading the shell. The KPI row became one plain summary sentence; the "Last 7 days" dots are gone (the calendar view covers them). Roles are fetched once (`service._roles`) instead of one query per member.
- Leave preview (`LeaveSplitPreviewView`) now says "only ask for leave from today onward" for a past start; submit already refused it. The end-date picker also has `min=today`.
- Payroll day rate is now salary / calendar days in the 27th-26th cycle (28 to 31), per the owner's handwritten example (8000 / 30 = 266.67). Weekly offs and holidays are paid days; a full cycle pays the salary exactly (`earned = salary x payable / cycle days`, rounded once); each unpaid day costs one day rate. Per-day profiles (no monthly salary) still pay working days only. Old payslips keep `breakdown.working_days`; new ones also carry `cycle_days`.
- Expenses filter by pay cycle, named by the month it ends in (`month=2026-10` is 27 Sep to 26 Oct; `filters.cycle_key`). Side panel "Still to pay back" lists cycles with expenses neither repaid by hand nor taken by a payroll run.
- Attendance now treats a company `Holiday` like a weekly off: team day ("Holiday: Diwali" header and pill), calendar view cell, my month squares ("holiday: <name>" tooltip, not "no punch"), my week strip, and the month grid (never counted absent). Late penalties on a punch made on a holiday are not changed.
- Search no longer returns tickets (`SEARCH_TICKETS = False` in `apps/core/search.py`; flip it to bring them back). The bell's unread count uses the same outlined count pill as the sidebar counts.

## 2026-10-29 (mid-cycle joiners)
- A person's first payroll profile that starts inside a cycle makes them a joiner (`payable_people(..., end)` sets `joins_on`): the cycle pays from that day to the 26th (salary x days / cycle days), leave and lateness before it are ignored, and the payslip says "Joined 10 Nov 2026, 17 of 31 days". A later raise is not a joiner. The date is the profile's Effective from; there is no separate joining-date field.

## 2026-10-29 (payroll month picker)
- The payroll preview picks a month from a list (`?month=2026-10` is 27 Sep to 26 Oct, named by the month it ends in; each option says In progress, Not created, Created or Locked). With no month it opens the newest finished cycle, the one ready to pay, not the running one. Fixed: "Create payslips" ignored the page and always created today's cycle; it now reads the same `month` the page shows (`views._requested_cycle`, `service.cycle_options`).

## 2026-10-29 (PWA)
- Manifest gained `display_override`, `launch_handler`, categories, lang and two more shortcuts. The worker now warms htmx, Alpine and the font sheet at install (list `WARM` in `templates/pwa/sw.js`; a test fails if it drifts from `base.html`). htmx loads with `defer` so it no longer blocks first paint. iOS Safari gets the Install app button with a Share, Add to Home Screen hint. The unread count is set on the installed app's icon through the Badging API.

## 2026-10-29 (DSR API hardening, clickable links)
- DSR API: PUT on another person's entry is now 403 (was 404); owner always comes from the token. Hours: one entry max `DSR_MAX_ENTRY_HOURS` (12); non-manual entries must fit the punch card's net minutes + `DSR_ATTENDANCE_TOLERANCE_MINUTES`. A day with no punch is not checked. Blank `source` becomes `manual`, and `DSREntry.unverified` (source == manual) shows a badge in the manager view. Deliberately not added: a 7-day back-date window, since non-managers are already limited to today.
- `ExternalAccessToken` expires after `EXTERNAL_TOKEN_LIFETIME_DAYS` (30), keeps `last_used_at`/`last_used_ip`, and is revoked from the profile "Connected apps" tab. Existing tokens got a fresh 30 days in the migration.
- `linkify` filter (`apps/core/templatetags/text_tags.py`) escapes then links http(s) only; used for DSR notes and ticket descriptions. The editable note input on today's row is plain text.
