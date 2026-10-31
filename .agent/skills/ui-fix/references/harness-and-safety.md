# Test harness, restore points, and "I don't see the change"

---

## 1. Test harness — for pages behind login or an API

Real screenshots, walkthroughs and re-checks need the page to render with realistic data. When the page needs a login, a backend, or data you don't have locally, build a harness instead of guessing.

**Build it once, reuse it:** save to `.ui-fix/harness/` (e.g. `.ui-fix/harness/<screen>.mjs` or `.spec.ts` if the project uses Playwright Test). Note it in `.ui-fix/memory.md` so later runs reuse it.

How:
1. **Use what the project already has first**: existing Playwright/Cypress setup, test fixtures, factories, seed scripts, Storybook stories, MSW handlers, mock JSON. Reuse those fixtures for mock data.
2. **Check the real response shapes** before mocking: read the API types/serializers/schemas (TypeScript types, OpenAPI, Pydantic/Django serializers) or capture one real response from the local backend. Mocks must match field names, nesting, nulls and pagination exactly.
3. **Mock with Playwright routes**, e.g.
   ```js
   await page.route('**/api/jobs/**', r => r.fulfill({ json: fixture }));
   ```
   Auth: set the session cookie / token in `storageState`, or mock the `/me` endpoint, or use a test account from seed data. Never use real user credentials.
4. **Cover every role / variant** the screen has (admin, manager, staff…; empty / full / error data). If the app has a role or preview switcher, drive it.
5. **Mock crashes are not findings.** If the page breaks because a mock is wrong or incomplete, fix the mock. Only report a crash when it happens with realistic data matching the real API.
6. **Screenshot after every change** you make, not just at the end, into the run folder (`step-01-<what>.png`, …). This catches a fix that broke something else immediately.
7. **Verify the dev server actually serves your change** before judging it: hard reload, then check the served source contains the change (fetch the module/CSS URL and search for a string you added, or check the build output timestamp). If hot-reload didn't pick it up, restart the dev server.

## 2. Restore point — before any multi-file edit

Files may not be tracked in git, or may have uncommitted work. Before editing more than one file:

1. Copy every file you'll touch to `.ui-fix/runs/<run>/backup-before/`, keeping relative paths.
2. Write `.ui-fix/runs/<run>/restore.sh` (and say the command) that copies them back:
   ```bash
   # restore everything this run changed
   cp -R .ui-fix/runs/<run>/backup-before/. ./
   ```
   On Windows also give the PowerShell equivalent if relevant.
3. State the **one-step restore** in the report.
4. **Prefer changes that can be switched off**: a new CSS class / variant / prop, a feature flag, a separate stylesheet import, or a wrapper component — so the old look is one line away. Say how to switch it off.
5. If the project is in git, also mention `git diff` to review and `git checkout -- <files>` to undo, but never rely on git alone.

## 3. "I don't see any changes" — check in this order

When the user says the change isn't visible, don't argue — check:
1. **Files changed?** Show the changed files and a one-line diff summary.
2. **Server serving them?** Is the dev server running from this folder? Did it rebuild? Fetch the served file and search for the change. Restart if needed.
3. **Right place?** Same URL, same route, same **role / account** (role-based screens show different components), same feature flag, same tenant/branch.
4. **Cache?** Hard refresh (Cmd/Ctrl+Shift+R), clear service worker, private window.
5. **Only local?** Nothing is committed, pushed or deployed unless you did it — say so. A staging/production URL won't show local changes.
6. **Subtle?** If the change is real but small, say so plainly, point to exactly where to look (with a before/after screenshot crop), and offer a bigger option.

## 4. design.md vs measurable rules

If design.md (or memory) requires something that fails a measurable accessibility rule — e.g. placeholder or helper text colour below 4.5:1, focus outline removed, tap targets under 44px:
- **Report the conflict** plainly ("Your design system's placeholder grey is 2.6:1; people with low vision can't read it").
- **Apply a scoped, opt-in fix** — limited to the screen you're fixing, easy to remove (a class or variant), not a global token change.
- **Propose the design.md rule change** with the exact new value. Never override design.md silently, and never change it without approval.

## 5. Memory precedence

- An explicit **"redesign completely" / "new look"** request overrides earlier look decisions in memory. Record in memory that it superseded them (date + what was superseded) so later runs follow the new direction.
- **Removed widgets / sections stay removed** unless the user asks for them back. Don't reintroduce them through a "restore defaults" or a template.
- Rejected suggestions stay rejected unless the user raises them again.

## 6. Shared components across roles and variants

When you change a shared component or a screen that renders differently per role/variant (role-based dashboards, plan tiers, light/dark, empty/full data):
- Re-render **every role and variant** before and after (use the app's role/preview switcher, or the harness).
- Compare screenshots side by side (pixelmatch if available). Unexpected differences get fixed before reporting.
