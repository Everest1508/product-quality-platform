# Design System

> Source of truth for how this product looks and behaves. Every UI change follows this file.
> Lines marked `(inferred)` were read from the code and still need a human to confirm them.

## Users
- Who uses this product:
- Devices (desktop / tablet / phone / kiosk / touch):
- Tech comfort (low / mixed / high):
- Language(s) for UI labels:

## Colors
| Token | Value | Use for |
|---|---|---|
| `--color-primary` | | Primary buttons, links, active states |
| `--color-primary-hover` | | |
| `--color-surface` | | Page background |
| `--color-surface-raised` | | Cards, modals |
| `--color-text` | | Body text |
| `--color-text-muted` | | Secondary text (must still pass 4.5:1) |
| `--color-border` | | Inputs, dividers |
| `--color-success` | | |
| `--color-warning` | | |
| `--color-danger` | | Destructive actions, errors |
| `--color-focus` | | Focus ring |

Dark mode: (yes/no — if yes, list overrides)

## Typography
- Font family (UI):
- Font family (numbers/code, if different):

| Level | Size | Weight | Line height | Use for |
|---|---|---|---|---|
| Display | | | | |
| H1 | | | | Page title |
| H2 | | | | Section title |
| H3 | | | | Card / group title |
| Body | | | | |
| Small | | | | Helper text, captions |

## Spacing & layout
- Spacing scale: (e.g. 4, 8, 12, 16, 24, 32, 48)
- Page max width:
- Grid / columns:
- Breakpoints: (e.g. 375 / 768 / 1024 / 1440)

## Radius, borders, shadows
- Radius: sm / md / lg =
- Border width:
- Shadows: sm / md / lg =

## Components
### Button
- Variants: primary / secondary / ghost / danger
- Sizes: sm / md / lg (min height 44px for touch)
- States: default, hover, focus, active, disabled, loading
- Rules: one primary per screen; label = verb + noun ("Save invoice")

### Input / Select / Textarea
- Label above field, always visible
- Required mark:
- Helper text position:
- Error style: red border + message below with how to fix

### Table
- Header style, row height, zebra (y/n)
- Numbers right-aligned
- Row actions:
- Empty state:
- Mobile behaviour:

### Card
### Modal / Dialog
### Toast / Alert
### Navigation (sidebar / topbar / tabs / breadcrumbs)

## States
- Loading: (skeleton / spinner / where)
- Empty: message + next-step action
- Error: plain-language message + retry
- Disabled: explain why (tooltip or helper text)
- Success: (toast / inline / redirect)

## Forms
- Label placement:
- Required vs optional convention:
- Validation timing: (on blur / on submit)
- Submit button: verb + noun, shows loading, blocks double-submit
- Long forms: sections or steps after ~8 fields

## Copy & voice
- Tone:
- Button labels: verb + noun
- Error messages: say what happened + how to fix, no codes
- Words to avoid:

## Accessibility
- Contrast minimum: 4.5:1 text, 3:1 large text and UI
- Focus style:
- Min tap target: 44×44px
- Icon-only buttons need aria-label

## Do / Don't
- Do:
- Don't:

## Changelog
- YYYY-MM-DD: created (from ui-fix)
