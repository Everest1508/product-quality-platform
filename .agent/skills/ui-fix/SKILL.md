---
name: ui-fix
description: Audit and fix any page, form, table, dashboard or UI component like a senior UI engineer — asks how far to go (fix, polish or redesign), understands what the screen is for, walks it as real users, measures it (layout, visual design, text density, clipped content, accessibility, naming, dependencies, keyboard, stress), fixes it against the project's design.md with a restore point, proves the change with screenshots, and explains what you'll see in plain language. Use when a screen looks wrong, is confusing, hard to use, needs to look better, or on /ui-fix.
---

# UI Fix

The user points at something: a page, a form, a table, a dashboard, a modal, one component, a mobile screen. You make it **obviously usable and visibly better** — then prove it, in words they understand.

**The bar:** a first-time user with zero context knows what this screen is, what to click, and what happens next, without thinking. A daily user finishes the job in the fewest steps. Nobody loses work. The user can **see** what changed.

## Mindset

- **Not broken ≠ good.** Judge by how fast and confidently real users get the job done.
- **Understand before you judge.** Know what the screen is for, who uses it, and what it does to the data.
- **Evidence over opinion.** Every finding has proof: a measured number, a screenshot, a walkthrough step.
- **Effort is the enemy.** Remove work: derive, default, defer, delete.
- **Every product looks like itself.** There is no default look. Start from the product's identity — brand, personality, domain, users, context — and never converge on the generic SaaS template (light grey page, white cards, tiny uppercase labels, one blue button, pills, pastel gradient). Directions must differ from each other and from other projects.
- **Have a design opinion.** Judge how it looks and always come back with concrete visual suggestions. "Follow the design system" means don't change the look *silently* — never "have no opinion".
- **Layout is the fix, not decoration.** Grid, alignment, balance, spacing, widths and placement decide whether a screen feels right.
- **Visible beats invisible.** Behind-the-scenes fixes (labels linked to fields, screen-reader names, contrast tweaks) are good — but when the user asked to make it *better*, they must also see a difference.
- **Fix the root.** Shared component first; then re-check everything it touches, in every role and variant.
- **Safe to try.** Every multi-file change has a restore point and, where possible, an off switch.
- **Never call a weak result good.** If the change is subtle, say so and offer more.

## How to talk to the user

The user may not be technical. Default to:
- **Plain language first.** Say what people will notice, not how the code works. No jargon (axe, aria, token, WCAG, DOM, props) unless the user uses it or asks — then explain in a few words.
- **Short answers, one question at a time.**
- **Lead with what they'll see**, not with the score, when they asked for a visual change.
- Technical detail (file:line, scan output, principle tags) goes in a **Details** section at the end; the **file list goes last**.
- Always include **"Not tested"** — what you couldn't check and why.

## Bundled files (paths relative to this SKILL.md)

Read the reference before the phase that uses it. Load only what the target needs.

| File | When |
|---|---|
| `references/understand-the-screen.md` | Every run — Phase 1 |
| `references/visual-design.md` | Every run — visual critique, within-system polish, design directions |
| `references/layout-and-spacing.md` | Every run — grid, alignment, balance, widths, spacing, placement, layout blueprint |
| `references/hierarchy-and-naming.md` | Every run — headings vs labels, confusing names, placeholders |
| `references/walkthrough-and-stress.md` | Every run — personas, stress tests, consistency |
| `references/harness-and-safety.md` | Every run — test harness for pages behind login/API, restore points, "I don't see changes", rule conflicts, memory precedence, role/variant checks |
| `references/prove-and-remember.md` | Every run — impact ranking, proof, regression guard, memory, hand-off, definition of done |
| `references/dashboards-and-content.md` | Dashboards, overviews, reports, reading-heavy screens |
| `references/forms-and-data-entry.md` | Forms, wizards, settings, data entry |
| `references/dependencies-and-navigation.md` | Dependent fields, or 4+ sections / long scroll |
| `references/design-md-template.md` | When design.md is missing |
| `references/library/styles.md` | **Design library** — 12 complete visual styles (Editorial, Swiss functional, Soft & friendly, Dense pro, Dark command center, Industrial, Warm hospitality, Clinical calm, Neo-brutalist, Premium minimal, Playful, Corporate trust) with type, colour, surfaces, shape, density, signature details, when to use/avoid, and blending |
| `references/library/patterns.md` | Layout patterns per screen type — dashboards, navigation, lists, detail pages, forms, settings, onboarding, empty states, feedback, search, mobile |
| `references/library/components.md` | Variants for metrics, buttons, inputs, choices, tables, status, progress, timelines, people, charts, dates, overlays, toasts, empty states, motion |
| `references/library/domains.md` | What good looks like per domain — HR, ERP, POS, salon/booking, CRM, finance, healthcare, e-commerce, education, logistics, monitoring, real estate, internal tools, marketing sites |
| `references/library/type-and-colour.md` | Font pairings by personality, type scales, building a palette from a brand colour (OKLCH), colour strategies, dark mode, chart colours |
| `scripts/style-inventory.js` | Browser — fonts, sizes, colours, radii, shadows, button styles in use; contrast |
| `scripts/layout-scan.js` | Browser — container width, grid, alignment, row balance, dead zones, widths, spacing, layout map |
| `scripts/text-density.js` | Browser — words per section/screen, tiny text, explanation lines, repeated numbers |
| `scripts/clip-scan.js` | Browser — text cut off by fixed heights, overflow, ellipsis, line clamps |
| `scripts/hierarchy-scan.js` | Browser — heading vs label styles, confusing names, placeholders, fake values |
| `scripts/axe-run.js` | Browser — accessibility checks, tap targets, overflow |
| `scripts/focus-scan.js` | Browser — keyboard order, visible focus, unreachable clickables |
| `scripts/dependency-scan.js` | Browser, dev only — flips choices to map dependent fields |
| `scripts/stress-text.js` | Browser — long text, other scripts, right-to-left, long values; reversible |
| `scripts/token-scan.mjs` | Shell (Node) — hardcoded colours/sizes/inline styles |

Browser scripts: run the file's contents with the browser's JS tool (or Playwright `page.evaluate`). Each has a `ROOT`/`TARGET`/`MODE` constant at the top to set first.

## Levels and modes

**Level — how far to go** (asked in Phase 0 when unclear):
- **Fix** — broken and confusing things only: usability, layout, naming, accessibility. The look stays.
- **Polish** — Fix + tidy the look within the current design system (consistent sizes, colours, spacing, emphasis). Same look, cleaner.
- **Redesign** — a new look. Render 2–3 directions as screenshots on the real page, apply the recommended one (or the user's pick), say how to undo it.

"Make it better" without more detail → ask (Phase 0). If the user isn't around to answer → **Polish**, plus directions rendered for them to pick.

**Mode — what to produce:**
- `fix` *(default)* — everything at the chosen level.
- `quick` — understand, see, walk, measure, judge, report. No code changes. Design suggestions included.
- `sweep` — audit every screen in a folder/route group → ranked table → fix shared root causes first. Ask before editing more than ~5 files.
- `handoff` — like `quick`, plus a paste-ready implementation prompt for another coding agent.

## Safety

- Local / dev / staging only. Never production. Never submit real data. Walkthroughs and `dependency-scan.js` click choices — never Save/Submit/Delete unless the data is disposable and you say so.
- Restore point before any multi-file edit (Phase 7).
- Don't change business logic, API payloads, permissions or unrelated files.
- Never rewrite or delete design.md rules or memory decisions on your own.

---

## Phase 0 — Ask first, once · then remember & ground

**Ask first, once.** If the request is vague ("fix", "make it better", "redesign", "looks bad"), ask **one** question before auditing — combine everything into it:
> What feels wrong to you, and how far should I go — **Fix** (broken things only), **Polish** (same look, tidied), or **Redesign** (new look)? *(+ if several screens match: "Which one — Admin, Manager or Staff dashboard?")*

Use the question tool if available. Don't ask when the request already says what's wrong and how far, or when the user isn't present (then use the default above and state it). Never ask a second round of questions before showing work.

Then:
1. Read **`.ui-fix/memory.md`** if it exists. Follow Decisions, don't re-propose Rejected, use the Glossary. **An explicit "redesign completely" overrides earlier look decisions** — record that it superseded them. Removed widgets stay removed unless asked (`harness-and-safety.md` §5).
2. Find **design.md** (root, `docs/`, `.design/`, `design/`, `src/`, `frontend/`, `client/`, `*design-system*.md`, `*style-guide*.md`). Read it fully. Missing → say so, infer from the code (Tailwind config / CSS variables / theme / most-used components), list what you inferred, offer to generate one from `references/design-md-template.md`.
   - design.md vs code → design.md wins; flag it.
   - **design.md vs a measurable accessibility rule** (e.g. placeholder contrast) → report the conflict, apply a scoped opt-in fix, propose the rule change. Never override silently (`harness-and-safety.md` §4).
3. **Product identity** (`visual-design.md` §0, plus the matching playbook in `library/domains.md`): personality (3 adjectives), context of use, brand anchors (logo, colours, typeface, mascot/illustration), domain cues, and distinctive things to keep — from design.md, brand assets in the repo, memory, the existing UI, the Screen brief. Still unclear and it matters (Polish/Redesign) → fold it into the one intake question: "three words for how it should feel?". Read the stored **look signature** from memory if there is one.
4. Note the stack, component library, icon set, test/lint setup, and whether the screen differs by **role or variant**.
5. Run folder: `.ui-fix/runs/<YYYY-MM-DD>-<target-slug>/`.

## Phase 1 — Understand the screen

Do `references/understand-the-screen.md`: read the source, children, shared styles, form schema, the API it calls, the backend handler and model. Produce the **Screen brief** — purpose, job type, users, data in/out, rules, flow, element inventory, primary task path, UI↔backend mismatches, assumptions. Every later finding ties back to it.

## Phase 2 — See it for real

1. Use the running dev server or start it with the project's command.
2. **Behind login or an API, or no local data?** Build a **test harness** (`harness-and-safety.md` §1): Playwright with mocked routes, reusing the project's own fixtures, matching the **real response shapes**. Save it in `.ui-fix/harness/` and reuse it next time. Mock crashes are not findings — fix the mock.
3. Screenshot desktop (~1440) and mobile (375), plus reachable states, **for every role/variant** of the screen. Save as `before-*.png`.

No browser → say so in one line; work from code and any screenshot given.

## Phase 3 — Walk it as real users

From `references/walkthrough-and-stress.md`: persona walkthroughs (always Newcomer + Keyboard-only; others as the brief suggests), 5-second and first-click tests, friction log; stress tests (breakpoints, 200% zoom, `stress-text.js`, data volume, missing data, slow network, errors, dark mode); consistency with sibling screens.

## Phase 4 — Measure

Keep the raw numbers for before → after:
- **Visual critique** (`layout-and-spacing.md` §1 + `visual-design.md` §1): 5–8 lines on grid, alignment, balance, rhythm, focal point, reading path, density, fit, type, colour, surfaces — and **identity**: could you tell which product this is with the logo covered?
- `style-inventory.js` — always.
- `layout-scan.js` — always, desktop and 375px.
- `text-density.js` — always. Dashboards/overviews: aim ≤ 250 words per screen, explanations in tooltips.
- `clip-scan.js` — always, at every breakpoint you check. Text hidden by fixed heights is a top finding.
- `hierarchy-scan.js`, `axe-run.js`, `focus-scan.js` — always.
- `dependency-scan.js` — forms (dev only), plus a code search for conditions on other fields.
- `token-scan.mjs` — on the target's files.
- Forms: Effort table. Dashboards: the dashboard check (`dashboards-and-content.md` §1).

## Phase 5 — Judge

Only real problems. Categories:

- **L. Layout, spacing & placement** (`layout-and-spacing.md`) — one grid, aligned edges, sensible width, balanced rows, widths that match content, spacing on the scale with clear grouping, placement by task order → dependency → importance → grouping.
- **H. Hierarchy & naming** (`hierarchy-and-naming.md`) — section titles vs labels, confusing/vague/abbreviated names, placeholders, fake values, choices that look like choices.
- **I. Dependencies & way-finding** (`dependencies-and-navigation.md`) — child under its parent, hide or explain disabled, numbered sections, section index.
- **B. Zero-context clarity** — what is this screen, one obvious primary action, labels that say what happens, a way out, feedback for every action.
- **C. By target type** — compare against the domain playbook (`library/domains.md`) and the best-fitting pattern (`library/patterns.md`) — is this the right layout pattern for the job at all? Then: forms (`forms-and-data-entry.md`); **dashboards** (`dashboards-and-content.md`: one headline sentence, 3 signals, no duplicated metrics, details on demand, a reason for every chart vs table); tables; modals; navigation; single components; staff/data-entry screens; public pages.
- **T. Text & content** (`dashboards-and-content.md` §2–3) — too many words, tiny text, too many explanation lines, repeated numbers, **clipped/hidden content**.
- **D. States** — loading, empty, error, disabled with reason, success.
- **E. Accessibility** — contrast, focus, keyboard, names on icon buttons, colour never the only signal.
- **F. Responsive & stress.**
- **G. Consistency** — same job, same pattern, same names.
- **V. Visual design** (`visual-design.md`).
- **A. Design-system adherence.**

For every issue: severity (🔴 blocks / hides / loses data · 🟠 confuses / slows · 🟡 polish), **Impact = Severity × Frequency × Reach**, evidence, file:line, principle tag (tags go in Details, not the main report). Root cause: shared component or theme → list every screen, role and variant it affects.

### Score — rubric v3

Each category starts at max; subtract per issue (🔴 −8, 🟠 −4, 🟡 −2), floor 0.

| Category | Max |
|---|---|
| Clarity, hierarchy, naming & way-finding (H + I + B) | 20 |
| Layout, spacing & placement (L) | 20 |
| Usability for this kind of UI + text & content (C + T) | 15 |
| States & feedback (D) | 10 |
| Accessibility & keyboard (E) | 15 |
| Visual design, system & consistency (V + A + G) | 10 |
| Responsive & stress (F) | 10 |

**Keep the rubric stable.** Always say "rubric v3" next to a score. Compare scores only within the same rubric version; if memory holds an older-version score, show it but don't compare. Change the rubric only in a new skill version.

## Phase 6 — Report

Plain language, short. **Order matters:**

```
## What you will see differently
- <visible change> — <where to look: section / position on screen>
- … (max 5)

## How to see it
- Open: <URL> · as: <role/account> · then: hard refresh (Cmd/Ctrl+Shift+R) <or "restart the dev server: <command>">
- Status: changed on your computer only — not committed, not deployed  <or what was committed/pushed>
- Undo: <one command / one step>

## What was wrong
1. <plain-language problem — who it hurts and how> 
2. …

## Options to go further
<Design suggestions (`visual-design.md` §3): 2–3 directions built from the product's identity, each a different position on the axes (type, colour strategy, surfaces, shape, density, layout — ≥3 axes differ), with what changes, what stays, who it suits, and which you recommend. Rendered as screenshots. For Redesign: which one was applied.>

## Not tested
- <what you couldn't check and why — e.g. real login, other roles, Safari, production data>

## Score (rubric v3)
<before → after, per category — or only "before" in quick mode>

## Details
<Screen brief · Layout map + blueprint & Why table · Hierarchy / Rename / Dependency / Effort / Stress / Consistency / Text-density / Clip tables · walkthrough friction log · scan numbers · principle tags · file:line per issue>

## Files changed
<list, last>
```

- In `quick` mode, replace "What you will see differently" with "What I'd change, and what you'd see".
- **If the result is subtle, say so plainly** in the first section and offer a bigger option. **Never finish with only invisible fixes** (label links, screen-reader names, contrast) when the user asked to make it better — add visible improvements or render directions.
- Design suggestions appear in every mode.

## Phase 7 — Fix

**Restore point first** (`harness-and-safety.md` §2): before any multi-file edit, copy the files to `.ui-fix/runs/<run>/backup-before/`, write `restore.sh`, and state the one-step restore. Prefer changes that can be switched off (a class, variant, flag or separate stylesheet) and say how.

By level:
- **Fix** — every 🔴 and 🟠, including layout (implement the Layout blueprint: regroup, reorder, re-grid, resize, respace, move children under parents). Only a real blocker excuses one — name it.
- **Polish** — Fix + within-system visual polish (`visual-design.md` §4) that **sharpens** the product's identity, never sands it down to neutral.
- **Redesign** — Polish + build 2–3 identity-driven, genuinely different directions **from the design library**: each picks a style or blend (`library/styles.md`), a layout pattern (`library/patterns.md`), component variants (`library/components.md`) and type/colour from `library/type-and-colour.md` (brand colour → palette in OKLCH), (pass the **anti-template check**, `visual-design.md` §5), **render each as a screenshot on the real page** (apply as a temporary stylesheet/variant in the harness or dev server), apply the recommended one (or the user's pick), say how to undo. Write the chosen direction's tokens into design.md on approval.

Always:
- **Minimal-change trap:** if your change list is mostly markers, renames and colours while layout or text problems were found, you're not done.
- **Screenshot after every change** (`step-NN-<what>.png`) — catch breakage immediately.
- **Verify the dev server serves the change** before judging it (`harness-and-safety.md` §1.7).
- Root causes first; shared component changes keep the API compatible or update every call site.
- Project's stack, components, icon set and tokens only; propose design.md rules instead of inventing silently.
- Keep business logic, payloads and data flow intact.
- Workflow upgrades (wizard, presets, copy-from-previous) → show as an Upgraded view, apply on a yes. Check memory's Rejected list first.

## Phase 8 — Prove, lock in, remember

From `references/prove-and-remember.md`:
1. **Prove:** re-run every scan, re-walk, re-screenshot (`after-*.png`) **for every role/variant**, re-score with the same rubric. Visual regression on everything a shared change touches. Payload and tests intact. Anything fails → fix and re-prove.
2. **Demo** — one self-contained HTML file: Before / After (and Upgraded / Directions) as tabs, real screenshots with desktop/mobile toggle, live interactive After with real tokens, numbered callouts, a proof panel. Published as an artifact or inline preview if the environment allows.
3. **Lock in:** a focused test if the project has a test setup; propose a lint rule if it has a linter.
4. **design.md:** generate if missing (with approval); propose rules for gaps; append on approval with a Changelog line.
5. **Memory:** decisions, rejections, superseded decisions, glossary, **look signature** of any applied direction, harness location, screen log row (score + **rubric version**, open items).

## Phase 9 — Wrap up

Check the Definition of done (`prove-and-remember.md`), then deliver the Phase 6 report with the after-state filled in.

**If the user says "I don't see changes"** → follow `harness-and-safety.md` §3 in order: files changed? server serving them? right URL/role/account? hard refresh? only local? subtle? Don't argue — check and show.

---

## Don'ts

- Don't start a vague request without the one intake question (unless the user is away — then default to Polish and say so).
- Don't ask more than one round of questions before showing work.
- Don't lead with the score or jargon when the user wants to see a visual change.
- Don't finish "make it better" with only invisible fixes.
- Don't edit several files without a restore point.
- Don't report mock crashes as findings, or judge a change the dev server isn't serving.
- Don't change a shared component without re-rendering every role and variant.
- Don't override design.md silently — report conflicts, scope the fix, propose the rule.
- Don't compare scores across rubric versions.
- Don't reintroduce removed widgets, or re-propose rejected ideas.
- Don't leave a 🔴/🟠 unfixed without naming the blocker.
- Don't run against production, submit real data, or click destructive actions.
- Don't fall back to a default look. No two products should come out looking the same — run the anti-template check.
- Don't flatten a product's distinctive features (mascot, signature colour, characterful type) into neutral.
- Don't add new libraries or touch unrelated logic.
