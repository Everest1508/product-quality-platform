# Walk it like real users, then break it on purpose

Measuring a screen tells you what's wrong with its parts. Walking it tells you what's wrong with the experience. Do both. Walkthroughs need a browser; stress tests need a browser; without one, do them mentally against the code and screenshots and say so.

**Local / dev / staging only.** Walkthroughs may fill fields; never submit real data to a production backend. If submitting is needed to see the success state, only do it where the data is disposable (local DB, seed data), and say you did.

---

## Part 1 — Persona walkthroughs

Pick the personas that match the Screen brief (always do **Newcomer** and **Keyboard-only**; add others when they apply). For each, actually try to complete the **primary task path** in the browser, thinking aloud.

| Persona | Who | What they expose |
|---|---|---|
| **Newcomer** (always) | First day, no training, doesn't know the codes or the business rules | Unclear labels, hidden meaning, missing guidance, wrong first click |
| **Keyboard-only** (always) | Can't or won't use a mouse; power users entering data all day behave the same | Tab order, focus visibility, traps, mouse-only controls |
| **Daily power user** | Fills this 50× a day, knows every field | Wasted clicks, no defaults, no shortcuts, slow dropdowns, re-entering known data |
| **Touch / tablet / phone** | Tablet at a counter or in a warehouse, field staff on a phone | Small targets, hover-only actions, cramped layout, keyboard covering inputs |
| **Low vision** | Uses 200% zoom or large text | Overlap, truncation, horizontal scroll, low contrast |
| **Regional language** | Reads their own language best (often a non-Latin or right-to-left script), or the UI will be translated | Labels that break, layout that can't take longer text |
| **Interrupted** | Gets a phone call halfway, comes back, or hits an error | Lost work, unclear state, no way to resume |

### How to walk
1. **5-second test** (Newcomer): look at the first screenful for 5 seconds. Write down: what is this screen, what's the main action. If you can't, that's a 🔴 clarity issue.
2. **First-click test** (Newcomer): for the primary task, where would a new user click first? Is that the right place? A wrong first click is a strong predictor of failure.
3. **Do the task**, step by step, as that persona. Log every moment of friction:

| # | Persona | Step | What happened | Friction | Severity |
|---|---|---|---|---|---|
| 1 | Newcomer | Pick plan | Two fields: "Plan" and "Plan tier" — unsure which sets the price | hesitation | 🟠 |
| 2 | Keyboard | Tab from Country | Focus jumped to Save, skipping Postal code | wrong order | 🔴 |
| 3 | Power user | New invoice | Re-entered 9 fields identical to the last invoice | repeat work | 🟠 |

Friction types: **hesitation** (had to think), **wrong click**, **dead end** (no way forward), **backtrack**, **repeat work**, **surprise** (something unexpected happened), **lost work**, **can't tell state** (did it save? is it on?).

4. Count per persona: steps, clicks/keys, friction points, and whether they **completed** the task. Before vs after goes in the report — this is the most convincing proof a fix worked.

### Keyboard walk (with `scripts/focus-scan.js`)
Run the script first — it lists tabbable elements in tab order vs visual order, elements with no visible focus, positive tabindex, and clickable things that can't be reached by keyboard. Then actually press Tab through the form:
- Focus order follows the visual order (left→right, top→bottom, section by section).
- Focus is always visible (a clear ring, not just a faint colour change).
- Every control works from the keyboard: Space/Enter on buttons and choices, arrows in radio groups and selects, Esc closes dialogs and dropdowns, Enter submits where expected.
- No traps (can't Tab out), no skipping into hidden content.

---

## Part 2 — Stress tests

Screens are designed with perfect data. Users don't have perfect data. Break it on purpose, screenshot each, note what breaks.

| Test | How | Look for |
|---|---|---|
| **Breakpoints** | Resize to 320, 375, 768, 1024, 1280, 1440 | Overflow, overlap, squeezed columns, hidden actions, 2-column grids that should collapse |
| **Zoom 200%** | Browser zoom or `document.body.style.zoom = 2` / set viewport to half width | Same as above + truncation; WCAG requires usable at 200% |
| **Long text** | `scripts/stress-text.js` mode `expand` (pseudo-localization, +40% length) | Truncated labels, buttons that wrap or overflow, broken alignment |
| **Other scripts** | `stress-text.js` mode `script` with `SCRIPT` = the users' script (`devanagari`, `arabic`, `cjk`, `thai`, `cyrillic`) | Font fallback, clipped diacritics/ascenders, line-height, wrapping |
| **Right-to-left** | `stress-text.js` mode `rtl` (if the app supports or will support Arabic/Hebrew/Urdu) | Mirrored layout, icons and chevrons pointing the wrong way, misaligned numbers |
| **Long values** | `stress-text.js` mode `long-values` (fills text inputs with long but realistic values, never submits) | Inputs that don't scroll, values hidden, layout pushed |
| **Data volume** | Seed or mock 0, 1, 10, 1000 rows/options (local data only) | Empty state, single-item layout, slow dropdowns, no search/pagination, table blowing up |
| **Missing data** | Null names, no image, empty optional fields | "undefined", "null", broken images, collapsed layout |
| **Slow network** | Throttle (Slow 3G) in the browser if available, or note loading code paths | No loading state, double submits, layout shift when data arrives |
| **Errors** | Trigger validation errors; if safe locally, a failed save (stop backend / bad payload) | Error placement, message quality, data kept, retry |
| **Dark mode** (if the app supports it) | Toggle theme / `prefers-color-scheme` | Hardcoded colours that vanish, low contrast |

Run `stress-text.js` with mode `restore` afterwards — it puts the original text back.

Report as a **Stress table**: Test · Result (pass/fail) · What broke · Severity. Only list fails in detail.

---

## Part 3 — Consistency with sibling screens

Find 2–3 screens that do the same kind of job in this app (other create forms, other lists). Compare:
- Where the primary action sits (top right / bottom / sticky bar) and what it's called.
- Section and label style, required marks, validation style, date/number formats.
- The same concept named the same way (Job vs Order vs Work order).
- Same component used for the same job (one Select, one DatePicker), not three different ones.

A screen that behaves differently from its siblings makes users relearn it. Inconsistencies → 🟡, or 🟠 when they cause wrong actions (Save in a different place than everywhere else). Report a short **Consistency table**.
