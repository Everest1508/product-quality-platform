# Type & colour toolkit

---

## 1. Font pairings by personality (Google Fonts)

| Personality | Headings | Body / UI | Numbers / code |
|---|---|---|---|
| Neutral, modern | Inter Tight | Inter | Inter (tabular) |
| Precise, technical | IBM Plex Sans | IBM Plex Sans | IBM Plex Mono |
| Editorial, intelligent | Fraunces / Newsreader | Source Sans 3 | Source Code Pro |
| Friendly, rounded | Nunito / Fredoka | Nunito | — |
| Warm, human | DM Serif Display | DM Sans | DM Mono |
| Geometric, confident | Manrope / Outfit | Manrope | JetBrains Mono |
| Industrial, condensed | Barlow Condensed | Barlow | Barlow (tabular) |
| Bold, quirky | Space Grotesk / Archivo Black | Inter | Space Mono |
| Premium, refined | Cormorant Garamond / Playfair Display | Manrope | — |
| Highly legible | Atkinson Hyperlegible | Atkinson Hyperlegible / Source Sans 3 | — |
| Corporate, public-sector | Public Sans | Public Sans | IBM Plex Mono |
| Playful, youthful | Baloo 2 / Rubik | Rubik | — |
| Multilingual (incl. Indic, Arabic, CJK) | Noto Sans (+ script-specific Noto) | Noto Sans | Noto Sans Mono |

Rules: max 2 families; use the brand font if it exists; check the font covers the users' scripts; use tabular figures (`font-variant-numeric: tabular-nums`) for numbers that are compared.

## 2. Type scales

| Context | Base | Ratio | Example steps |
|---|---|---|---|
| Dense app (ERP, tables) | 13–14px | 1.2 | 12 · 14 · 17 · 20 · 24 |
| Regular app | 14–16px | 1.25 | 12 · 14 · 16 · 20 · 25 · 31 |
| Editorial / marketing | 16–18px | 1.333 | 16 · 21 · 28 · 38 · 50 |
| Touch / industrial | 16–18px | 1.25 | 16 · 20 · 25 · 31 · 39 |

Line-height: 1.5–1.6 body, 1.2–1.3 headings. Max line length ~65–75 characters for reading text.

## 3. Building a palette from a brand colour

Work in **OKLCH** (perceptually even) when possible.
1. **Brand scale** — 10–11 steps from the brand colour by varying lightness (L ≈ 0.97 → 0.25) and easing chroma down at the extremes. The brand colour lands near step 500–600.
2. **Neutrals** — a grey scale with a tiny tint of the brand hue (chroma 0.005–0.02). Warm brand → warm greys; cool brand → cool greys. This alone makes a product feel less generic.
3. **Semantic** — success (green), warning (amber), danger (red), info (blue); each with a light background, a border and a text tone. Shift hues slightly toward the brand so they feel related.
4. **Roles, not raw colours** — define tokens: `bg`, `surface`, `surface-raised`, `border`, `text`, `text-muted`, `primary`, `primary-hover`, `primary-text`, `focus`, `success/warning/danger/info` (+ `-bg`, `-text`).
5. **Check contrast** for every text/background pair you use (≥ 4.5:1 text, ≥ 3:1 large text and UI parts).

## 4. Colour strategies (pick one per direction)

| Strategy | Feel | Notes |
|---|---|---|
| Neutral + one accent | calm, focused | Accent only for primary/active/focus |
| Brand-saturated | confident, branded | Brand colour as large surfaces (header, sidebar); keep content areas neutral |
| Warm neutrals | human, crafted | Cream/sand bases, earthy accents |
| Cool neutrals | technical, clean | Blue-grey bases |
| Dark / low-light | focused, premium, monitoring | Raise surfaces with lighter greys, not shadows; desaturate accents slightly |
| High-contrast | rugged, accessible | Black/white + one signal colour |
| Category-coded | scannable modules | One tint per module/type; same tint everywhere it appears |
| Duotone | distinctive, branded | Two brand colours carry all emphasis |

## 5. Dark mode
- Don't invert. Use dark greys (not pure black) for background, lighter greys for raised surfaces.
- Reduce saturation of accents; keep semantic colours distinguishable.
- Text at ~87% / 60% white for primary / secondary.
- Re-check every contrast pair and every chart colour.

## 6. Data-viz colours
- **Categorical, colour-blind safe** (Okabe-Ito): `#E69F00` `#56B4E9` `#009E73` `#F0E442` `#0072B2` `#D55E00` `#CC79A7` `#000000`.
- **Sequential**: one hue, light → dark. **Diverging**: two hues around a neutral midpoint (for above/below target).
- One highlight colour for "the thing to notice", the rest neutral grey.
- Never rely on colour alone: direct labels, patterns or markers.
