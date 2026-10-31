# Understand the screen before judging it

You can't fix a screen you don't understand. A layout that looks "clean" can be wrong for the job; a "cluttered" one can be exactly what a daily user needs. Do this investigation before the audit, and judge every finding against it.

Work from the code first (it's the truth), then the running UI, then ask the user only for what neither can tell you.

---

## 1. Purpose — what is this screen for?

Answer in one sentence: **"<Who> uses this to <do what> so that <outcome>."**
e.g. "Accounts staff use this to create an invoice for a customer so they get billed on time." · "Shoppers use this to pay for their cart so the order ships." · "Admins use this to set who can see which reports."

Find it from: route/page name, page title, menu placement, the API it calls, the model/table it writes, comments, README/SRS/docs in the repo, commit messages touching the file.

Then classify the main job:
- **Create** (new record), **Edit** (change existing), **Review/approve**, **Look up/search**, **Monitor** (dashboard/status), **Configure** (settings), **Act on many** (bulk list), **Read/learn** (content page), **Convert** (sign-up, purchase, contact).

The job type decides what "good" means: a Create form is judged on speed and error-free entry; a Monitor screen on how fast the important number is spotted; a Look-up screen on search and filters; a Convert page on clarity of the one action.

## 2. Users & context

- **Who:** role(s) that use it (from auth/permissions code, menu config, design.md, docs).
- **How often:** once (onboarding), occasionally, or **many times a day** (power users — speed and keyboard matter more than hand-holding).
- **Where/how:** desk with mouse and keyboard, tablet on a counter or warehouse floor, phone on the move, kiosk, shared PC.
- **What they know:** domain experts who know the codes, or new/temporary staff who don't.
- **Language:** what language the users read best.

If the answer would change the fix and you can't find it, ask one short question. Otherwise state your assumption in the Screen brief.

## 3. What it actually does — trace the data

Read the code end to end:
- **Data in:** what loads when the screen opens (API calls, queries, props, URL params). What's prefilled and from where.
- **Data out:** what the save/submit sends — endpoint, payload shape, model/table written.
- **Business rules:** backend validation, required fields on the server, unique checks, cross-field rules, permissions, status transitions. These must be reflected in the UI (shown up front, not discovered on save).
- **Side effects:** what happens after save — record created, status changed, email/notification sent, stock moved, document generated, another screen unlocked.
- **Dependencies between fields:** which choices change other options or values (country → state, customer → billing address and currency, product → unit price and tax).
- **Mismatches:** fields the UI collects that the API ignores; fields the API requires that the UI doesn't mark required; validation in the backend only; options hardcoded in the UI that should come from master data. These are real bugs — report them.

## 4. Where it sits in the flow

- **Comes from:** which screen/menu/button leads here, and with what context (e.g. from an order → customer already known).
- **Goes to:** what the user does next after success (view record, add another, go back to list, print).
- **Related screens:** list/detail/edit versions of the same thing — they should look and behave consistently.

A screen that ignores where the user came from (asks again for what's already known) or leaves them stranded after success is a usability issue.

## 5. Element inventory

List every meaningful element on the screen. For a large form, group by section.

| Element | Type | Purpose | Data (source → destination) | Required? | Used how often | Notes |
|---|---|---|---|---|---|---|
| Customer | searchable select | who gets billed | customers API → invoice.customer_id | yes | every invoice | drives address, currency |
| Due date | date | when payment is due | user → invoice.due_date | yes | every invoice | could default from payment terms |
| Export PDF | button | download a copy | invoice → pdf | — | rare | sits next to Save, same weight |

Flag:
- **No clear purpose** (nothing reads it, no one knows why it's there) → ask whether it can go.
- **Purpose not obvious from the label** → rename or add helper text.
- **Important but buried / rare but prominent** → reorder by importance and frequency.
- **Duplicate** (same data asked twice, or already known from context).

## 6. Primary task path

Write the shortest path a typical user takes to finish the main job, step by step:
1. Open "New invoice" from the customer page
2. Pick customer (already known — should be prefilled)
3. Add line items
4. … 
n. Save → sees invoice number → sends it

Count steps and clicks. This path is what your fix must make shorter, clearer and safer. Any element that isn't on the path should not compete with it visually.

## 7. Screen brief (output this before the audit)

```
### Screen brief — <name>
Purpose: <who> uses this to <do what> so that <outcome>.
Job type: Create | Edit | Review | Look up | Monitor | Configure | Bulk | Read | Convert
Users: <roles>, <frequency>, <device/setting>, <domain knowledge>, <language>
Data in: <what loads, from where>
Data out: <what save sends, where, side effects>
Key rules: <validation, dependencies, permissions>
Flow: from <screen> → here → <next screen>
Primary path: <n> steps, <n> clicks
Elements: <n> total — <n> on the primary path, <n> secondary, <n> unclear purpose
Mismatches found: <UI vs backend issues, or "none">
Assumptions: <anything you guessed>
```

Keep it tight — this is so the user can confirm you understood the screen, and so every finding afterwards has a reason ("this hurts the primary path because…").
