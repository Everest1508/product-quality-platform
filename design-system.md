# PQ Platform UI design system

How the app looks and how to keep it that way. `design.md` in this folder is a
different thing: it styles generated PDF documents. This file is for the web app.

## Where things live

| What | File |
|---|---|
| Colors and every other token | `templates/core/css/_tokens.css` |
| Base styles (layout, sidebar, tables, forms, kanban) | `templates/core/css/_app.css` |
| Presence, punch panel, team attendance, DSR form | `templates/core/css/_components.css` |
| Phone, tablet, touch, print, reduced motion | `templates/core/css/_responsive.css` |
| Logo files, favicons, app icons | `brand/` (see `brand/README.md`) |

`base.html` includes the four CSS files in that order, inside one `<style>`, so a
later file wins when specificity is equal. There is no build step and no static
files folder. Do not add one for CSS. The Docker image runs daphne, which does
not serve static files.

## Colors

Change a color in `_tokens.css` and nothing else. Every other file reads tokens.

| Token | Value | Use |
|---|---|---|
| `--accent` | `#1A5BFF` | Links, active nav item, focus rings, primary highlights |
| `--accent-soft` | `#EBF0FF` | Active nav background, selected rows, soft chips |
| `--primary` | `#0D1117` | Main buttons, headings, strong text |
| `--text` / `--muted` | `#0D1117` / `#6B7280` | Body text and secondary text |
| `--bg` / `--surface` | white | Page and cards |
| `--panel` | `#F5F7FC` | Table headers, quiet blocks |
| `--border` / `--border-strong` | `#D1D8E8` / `#C2CEE8` | Lines and hovered lines |
| `--green` `--orange` `--red` `--purple` | status hues | Status only, never decoration |
| `--*-bg` | pale versions | Backgrounds behind the matching status text |

Rules:

- Status colors mean something. Green is good or active, orange needs a look,
  red is wrong or costs money. Do not use them to make a page livelier.
- Write attribute selectors without quotes (`input[type=date]`). The stylesheet is
  inlined into every page and some tests search the HTML for the quoted form.
- Never put a literal hex in a template. Add a token if none fits.
- Favicons and data-URI images cannot read CSS variables, so they use the hex
  directly. Update them when the palette changes.

## Type and spacing

Inter, loaded from Google Fonts, with the system font as the fallback. Body text
is 14px with a 1.5 line height. Page titles are 19px, card titles 15px, and
labels or table headers 12px. Numbers that change (timers, counts, money) use
`font-variant-numeric: tabular-nums` so they do not jitter.

Spacing runs in steps of 4px. Cards use 16 to 20px of padding with a 10 to 14px
radius. Page gutters are 36px on desktop, 24px on a small laptop, 16px on a phone.

## Components

- **Card.** `.card`, white, 1px border, radius 8 to 14. Quiet blocks use `--panel`.
- **Buttons.** `.btn` is the default, `.btn-primary` is navy, `.btn-sm` is smaller.
  One primary button per view. The punch buttons are the only large ones.
- **Pills.** `.pill` with `open`, `high`, `resolved` or `closed` for status.
- **Stat card.** `.card.stat`, or `.kpi` when it is clickable. Icon, big number, label.
- **Chips.** `.chip` for filters (`.is-on` when active), `.dc-chip` for shortcuts.
- **Toasts.** Stack bottom right and, on a phone, run full width at the bottom.
  Trigger one with `window.dispatchEvent(new CustomEvent('django-message',
  { detail: { text, tags: 'success' | 'error' | 'warning' } }))`.
- **Presence.** `{% include "core/_presence_panel.html" %}` anywhere shows who is
  online. It reads the shared `presence` Alpine store, so it updates live.
- **Icons.** Lucide, inline, 24px grid, 2px round stroke, through `{% icon 'name' %}`.
  The logo is `{% brand_mark %}` and is kept out of the picker list on purpose.

## Layout

The shell is a fixed-height grid. The sidebar is 272px and collapses to icons.
Below 860px the sidebar becomes a drawer and a top bar appears. The page scrolls
inside `.main`, not the document.

Breakpoints: 1100 (small laptop), 1000 (four-up rows become two), 860 (drawer),
760 and 640 (phone), 380 (small phone).

Grids: `.grid-2`, `.grid-3`, `.grid-4` collapse as the screen narrows. Grid items
get `min-width:0`, otherwise long text pushes a column past the screen.

Tables stay tables. A small script wraps each one in `.table-scroll`, which scrolls
sideways on a phone and does nothing on a desktop.

## Touch and small screens

- Inputs are 16px on phones so iOS does not zoom when one is focused.
- Coarse pointers get 40 to 44px tall targets.
- `100dvh` instead of `100vh` where the page fills the screen, so the browser bar
  does not cover the bottom.
- Safe-area insets pad the top bar, sidebar and toasts around notches.
- Hover-only effects are switched off on touch.

## Motion

Short and quiet. 120 to 220ms for hovers and entrances. The only looping motion
is the presence dot and the clock. `prefers-reduced-motion` stops all of it.

## Accessibility

- Every input has a label with a matching `for`.
- Status is never color alone. A pill has text, a dot has a title.
- Focus is a 2px accent outline. Do not remove it.
- Only the result of an action is `aria-live`. A counter that changes every second
  is not, because it would interrupt a screen reader forever.
- Known gap: the custom select and date popovers in `base.html` have no keyboard
  handling or ARIA yet.

## PWA

`/manifest.webmanifest`, `/sw.js` and `/offline/` are Django views, not files, so
the worker can sit at the site root. The worker never caches pages or form posts,
because every page is per user. It caches the logo files and the htmx, Alpine and
font files, and shows `/offline/` when a page load fails. Installing needs HTTPS
or localhost.

## Live presence

`/ws/presence/` is one WebSocket per tab, signed in by session cookie and limited
to this site's origin. The server turns the page path into a label such as
"Viewing ticket #14". Labels never contain titles or product names, because the
people reading the list may not have access to them.

## Adding something new

1. Look for an existing component and token first.
2. Put new CSS in `_components.css` and read tokens only.
3. Check it at 360, 768 and 1440px wide, and with the keyboard.
4. A multi-line note in a template needs `{% comment %}`. A `{# #}` that spans
   lines prints on the page. A test now catches it.
