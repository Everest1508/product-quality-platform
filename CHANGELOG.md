# Changelog

This is what the **What's new** button in the sidebar shows, so write it for the
person using the app: what they can now do, what got easier, what was broken.
No class names, no field names, no test names, no file paths — if a change needs
that kind of detail it belongs in `AGENTS.md` instead, which is where the
engineering invariants live.

Format follows [Keep a Changelog](https://keepachangelog.com/); this project is not
yet versioned. Older releases are below the newest.

## [Unreleased] — 2026-10-02 · long-running tickets & DSR day close

### Fixed

- **Your dashboard no longer breaks on a long-running ticket.** A ticket left
  open for weeks used to log an absurd number of hours against your name, and
  that was enough to crash the dashboard with an error — taking your timesheet
  and everything else on the page with it. Hours are now counted over a far wider
  range, so long-running work finally shows up as the figure it really is.

### Added

- **Today's timesheet closes at midnight.** Fill in your daily status report
  until 11:59pm and it is submitted; you no longer have to get it exactly right
  the first time. A day that has not happened yet is closed to everyone, so
  nobody can log hours they have not worked.
- **Older days stay open for checking.** Every past report is still readable, so
  you can look back at any earlier day, copy its summary and compare it, without
  being able to rewrite what you already submitted.
- **Managers can still put right a closed day.** An owner or admin can correct a
  past report for anyone, so a forgotten entry or a typo is never stuck.

## [Unreleased] — 2026-10-02 · one dropdown across the app

### Improved

- **Every dropdown in the app now looks the same.** Filters, sort menus, status
  and priority pickers, leave types, colours, categories and employee pickers all
  share one control instead of the browser's plain grey box, so the app reads as a
  single product rather than a mix of styles.
- **Filters still work the moment the page loads.** Choosing an option reloads
  the list exactly as before, and a filter you have not touched is still sent
  along, so nothing quietly drops out of your results.
- **"All" is back where it should be.** Clearing a filter to see everything is
  available again on every list screen.
- **People are shown by name, properly.** Dropdowns listing team members used to
  show the wrong text for some entries; they now show each person's name and fall
  back to their username, the same as everywhere else in the app.
- **Leave-type colours and the staff rows in the timesheet** use the new control
  too, without losing their colour coding.

### Fixed

- **Leave settings no longer look unlabelled.** The colour picker and the day
  limits are each clearly marked, so it is obvious what each number means.
- **The activity log filters** and the ticket filters no longer leave a filter
  with no way back to showing everything once you picked one.

## [1.0.1] — 2026-10-02 · punch panel, forgotten check-outs & leave caps

Every earlier release note is kept below this one. The reasoning behind all of
it, and the questions still open, are in [context.md](context.md).

**The short version:** confirmation messages never appeared anywhere in the app,
nobody was ever charged for being late, the punch button wouldn't tell you what
time you arrived, a forgotten check-out cost you the day, and going over your
leave allowance was refused instead of charged. All five are fixed.

### New

- **A leave request that runs past your allowance is now accepted, not refused.**
  The days up to your limit are paid and **the rest is simply unpaid**, so you no
  longer have to guess how much to ask for and get it turned away.
  - The split is decided when the request is made and stored with it, so a later
    change to the policy cannot rewrite a decision that has already been made.
  - Payroll reads the stored split, so editing a leave type later never restates
    a payslip that has already been issued.
- **You can see which days will be unpaid before you submit.** The apply screen
  prices the request as you choose your dates, so a spell that runs past your
  limit tells you on the spot instead of after it is approved.
  - The panel stays empty while the dates are incomplete or a range contains no
    working days, rather than claiming "0 paid" for something you haven't
    finished typing.
- **Approvers can correct the dates and the paid/unpaid split** when they
  approve, on the same screen, using the same numbers the applicant saw.
  - Rejecting still costs nothing, and never records a split — there is nothing
    to pay for a request that was turned down.
- **Working days are counted as you'd expect.** Friday to Monday is 2 days, not
  4, and a half day is charged as half.

### Improved

- **The punch button now tells you when you came in, and whether you were late.**
  It used to say "on the clock" and then print a *duration*, so the one number
  you actually wanted was nowhere on the screen — and it said nothing about
  lateness at all.
  - Your office hours sit right under the button, and the time ticks up while you
    work.
  - Lateness is spelled out the moment it happens — "45m late" — using exactly
    the same figure your payslip is built from, so the two can't disagree. Half a
    day says so.
  - Before you've arrived there is no arrival time, so nothing claims you're late.
  - Every state carries both the hours and the lateness. A punch used to swap
    "on the clock, late 45m" for "checked out" and lose both.
  - The check-in and check-out buttons are now visually distinct; they were
    styled identically, because the two styles they asked for had never been
    written.
  - The result is announced to screen readers. The running timer deliberately is
    not — it refreshes every 30 seconds and would interrupt you constantly.
  - Clicking twice in a row used to make the panel claim you'd "already checked
    in and out". The button now waits for the first punch to land. The button
    also works if your browser has JavaScript turned off.
- **A forgotten check-out is now something you find out about, not something you
  find in a payslip.** If you clocked in and never clocked out, the punch panel
  lists the day and explains what it is costing you.
  - Your hours on that day are counted from when you arrived, so you do not lose
    the day outright — but they are capped at one full working day until an admin
    closes it, because nobody can know when you actually left. The cap matters:
    without it a forgotten punch from last month would report hundreds of hours.
  - The warning covers **every** month, not just the one you are looking at.
  - Today's own open punch is never listed as forgotten — that would put the
    warning on every working day and stop it meaning anything.
  - This **cannot change anyone's pay**: payslips are priced in days, and only
    your arrival time can carry a late penalty.
- **Managers can fix a forgotten check-out from wherever they see it** — inline
  next to the day on the team page, and as a link on the calendar, which has no
  room for a form but has room for a link.
  - Leaving the check-out box empty fills it with closing time, since that is
    what the cap already assumes, so nobody has to retype 19:00 by hand.
  - Clearing the box on purpose keeps the day open.
  - Opening somebody else's attendance as a manager no longer hides the whole
    punch panel. The button is hidden, because it would punch *you*, but the
    warning about them stays — which is the reason you opened the page.
- **The approver's dialog is wide enough to use.** It holds two date boxes, a
  switch and two day boxes, and at its old width they stacked into unreadable
  slivers.
- **Panels driven by the page state no longer flash on load** before the page
  settles.

### Fixed

- **Confirmation messages never appeared — anywhere.** Every "Saved", "Approved",
  "Edited" and every error message in the app rendered nothing: **79 places in
  the app** asked for a confirmation and none of them showed one. The messages
  were being handed to the page before it was ready to receive them, so the
  whole queue was quietly discarded.
  - Nothing had gone wrong with the actions themselves, which is what made this
    so confusing: the edit worked, and the app said nothing.
  - **A handful of actions never asked for one at all**, and were found by
    auditing every save handler rather than by the pages people happened to
    visit. Deleting DSR time, deleting a milestone, and advancing a milestone's
    status all finished silently; a status change with no confirmation looks
    exactly like a dead button. They report what happened now — and the
    milestone reports what it *became*, not just that you clicked it.
- **The app was running four and a half hours behind India.** Times were shown,
  and — more seriously — **lateness was scored in the wrong zone, so nobody was
  ever charged for being late.** A 10:45 arrival was recorded as 05:15, compared
  against a 10:00 start, and came out as *on time*; the punch button also
  cheerfully printed "05:15 AM" for a morning shift.
  - An arrival of 10:45 now reads as 10:45 and lands in the Rs 100 band, as the
    policy always said it should.
  - The lateness bands now sit where you set them: up to 15 minutes is on time,
    up to 30 costs Rs 50, up to an hour costs Rs 100, later than that costs half
    a day.
  - Everything is stored in UTC behind the scenes; only what is shown to you, and
    where a day starts and ends, changed.
  - **Your existing attendance history is not rewritten**, so records taken
    before this change will read some hours off. Ask an admin to correct them, or
    re-seed the demo workspace.
- **The "What's new" panel was empty in production.** Release notes were dropped
  from the container image entirely, so the button in the sidebar opened onto
  nothing — no error, nothing in the logs, and every check on your machine looked
  fine because the file was right there.
  - A missing changelog is now written to the logs once, so if it ever goes
    missing again the cause is on the server rather than a guess.
  - A deployed image needs rebuilding to pick this up.
- **The timesheet and dashboard counted a forgotten check-out as zero hours**,
  which quietly cost you the day until somebody noticed.
- **Opening a colleague's attendance as a manager showed you your own
  forgotten days** instead of theirs, on any day they had not yet punched.
- **Day counts could crash a leave page.** A whole number of days was being
  formatted as though it were always a fraction, so a request of 12 days could
  raise an error in the middle of an approval.
- **The demo team arrived at 06:30 for a 10:00 shift.** The seeder was avoiding
  late penalties by inventing early arrivals; it now seeds a realistic spread
  around your office hours, including genuinely late ones.
- **Clicking the punch button twice made the panel say you had already checked
  in and out.** The second click was correctly ignored, and then reported the
  opposite of what happened.

### Known issues (pre-existing, not addressed here)

- `apps.accounts.tests.test_tenant_isolation`: `test_signup_creates_user`
  (`NoReverseMatch` for `accounts:signup` — self-signup is not wired up). Still
  the only failing test, and it is a product question about whether signup should
  exist at all, not a regression.
- The three older release blocks below are still tagged **Unreleased**, so the
  dialog labels them "In development". They describe shipped work; only this
  block has been versioned.

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
