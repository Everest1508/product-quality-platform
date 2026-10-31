# Visual design — how it looks, and how it could look better

Read this on **every run**. Usability and layout make a screen work; visual design makes it feel like **this** product — clear, trustworthy, and recognisably its own. A screen can be usable and still look dated, noisy, cheap — or generic. Judge all of that, and **always come back with concrete visual design suggestions**.

Two kinds of output, never confuse them:
1. **Polish within the system** — required. Use the product's existing tokens and components better. No approval needed.
2. **Design suggestions** — always proposed, applied only on approval (or at the Redesign level). Shown as rendered options; the chosen one is written into design.md.

"Follow the design system" means don't change the look *silently*. It never means "have no opinion about the look".

---

## 0. Start from the product's identity — never from a default look

There is no default look. Every product should look like itself. Before judging or proposing anything visual, work out the identity — and write it in 4–6 lines:

**Where to find it** (in this order): design.md · brand guide / logo / marketing site / favicon in the repo (`public/`, `assets/`, `brand/`) · `.ui-fix/memory.md` · the existing UI's strongest choices (what's distinctive and worth keeping) · the domain and users from the Screen brief · ask the user one question if still unclear ("Three words for how this product should feel?").

**Write:**
- **Personality** — 3 adjectives. e.g. *calm, clinical, precise* (hospital records) · *warm, playful, quick* (café POS) · *bold, industrial, no-nonsense* (factory floor app) · *refined, quiet, premium* (private banking) · *friendly, encouraging, light* (learning app).
- **Context of use** — where and how it's used: bright shop floor on a tablet, dim control room, phone in the field, office desk all day, occasional customer visit.
- **Brand anchors** — what must stay: logo, brand colour(s), brand typeface, illustration or mascot style, tone of voice.
- **Domain cues** — what the domain's best tools feel like (e.g. trading = dense, monospaced numbers, dark; healthcare = calm, high-legibility, restrained; hospitality = warm, image-led; logistics = map/status-led, colour-coded).
- **Keep** — the existing UI's distinctive choices worth keeping (a mascot, an illustration style, a signature colour, a characterful font).

Every direction and every polish decision must trace back to this identity. "It's cleaner" is not enough — say *how it expresses the personality better*.

If the user has its own brand across several products (e.g. an agency or a product suite), use that brand's design.md or guide for its own products — but **each client's product follows that client's identity**, not the agency's.

## 1. Visual critique — judge these every time

Use the screenshots plus `scripts/style-inventory.js` (counts every distinct font, size, weight, colour, radius, shadow, border and button style on the screen).

| Area | Good looks like | Common problems |
|---|---|---|
| **Identity** | You could tell which product this is with the logo covered; choices express the personality | Interchangeable with any SaaS template; personality in the brief but nowhere on screen |
| **Typography** | A typeface that suits the personality (not automatically the same sans as everyone); a clear scale of 4–6 sizes, 2–3 weights, comfortable line-height, readable body size (≥14px dense UI, ≥16px content); numbers in tabular figures where they're compared | 8+ sizes, sizes 1–2px apart, everything the same weight, cramped line-height, all-caps paragraphs, decorative type for data |
| **Colour** | A deliberate colour strategy that fits the identity (see §3 axes); semantic colours only for meaning; text in 2–3 levels by importance; contrast passes | Colour used at random; brand colour on everything; many unrelated colours; grey-on-grey low contrast; colour-only meaning |
| **Surfaces & depth** | One consistent surface model per level (flat with dividers, cards, inset panels, borderless, layered) | Mixed models on one screen; boxes inside boxes; heavy borders everywhere; random shadows |
| **Shape** | One radius scale applied consistently, chosen for the personality (sharp = precise/industrial, round = friendly) | 4–5 radii; sharp inputs next to round buttons |
| **Components** | Clear button variants; controls on a row share height; choices look like choices; consistent padding | Several styles for the same job; filled buttons for options |
| **Visual weight & emphasis** | The eye lands on the most important thing first, then the primary action | Everything equally loud → nothing stands out |
| **Imagery & iconography** | One icon set, one stroke weight; illustrations/mascots used with purpose and consistently | Mixed icon styles, emoji next to line icons, decoration that adds noise |
| **Density** | Fits the users and context (compact for daily power users, generous for occasional/public) | Cramped and empty on the same screen |
| **Polish** | Pixel-aligned, designed states, small purposeful motion (150–200ms), no layout jump | Off-by-a-few-pixels, missing hover/focus, abrupt changes |

Severity: visual problems that hide meaning (can't tell selected state, can't find the primary action, low contrast) → 🔴/🟠 under their usability category. Pure aesthetics (generic, dated, too many sizes) → 🟡, and they must appear in Design suggestions.

## 2. Style inventory targets

From `style-inventory.js`, flag when the screen uses more than:
- font families: 2 · font sizes: 6 · font weights: 3
- text colours: 4 · background colours: 5 (excluding images) · accent colours: as defined by the colour strategy (usually 1–3)
- border radii: 3 · shadows: 3 · border colours: 3
- button visual styles: 4 (primary, secondary, ghost, danger)

These are limits on noise, not a style. Map extras to the design.md token they should be, or propose one.

## 3. Design directions — genuinely different, all on-brand

Every run (including `quick`) includes **Design suggestions**: **2–3 directions**. Each one keeps the brand anchors and the product recognisable — and the directions must be **genuinely different from each other**, not three shades of the same template.

**Draw on the design library** — that's where the range comes from:
- `library/styles.md` — pick a style or a blend per direction (shortlist by identity, drop by "avoid when", never the same style twice in one set).
- `library/patterns.md` — directions can differ in **layout pattern**, not just colour (e.g. KPI strip vs My day vs Split list-detail).
- `library/components.md` — choose component variants that fit the style and content.
- `library/type-and-colour.md` — font pairing by personality; build the palette from the brand colour; pick a colour strategy.
- `library/domains.md` — check each direction against what good looks like in this domain.

Then place each direction on these axes (and say which). At least **3 axes must differ** between any two directions:

| Axis | Options (examples, not a menu to always pick from) |
|---|---|
| Typography | neo-grotesk · humanist sans · geometric · rounded · serif headlines · slab · monospace for data · condensed for dense tables |
| Colour strategy | neutral + one accent · brand-saturated surfaces · warm neutrals · cool neutrals · dark/low-light · high-contrast · colour-coded by status/category · duotone |
| Surface model | flat with dividers · cards on tinted page · inset panels · borderless with whitespace · layered/elevated · outlined |
| Shape | sharp (0–2px) · soft (4–8px) · round (12px+) · pill controls · mixed by role |
| Density | compact · regular · comfortable · spacious |
| Layout pattern | single column · sidebar + content · split view · bento/grid of tiles · list-first · timeline · board/kanban · map/visual-first |
| Emphasis | typographic (size/weight) · colour blocks · illustration/imagery · data-viz-led |
| Personality | calm · energetic · playful · editorial · industrial · clinical · premium · friendly |

**Format:**

```
### Design suggestions — <product>, personality: <3 adjectives>

A. <name that describes the idea, not a generic label>
   Style: <library style or blend, e.g. "Dense pro × Warm hospitality"> · Pattern: <library pattern>
   Axes: type <…> · colour <…> · surfaces <…> · shape <…> · density <…> · layout <…>
   Changes: <exact tokens/components that change — from design.md where possible>
   Keeps: <brand anchors kept>
   Suits: <which users/context from the Screen brief, and why>
   Effect: <what gets easier/clearer, and how it expresses the personality>

B. …  (differs from A on ≥3 axes)
C. …  (bolder option — the one that would surprise the user in a good way)

Recommended: <A/B/C> — <why, tied to identity + users>
```

**Render, don't just describe.** Build each direction on the real page (temporary stylesheet/variant in the harness or dev server) and screenshot it; show them side by side in the demo. Users pick looks by seeing them.

If design.md exists, directions evolve it — say which tokens change. On approval, write the chosen tokens/components into design.md (with a Changelog line) and implement.

## 4. Within-system polish — always apply

Without asking, using existing tokens:
- Collapse near-duplicate font sizes, colours, radii, shadows to the nearest token.
- Give the primary action the primary style and quiet what competes with it.
- Make choice controls look like choices, not like action buttons.
- Equal heights for controls on the same row; consistent padding.
- Designed hover / focus / active / disabled states where missing.
- One surface model per level, applied everywhere on the screen.
- **Strengthen, don't flatten, the identity**: keep and sharpen what's distinctive (a mascot, a signature colour, a characterful font) instead of sanding it down to neutral.

## 5. Anti-template check — before proposing or applying any look

The most common AI-generated UI right now is: very light grey page · white cards with 1px light border and ~12px radius · tiny uppercase grey section labels · one blue primary button · pill-shaped stat chips · thin progress bars · soft pastel gradient hero · the same neo-grotesk sans · "empty state" grey sentences centred in boxes.

None of these are wrong on their own. Together, applied by default, they make every product look the same.

For every direction (and for the Fixed result), count how many of those traits it uses **without a reason tied to the identity**:
- **0–3** → fine.
- **4–5** → justify each in one line, or change at least two.
- **6+** → it's the template. Rework it from the identity (§0) and the axes (§3).

Also check memory: if the last 2–3 runs in this project (or the same agency's other projects listed in memory) applied a look with the same axes, say so and offer a direction that differs.

## 6. Remember the look

After a direction is applied, record its **look signature** in `.ui-fix/memory.md` under Decisions:
`look: personality <…> · type <…> · colour <…> · surfaces <…> · shape <…> · density <…> · layout <…>`
Later runs on this product stay consistent with it; runs on other products use it to avoid copying it.
