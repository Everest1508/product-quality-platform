# Dependent fields & way-finding

Read this for any form or screen with more than one section, or any field that changes based on another field.

---

## Part 1 — Dependent fields (parent → child)

A **parent** field controls a **child**: "Ship to a different address: Yes/No" → address fields; "Payment method: Card" → card fields; "Country" → "State"; "Customer" → "Billing address". Users must be able to see that link without reading code.

### 1. Map the dependencies first

- **From the code**: search for conditions that reference another field — `disabled={!values.x}`, `watch('x')`, `v-if="form.x"`, `x-show`, `*ngIf`, `{% if %}`, `required_if`, `depends_on`, schema `when()`/`refine()`, `useEffect` that resets a field when another changes, backend `if data.x` validation.
- **In the browser**: run `scripts/dependency-scan.js`. It flips each Yes/No / radio / checkbox / select option, records which other fields become disabled, enabled, hidden, shown, or change value, then restores the original state. **Run only on local/dev/staging.**
- Build a **Dependency map** table: Parent · Value · Child · Effect (disabled / hidden / required / options filtered / value set) · Visible link? (yes/no) · Layout distance.

### 2. Rules for showing the link

- **Child sits right under (or right after) its parent.** Never in another column, another row group, or another section. Parent left / child right in a 2-column grid only if they're on the same row and visually joined. 🟠 if separated; 🔴 if the child is in another section or tab.
- **Child looks attached**: indented, or a left border/connector line, or a nested sub-card, or grouped in one bordered box with the parent. The parent + its children read as one unit.
- **Prefer hide over grey-out** when the child is meaningless without the parent (No access system → no access type). Reveal it when the parent turns on, with a smooth expand. Greyed-out fields still take space, still get read, and look broken.
- **If you must disable** (layout stability, or the user needs to see what's possible), say why right there: helper text "Turn on Email digest to choose how often" — never a silent grey box. Disabled fields still keep readable contrast.
- **Label the child in relation to its parent** where it helps: "Frequency" under "Email digest", "Card number" under "Pay by card" — the nesting carries the context, so the child label can be short.
- **Changing the parent clears or re-filters the child, and says so** ("State list updated for Canada"). Never keep a stale child value that's now invalid. Never silently submit hidden values — clear them or exclude them.
- **Required follows visibility**: a child is required only when shown/enabled. The `*` appears when it becomes required.
- **Chains** (A → B → C): show as a clear step order, top to bottom; each level indented or numbered.
- **Many Yes/No feature toggles in one section** (add-ons, options, permissions, notification channels…): use a checklist ("Choose the add-ons for this plan"), each checked item expanding its own details. One click per feature instead of two, and the children appear exactly where they belong.

Report: Dependency map + each broken link as an issue.

---

## Part 2 — Way-finding on long screens

Once a form/page has **4+ sections or needs scrolling more than ~2 screens**, users need to know where they are, what's left, and how to jump.

### 3. Section titles

- **Numbered**: "1. Customer", "2. Items", "3. Shipping", … "6. Review". Numbers make the order and progress obvious and give people something to say ("check section 5").
- **Specific names**, not catch-alls. "Other settings" → "Notifications", "Privacy & security". If a section is a junk drawer, split or rename it. Catch-all names ("Other", "Misc", "Additional", "General", "More") → 🟠.
- One-line description under the title when the purpose isn't obvious.
- Show **completion per section** where it helps: "3/5 filled", or a ✓ when done, a red dot when something's missing/invalid.

### 4. Section index / navigation

- **Sticky index** (side rail on desktop, collapsible top bar or dropdown on mobile) listing all sections with numbers, the current one highlighted (scroll-spy), each clickable to jump there.
- Tabs that hold sections must show status too: count of missing/invalid fields on the tab ("Specifications • 2").
- "Next section" / "Back" at the end of each section for top-to-bottom flow, when the form is filled in order.
- Keep the Save bar sticky so nobody scrolls back up to save.

### 5. Icons

Icons help scanning — only when they're consistent and meaningful.
- Use the **project's icon set** (check design.md / existing components: lucide, heroicons, material, font-awesome…). Don't add a new library.
- **One icon per section title** (and optionally per major feature toggle), picked for meaning: bell for notifications, lock for security, credit-card for payment, truck for shipping, user for profile, file for documents.
- Same size and colour everywhere, aligned with the text, `aria-hidden="true"` when the text already says it.
- **Never icon-only** for anything a user has to understand or click. Icon + text, always.
- If an icon doesn't have an obvious meaning, leave it out — a wrong icon is worse than none.

Add the section icon and numbering rule to design.md if it isn't there (Step 9).

### 6. Long-form layout checks

- 2-column grids: each row should hold related fields, read left→right then down. Unrelated pairs side by side ("Delivery notes" next to "Discount code") → regroup.
- Fields with units show the unit in the input ("m") and contain a number — never "NA" (see hierarchy-and-naming).
- The page shows where you are (index highlight) and how far you have to go (numbered sections or progress).
