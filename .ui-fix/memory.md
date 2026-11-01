# ui-fix memory — product-quality-platform

## Users & context
- Small software studio on **Asia/Kolkata**: owners/admins run the company, developers and support work tickets/errors, viewers read. Salaried monthly payroll, 27th–26th cycle.
- Desktop-first (laptops, 1440×900 typical) but the phone view is used for punching in/out and reading leave balances.
- The web UI is server-rendered Django with one `<style>` block of CSS custom properties; `design-system.md` at the repo root is the source of truth for it (`design.md` is a PDF design system for printed material — not the app).
- Vocabulary: workspace = company; Home = `/dashboards/`; "on clock" = punched in; leave is *charged* in days, paid or unpaid.

## Decisions (follow these)
- 2026-10-31: Home is **two flex columns**, not a 12-column bento grid. Left `.hm-col` is your day, right `.hm-side` is your own list (capped 420px). Add a card by choosing a column; there is no span to add. (approved — this is the fix itself)
- 2026-10-31: Card titles use `--fs-md` (16px) with weight 600; body copy stays `--fs-base`. Type sizes come from `_tokens.css` only. (approved)
- 2026-10-31: A balance bar fills with **what is left** and its label says "X of Y left" — the bar and the sentence must describe the same number. (approved)
- 2026-10-31: Interactive text on a surface uses `--muted-strong`, not `--muted`; `--muted` is for supporting text that is not itself actionable. (approved)
- 2026-10-31: Touch targets: 44px for pill/row controls on a phone (≤640px), 40px for tabs. The shared `.btn` stays 40px tall app-wide (passes WCAG 2.2 AA at 24px). (approved)
- 2026-10-31: A test that asserts "no native `<select>`" must strip `<script>` blocks first — a `<select>` inside a JS comment is not a rendered control, the sibling tests in the same file already did this. (approved)

- 2026-10-31 (pass 2): Home columns share one template, `minmax(0,1fr) minmax(360px,420px)`, in both `.hm-grid` and `.hm-tiles`, so the This week / Leave tiles sit under the same edges as the cards above. The tickets card has a visible "My tickets" heading with the tabs on its right. (applied)
- 2026-10-31 (redesign): Home is one desk, not six boxes. Regions are split by a hairline and space (rules live in `_ui.css`); only the to-do card stays framed because it holds a form. Section titles are small uppercase labels, tabs are underlined, attention counts are a ruled text strip (not pills), tickets lead with the key. (approved: user said "you can redesign")
- 2026-10-31 (pass 4): Sign in is a full-window split, not a card on dots. The left panel and the Home greeting share `--brand-panel`/`--brand-panel-2`, a pixel grid and `--on-brand` text, dark in both themes. Pintu lives on the login panel and reacts to the form (cool while typing a password, error face on failure). Mobile login shows a small `.auth-mini` mark instead of the panel. (approved: "improve it completely")
- 2026-10-31 (dashboard-all): All four dashboards completely overhauled per ui-fix redesign:
  1. Home: Dead queries cleaned up, unused partials removed, `.hm-pill-row` token classes.
  2. Product: Breadcrumbs, `.pj-tabs` navigation, linked stat cards, 30d trends, meters, and recent activity feed.
  3. Reports: Modern breadcrumbs, `.rep-range-pill` date indicator, tokenized `.rep-toolbar`, upgraded KPI comparison cards with delta trends, bento completion rate rings, collapsible tables with right-aligned numeric data, and interactive activity feed.
  4. Audit Log: Standard `.pg-head` breadcrumbs, `.audit-toolbar` with search and app-wide dropdowns (`{% dropdown "type" %}`, `{% dropdown "actor" %}`), accessible date filter inputs with `<label>` tags, tokenized `.audit-card` table layout, date/actor avatar styling, and clean zero-event empty state. All inline styles removed. (approved: "all")
- 2026-10-31 (changelog-all): "What's new" modal modernized into two-pane layout with color-coded type indicator dots on chips (`.cl-chip-dot`) and section headings (`.cl-sec::before`), rich release rail items (version, codename, `Latest` badge, change count, date), arrow keyboard navigation, zero-match search empty state with clear button, and mobile 1-column layout. Dead legacy `.changelog` rules removed from `_pages.css` and `_app.css`. (approved: "do all")
- 2026-10-31 (gap-fix & tooltip-redesign):
  - Home Dashboard: Eliminated the vertical gap below "My tickets" by placing "This week" into `.hm-col` and "Leave" into `.hm-side`. Bounded `.hm-team-rows` to `max-height: 280px; overflow-y: auto;` to keep both columns balanced.
  - Global Tooltip (`.pq-tooltip`): Rebuilt with 120ms hover intent delay, 280ms warm grace period, dynamic micro-arrow pointing directly at trigger center even when clamped at screen bounds, shortcut parsing (`<kbd class="pq-kbd">`), and backdrop blur with hairline border.
  - Changelog Modal: Fixed close button `position: static;` so it sits cleanly alongside `<kbd>Esc</kbd>` without overlapping.
  - Reports page header: Added `.pg-title-row` flex rules so titles, badges, and range pills align horizontally. (approved: "fix the gap~ also impve and redeisgn the tooltip")

## Rejected (don't propose again unless asked)
- 2026-10-31: Restyling `.btn` to 44px everywhere to fix phone tap targets — the 40px shared button passes, and a global size change is a visual restyle outside this screen.
- 2026-10-31: Splitting the Home page into tabs/sections to make it fit — the ask is one glance at your day, not more navigation.
- 2026-10-31: Edits to `base.html` to please the audit-page test (e.g. rewording the shipped JS comment) — the test was wrong, not the comment.
- 2026-10-31: A CSS workaround for "clipped dropdown labels" at 200% zoom — false positive: `.dd-text` labels live inside closed `<details>` and are never painted. Verified with `checkVisibility()` / `elementFromPoint`.

## Glossary (one name per concept)
- Home (never Dashboard) · My to-do · Team today · This week · Leave · All my tickets
- Punch in / Punch out (never Clock in / Check in in the UI)
- Paid / Unpaid leave days · Remaining ("left") vs Used

## Screens
| Screen | File | Last run | Score before → after | Open items |
|---|---|---|---|---|
| Login | `templates/accounts/login.html`, `templates/core/css/_ui.css` | 2026-10-31 | not scored | OAuth authorize page (`.auth-card`) not restyled |
| Home | `templates/dashboards/partials/_dashboard_content.html`, `templates/core/css/_pages.css`, `_ui.css` | 2026-10-31 | 58 → 98 | none — gap eliminated, columns balanced (This week in left column, Leave in right column), team rows bounded |
| Product Dashboard | `templates/dashboards/product_dashboard.html`, `templates/dashboards/partials/_product_dashboard_content.html`, `_ui.css` | 2026-10-31 | 54 → 90 | none — breadcrumbs, project tabs, clickable stat cards, 30d trends, meters, and recent activity feed added |
| Reports Dashboard | `templates/dashboards/reports.html`, `templates/dashboards/partials/_report_content.html`, `_ui.css` | 2026-10-31 | 52 → 93 | none — breadcrumbs, range pill, tokenized date toolbar, KPI cards, bento charts, collapsible tables, and activity ledger |
| Audit Log Dashboard | `templates/dashboards/audit_log.html`, `templates/dashboards/partials/_audit_log_rows.html`, `_ui.css` | 2026-10-31 | 50 → 94 | none — breadcrumbs, count badge, tokenized toolbar, accessible label inputs, app-wide dropdowns, card-wrapped table, and actor avatars |
| Changelog / What's New | `templates/core/_changelog_modal.html`, `templates/core/css/_ui.css`, `_pages.css`, `_app.css` | 2026-10-31 | 55 → 98 | none — complete revamp with card-grouped changes, summary badge, search clear button, keyboard Esc/Arrow navigation, and mobile horizontal tabs |
