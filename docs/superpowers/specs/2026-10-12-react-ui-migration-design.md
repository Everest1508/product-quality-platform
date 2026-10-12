# React UI migration: design

Date: 2026-10-12 · Status: draft for review

## Goal

Replace the server-rendered UI (148 templates, ~10.6k lines, htmx + Alpine) with a React UI that is more interactive, looks modern and is easy for the team to maintain.

**Not goals:** a public API for other clients, mobile reuse, a separately deployed frontend, any change to backend language, models or business rules.

**Success:** every current page works in React with identical permissions and behaviour; each page ships independently; the existing test suite still passes after every step.

## Approach: incremental, page by page

Django stays the backend (Python, same DB, same session auth). A React app in `frontend/` talks to it over JSON endpoints. Pages are migrated one at a time; the Django template for a page stays in place until its React version is verified.

Rejected: full SPA rewrite (nothing ships until everything is done; highest risk to HR/payroll flows) and React-shell-only (gives the look but not the interactivity).

## Guardrails

- **Old pages stay live.** A per-page setting (`REACT_PAGES = {"tickets_board", ...}`) selects React or the legacy template, so rollback is a config change.
- **Business rules untouched.** Models, every `service.py`, `Ticket.transition_to`, DSR auto-logging, notifications, Discord webhooks, `log_activity`, attendance/leave/payroll rules are not modified. React only renders and submits input.
- **No duplicated access logic.** Each endpoint calls the existing helpers (`accessible_products`, `accessible_tickets`, `require_product_access`, `require_ticket_access`, `require_error_group_access`, the `Company*Mixin`s) and the same service functions the current views call. Shared logic is extracted from a view only when both the legacy view and the endpoint need it.
- **Tests are the gate.** `manage.py test apps` must match baseline (one known failure: `test_signup_creates_user`) after every step. Each new endpoint gets tests for company isolation, per-product access and role checks.
- **Side effects preserved.** Mutating endpoints keep `log_activity`, notifications and webhooks. Toast messages move to the JSON response and the React toast layer; `messages.*` stays for legacy pages.

## Architecture

**Backend (Python, additive only).**
- New app `apps/uiapi/` mounted at `/ui-api/v1/`. Plain DRF `APIView`s using `SessionAuthentication` (CSRF enforced), reusing `request.company` / `request.company_role` from `CurrentCompanyMiddleware`. Distinct from `/api/v1/` (API keys) and `/api/serop/` (bearer tokens), which are unchanged.
- Serializers shape responses from the same querysets the legacy views use (including `select_related("product")` so `ticket.key` works).
- `GET /ui-api/v1/bootstrap/` returns user, active company, role, company list, nav products, open counts and app version: the data the `product_context` / `workspace_context` processors give templates.

**Frontend.**
- `frontend/`: Vite + React + TypeScript, TanStack Query for data, React Router inside each migrated section.
- **UI library: [befui](https://befui.vercel.app/)** (191 components, 27 blocks; React + Tailwind 4 + Radix). It is not an npm package: components are copied into `frontend/src/components/ui/` with `npx befui add <name>` and owned by us, so there is no version lock-in. All new UI is composed from befui components and blocks; we write a custom component only when befui has none.
- Theming: befui is rebranded by changing `--primary`, `--ring` and the accent variables (light and dark follow). These are set once in the frontend CSS, seeded from the current accent in `_tokens.css`. The old five CSS files are not ported; they are deleted with the legacy templates.
- Tailwind 4 is added to the Vite build only. Legacy templates keep their inline CSS, so the two styling systems never share a page.

### befui mapping (starting point, confirm per page)

| Current feature | befui component / block |
|---|---|
| `core/base.html` shell, `_sidebar.html` | App shell, Sidebar, Navbar, Bottom navigation (phones), User menu, Theme toggle |
| Toasts from `messages` | Toast |
| `{% dropdown %}` choice controls | Select, Combobox, Dropdown menu |
| `/search/` | Command palette, Search bar |
| Ticket lists, filters, saved views | Data table, Filter bar, Saved views, Pagination |
| Ticket board by status | Kanban board |
| Ticket / error detail history | Timeline, Comment thread, Activity feed, Audit log |
| Notifications, presence | Notification center, Avatar, Status dot |
| Dashboards, product cards | Stat card, charts (Area, Bar, Pie, Line), Leaderboard |
| Attendance, leave | Calendar, Event calendar, Week strip, Approval flow, Stat card |
| Payroll, DSR | Data table, Invoice, Description list |
| Role/product access settings | Permission matrix |
| What's new dialog | Changelog, Dialog and Sheet |
| Forms | Field, Input, Date picker, Time picker, Schema form |

If a mapped component turns out to be missing a needed behaviour (for example drag-to-change-status on the board), we extend our copy of it; that is the point of copy-paste ownership.
- Reuses the existing WebSockets (`/ws/presence/`, `/ws/inbox/`) with the same session cookie; no protocol change.

**Serving.** Django serves the built files from the same origin (a small view like `apps/core/brand.py`, since there is no static pipeline). Same origin means no CORS, no tokens, and login, CSRF and company switching keep working as today. A migrated page's template becomes a thin shell: base layout + a mount `<div>` + the bundle script. Sidebar and toasts keep working during the transition.

**Dev and deploy.** Dev: `runserver` + `vite dev` with a proxy to Django. Docker: add a Node build stage producing `frontend/dist`. Production runs no Node.

## Migration order (each step independently shippable)

1. **Foundation + pilot.** Vite scaffold, Tailwind 4, befui init and base components (app shell, sidebar, toast), `uiapi` app, bootstrap endpoint, serving view, `REACT_PAGES` switch, shell template, one small low-risk page to prove the pipeline end to end.
2. **Interactive core.** Ticket board and detail (global and product-scoped), error groups, inbox.
3. **Dashboards, products, surveys, milestones, rules, settings, search, notifications.**
4. **HR last.** Attendance, leave, payroll (most rules, highest stakes; payslip 404-not-403 behaviour preserved).
5. **Retire legacy.** Remove templates/views for fully migrated areas only after a stable period.

Global and product-scoped views must be migrated together per domain, since the CLAUDE.md invariant requires them to stay in sync.

## Testing

- Backend: Django tests per endpoint (isolation, product access, roles, side effects). Existing tests untouched.
- Frontend: Vitest + Testing Library for components; one smoke check per migrated page against the running dev server.
- Per-page parity checklist (list, filters, create, edit, status change, permissions) verified before flipping its switch.

## Risks

- Parity gaps in rarely used pages: mitigated by per-page checklist and the rollback switch.
- Drift between legacy view and endpoint logic during coexistence: mitigated by extracting shared helpers and deleting the legacy view once flipped.
- Service worker/PWA (`apps/core/pwa.py`): checked, it only caches `/brand/` icons and CDN hosts, so our bundle is not cached by it. The bundle is served `no-cache` with stable names; revisit (hashed names) if load time matters.

## Open questions

1. ~~Pilot page~~ Resolved: notifications (`/notifications/`). The bootstrap endpoint is deferred to the first full-page React section, because the pilot runs inside the legacy shell.
2. ~~TypeScript~~ Resolved: yes.
3. ~~Visual direction~~ Resolved: use befui for the UI and all components; brand colour set via befui's `--primary` variables (keep current accent unless told otherwise).
4. befui is new and small; confirm its licence and that its CLI works against Tailwind 4 + Vite in step 1 before committing to it for every page.
