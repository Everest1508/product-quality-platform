# CRM API plan (for a separate React frontend)

Status: **plan, not built.** This file is the contract we build the backend to. `API.md` documents the CardSnap
mobile API that already exists; this one is about the team web app.

## Where we are

- The CRM is server-rendered Django. About **330 routes** serve HTML or redirects (forms, htmx fragments). Only about
  **35** return JSON: ingestion (`/api/v1/errors|feedback|tickets`), DSR (`/api/v1/dsr/...`), Serop (`/api/serop/...`),
  CardSnap (`/api/app-auth/...`), `version`, `changelog`.
- None of those JSON APIs suit a React app. Each uses a different credential: a per-product API key, a DSR token, a
  Serop bearer token, or the CardSnap app JWT. Team members sign in with a **session cookie** and CSRF.
- The rules that matter live in two places and must not be copied into React:
  - **Access:** `apps/products/access.py` (`accessible_products`, `require_*_access`) and `CompanyMemberRequiredMixin` /
    `CompanyAdminRequiredMixin`.
  - **Business logic:** each app's `service.py` (attendance, leave, payroll, expenses, leads, costing, dsr,
    notifications, dashboards). Several apps still keep logic in views, and those parts need extracting first.

## Recommendation

1. **Keep Django as the backend and add a new versioned API at `/api/web/v1/`.** Do not touch the existing `/api/v1`
   (SDKs depend on it). Build it with DRF, which is already installed.
2. **Migrate module by module (strangler).** The server-rendered pages keep working while React takes over one area
   at a time. Do not freeze the old UI waiting for a big bang.
3. **A thin API layer over services, never a copy.** Each endpoint calls the same `service.py` function and the same
   `accessible_*` / `require_*` helpers as the HTML view. Where a view holds logic, move it into `service.py` in the same
   change, so HTML and API share one code path. This is what keeps the two layers from drifting apart.
4. **Sign-in: same parent domain + session cookie.** Example: `app.example.com` (React) and `api.example.com` (Django),
   `SESSION_COOKIE_DOMAIN=.example.com`, `SameSite=Lax`, CSRF token header. This is the simplest and safest, and keeps
   the middleware that sets `request.company` working unchanged. If they must be on different sites, use short-lived access
   JWT plus refresh (the CardSnap pattern in `apps/appauth/service.py`) and send the active company in a header.
5. **Generate the contract.** Add `drf-spectacular` for OpenAPI and generate the TypeScript client from it
   (`openapi-typescript` + `TanStack Query`). Then this file is the plan and the schema is the truth.
6. **Start with the read-heavy modules** (dashboard, tickets, products, errors). Payroll and attendance come last: they have
   the most rules and the highest cost of a mistake.

Not recommended: GraphQL (a lot of new machinery for no gain here), or rewriting the logic in Node.

## Conventions (every endpoint)

- **Base:** `/api/web/v1/`, JSON in and out, snake_case, ids are the database id (ticket also has `key` like `AUM-014`).
- **Auth:** session cookie (or bearer, see above). `401` signed out; `403` signed in but not allowed; `404` (not 403)
  where the web UI already hides existence (e.g. someone else's payslip, a product you cannot access).
- **Company:** the active company comes from the session, as today. `POST /session/company/` switches it. Every query
  filters by company.
- **Errors:** `{"code": "snake_case", "message": "plain words"}`, same shape as `API.md`. Validation errors add
  `"fields": {"name": ["..."]}`. No stack traces.
- **Lists:** `?page=` and `?per_page=` (10, 20, 50, 100, same as the UI), returns
  `{"results": [...], "count": n, "page": n, "pages": n}`. Counts follow the existing "open" rules in `CLAUDE.md`.
- **Filters and sort:** query params named as the HTML filters are today. `?ordering=-created_at`.
- **Mutations:** `POST` create, `PATCH` update, `DELETE` remove, `POST .../<action>/` for state changes (as the web
  routes do). Each mutation still calls `log_activity`, the Discord notify helpers and `notifications.service.notify`
  exactly as the view does. The API must not skip side effects.
- **Dates:** ISO 8601 with offset. Day boundaries use `Asia/Kolkata` on the server, never the browser clock.
- **Money:** decimals as **strings** (`"1234.50"`), never floats.
- **Rate limits:** `anon` 20/min, `user` 600/min, writes 120/min (DRF throttles).
- **CORS:** only the React origin, with credentials. Never `*` with credentials.
- **Files:** uploads go through `multipart/form-data`. Downloads (CSV, Excel, PDF) stay as plain GET links.
- **Realtime:** `/ws/presence/` and `/ws/inbox/` already exist. Cookie sockets only work on the same parent domain; for
  other origins, accept `?token=` as `/ws/inbox/` does.

## Endpoint map

"From" is the existing web route the endpoint replaces. Everything here is **to build** unless marked *exists*.

### Session and team (`apps/accounts`)
| Endpoint | From |
|---|---|
| `POST /session/login/`, `POST /session/logout/`, `GET /session/` (user, role, active company, companies, feature flags) | `login/`, `logout/` |
| `POST /session/company/` switch active company | `company/switch/` |
| `POST /companies/` create (first-run setup) | `company/setup/` |
| `GET/POST /team/`, `POST /team/invite/`, `GET/PATCH/DELETE /team/<id>/` | `team/...` |
| `GET/PATCH /profile/`, `GET/PATCH /profile/notifications/`, `DELETE /profile/apps/<id>/` | `profile/...` |

### Home and reports (`apps/dashboards`, `apps/reports`)
| Endpoint | From |
|---|---|
| `GET /home/` personal dashboard (`get_personal_dashboard_data`) | `dashboards/` |
| `GET /dashboards/product/<id>/`, `GET /dashboards/summary/` | `dashboards/product/...`, `reports/` |
| `GET /audit/` (owners and admins) | `dashboards/audit/` |
| `GET/POST /todos/`, `POST /todos/<id>/toggle/`, `DELETE /todos/<id>/`, `POST /todos/clear-done/` | `dashboards/todos/...` |
| `GET /reports/`, `GET /reports/<key>/` (+ `?format=csv\|xlsx` download) | `reports/...` |
| `GET /search/?q=` (already scoped by access) | `search/` |

### Products (`apps/products`)
| Endpoint | From |
|---|---|
| `GET/POST /products/`, `GET/PATCH/DELETE /products/<id>/`, `GET /products/key-suggestion/?name=` | `products/...` |
| `POST /products/<id>/lifecycle/`, `.../stage/`, `.../project/` | same names |
| `GET/POST /products/<id>/versions/`, `DELETE .../versions/<v>/` | `versions/...` |
| `GET/POST/DELETE /products/<id>/access/` (who can see this product) | `access/...` |
| `GET/POST /products/<id>/api-keys/`, `POST /api-keys/<id>/rotate/`, `POST /api-keys/<id>/revoke/` (raw key shown **once**) | `api-keys/...` |
| `GET/PATCH /products/<id>/hosting/`, `GET/POST /products/<id>/log/`, `GET/POST /products/<id>/crunch/`, `POST /crunch/<id>/done/` | same names |
| `GET/POST /products/<id>/milestones/`, `POST /milestones/<id>/toggle/`, `DELETE /milestones/<id>/` | `milestones/...` |
| `GET/POST /projects/` (project list and mapping) | `products/projects/...` |

### Tickets (`apps/tickets`; the product-scoped lists are the same endpoint with `?product=`)
| Endpoint | From |
|---|---|
| `GET /tickets/` (filters: `product`, `status`, `priority`, `assignee`, `q`, `view=list\|kanban`), `POST /tickets/` | `tickets/`, `kanban/`, `list/`, `create/` |
| `GET/PATCH/DELETE /tickets/<id>/` | `<id>/`, `edit/`, `delete/` |
| `POST /tickets/<id>/status/`, `/priority/`, `/assign/`, `/deadline/`, `/follow/` | same names |
| `GET/POST /tickets/<id>/comments/` | `comment/` |
| `POST /tickets/bulk-delete/` | `bulk-delete/` |

Rule: every ticket query goes through `accessible_tickets`; every object through `require_ticket_access`. Status changes
call `Ticket.transition_to()` (this also writes the DSR entry).

### Errors, automation, feedback, leads
| Endpoint | From |
|---|---|
| `GET/POST /errors/`, `GET/DELETE /errors/<id>/`, `POST /errors/<id>/status\|ignore\|resolve\|convert-to-ticket/` | `errors/...`, `products/<id>/errors/...` |
| `GET/POST /automation/rules/`, `PATCH/DELETE /automation/rules/<id>/`, `POST .../toggle/` | `automation/...` |
| `GET/POST /feedback/`, `GET/DELETE /feedback/<id>/`, `POST /feedback/<id>/toggle/`, `GET /feedback/cs-hub/` | `feedback/...` |
| Public: `POST /feedback/respond/<id>/` (stays unauthenticated, rate limited) | `feedback/respond/<id>/` |
| `GET/POST /leads/`, `GET/PATCH/DELETE /leads/<id>/`, `POST /leads/<id>/log\|status\|convert\|promote/`, `GET /leads/website/`, `POST /leads/rotate/` | `leads/...` |

### People and time (`attendance`, `leave`, `dsr`, `payroll`, `expenses`)
| Endpoint | From |
|---|---|
| `GET /attendance/me/`, `POST /attendance/punch/`, `GET /attendance/team/`, `GET /attendance/timesheet/<user>/`, `PUT /attendance/weekly-off/` | `attendance/...` |
| `GET/POST /attendance/corrections/`, `POST .../<id>/cancel\|approve\|reject/` | `attendance/corrections/...` |
| `POST /attendance/records/` (add a day), `PATCH /attendance/records/<id>/` | `add/`, `<id>/edit/` |
| `GET/POST /leave/`, `POST /leave/preview/`, `POST /leave/<id>/cancel\|approve\|reject/`, `GET /leave/calendar/`, `GET/POST/PATCH /leave/policies/` | `leave/...` |
| `GET /dsr/?date=`, `POST /dsr/`, `PATCH/DELETE /dsr/<id>/`, `GET /dsr/suggestions/`, `POST /dsr/suggestions/add\|add-all/` | `dsr/...` |
| `GET /payroll/runs/`, `POST /payroll/preview/`, `GET /payroll/runs/<id>/`, `POST .../lock/`, `GET/DELETE /payroll/payslips/<id>/`, `GET/POST /payroll/holidays/`, `GET/PATCH /payroll/profiles/` (admin) | `payroll/...` |
| `GET /payroll/me/`, `GET /payroll/me/<id>/` (member only, **404** for someone else's slip) | `payroll/me/...` |
| `GET/POST /expenses/`, `GET/PATCH/DELETE /expenses/<id>/`, `POST .../salary\|repaid/`, `GET/POST .../comments/`, `DELETE .../comments/<id>/`, `GET /expenses/export/` | `expenses/...` |

### Costing, notifications, presence, settings
| Endpoint | From |
|---|---|
| `GET/POST /costing/`, `GET/PATCH/DELETE /costing/<id>/`, `POST .../duplicate/`, `POST /costing/calc/`, `GET .../quote/` | `costing/...` |
| `GET /notifications/`, `POST /notifications/<id>/read/`, `POST /notifications/read-all/`, `POST /notifications/push/subscribe\|unsubscribe/` | `notifications/...` |
| `POST /presence/beat/` (polling fallback) | `presence/beat/` |
| `GET/PUT /settings/email/` (owners and admins; the key is write-only) | `settings/email/` |
| `GET/POST /servers/`, `DELETE /servers/<id>/` | `servers/...` |
| `GET /app-users/`, `GET /app-users/<id>/`, `POST .../<id>/revoke\|restore\|logout\|delete\|purge/`, `GET /app-users/export/` | `app-users/...` |
| `GET /app-users/cards/` as two views: `?view=users` (one row per person: backup on/off, card count, last backup) and `?view=cards` (filters `user`, `exhibition`, `from`, `to`, `multi=1` for scanned more than once, `q`; `sort` = `-updated` default, `name`, `company`, `owner`, each with `-`; plus the stat tiles `total`, `users_on`, `week`; and the owner and exhibition choices for the filter bar) | `app-users/cards/` |
| `GET /app-users/scan-quality/` (overview: `version`, `from`, `to`, `mode`, `parser`; compare: `view=compare&a=&b=`; returns tiles, per-field rows with fix rate and average confidence, version choices), `GET /app-users/scan-quality/export/` (CSV of the same view) | `app-users/scan-quality/` |
| `GET /app-users/cards/<id>/` (card, owner, owner's other card count), `GET /app-users/cards/export/` (CSV of the same filters) | `app-users/cards/<id>/`, `cards/export.csv` |

Every one of the three card endpoints writes an `AppCardAccessLog` row (who, whose cards, when, filters). The React app must call them like any other: **never cache them client-side across visits**, or the access log undercounts. Cards waiting for erasure (`deletion_requested_at` set) never appear: read through `AppCard.objects.live()`. The card payload carries `scan_count` and `exhibition_name`; the "Merged" badge is `scan_count > 1`.
| `GET /meta/` version, changelog, enums (statuses, priorities, roles) so React does not hardcode them | `api/v1/version\|changelog/` |

Left as they are: `/api/v1/*` (SDK ingestion), `/api/serop/*`, `/oauth/*`, `/api/app-auth/*`, the lead webhook, and the
public CardSnap pages.

## Build order

1. **Foundation:** DRF settings for the web API, session auth + CSRF, CORS, error handler, pagination, throttles,
   `drf-spectacular`, `GET /session/`, `GET /meta/`. One tested example module (tickets read) to fix the pattern.
2. **Core read screens:** home, products, tickets, errors, search, notifications.
3. **Writes for those:** ticket create/edit/status/comment, error actions, product edit, team.
4. **Work modules:** leads, feedback, automation, DSR, leave, expenses, costing.
5. **Money and time last:** attendance, payroll (admin and self-service), app-users, settings.
6. When a module is done in React, the matching HTML routes redirect to it. Delete the old templates only after.

## Tests and safety (required per module)

- A test per endpoint for: signed out (401), wrong role (403), **a user without access to the product cannot read or
  change its tickets/errors/surveys/rules** (the rule in `CLAUDE.md`), another company's ids (404), and the happy path.
- A test that the API and the HTML view produce the same result for the same action (status change, leave split,
  payslip numbers), so a rule change cannot land in only one.
- Mutations must still write the activity log and notifications. Test that the row is written.
- A test fails if a serializer field has no description (the same rule
  `apps/ingestion/docs.py` already enforces).

## Open questions

1. Same parent domain for React and Django (cookie sign-in), or different sites (JWT)? This decides the auth work.
2. Do we keep `htmx` pages alive while React grows, or flip each module and redirect?
3. Is the React app only for the team, or will customers or CardSnap users also use it? That changes which of the
   permission classes we need.
4. Should realtime (inbox, presence, live ticket updates) move to one socket with the same auth as the API?
