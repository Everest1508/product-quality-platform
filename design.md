# Beforth PDF Design System

Style guide for generating branded PDF documents (SRS, dev guides, proposals) using WeasyPrint + HTML/CSS + inline SVG.

---

## 1. Colors

### Primary

| Name | Hex | Usage |
|---|---|---|
| Navy | `#0D1117` | All headings, dark surfaces, strong text |
| Blue | `#1A5BFF` | Accent color — links, buttons, active states, requirement ID tags, brand strip |
| Slate BG | `#EDF0F8` | Page background on content pages |
| White | `#FFFFFF` | Card backgrounds, table cell fills, cover text on dark |

### Secondary

| Name | Hex | Usage |
|---|---|---|
| Deep Navy | `#1C2333` | Dark surfaces (cover background, callout headers) |
| Stone | `#6B7280` | Body text, captions, muted content |
| Border | `#D1D8E8` | Table borders, dividers, rule lines |
| Blue Tint | `#EBF0FF` | Blue wash backgrounds (alternating table rows, callout bodies) |
| Dot Grid | `#C2CEE8` | Texture dots on cover page and section dividers |

---

## 2. Typography

### Typeface Sources

- **Bebas Neue** — Google Fonts. Regular weight only. Use for all display/headline text.
  - Local file: `~/.fonts/BebasNeue-Regular.ttf`
  - Google Fonts: `https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap`
- **Inter** — Google Fonts. Variable weight (400, 500, 600, 700). Use for all body copy, labels, tables.
  - Google Fonts: `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap`

### @font-face Setup

```css
@font-face {
  font-family: 'Bebas Neue';
  src: url('file:///home/ritesh/.fonts/BebasNeue-Regular.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
}

@font-face {
  font-family: 'Inter';
  src: url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  font-weight: 400;
}
```

### Type Scale

| Role | Font | Weight | Size | Color | Transform | Usage |
|---|---|---|---|---|---|---|
| H1 | Bebas Neue | 400 | 48px | Navy | uppercase | Section titles |
| H2 | Bebas Neue | 400 | 32px | Navy | uppercase | Sub-section titles |
| H3 | Inter | 700 | 18px | Navy | none | Card/box headings |
| Body | Inter | 400 | 10.5px | Stone | none | All body copy |
| Body Bold | Inter | 600 | 10.5px | Navy | none | Emphasis within body |
| Caption | Inter | 400 | 9px | Stone | none | Figure captions, footnotes |
| Table Header | Inter | 600 | 9.5px | White | none | TH cells |
| Table Cell | Inter | 400 | 9.5px | Stone | none | TD cells |
| Tag | Inter | 600 | 8px | Blue | uppercase | Requirement IDs, status labels |
| Code | monospace | 400 | 9px | Navy | none | Inline code, API endpoints |

---

## 3. Page Setup

```css
@page {
  size: A4;
  margin: 0;
}

@page :first {
  /* Cover page — no numbering */
}

@page content {
  margin: 0;
  @bottom-center {
    counter-increment: page;
    content: counter(page);
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    color: #6B7280;
  }
}
```

Every content page uses a `.page` div that provides internal padding:

```css
.page {
  width: 210mm;
  min-height: 297mm;
  padding: 60px 65px 50px 65px;
  box-sizing: border-box;
  background: #EDF0F8;
  page: content;
  page-break-after: always;
  position: relative;
}
```

---

## 4. Cover Page

### Structure

Three-section flex layout inside a `.cover` div:

1. **Top bar** — 6px solid Blue strip (brand accent)
2. **Center block** — Company name (Bebas Neue, 72px, White), document title (Bebas Neue, 36px, White), subtitle/version (Inter, 14px, Slate)
3. **Bottom block** — Date, version, classification, rendered in Inter on the dark background

### Cover CSS

```css
.cover {
  width: 210mm;
  height: 297mm;
  background: #0D1117;
  display: flex;
  flex-direction: column;
  page-break-after: always;
  position: relative;
  overflow: hidden;
}

.brand-strip {
  height: 6px;
  background: #1A5BFF;
  width: 100%;
  flex-shrink: 0;
}

.cover-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 65px;
}

.cover-bottom {
  padding: 40px 65px;
  border-top: 1px solid rgba(255,255,255,0.1);
}
```

### Dot-Grid Texture (Cover Background)

Radial dots on the cover's dark background:

```css
.cover::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, #C2CEE8 1px, transparent 1px);
  background-size: 28px 28px;
  opacity: 0.15;
  pointer-events: none;
}
```

---

## 5. Components

### Tables

```css
table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'Inter', sans-serif;
  font-size: 9.5px;
}

th {
  background: #0D1117;
  color: #FFFFFF;
  font-weight: 600;
  padding: 8px 12px;
  text-align: left;
}

td {
  padding: 7px 12px;
  border-bottom: 1px solid #D1D8E8;
  color: #6B7280;
  vertical-align: top;
}

tr:nth-child(even) td {
  background: #EBF0FF;
}

tr:nth-child(odd) td {
  background: #FFFFFF;
}
```

### Requirement ID Tags

Small inline badges for requirement numbering:

```css
.req-tag {
  display: inline-block;
  background: #EBF0FF;
  color: #1A5BFF;
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 8px;
  padding: 2px 8px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-right: 6px;
}
```

### Callout / Warning Boxes

```css
.callout {
  background: #FFFFFF;
  border-left: 4px solid #1A5BFF;
  border-radius: 4px;
  padding: 16px 20px;
  margin: 16px 0;
}

.callout.warning {
  border-left-color: #F59E0B;
}

.callout-header {
  font-family: 'Inter', sans-serif;
  font-weight: 700;
  font-size: 12px;
  color: #0D1117;
  margin-bottom: 6px;
}

.callout-body {
  font-family: 'Inter', sans-serif;
  font-size: 10.5px;
  color: #6B7280;
  line-height: 1.6;
}
```

### Term Definition Cards

For glossary and key-term callouts:

```css
.term-card {
  background: #FFFFFF;
  border: 1px solid #D1D8E8;
  border-radius: 6px;
  padding: 14px 18px;
  margin-bottom: 10px;
}

.term-name {
  font-family: 'Inter', sans-serif;
  font-weight: 700;
  font-size: 11px;
  color: #0D1117;
}

.term-def {
  font-family: 'Inter', sans-serif;
  font-size: 10px;
  color: #6B7280;
  margin-top: 4px;
  line-height: 1.5;
}
```

### Step Lists

Numbered process steps:

```css
.step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 14px;
}

.step-number {
  width: 28px;
  height: 28px;
  min-width: 28px;
  background: #1A5BFF;
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Inter', sans-serif;
  font-weight: 700;
  font-size: 12px;
}

.step-text {
  font-family: 'Inter', sans-serif;
  font-size: 10.5px;
  color: #6B7280;
  line-height: 1.6;
  padding-top: 3px;
}
```

---

## 6. SVG Diagram Approach

Architecture and flow diagrams are drawn as inline SVG within the HTML, not CSS boxes.

### Box Helper Pattern

```svg
<svg width="W" height="H" xmlns="http://www.w3.org/2000/svg">
  <!-- Box -->
  <rect x="X" y="Y" width="W" height="H" rx="6"
        fill="#FFFFFF" stroke="#D1D8E8" stroke-width="1"/>
  <!-- Label -->
  <text x="CX" y="CY" text-anchor="middle"
        font-family="Inter" font-size="10" fill="#0D1117">
    LABEL
  </text>
</svg>
```

### Arrow Helper Pattern

```svg
<line x1="X1" y1="Y1" x2="X2" y2="Y2"
      stroke="#1A5BFF" stroke-width="1.5" marker-end="url(#arrow)"/>
<defs>
  <marker id="arrow" markerWidth="8" markerHeight="6"
          refX="8" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6" fill="#1A5BFF"/>
  </marker>
</defs>
```

### Validation Rules

- All boxes must fit within the content area width (`210mm - 2*65px padding`)
- Arrows must connect box edges (not overlap boxes)
- Text labels must not overflow their parent boxes
- Run geometric validation: check `x + width <= container_width` for every box

---

## 7. Tone Guide

### SRS Documents (Formal)

- Use "shall" for mandatory requirements
- Use "should" for recommendations
- Passive voice acceptable ("The system shall...")
- Each requirement gets a unique ID tag: `REQ-XXX-NNN`
- Source traceability via note-page references

### Developer Guides (Plain English)

- Direct address ("You will...", "This means...")
- Concrete examples with real numbers
- Short sentences, active voice
- Jargon defined in a glossary section
- Step-by-step numbered lists for processes

---

## 8. Build Toolchain

- **PDF engine**: WeasyPrint (Python)
- **HTML**: Single Python script (`build.py`) generates HTML string with inline CSS
- **Diagrams**: Inline SVG generated by helper functions in `build.py`
- **Output**: PDF file in `outputs/` directory
- **Fonts**: Local `.ttf` for Bebas Neue, Google Fonts CDN for Inter (or local `.ttf` if downloaded)

### WeasyPrint Install

```bash
pip install weasyprint
```

### Basic Build Pattern

```python
from weasyprint import HTML

html = f"""<!DOCTYPE html>
<html>
<head><style>{CSS}</style></head>
<body>
  {cover_page}
  {content_pages}
</body>
</html>"""

HTML(string=html).write_pdf('outputs/document.pdf')
```
