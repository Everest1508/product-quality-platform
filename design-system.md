# PQ Platform UI design system

The one place that says how the app looks, so every new page matches the old ones.
`design.md` in this folder is a different thing: it styles generated PDF documents
(SRS, proposals). This file is for the web app. If a rule here and a stylesheet
disagree, fix the stylesheet.

## Where things live

| What | File |
|---|---|
| Every color, space, size and radius (tokens) | `templates/core/css/_tokens.css` |
| Base: reset, layout shell, sidebar, forms, tables | `templates/core/css/_app.css` |
| Widgets: buttons, badges, tabs, dialogs, ledger rows, presence | `templates/core/css/_components.css` |
| Page layouts: home bento, DSR, profile, projects | `templates/core/css/_pages.css` |
| Phone, tablet, touch, print, reduced motion | `templates/core/css/_responsive.css` |
| Icons | `apps/core/icons.py` (outline set) and `apps/core/befui_icons.py` (befui set) |
| Logo, favicons | `brand/` |

`base.html` inlines the five CSS files in that order, so a later file wins at equal specificity.
There is no build step and no static folder. Do not add one for CSS.

## The rule above all the others

**Use a token. Never write a literal color, pixel gap or font size in a template or a new rule.**
If none fits, add a token to `_tokens.css` first. Dark mode works only because every color is a token.

## Color

Light is the default; `html.dark` swaps the same names. Never test only one theme.

| Token | Meaning | Use for |
|---|---|---|
| `--accent`, `--accent-soft`, `--accent-line` | The brand blue and its tints | Primary action, links, current item, focus, selected |
| `--text`, `--muted`, `--muted-2` | Body, secondary, faint text | Everything written |
| `--bg`, `--surface`, `--panel` | Page, card, quiet block | Backgrounds, from back to front |
| `--border`, `--border-strong`, `--line` | Outlines, hover outlines, hairlines | Dividers and card edges |
| `--green` / `--green-bg` | Good, done, active | Status only |
| `--red` / `--red-bg` | Wrong, late, destructive | Status only |
| `--orange` / `--orange-bg` | Needs a look, Crunch | Status only. A warm orange, never yellow |
| `--blue` / `--blue-bg` | Information | Notes and info |
| `--purple` / `--purple-bg` | Leave, decisions | Status only |

- **No yellow or amber anywhere**, in light or dark. Greetings and banners stay in blue and violet.
- Status colors mean something. Do not use them to make a page livelier.
- Status is never color alone: a badge has text, a dot has a title.
- Write attribute selectors without quotes (`input[type=date]`); the stylesheet is inlined and tests search the HTML for the quoted form.

## Spacing

Everything is a multiple of 4. Use the tokens.

| Token | px | Use |
|---|---|---|
| `--space-1` | 4 | Icon to its label, tight pairs |
| `--space-2` | 8 | Between buttons, chips, small controls |
| `--space-3` | 12 | Between rows in a list, inside small cards |
| `--space-4` | 16 | Between form fields, inside dense cards, grid gap in boards |
| `--space-5` | 20 | **Card padding, and the gap between cards** |
| `--space-6` | 24 | **Between sections and form cards; page header to content** |
| `--space-8` | 32 | Between page-level blocks |
| `--space-10` | 40 | Page gutters on a wide screen |

Rules of thumb:

- **Cards never touch.** Two cards side by side or stacked are `--space-5` apart (`--space-6` for form sections). 12px is only for items inside a card.
- Card padding is `--space-5` (`--space-6` for form cards). Never less than `--space-4`.
- A label sits `--space-2` above its field; a field and the next field are `--space-4` apart; a hint sits `--space-1` under its field.
- The page header (`.pg-head`) is `--space-6` above the content. A section heading is `--space-4` above its first item.
- Page gutters: 40px wide desktop, 24px small laptop, 16px phone.

## Type

Inter, with the system font as fallback. Weights 400 body, 500 labels and buttons, 600 headings, 650 page titles.

| Token | px | Use |
|---|---|---|
| `--fs-xs` | 12 | Captions, table headers, badges, hints, timestamps |
| `--fs-sm` | 13 | Secondary text, dense lists, field hints |
| `--fs-base` | 14 | Body, inputs, buttons (the default) |
| `--fs-md` | 16 | Card and section titles |
| `--fs-lg` | 20 | Big numbers in a card |
| `--fs-xl` | 24 | Page titles |

Line height 1.5 for text, 1.1 for big numbers. Numbers that change (counts, money, timers) use
`font-variant-numeric: tabular-nums`. Table headers and small section labels may be uppercase with 0.05em tracking. Nothing else is.

## Shape and depth

Radius `--radius` (8px) for controls and small cards, `--radius-lg` (12px) for cards and dialogs, `99px` for pills and avatars.
Borders are 1px `--border`. Shadows are `--shadow-sm` at rest and `--shadow-md` for a raised or hovered card and for popovers. No other shadows.

## Icons

- Inline SVG through `{% icon 'name' %}`. 24px grid, 2px round stroke, `currentColor`, so an icon takes its text color.
- Size: 16px beside text (`.ic`), 15 in dense rows, 20 to 24 on their own. Never stretch an icon.
- **Every text button starts with an icon**, then its label. Icon-only buttons need an `aria-label`.
- Pick from the existing sets (about 75 outline icons and 283 befui icons). `bef:name` forces the befui drawing; add `icon-draw` for the hover redraw. Do not paste ad-hoc SVG into a template.
- A project can carry its own icon; the products list and switcher draw it with `{% product_icon %}`.

## Layout

The shell is a fixed-height grid: a 272px sidebar (collapses to icons; a drawer below 860px), a top bar, and the page scrolling inside `.main`.
A page is: breadcrumbs (when nested), `.pg-head` (title and one-line subtitle on the left, actions on the right, one primary button), an optional `.toolbar`, then cards.
Content width: lists and boards use the full width; forms and reading pages cap at about 860px and sit on the left.
Breakpoints: 1180, 1100, 980, 860 (drawer), 760, 640 (phone), 380.
Grid items get `min-width:0`, or long text pushes a column past the screen. Tables scroll sideways on a phone inside `.table-scroll`.

## Components

Reuse before you write. Each is a class in `_components.css`; the markup is on any page that uses it.

- **Card** `.card` (white, 1px border, `--radius-lg`, `--space-5` padding). Quiet blocks use `--panel`. **Ledger** `.ledger` with `.lrow` for a list of rows.
- **Button** `.btn`, `.btn-primary` (one per view), `.btn-danger`, `.btn-sm`, `.icon-btn`. **Badge** `.bdg` with `-green -orange -red -blue -outline`; **pill** `.pill` for ticket status.
- **Tabs** `.seg` (links or buttons, current one `.is-on`). **Dialog** native `<dialog class="dlg">` with `.dlg-head`, `.dlg-body`, `.dlg-foot`; it opens centred and closes on Esc and on the backdrop. Dropdowns and date pickers open *inside* an open dialog.
- **Confirm** add `data-confirm="Delete this?"` (the value is the title; a bare attribute never asks), `data-confirm-text` and `data-confirm-label` to a form; every delete asks first.
- **Dropdown** `{% dropdown %}`; native `<select>` is enhanced by the same popover. **Toast** `window.pqToast(text, kind)` or a Django `messages` call.
- **Avatar** `.kt-av` (initial in a circle, `.lg` and `.more` variants). **Empty state** `.empty-state`: one line of what is missing and one line of what to do.
- **Home bento** `.hm-bento`: a 12 column grid whose cards stretch to the row, so nothing leaves a hole. A new Home card needs its own `grid-column:span N` line under `.hm-bento` in `_pages.css` (4 for a side card, 8 for a wide one); without it the card shrinks to one column. Plain rows inside a card are `.hm-rows li.is-plain` with a `.t` name and a `.m` detail, or `li > a` when the row links somewhere. **Projects** use `.pj-*`: board columns, cards, journey track, lifecycle feed, Pod and phase pickers.
- **Notifications** go through `apps.notifications.service.notify`; toasts, presence, the palette and the changelog dialog are described in their templates.

## Forms

Every form tells the person what to do. No guessing.

1. **Say what is required.** A card header carries a pill: `Required` (blue) or `Optional` (gray). If only one thing is required, say so in the page subtitle ("Only the name is required").
2. **Say what a section is for** in one sentence under its title (max about 62 characters wide), in `--muted`. Name the consequence: "Phases you leave out are grayed on the board".
3. **Every control has a visible label.** A placeholder is an example ("e.g. Billing Portal"), never the label.
4. **Choices that are people or things use cards,** not a bare checkbox list: avatar or icon, a name, a second line, and a visible tick. Show how many are selected.
5. **Repeated rows get column headings** ("Feature that must come early", "Must be ready by", "Why it cannot wait") and one example in the placeholders.
6. Errors appear above the form in an `.alert`, in plain words, naming the field. Nothing is saved when anything is wrong.
7. Primary action bottom left ("Create project"), then Cancel. Never two primary buttons.

## Writing

Plain words, sentence case, no jargon. Buttons are verbs ("Add to log", "Move"). Say why: "Why are you moving this?". Dates read `14 Oct 2026`; times `4:10 pm` with the exact time on hover. Counts pluralize ("1 day", "2 days").

## Check before you finish

- Tokens only: no hex, no px gap that is not on the scale, no `font-size` outside the type scale.
- Looks right in light and dark, at 360, 768 and 1440px wide, and with the keyboard (visible focus on everything you can click).
- Cards have breathing room (see Spacing). Nothing yellow. Every text button has an icon.
- A new page is added to the sidebar active-state conditions and the palette (`apps/core/search.py`) if it deserves a shortcut.
- A user-facing change gets a `CHANGELOG.md` entry; a multi-line template note uses `{% comment %}`, never a multi-line `{# #}`.

## Touch and small screens

- Inputs are 16px on phones so iOS does not zoom when one is focused.
- Coarse pointers get 40 to 44px tall targets.
- `100dvh` instead of `100vh` where the page fills the screen, so the browser bar
  does not cover the bottom.
- Safe-area insets pad the top bar, sidebar and toasts around notches.
- Hover-only effects are switched off on touch.

## Motion

Short and quiet, and always optional: every animation sits inside `@media (prefers-reduced-motion:no-preference)` (bottom of `_components.css`), so a person who asks for less motion gets the plain page.

| Token | Use |
|---|---|
| `--dur-1` 120ms | Hover and press feedback (buttons, sidebar items, tabs) |
| `--dur-2` 200ms | Hover lift, menu and card state changes, page fade-out |
| `--dur-3` 320ms | Page and card entrance |
| `--ease-out` | The only curve: fast start, soft landing |

What moves, and what does not:

- **Page to page:** the content cross-fades (`@view-transition`), while the sidebar and top bar stay put.
- **A page assembling:** cards, rows and feed entries rise in one after another, 40ms apart, for the first six.
- **Pressing:** buttons dip to 97% when pressed; primary buttons glow slightly on hover; sidebar icons grow a little on hover.
- **Opening things:** menus and popovers pop in (`pqPop`), accordions and the Admin fold slide open (grid rows `0fr` to `1fr`), dialogs use `dlgIn`.
- **Values:** progress bars and bar charts grow to their value when they appear.
- **Content swapped by htmx** fades in (`.htmx-added`); a request in flight dims its element.
- Nothing loops except the presence dot and the clock, and nothing animates `width`, `height` or `top` on a hot path other than the one-off bar growth.

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

If the socket cannot connect twice in a row, the `presence` store switches to polling
`POST /presence/beat/` every 25 seconds. That endpoint writes the same `PresenceSession`
row the socket does, so the person still counts as online. The store's `mode` is `live`,
`polling`, `connecting` or `offline`. The user-facing explanation is in
`docs/guides/presence-and-alerts.md`.

## Adding something new

1. Look for an existing component and token first. Never put a bare `<section>`, `<ul>` or `<li>` in a page grid: give it the card class and the row class its siblings use, then look at it in the browser before you call it done.
2. Put new CSS in `_components.css` (widgets) or `_pages.css` (page layouts) and read tokens only.
3. Check it at 360, 768 and 1440px wide, and with the keyboard.
4. A multi-line note in a template needs `{% comment %}`. A `{# #}` that spans
   lines prints on the page. A test now catches it.
