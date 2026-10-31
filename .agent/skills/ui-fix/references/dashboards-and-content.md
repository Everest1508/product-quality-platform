# Dashboards, overview pages & text density

Read this for dashboards, home/overview pages, reports, and any screen that's mostly reading rather than entering data. Run `scripts/text-density.js` and `scripts/clip-scan.js` on every such screen.

---

## 1. Dashboard check

A dashboard answers "how are things, and what needs my attention?" in a few seconds. Check:

1. **One headline sentence** at the top that states the situation in words: "Sales are 12% above target this month; 3 orders are overdue." If you can't write it from the screen, the screen doesn't tell the story.
2. **Three signals**, not twelve. The 3 numbers that matter most for this role, biggest and first. Everything else is secondary or behind "details".
3. **No duplicated metrics.** The same number shouldn't appear in a tile, a chart label and a table (`text-density.js` → repeated numbers). Show it once, where it's most useful.
4. **Details on demand.** Explanations, definitions, breakdowns and long lists go into tooltips, expandable rows, drawers or a "View details" link — not on the main canvas.
5. **A reason for every chart vs table:**
   - Trend over time → line chart. Comparison of a few categories → bar chart. Part-of-whole with ≤ 4 parts → stacked bar (pie only if very few parts).
   - Exact values, lookup, or many rows → table.
   - Single value → a number with its change and period, not a chart.
   - If a chart doesn't answer a question the user actually has, remove it.
6. **Every metric** has a label, unit, period and comparison ("₹12.4L · this month · ▲ 12% vs last month").
7. **Actionable**: things that need attention link straight to where they're handled.
8. **Per role**: different roles need different top signals. Don't show every role everything.

## 2. Text density

Measured by `text-density.js`:
- **Dashboards / overview pages: aim for ≤ 250 words per screen.** More means people stop reading. Move explanations into tooltips or "learn more".
- **Wordiest sections** first: cut, move to tooltips, or replace sentences with labels and numbers.
- **Text under 13px**: only for truly secondary metadata (timestamps, footnotes). Labels, values and anything people must read → 13px+ (14px+ preferred).
- **Explanation lines** (descriptions, helper paragraphs, captions): more than ~5 on a screen → consolidate.
- **Repeated numbers**: each appearance after the first is a candidate for removal.

## 3. Clipped content

Measured by `clip-scan.js`, at every breakpoint you check:
- Any element holding text with `scrollHeight > clientHeight` (or width) whose overflow hides it → content is being cut off. Fixed-height cards and tiles are the usual cause; they look tidy with sample data and hide real data.
- Fix by: letting the card grow (min-height instead of height), wrapping text, reducing content, or giving a clear way to see the rest ("+3 more", expand, tooltip with the full text, a link to details).
- Intentional truncation (ellipsis, line clamp) is fine **only** with a way to see the full text and only for non-critical text.
- Hidden content the user needs to do their job → 🔴. Cut-off labels or names → 🟠.
