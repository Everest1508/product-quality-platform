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
- 2026-10-31 (pass 4): Sign in is a full-window split, not a card on dots. The left panel and the Home greeting share `--brand-panel`/`--brand-panel-2`, a pixel grid and `--on-brand` text, dark in both themes. Mobile login shows a small `.auth-mini` mark instead of the panel. (approved: "improve it completely")
- 2026-11-20 (login redesign): The split stays, but the left panel is now a **workspace console**, not a mascot stage: brand row with a "Workspace console" tag, a short lead statement, a CSS-only signal trace labelled Input / Triage / Records, a numbered 01/02/03 list of what the product does, and a small foot line. The trace is `aria-hidden` and carries no numbers, so it cannot claim to be live data. The form gets one heading group (eyebrow + `Sign in` + sub) and an icon-led help line; fields, labels, eye button and submit are untouched. No canvas, no art JSON. (approved: user chose "Redesign" for "impove login page")
- 2026-11-20: Auth CSS contract tests read the **served CSS bundle**, not just `_app.css`; new rules live in the `_ui.css` layer and are equally real. Comments are stripped before matching so a mention is not mistaken for a rule.
- 2026-11-20 (design-system pass): Login follows the written rules, not just the palette. Inputs use `--border-strong` + `--focus-ring` like `.form-input`; the submit button leads with `arrow-right` (every text button has an icon); only small section labels are uppercase at 0.05em; the form side is `var(--bg)` so white fields are cards. Removed the fake `PQ / 01` readout — decoration must not look like live data — and a `.auth-submit .ic` rule that duplicated `.btn .ic`. Help line bolds "workspace owner". Verified 37 login tests / 243 with `apps.core`, CDP no overflow at 1440×757 and 500×701, mobile inputs 16px/44px. `runserver --noreload` caches templates: restart before debugging a stale rendered page. (approved: "make the login better, match our design")
- 2026-11-20 (visible redesign): **Token polish is invisible to the requester.** Owner said "i dont see any changes wtf" after that pass; they were on the right URL and saw the console, so the fix was a structural change. Login now has a framed `.auth-access` card (surface, border, radius-lg, shadow-md), a "Workspace access" strip with `bef:shield-check`, a 32px h1, a decorative `user` / `bef:lock` glyph leading each 44px input, an 80px trace and a token-only radial glow. Verified 38 login tests / 244 with `apps.core`; CDP card 460×604 desktop / 448×569 mobile, no clipped or overflowing elements. Keep making changes you can point at on the screen. (approved: "make the login better")
- 2026-11-20 (animated left panel): Owner: "mane the left side is shit improev it , aniamted etc use whatever you can". The console became an animated instrument: two scrolling waves, scan line, 3-stage pipeline, pinging dot, blinking live tag, drifting grid and breathing glow. Verified 40 login tests / 246 with `apps.core`; CDP showed 24 running animations, 0 under emulated `reduce`. **(Reverted later the same day — see below.)**
- 2026-11-20 (console removed): Owner: "i meant remove the singla flow box , what is that supposed to be in login page". They could not see what the animated instrument was for, and they were right: it was decoration posing as live telemetry, repeating the numbered list. **Do not animate an abstract visual unless its meaning is obvious; a fake readout is worse than no visual.** Removed the console markup/CSS and all its keyframes; kept the brand, the one-line purpose, the 01/02/03 list and the reduced-motion-gated entrance fades. Test `test_the_brand_panel_has_no_fake_console` pins the removal (38 login tests OK). (approved: "remove the signal flow box")
- 2026-11-20 (white-and-blue parallax): Owner first chose "Home sky on the left", then rejected the night version: "nah nah i dont like that ~ make the white and blue parallax so it doenst get cutted offed". When asked, they chose a **blue panel with white layers**. Replaced the borrowed moon/stars with three `auth-parallax` layers: white ellipses derived from `--on-brand` drift in opposite directions over the deep blue and a haze breathes below. Each moving layer is **three tiles across 300%**, so translating one third loops with no seam — that is how "not cut off" is guaranteed, not by hiding an element at the edge. Verified 39 login tests / 245 with `apps.core`; CDP shows 3 running animations, transforms moving in opposite directions over 2s, 0 under emulated `reduce`, `scrollHeight == viewport`, no clipped children; mobile hides the panel. Screenshot `login-v7-desktop.png`. (approved: "white and blue parallax")
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

- 2026-11-02 (audit-log-redesign):
  - Audit Log upgraded to a command-center interface:
    - 4 KPI Bento summary cards (`stats.total`, `stats.today`, `stats.security`, `stats.actors`).
    - Category quick-filter tabs (All Activity, Security & Access, Tickets & Errors, Finance & Payroll, Attendance & Leave, Projects & System).
    - Quick date presets (`All`, `Today`, `7d`, `30d`) integrated into the toolbar.
    - Rich rows with category icon pills, inline transition chips (`from -> to`), amount badges (`₹...`), role & stage badges, accessible title link, right-aligned jump button (`Open ->`), and expandable metadata JSON payload inspector.
    - Verified strict test requirements: dropdowns and metadata summary tags carry `aria-label`, `<label for="audit-from/to">` on date inputs, zero native `<select>` tags. (approved: "do all")
- 2026-11-02 (boosted-sub-containers):
  - `HtmxBoostMiddleware` in `apps/core/middleware.py` checks `is_shell_target = not target or target in ("main", "body")` before stripping `HTTP_HX_REQUEST`. Fixes double nested sidebar in sub-containers like `#team-main` (`templates/attendance/partials/_team_main.html`) while preserving full `<div class="main">` shell for full-page navigations.

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
| Login | `templates/accounts/login.html`, `templates/core/css/_ui.css` | 2026-11-20 | not scored; measured in Chrome at 1440×757 and 500×701, no overflow | OAuth authorize page (`.auth-card`) not restyled |
| Home | `templates/dashboards/partials/_dashboard_content.html`, `templates/core/css/_pages.css`, `_ui.css` | 2026-10-31 | 58 → 98 | none — gap eliminated, columns balanced (This week in left column, Leave in right column), team rows bounded |
| Product Dashboard | `templates/dashboards/product_dashboard.html`, `templates/dashboards/partials/_product_dashboard_content.html`, `_ui.css` | 2026-10-31 | 54 → 90 | none — breadcrumbs, project tabs, clickable stat cards, 30d trends, meters, and recent activity feed added |
| Reports Dashboard | `templates/dashboards/reports.html`, `templates/dashboards/partials/_report_content.html`, `_ui.css` | 2026-10-31 | 52 → 93 | none — breadcrumbs, range pill, tokenized date toolbar, KPI cards, bento charts, collapsible tables, and activity ledger |
| Audit Log Dashboard | `templates/dashboards/audit_log.html`, `templates/dashboards/partials/_audit_log_rows.html`, `_ui.css` | 2026-11-02 | 50 → 99 | none — command center redesign with 4 KPI cards, category tabs, date presets, rich metadata chips, payload inspector, and action jump button |
| Changelog / What's New | `templates/core/_changelog_modal.html`, `templates/core/css/_ui.css`, `_pages.css`, `_app.css` | 2026-10-31 | 55 → 98 | none — complete revamp with card-grouped changes, summary badge, search clear button, keyboard Esc/Arrow navigation, and mobile horizontal tabs |
