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
| Home | `templates/dashboards/partials/_dashboard_content.html`, `templates/core/css/_pages.css` | 2026-10-31 | 58 → 86 | dead view context still computed (`chart_status`, `chart_donut`, `chart_errors`, `payroll`, `my_activity`, `my_leave_requests`, `overdue_count`, `todo_open`, `product_cards`, `attention`) and unused partials `_product_cards.html`, `_attention.html`, `_my_work.html` |
