# Layout, spacing & placement — where everything goes, and why

Read this on **every run**. Most "this looks off" complaints are layout: things placed without a grid, spacing that changes randomly, columns that don't balance, fields sized without regard to what goes in them. Fixing labels and adding `*` while the layout is broken is not a fix.

**Layout fixes are required fixes, not optional upgrades.** Misalignment, unbalanced columns, wrong widths, inconsistent spacing and wrong placement are 🟠 (🔴 if they make people miss or misread things). Fix them in the same run, with the existing design system.

---

## 1. Look like a designer first (visual critique pass)

Before measuring, study the screenshots (desktop + mobile) and write 5–8 lines answering:
1. **Grid** — what grid is this using? How many columns? Do all blocks snap to it?
2. **Alignment lines** — how many distinct left edges are there? (Fewer = calmer. A form should have 1–2 per column.)
3. **Balance** — is visual weight spread evenly, or is one side heavy and the other empty?
4. **Rhythm** — is the spacing between fields the same everywhere? Between sections?
5. **Focal point** — where does the eye go first? Is that the most important thing?
6. **Reading path** — does the eye move in a clean line (top→bottom, left→right), or zig-zag?
7. **Density** — cramped, airy, or wasted space?
8. **Fit** — does each field's size match what goes in it?

Then run `scripts/layout-scan.js` to back every observation with numbers.

## 2. Grid & alignment

- Pick **one grid** for the screen: usually 12 columns (or the design system's grid). Every block spans whole columns. No free-floating widths.
- **Forms**: default to **one column**. Use 2 columns only for short, related pairs (Min/Max, City/PIN, Start/End, First/Last name). A 2-column grid filled with unrelated fields in "next free slot" order creates a zig-zag reading path → 🟠.
- **Align edges**: labels, inputs and section titles in a column share one left edge. Edges that are 1–8px apart (near-misses) look like mistakes → 🟡/🟠.
- **Align rows**: blocks side by side share a top edge; their controls share a baseline. If one block in a row is much taller (help text, a wrapping label), the row looks ragged → 🟡.
- **Max width**: forms read best at ~**640–960px** wide content. A form stretched across 1800px makes eyes travel too far between label and the next field and leaves controls lost in space → 🟠. Dashboards and tables may go wider.
- Content and its actions align: the Save bar aligns with the form's edges, not the page's.

## 3. Field width = expected content

The width of a field is a hint about what goes in it. Wrong widths mislead and waste space.

| Content | Width |
|---|---|
| Yes/No, 2–4 options | fit content (segmented control or radios), never stretched full width |
| Number with unit (qty, length, temp) | narrow: ~8–14 characters (~120–200px) with unit suffix |
| Code / ID / PIN / short code | ~ the code length + padding |
| Date / time | ~160–200px |
| Phone | ~200px |
| Name / short text | ~300–400px |
| Select | as wide as its longest option + chevron (cap at the column) |
| Email / URL / address / long text | full column |
| Textarea | full column, grows |

Rules:
- Same kind of field → same width everywhere on the screen.
- In a 2-column row, if one side is a short control (Yes/No, number) and the other is a full-width select, the row looks unbalanced. Either pair short with short, or let the short field sit in a narrower column (e.g. 4/8 split on the 12-col grid), or stack them.
- A field much wider than its content (>3× and >300px) → 🟡; when it makes a row look broken or wastes most of a column → 🟠.

## 4. Spacing system & rhythm

- Use the design system's **spacing scale** (usually 4/8-based: 4, 8, 12, 16, 24, 32, 48, 64). Any value off the scale (13px, 22px, 27px) → 🟡; a mix of many values in one section → 🟠 ("random spacing").
- **Hierarchy of space** (law of proximity) — always:
  `label→its input (4–8)` < `between fields in a group (16–24)` < `between groups/sub-sections (24–32)` < `between sections (40–64)`.
  If any of these are equal or reversed, grouping breaks: people can't tell what belongs together → 🟠 (🔴 if it makes them read the wrong label for a field).
- **Consistency**: the same relationship gets the same space everywhere (every label→input gap identical, every field→field gap identical).
- **Inner padding** of cards/sections ≥ the gap between fields; section content doesn't touch the card edge.
- **Density** fits the users: daily data-entry users can take compact spacing (but never <44px tap targets on touch); occasional users get more air.

## 5. Placement — where should each thing be

Decide the position of every element by these rules, in order:
1. **Task order** — the order the user works in the real world (or the order on their paper form / the order the customer gives info).
2. **Dependency** — parents before children; a child sits directly under its parent (see dependencies-and-navigation.md).
3. **Importance & frequency** — required and frequently used first; rare/optional later or behind "More details".
4. **Grouping** — things that belong together sit together, inside one section/card; unrelated things are separated by space or a divider.
5. **Pairing** — only truly related short fields share a row.
6. **Primary action** — in one consistent place for this app (check sibling screens and memory): bottom of the form aligned to the content edge, or a sticky action bar. Primary on the reading-path end (right in LTR), secondary next to it, destructive separated.
7. **Reading path** — the result should read top→bottom in one line per column, no zig-zag.

For a section of many Yes/No features (accessories, options), the clean layout is a **checklist** of features (one column, or a balanced 2–3 column grid of checkboxes), each expanding its own details directly beneath it — not a 2-column grid of Yes/No button pairs with details scattered across columns.

## 6. Balance & symmetry

- Symmetric layouts (equal columns) only work when both sides hold similar content. Asymmetric content in a symmetric grid looks broken.
- Measure fill: in each row, how much of each block is actually used by its control. One side 90% full and the other 20% → unbalanced row → 🟠.
- Avoid big dead zones: large empty areas to the right of short controls across a whole section → regroup or narrow the container.
- Visual weight: dark/filled elements (selected buttons, primary colour) concentrate attention — many filled "Yes" buttons scattered in two columns create noise; a checklist with checkmarks is calmer.

## 7. Responsive layout

- Below ~768px every form is one column; pairs stack.
- Section index → collapsible bar on mobile.
- Sticky action bar stays reachable; the keyboard doesn't cover the focused input.

---

## 8. Layout blueprint (required output when layout issues exist)

Don't just list problems — specify the new layout. Produce a blueprint for each affected section:

```
### Layout blueprint — 4. Notifications   (container 800px, 12-col grid, 24px field gap, 48px section gap)

Channels (checklist, one column, cols 1–12)
  ☐ Email
    └ when ✓ → Email frequency [segmented: Instant / Daily / Weekly, fit content] (indented 24px, directly under Email)
  ☐ SMS
    └ when ✓ → Mobile number [tel, 200px] (indented, under SMS)
  ☐ Push notifications

Quiet hours (cols 1–12)
  Pause notifications at night?  (•) Yes ( ) No   [radio, fit content]
  From [time, 140px]   To [time, 140px]            [one row — a related pair]

Session
  Auto sign-out after [number, 120px, suffix "min"]  [cols 1–3]
```

Then a **Why table** — one line per decision:

| Change | Why |
|---|---|
| 5 Yes/No pairs in two columns → one checklist | all choices in one glance; 1 click each instead of 2; no zig-zag across columns [Hick][Efficiency] |
| Email frequency under Email | child next to its parent; was in the other column [Proximity] |
| Auto sign-out 900px → 120px with "min" | width signals a short number; unit visible in the field [Match] |
| From / To on one row | they're a pair; everything else stays one column [Proximity] |
| Container 1800px → 800px | label→field eye travel cut; matches form max width in design.md [Fitts] |
| Gaps 13/16/22px → 24 field / 48 section | on the 8-scale; groups now readable [Proximity][Consistency] |

The blueprint is what the Fixed view in the demo must show, and what the code change implements.
