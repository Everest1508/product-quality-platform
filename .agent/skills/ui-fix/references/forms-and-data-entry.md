# Forms & data entry — the playbook

Read this whenever the target is a form, a wizard, a settings page, or any screen where people select or enter data. Most of the pain in business apps lives here.

The goal: **fewest decisions, fewest keystrokes, zero guessing, zero lost work.**

---

## 1. Measure the effort first

Before changing anything, count these for the current form (from the code + screenshots):

| Metric | How to count |
|---|---|
| Fields total | every input/select/checkbox/radio the user can touch |
| Required fields | marked or enforced by validation |
| Dropdowns | every `<select>`/combobox, plus how many options each has |
| Decisions | fields with no default that the user must actively choose |
| Clicks to complete | minimum clicks/taps to fill required fields and save (open dropdown + pick = 2) |
| Typing | free-text fields that could be selected, derived, or defaulted instead |
| Tabs/steps | how many places the user must visit |

Report them as an **Effort table** (before → after). A good fix makes these numbers drop. If they don't drop, you didn't really fix the form.

## 2. Remove before you redesign

Best field is the one the user never has to fill. For every field ask, in order:
1. **Can we derive it?** From another field (postal code → city and state, product → price and tax rate, customer → currency and terms), from the logged-in user, the date, the selected customer/project, the last record. Derive it and show it read-only (with an "edit" option if overriding is legit).
2. **Can we default it?** The most common value, the user's last-used value, the company default. A good default turns a decision into a glance.
3. **Is it needed now?** If it's only needed later (approval, dispatch, invoicing), move it to that stage or behind "More details".
4. **Is it needed at all?** If nothing reads it, flag it to the user as removable — don't silently delete.

## 3. Pick the right input for every field

Wrong control type is the #1 cause of slow forms.

| Situation | Use | Not |
|---|---|---|
| 2–4 options, all short | Radio buttons or a segmented control (all visible, one click) | Dropdown (2 clicks + hidden options) |
| Yes / No, On / Off | Toggle or single checkbox | Dropdown with Yes/No |
| 5–10 options | Native-style select, options in a sensible order | Free text |
| 10+ options | **Searchable select / combobox** (type to filter) | Plain dropdown the user scrolls through |
| 50+ options or comes from a master table (customers, items, vendors) | Async searchable select, shows code + name, recent items on top | Loading all options into a plain select |
| Multiple choices from a list | Checkbox group (≤7) or multi-select with chips (>7) | Ctrl-click multi `<select>` |
| Number with a unit | Number input with the unit as a suffix ("°C", "kg", "L") | Bare number with unit in the label only |
| Range (min–max) | Two number inputs side by side, one label | Two separate fields far apart |
| Date | Date picker that also accepts typing | Three dropdowns (day/month/year) |
| Small integer (qty 1–10) | Stepper (− 1 +) | Dropdown of numbers |
| Long free text | Textarea that grows | Single-line input |
| Code that maps to a name | Show "Name (CODE)" in options and display | Code only |

## 4. Dropdowns done right

For every dropdown, check:
- **Option order**: most used first, or logical order (sizes ascending), or alphabetical — never database insert order.
- **Option labels**: full words a new user understands. Codes/abbreviations go in brackets after the name: "Net 30 days", not "N30"; "Stock keeping unit (SKU)".
- **Placeholder** reads as an instruction ("Select country"), has readable contrast, and is not selectable as a value.
- **Searchable** once there are more than ~10 options.
- **Dependent dropdowns (cascading)**: when B depends on A, B is disabled with a hint ("Choose a country first") until A is chosen; changing A resets or re-filters B and says so. Never show options in B that are invalid for A.
- **Empty / loading / error** states for options fetched from the server ("Loading items…", "No vendors found — add one", "Couldn't load, retry").
- **"Other" escape hatch** when the list can't cover everything: picking it reveals a text field.
- **Create inline** when the user is likely to need a new master record ("+ Add new vendor") instead of making them leave the form.
- **One-option dropdowns**: if only one valid option exists, pre-select it (or show it as text).

## 5. Structure & flow

- **Required first, optional later.** Put what the user must fill at the top of each section; optional fields grouped below or behind "More details".
- **Group into sections** with clear headings once there are more than ~8 fields. Each section = one idea ("Customer", "Items", "Payment", "Delivery").
- **Long forms (25+ fields):** split into steps with a progress indicator, or sections with a sticky side/top index showing completion per section (e.g. "Payment 3/5"). Don't hide required fields in a tab the user may never open — show which tabs have missing/invalid fields (dot or count on the tab).
- **Layout**: one column by default; two columns only for short, related fields (Min/Max, City/PIN). Labels above fields.
- **Sticky action bar** on long forms: Save / Cancel always visible.
- **Field order follows the real-world order** the user works in (the order on their paper form, the order the customer gives info).

## 6. Speed for people who fill this every day

- **Duplicate / start from previous**: "Copy from job #…" or "Use last values" for repetitive entries.
- **Templates / presets** if the same combinations come up often (e.g. "Standard monthly retainer", "Domestic shipment").
- **Remember last-used values** per user for fields that usually repeat.
- Full **keyboard flow**: Tab moves in visual order, Enter in a select picks, typing jumps to options, Ctrl/Cmd+S saves, Esc cancels dialogs.
- **Autofocus** the first field that actually needs input.
- **Auto-format as they type** (phone, postal code, tax/VAT ID, card number), not error after.

## 7. Validation & not losing work

- Validate **on blur** for format, **on submit** for required; never yell while the user is still typing.
- Error messages say what to do: "Enter a temperature between 105 and 134 °C", not "Invalid input".
- On submit with errors: **error summary at the top** listing each problem as a link that jumps to the field, AND the first invalid field focused. If it's in another tab/section, switch there.
- Cross-field rules shown up front ("Max must be higher than Min") not discovered on save.
- **Autosave drafts** or warn on leave with unsaved changes. Never lose input on an error, refresh, or tab switch.
- Submit button shows loading and blocks double-submit; success says what happened and what's next ("Job AE-1042 created — Add another / View job").

## 8. Review before commit

For high-stakes forms (orders, jobs, payments, anything hard to undo): a short **review summary** before final save, grouped by section, with "Edit" links. Derived/defaulted values clearly shown so nothing surprising goes through.

---

## What to report for forms

In addition to the normal issue list, always include:
1. **Effort table** before → after (fields, required, dropdowns, decisions, clicks, typing, tabs).
2. **Field-by-field table** for any field you'd change: Field · Now · Should be · Why. (e.g. "Door type · dropdown, 2 options · segmented control · 1 click instead of 2, both options visible")
3. Fields you'd **derive, default, move later, or flag as removable**.
