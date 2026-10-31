# Component library — variants and when to use them

Several ways to build each common component. Choose the variant that fits the content and the style (`styles.md`), and keep one variant per job across the product.

**Where the component comes from:**
1. The project's own component library / design system — always first.
2. The UI kit the project already uses (shadcn/ui, MUI, Chakra, Ant, Flutter Material…).
3. For **React + Tailwind** projects with nothing suitable: **befui** (https://befui.vercel.app) — copy-paste components on Radix + Tailwind, including HRMS and marketing blocks, with a CLI and an MCP server (use its MCP/CLI if available in the session). Ask before adding it; restyle to the product's tokens and chosen style so it doesn't import a foreign look.
4. Otherwise build it in the project's stack with its tokens.

---

## Metric / stat displays
| Variant | Use when |
|---|---|
| **Number + delta** — value, label, change vs period (▲ 12% vs last month) | Headline KPIs |
| **Number + sparkline** | The trend matters as much as the value |
| **Progress ring / bar to target** | There's a goal (attendance, quota, budget) |
| **Comparison pair** — this vs last / plan vs actual | Variance is the story |
| **Status tile** — big state word + colour + time in state | Machines, services, shifts, orders |
| **Mini table** — 3–5 rows ranked | "Top 5" lists |
| **Sentence metric** — "3 leave requests need your approval" | Action-driving counts; link the sentence |

Always: label, unit, period. Tabular numbers. Don't repeat the same metric elsewhere.

## Buttons
- **Primary** (one per view), **secondary**, **tertiary/ghost**, **danger**, **icon button** (with tooltip + accessible name), **split button** (main action + menu), **toggle button** (pressed state).
- Sizes: compact 32 · regular 40 · touch 48. Same height as inputs on the same row.
- Loading state keeps width; disabled state explains why (tooltip/helper).
- Label = verb + object ("Create invoice").

## Inputs
- **Label above** (default, most legible) · **inline label** (dense tables/filters) · **floating label** (only with care — keep visible label when filled) · **borderless/underlined** (editorial, inline edit).
- Prefix/suffix for units and currency; character count for limited text; clear button for search.
- States: default, hover, focus, filled, disabled, read-only, error, success.

## Choice controls
| Options | Variant |
|---|---|
| 2 (on/off) | Switch (applies immediately) or checkbox (applies on save) |
| 2–4 exclusive | Segmented control or radio group |
| 2–4 exclusive with explanation | Radio cards (title + one line each) |
| 5–10 exclusive | Select |
| 10+ | Searchable select / combobox |
| Many, multiple | Checkbox list (≤ 7) · multi-select with chips (> 7) |
| Visual options | Image/colour swatches |
| Rating/scale | Segmented scale or slider with labelled ends |

## Tables
- Row density: compact 32 · regular 44 · comfortable 56.
- Separation: zebra · hairline dividers · hover highlight only.
- Columns: numbers right-aligned, status as chips, dates relative + absolute on hover, actions in the last column or on row hover **plus** an always-visible menu.
- Header: sortable indicator, sticky, column resize/chooser for wide tables.
- Mobile: card fallback or pinned first column with horizontal scroll.

## Status & labels
- **Chip/badge** (soft fill + text) · **dot + text** (calm lists) · **solid pill** (high attention) · **outlined tag** (categories, not status).
- Always text, not colour alone. Keep one colour per status across the product.

## Progress
- **Bar** (simple %) · **segmented bar** (parts of a whole: leave types, budget categories) · **ring** (single goal) · **stepper** (stages with names) · **checklist progress** ("3 of 5 done").

## Timelines & activity
- Vertical with icons per event type · grouped by day · compact one-line entries with expandable details · filters by event type.

## People
- Avatar (image or initials with consistent colours) · avatar stack with "+N" · presence dot (online/away/punched-in) · person row (avatar, name, role, status).

## Charts (pick by question)
| Question | Chart |
|---|---|
| How does it change over time? | Line (area for one series) |
| How do categories compare? | Horizontal bar (sorted) |
| What's the composition? | Stacked bar / 100% bar (pie only ≤ 4 parts) |
| How is it distributed? | Histogram / box plot |
| How do two values relate? | Scatter |
| Where? | Map / floor plan |
| Is it on target? | Bullet chart / bar with target line |
| Single value | A number, not a chart |

Direct labels over legends where possible; one highlight colour, the rest neutral; colour-blind-safe categorical palette (`type-and-colour.md`).

## Date & time
Date picker that accepts typing · quick ranges (Today, This week, This month, Custom) · relative display ("2 h ago") with absolute on hover · time slots as chips for booking.

## Overlays
- **Modal** — short, focused decisions; one primary action.
- **Drawer** — create/edit while keeping context.
- **Popover** — small settings or details next to the trigger.
- **Tooltip** — short explanation; never the only place for critical info.
- **Bottom sheet** — mobile options and quick actions.

## Toasts & messages
Toast (auto-dismiss, with Undo where it applies) · inline alert (stays until resolved) · banner (page/app-wide) · confirmation dialog only for destructive, irreversible actions.

## Empty states
Illustration or icon (in the product's style) + one sentence of what goes here + one action. No-results: echo the search, suggest broader terms, "Clear filters".

## Motion
- Durations: 120–150ms small (hover, toggle), 200–250ms medium (drawer, expand), 300ms+ only for large transitions.
- Ease-out for entering, ease-in for leaving.
- Animate opacity/transform, not layout. Respect `prefers-reduced-motion`.
- Purposeful only: show where something came from/went, confirm an action, draw attention to a change.
