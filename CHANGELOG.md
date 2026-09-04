# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project is not yet versioned.

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
