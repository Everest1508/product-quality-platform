# Visual hierarchy & naming

Read this on every run. If people can't tell a section title from a field label, or one field name from another, nothing else matters — they're lost before they start.

---

## 1. Levels must look different — at a glance

Every screen has levels. Each level needs its own look, and the difference must be obvious without reading:

| Level | Example | Must look like |
|---|---|---|
| Page title | "New invoice" | Biggest, boldest text on the screen |
| Tab / step | "Specifications" | Clearly a navigation control, active one obvious |
| **Section title** | "Billing address", "Payment" | **Clearly a heading for a group** — not a field label |
| Sub-section (if any) | "Card details" | Between section and label |
| **Field label** | "Postal code" | Small, attached to its field |
| Helper / hint | "Choose a country first" | Smaller, muted, under the field |
| Value / placeholder | "Select country" | Inside the field, placeholder visibly lighter than a real value |

**Rules for section vs field label (the most common failure):**
- Size: section title at least **1.25× the label size** (e.g. label 14px → section 18px+), **and** a heavier weight, or a distinct style (uppercase eyebrow, color, icon).
- Size alone isn't enough if the difference is under ~25% — add weight, color, a divider, or a container.
- **Group the fields visually**: each section in a card/panel, or separated by a divider line, or a `<fieldset>` with a `<legend>`.
- **Spacing**: space above a section title ≥ **2×** the space between fields in a section. Fields inside a section sit close together; sections sit far apart (law of proximity).
- Optional but strong: a one-line description under the section title ("Where we send the invoice").

Use the design.md type scale. If design.md has no section-heading style, propose one (Step 9).

**Tests:**
- **Squint test** — look at the screenshot blurred/zoomed out. Can you count the sections? Can you tell where one ends and the next starts? If not → 🔴.
- **Heading scan** — read only the section titles top to bottom. Do they read like a table of contents for the form?

Measure it — run `scripts/hierarchy-scan.js` in the browser. It reports the computed font size/weight/color of headings vs labels and flags levels that are too close.

## 2. Names must be distinct and self-explanatory

**Label-only test:** read only the field labels, top to bottom, as someone who has never seen this app. For each one: do I know what to enter? Could I confuse it with another field?

Flag and fix:
- **Section and field with the same name** — section "Shipping" → field "Shipping". The field must say *what about* it: "Shipping method", "Shipping speed", "Ship to". 🟠
- **Near-duplicate labels** — "Account type" / "Account category" / "Account class" / "Account details": if a user can't instantly say how they differ, rename so the difference is the first word they read, or add a helper line. 🟠
- **Repeated prefix inside a section** — under "Billing address", every label starting with "Billing" adds noise ("Billing street", "Billing city"…); the section already says it. Keep a prefix only where the section mixes two things (e.g. "Billing & shipping" → "Billing city" / "Shipping city").
- **Abbreviations and codes** — Qty., Amt., SKU, PO, ETA, internal codes: spell out, code in brackets: "Quantity", "Stock keeping unit (SKU)", "Purchase order no. (PO)". Domain experts lose nothing; new staff stop guessing. 🟠
- **Vague labels** — "Details", "Info", "Data", "Type", "Other", "Remarks" with no subject. 🟠
- **Yes/No questions without a question** — "Notifications" + Yes/No, "Data required" + Yes/No: about what? Rewrite as a question: "Email this customer when the invoice is paid?" 🟠
- **Same thing, different names across screens** — list says "Job", form says "Order", PDF says "Work order". Pick one (check design.md / existing screens) and use it everywhere. 🟡
- **Masters vs records** — "Product master" (the list you manage) vs "Product" (the one chosen on this order). In forms, label by what the user is choosing ("Product"), never by the master's table name. Where master data can be managed, link to it explicitly: "Manage products →". 🟠
- **Truncated labels** ("Preferred delivery wind…") — 🔴 if the user can't know the field; fix layout (wrap, wider column, shorter clear label), never rely on a tooltip.

Write a **Rename table** for every change: Current label · New label · Why.

## 3. Placeholders & values

- Placeholder says what to pick: **"Select country"**, not "Select" / "Choose" / "--". Placeholder never replaces the label.
- Placeholder colour is visibly lighter than real values but still readable (≥ 4.5:1 is ideal; ≥ 3:1 minimum).
- **No fake values**: "NA", "-", "0", "N/A" typed into fields as defaults. If a field doesn't apply, either hide it (conditional on another field), disable it with a reason, or leave it empty with an explicit "Not applicable" option. A number field must not hold text. 🟠
- List-type values typed as text ("red, blue, sale", "Mon, Wed, Fri") → checkbox group or multi-select chips. 🟠

## 4. Choices must look like choices

- Yes/No (and other 2–4 option) button groups must show a **clearly selected state** (filled/colored, check icon) and an obvious unselected state, and look different from action buttons (Save, Add). If nothing is selected by default, it must be obvious nothing is selected yet. 🔴 if you can't tell the current value.
- Prefer a real radio group / segmented control (with `role="radiogroup"` and arrow-key support), or a toggle/checkbox for single on/off.
- Grouped choices sit next to their label, aligned with other fields in the section.

## 5. Layout consistency

- Fields in a row should be related (City + Postal code is fine; Phone + Discount code is not).
- Consistent widths for similar fields; short inputs (qty, yes/no) shouldn't stretch full width while long ones are cramped.
- Columns align; labels line up; no field half off-screen at common widths (check 1280px and 375px).

---

## What to report

Add to the issue list, and include:
1. **Hierarchy table** — level · font size · weight · color · spacing above (from `hierarchy-scan.js`), with "too close" flags.
2. **Rename table** — current label · new label · why.
3. Squint-test result in one line.
