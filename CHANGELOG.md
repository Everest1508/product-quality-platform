# Changelog

This is what the **What's new** button in the sidebar shows, so write it for the
person using the app: what they can now do, what got easier, what was broken.
No class names, no field names, no test names, no file paths — if a change needs
that kind of detail it belongs in `AGENTS.md` instead, which is where the
engineering invariants live.

Format follows [Keep a Changelog](https://keepachangelog.com/); this project is not
yet versioned. Older releases are below the newest.

## [Unreleased] — 2026-09-30 · attendance, leave & payroll

Three new sections — Attendance, Leave and Payroll — plus a home page built around
your own week, a rebuilt sidebar and a pass over accessibility. The reasoning
behind each of these, and the questions still open, are in
[changes-2026-09-30.md](changes-2026-09-30.md).

### New

- **Clock in and out from anywhere in the app.** Your company sets its own office
  hours and decides how late is too late.
  - Office hours are 10:00–19:00 with a 60-minute unpaid break, so a full day
    reads 8 hours rather than 9.
  - Up to 15 minutes late is on time, up to 30 costs Rs 50, up to an hour costs
    Rs 100, and later than that costs half a day. A day you never clocked in is
    never charged.
- **Your own attendance and a monthly timesheet.** When you came in, when you left,
  and what it means for your pay — without asking an admin.
- **Request leave, and approve it.** Everyone can request time off; an approver
  works through a queue of requests waiting on them.
  - Approvers are picked per person in the team settings. Owners and admins can
    always approve, whatever the toggle says.
  - Owners and admins also see what is waiting on them, right on the home page.
- **Leave types you can tell apart.** Each type carries its own colour and icon, so
  casual and sick are not two identical grey rows.
- **Lateness on your payslip.** Every late arrival is listed with the date, the
  time you arrived and what it cost — on your own payslip, not just an admin's.
  - What the screen shows before the run is issued is calculated the same way, so
    the estimate and the payslip can never disagree.
- **A home page about you.** It shows your attendance, your pay, your leave balance
  and your own tickets, instead of company-wide totals that told you nothing about
  your week.
  - Managers and owners additionally see the team's numbers, and tickets from
    products you don't have access to stay hidden.
  - The main button is now **Request leave** rather than **New ticket**, and a
    banner tells you when you are on approved leave today.
- **What's new, in the sidebar.** The footer shows the version, and the button
  beside it opens these notes.
  - It opens on the current release. The two earlier ones are folded away, and you
    can filter down to just what was fixed or improved.
- **A show/hide button on the password field** when you sign in.

### Improved

- **Leave is simpler to keep track of.** 17 days a year — 12 casual and 5 sick —
  and you can take at most 3 working days off at a time, counted across all types
  together.
  - Counted in working days, so Friday to Monday costs 2 days, not 4.
- **The leave settings page is one clear row per type**, instead of a table whose
  headings didn't line up with the boxes you were editing.
  - A type with no limit now reads **No cap**, rather than "Unlimited" — 0 is a
    real setting.
- **Lunch breaks are handled honestly.** The hour comes out of your day only if
  your day was long enough to include it, so leaving at 11:00 is not reported as
  less time than you actually worked.
- **The sidebar knows where you are.** It highlights the page you're on, names its
  sections properly for screen readers, and keeps its highlight and tooltips when
  collapsed.

### Fixed

- **The app used to go blank next to the sidebar.** A misplaced closing tag made
  everything to the right of it invisible. The product edit form had the same
  fault.
- **Signing in used to land everyone on a 404.** You now go to your home page.
- **A bad month of lateness could tell you to hand money back.** Someone on a low
  salary who was late every day came out at **-99.96** on their payslip. The
  deduction is now capped at what the month can absorb, so a payslip can never go
  negative.
- **"Add entry" on the timesheet made up a row for you.** It quietly logged an hour
  of "New Task" as complete. It now asks for the task and the hours, and won't
  accept more than 24 in a day.
- **The timesheet ignored anything invalid you typed.** Bad values are now
  rejected with a message instead of being silently saved.
- **90 controls were unlabelled for screen readers.** Every field now has a label
  that is actually attached to it, so clicking it focuses the box and a screen
  reader announces it.
  - This covered search and sort boxes, the bulk-select boxes on ticket cards, the
    audit log's date filters, and the assignee picker's remove buttons — which all
    announced "Remove assignee" regardless of who you were removing.
  - Two of these were only found on a second pass, because the first check was
    itself looking the wrong way.
- **Seven pages had no sidebar highlight at all**, including Automation and
  Feedback, which you could only reach by typing the URL.
- **Your payslip said unpaid leave was the only thing that reduced your pay**, which
  stopped being true the moment lateness could, and three places still said
  "medical" after we renamed it to sick.
- **The demo data changed depending on what time you seeded it**, and past 10:15 it
  invented a late penalty for your demo team.
- **Two copies of the timesheet's add form shared the same field ids**, so labels
  pointed at the wrong box. Links that open in a new tab also now carry the
  attribute that stops the new page reaching back into this one.

### Security

- **A live API token is committed in the repository.** It does not validate against
  this app's database, but if it was ever valid anywhere it **should be rotated**.
  - Two files are named so the test runner picks them up, which is why
    `manage.py test` reports three errors that have nothing to do with your code.
  - They also send real requests to whatever is running on your machine when the
    test suite starts.
  - Not changed yet. It needs a decision about where the token should live.

## [Unreleased] — 2026-09-04 · dashboard & ticket boards

### Added

- **Home dashboard rework.** Stat cards for open errors, open tickets, tickets
  resolved this week, and tickets assigned to you — each with a week-over-week
  delta. Below them: a grouped "Needs attention" list (critical errors, stale
  tickets, unassigned tickets), a products table (health, open errors/tickets,
  CSAT, stale count), and — for owners/admins — recent activity and a team
  breakdown.
- **Inline actions on the dashboard.** Assign a ticket to yourself, resolve or
  ignore an error, and start or resolve your own tickets straight from the
  attention/assigned lists. Each action posts via htmx and refreshes the whole
  dashboard in place, so the counts and lists stay current without a reload.
- **One shared filter bar** across all four ticket boards (company-wide and
  product-scoped, kanban and list) — the same controls in the same order. The
  kanban board gained the sort dropdown it was missing.
- **htmx filtering on the ticket boards.** Changing a filter, sort, search term,
  or page swaps just the board or table in place instead of reloading the page;
  the count in the header updates with it.
- **Touch fallback for the kanban** — long-press a card to pick a target column,
  since native drag-and-drop doesn't work on touchscreens.
- Breadcrumb and a "Last seen" stat on the company-wide error detail page.

### Changed

- Relative dates ("3 days ago") are used consistently across ticket and error
  lists and detail pages, with the exact timestamp on hover. Removed the mix of
  relative and absolute formats (some panels showed both for the same value).
- The Kanban ⇄ List toggle carries the active filters across the switch.
- Consolidated the duplicated filter logic across the four ticket views into
  shared `apply_ticket_filters` / `sort_tickets` helpers, and extracted the
  kanban board markup and drag script into reusable partials.

### Fixed

- **htmx CSRF handler.** The global `htmx:configRequest` handler used htmx-1.x
  syntax (`evt.headers`) and so never attached the CSRF token under htmx 2.x —
  any header-based htmx `POST` failed with 403. Form-based htmx requests carried
  their own hidden CSRF field, which is why the bug went unnoticed. This also
  unblocks non-form htmx actions elsewhere in the app.
- Dashboard sections and their empty states ("All caught up", "Nothing assigned")
  are now contained in labelled panels instead of floating in whitespace, which
  made a sparse or new workspace hard to read.

## [Unreleased] — 2026-09-04

### Security

- **Per-product access is now enforced on the company-wide ticket views.** The
  global ticket board, list, detail page, and every mutation endpoint
  (status, priority, assign, comment, deadline, edit, delete, bulk-delete)
  filtered only by company. Any member — including one with no `ProductAccess`
  at all — could see and modify tickets belonging to products they were never
  granted. All of these now scope to `accessible_products` and 404 on tickets
  outside the caller's reach. Owners and admins are unaffected.
- **Same fix for the company-wide error views** (`apps/errors/views.py`): list,
  detail, status change, ignore, resolve, convert-to-ticket, and delete now
  enforce product access.
- The ticket and error "create" forms restrict the product dropdown to products
  the user can access, and the product-scoped create views reject a mismatched
  product in the POST body.

### Added

- `apps/products/access.py`: `accessible_tickets` / `require_ticket_access` and
  `accessible_error_groups` / `require_error_group_access` helpers.
- **Product switcher** in the sidebar — jump between accessible products without
  returning to the product list.
- **User menu** pinned to the sidebar footer (initials avatar + name + role →
  Settings, Sign out), replacing the bare "Sign out" button.
- **Collapsible sidebar** — toggles to a 60px icon rail with hover tooltips;
  state persists in `localStorage` and applies before first paint.
- **Mobile navigation** — the sidebar becomes an off-canvas drawer with a
  backdrop, opened from a hamburger in a new sticky top bar. `Escape` or a
  backdrop tap closes it. Page headers, tab strips, and toolbars now wrap
  instead of clipping off-screen on narrow viewports.
- **Breadcrumbs** on product ticket/error list, kanban, and detail pages.
- Company-wide open-ticket / open-error count badges on the primary nav.
- Regression tests: `TicketProductAccessTest`, `ErrorProductAccessTest`.

### Changed

- The company-wide boards are now clearly labelled **"All tickets"** and
  **"All errors"** (page title, breadcrumb, `every product` scope note in the
  header). The sidebar entries were renamed to match, and the primary nav
  (`Home · Products · All tickets · All errors · Reports`) is now identical in
  every context instead of reshuffling when you enter or leave a product.
- **Sidebar rebuilt**: icons on every row, a visible active state (accent fill +
  left bar), and grouped sections (`Operations`, `Admin`). Settings moved out of
  the flat list into the user menu.
- The **Kanban ⇄ List** toggle now carries the active filters across the switch.
- **Kanban board**: height is bounded to the viewport so the horizontal
  scrollbar stays on screen; the scrollbar is themed; columns scroll-snap.
  Overdue tickets show one indicator (`Overdue · <date>`) instead of a badge
  and a red date.
- The **"Delete Tickets"** button (a selection-mode toggle) is relabelled
  **"Select"**.
- Assignee avatar chips render as intended — the `--accent` / `--accent-soft`
  design tokens they referenced were never defined; they now are.

### Fixed

- Product error and ticket counts in the sidebar collapsed to `0` on every
  product page except Overview, because those views passed a bare `product`
  that shadowed the count-annotated one from the context processor. The
  ticket/error views now attach counts explicitly.
- `TicketDetailView` returned **HTTP 500** on any `HX-Request` GET to
  `/tickets/<pk>/` — it rendered `tickets/partials/_ticket_detail_content.html`,
  which has never existed. No caller relied on it; the dead branch was removed.
- `test_sidebar_renders_company_switcher` updated for the renamed switcher CSS
  class (`org-switch` → `switch`).

### Known issues (pre-existing, not addressed here)

- `apps.accounts.tests.test_tenant_isolation`: `test_signup_creates_user`
  (`NoReverseMatch` for `accounts:signup`) and `test_request_has_company_after_login`
  (expects 200, the root view now redirects). Both are stale tests against
  refactored auth flow, unrelated to the changes above.
