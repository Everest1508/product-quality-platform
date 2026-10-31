# Style library — 12 complete visual styles

Each style is a full, buildable starting point. **None is the default.** Pick by the product's identity (`visual-design.md` §0), blend two when it fits (e.g. Dense pro structure + Warm hospitality colour), and adapt to the brand anchors (brand colour replaces the style's accent; brand font replaces the style's font if it has one).

All fonts are free (Google Fonts) unless the brand has its own. Values are starting points — tune to the brand, keep contrast ≥ 4.5:1 for text.

---

## 1. Editorial
- **Feels:** considered, intelligent, calm authority.
- **Best for:** reports, analytics summaries, knowledge bases, consulting/legal/premium B2B, annual reviews.
- **Type:** headlines *Fraunces* or *Newsreader* (serif, 600); body *Inter* or *Source Sans 3*; numbers tabular. Scale ratio 1.333 (large contrast between levels).
- **Colour:** paper `#FBFAF7`, ink `#1B1B1A`, muted ink `#5F5E5A`, one deep accent (oxblood `#7A1F2B`, ink blue `#1F3A5F` or forest `#22442F`).
- **Surfaces:** flat, hairline rules (`1px` ink at 12% opacity) instead of cards; generous margins.
- **Shape:** sharp (0–2px).
- **Density:** comfortable.
- **Signature details:** large section numerals ("01"), pull-quote style key metric, rules between sections, small caps labels, left-aligned ragged text.
- **Avoid when:** heavy data entry, small screens with dense tables.

## 2. Swiss functional
- **Feels:** precise, rational, confident.
- **Best for:** admin consoles, analytics, design-literate teams, internal tools that should feel sharp.
- **Type:** *Inter Tight*, *Geist* or *Archivo*; strong weight contrast (400 vs 700); big type for key numbers.
- **Colour:** pure white `#FFFFFF`, black `#0A0A0A`, greys from one ramp, single signal accent (red `#E5322D` or brand) used sparingly.
- **Surfaces:** flat, strict 12-column grid, alignment does the grouping; thin black rules.
- **Shape:** 0px.
- **Density:** regular.
- **Signature details:** asymmetric grid, oversized numerals, flush-left everything, no shadows, no gradients.
- **Avoid when:** users need warmth/reassurance (healthcare patients, consumer onboarding).

## 3. Soft & friendly
- **Feels:** approachable, encouraging, light.
- **Best for:** consumer apps, education, wellness, small-business tools, onboarding-heavy flows.
- **Type:** *Nunito*, *Plus Jakarta Sans* or *Manrope*; generous line-height (1.6).
- **Colour:** white or very light warm tint; a pastel tint per category/module (mint, lavender, peach, sky) with darker text tones of the same hue; brand colour for primary.
- **Surfaces:** cards with soft large shadows (`0 8px 24px` at 6–8% opacity), no borders.
- **Shape:** round (14–20px cards, full-pill buttons).
- **Density:** comfortable/spacious.
- **Signature details:** spot illustrations, emoji-free icon set with rounded strokes, celebratory success states, progress shown as friendly milestones.
- **Avoid when:** dense data, finance/compliance, power users.

## 4. Dense pro
- **Feels:** efficient, serious, built for experts.
- **Best for:** ERP data entry, operations, accounting, inventory, dev/IT tools, anything used all day.
- **Type:** *IBM Plex Sans* + *IBM Plex Mono* for codes/numbers, 13–14px base, tabular numbers.
- **Colour:** neutral greys (cool or warm to match brand), brand colour only for primary and focus, full semantic set (success/warn/danger/info) for status.
- **Surfaces:** borders not shadows; panels separated by 1px lines; zebra or hover rows in tables.
- **Shape:** small (3–4px).
- **Density:** compact (32px controls, 8px gaps), but tap targets ≥ 44px on touch devices.
- **Signature details:** keyboard shortcut hints, sticky headers and action bars, inline editing, split views, status chips, monospace IDs.
- **Avoid when:** occasional or first-time users without onboarding.

## 5. Dark command center
- **Feels:** focused, real-time, high-stakes.
- **Best for:** monitoring, IoT/energy dashboards, trading, control rooms, security/NOC, anything watched for long periods in low light.
- **Type:** *Inter* or *Geist* for labels; *JetBrains Mono* or *IBM Plex Mono* for live values; large numerals.
- **Colour:** background `#0E1116`, panels `#161B22`, text `#E6EDF3` / muted `#8B949E`; semantic colours tuned for dark (green `#3FB950`, amber `#D29922`, red `#F85149`, blue `#58A6FF`); brand as accent only.
- **Surfaces:** panels slightly lighter than background, 1px borders `#30363D`, no heavy shadows.
- **Shape:** small–soft (4–6px).
- **Density:** compact for data, big for the one headline value.
- **Signature details:** live indicators (pulsing dot), sparklines, threshold lines on charts, alarm states that are impossible to miss, clock/last-updated always visible.
- **Avoid when:** used in bright environments or by occasional users; always offer a light theme too if users switch contexts.

## 6. Industrial
- **Feels:** rugged, unambiguous, glove-friendly.
- **Best for:** factory floor, warehouse, field service, kiosks, tablets in harsh light.
- **Type:** *Barlow* / *Barlow Condensed* (condensed for headers and table columns), 16px+ base, bold labels.
- **Colour:** high contrast — near-black `#111` on white or light grey, safety yellow `#FFC400` for attention, clear red/green status; avoid subtle tints (washed out in sunlight).
- **Surfaces:** solid blocks, 2px borders, strong separation.
- **Shape:** sharp–small (0–4px).
- **Density:** spacious targets (48–56px), few items per screen.
- **Signature details:** huge primary action, status as full-width coloured bars, big numbers, scan-friendly codes, minimal text, works one-handed.
- **Avoid when:** office knowledge work, marketing pages.

## 7. Warm hospitality
- **Feels:** welcoming, sensory, human.
- **Best for:** restaurants, cafés, hotels, salons, spas, booking, events, food delivery.
- **Type:** headings *DM Serif Display* or *Playfair Display*; body *DM Sans* or *Outfit*.
- **Colour:** warm neutrals (cream `#FAF6F0`, sand `#EFE6D8`), espresso text `#2B2118`, accents like terracotta `#C8553D`, olive `#6B7F3A` or the brand's colour.
- **Surfaces:** image-led cards, soft shadows, photography or illustration of the product/space.
- **Shape:** soft–round (10–14px).
- **Density:** comfortable; staff-facing screens (POS, booking desk) go compact but keep the warmth in colour.
- **Signature details:** photos of dishes/services, time-slot chips, calendar as the hero, warm empty states.
- **Avoid when:** dense financial reporting.

## 8. Clinical calm
- **Feels:** safe, clean, trustworthy, legible.
- **Best for:** healthcare, pharma, labs, compliance, insurance claims, government services.
- **Type:** *Atkinson Hyperlegible* or *Source Sans 3*; 15–16px base; generous line-height.
- **Colour:** white, very light cool grey `#F4F7F8`, calm teal/blue-green primary (`#0F766E` or brand), restrained semantic colours with icons + text (never colour alone).
- **Surfaces:** light borders, clear sections, plenty of whitespace.
- **Shape:** soft (6–8px).
- **Density:** regular; critical info never hidden.
- **Signature details:** confirmations before irreversible actions, audit trail visible, clear status labels, large readable values with units.
- **Avoid when:** you need energy or playfulness.

## 9. Neo-brutalist
- **Feels:** bold, honest, energetic, memorable.
- **Best for:** creative tools, startups, youth brands, internal tools that want personality, portfolios.
- **Type:** *Space Grotesk*, *Archivo Black* for headlines, *Inter* body.
- **Colour:** white or cream base, black `#000` lines, saturated flat accents (yellow `#FFE14D`, pink `#FF6FB5`, blue `#3D5AFE`, green `#2BD47D`).
- **Surfaces:** 2–3px black borders, hard offset shadows (`4px 4px 0 #000`), no blur.
- **Shape:** 0–6px.
- **Density:** regular.
- **Signature details:** buttons that "press" (shadow collapses on click), sticker-like badges, big type, deliberate asymmetry.
- **Avoid when:** conservative enterprise, healthcare, finance, accessibility-first audiences (keep contrast strong if used).

## 10. Premium minimal
- **Feels:** refined, quiet, expensive.
- **Best for:** private banking, wealth, real estate, jewellery, luxury hospitality, premium memberships.
- **Type:** headlines *Cormorant Garamond* or *Playfair Display* (light/regular), body *Manrope* or *Inter* with slightly wider letter-spacing.
- **Colour:** ivory `#F7F4EE` or near-black `#121212` base, charcoal/ivory text, one metallic-feel accent used sparingly (bronze `#A27B4E`, deep gold `#B08D57`).
- **Surfaces:** almost none — whitespace and thin lines; large imagery.
- **Shape:** sharp (0–2px).
- **Density:** spacious.
- **Signature details:** fewer elements, larger type, slow subtle motion, numbers presented with restraint.
- **Avoid when:** high-volume operational work.

## 11. Playful / gamified
- **Feels:** fun, motivating, alive.
- **Best for:** culture/HR engagement, learning, habit/fitness apps, kids, community tools, products with a mascot.
- **Type:** *Rubik*, *Baloo 2* or *Fredoka* for UI; an expressive display font (pixel, handwritten, chunky) only for small accents that match the mascot/brand.
- **Colour:** bright, saturated set (3–5 colours) with clear jobs (rewards, streaks, levels); dark text on light for readability.
- **Surfaces:** chunky cards, colourful headers per module, playful empty states.
- **Shape:** round (12–20px), pills.
- **Density:** comfortable.
- **Signature details:** mascot reacts to state (success/empty/error), streaks, badges, progress as levels, small celebratory motion — always skippable and never blocking work.
- **Avoid when:** serious/regulated contexts, or let it live only in non-critical areas (greeting, achievements) while work areas stay calm.

## 12. Corporate trust
- **Feels:** stable, established, reliable.
- **Best for:** banking, insurance, enterprise B2B, government, legal, utilities.
- **Type:** *IBM Plex Sans*, *Source Sans 3* or *Public Sans*; conservative scale.
- **Colour:** navy `#14213D` or the brand's deep colour, white, cool greys, a single secondary accent; semantic colours conservative.
- **Surfaces:** cards with light borders, clear header bar, structured sidebar.
- **Shape:** small–soft (4–6px).
- **Density:** regular.
- **Signature details:** clear breadcrumbs, explicit labels, summaries before details, printable/exportable views, visible security cues.
- **Avoid when:** you need to stand out or feel young.

---

## Blending

Most real products blend: **structure** from one style (density, surfaces, layout) + **expression** from another (type, colour, imagery). Examples:
- Staff POS: Dense pro structure + Warm hospitality colour and type.
- HR engagement home: Corporate trust work areas + Playful greeting/achievements.
- Energy monitoring: Dark command center main view + Clinical calm for reports and settings.
- Factory supervisor desktop: Dense pro + Industrial status colours.

State the blend in the direction ("Dense pro × Warm hospitality").

## Choosing

1. Shortlist 3–4 styles whose **Best for** and **Feels** match the identity and users.
2. Drop any whose **Avoid when** applies.
3. The 2–3 directions you propose must use **different** styles or clearly different blends.
4. Check memory: don't reuse the style applied to the user's previous products unless this product's identity calls for it — and say why.
