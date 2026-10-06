# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The virtualenv lives at `venv/`. Prefix commands with `venv/bin/python` or activate it first.

```bash
venv/bin/pip install -r requirements.txt          # install deps
venv/bin/python manage.py migrate                 # apply migrations
venv/bin/python manage.py runserver 8010          # dev server
venv/bin/python manage.py seed_data               # wipe + reseed the "Acme Corp" demo workspace
                                                  #   logins: owner|admin|dev1|dev2|support|viewer / testpass123
venv/bin/python manage.py evaluate_rules [--dry-run]   # run the auto-ticket rule engine (see Automation below)
venv/bin/python manage.py audit_decimals [--model payroll.Payslip] [--fix --backup f.json]
                                                  # find DecimalField cells SQLite can't convert (one bad row 500s every page reading that table)
./bootstrap.sh                                    # migrate + superuser + demo data in one go
```

Tests use Django's runner (not pytest, despite `.pytest_cache` in `.gitignore`):

```bash
venv/bin/python manage.py test apps                                   # whole suite
venv/bin/python manage.py test apps.tickets                           # one app
venv/bin/python manage.py test apps.tickets.tests.test_tickets.TicketProductAccessTest.test_cannot_open_inaccessible_ticket   # one test
```

One test in `apps.accounts.tests.test_tenant_isolation` fails on a clean checkout: `test_signup_creates_user` (the `accounts:signup` route is gone; allauth signup isn't wired up). Not a regression. The full suite takes ~3.5 minutes — background it and poll the log. There is no CI, lint or typecheck; `manage.py check` (expect only `staticfiles.W004`) plus the suite is the whole gate.

Docker: `docker-compose up` builds and serves on `:8011` via `entrypoint.sh` (migrate + runserver), bind-mounting `db.sqlite3`. Also starts a `redis` service (`REDIS_URL`, used by Django Channels for the live inbox and presence feeds). `daphne` is first in `INSTALLED_APPS`, which is what makes `manage.py runserver` an ASGI server that serves WebSockets as well as HTTP; without it every `/ws/...` URL is a 404. With no `REDIS_URL` set the channel layer is in-memory, which is fine for one process.

Deploy and maintenance commands for Server Operator live in `.server-operator/*.serop` (see its README).

There is no frontend build step. Templates render server-side; htmx and Alpine.js load from CDN in `templates/core/base.html`. All CSS is a single `<style>` block in `base.html` driven by CSS custom properties (`--accent`, `--panel`, `--border`, …). `static/` does not exist, so the `staticfiles.W004` check warning is expected.

Root-level `test_api*.py`, `check_db*.py`, `check_serializer.py` are ad-hoc throwaway scripts, not part of the test suite.

## Companion docs — read before changing an area

- **`AGENTS.md`** is the long-form version of this file (per-feature invariants for attendance, leave, payroll, toasts, dropdowns, sidebar, changelog). Read the relevant section before touching those areas.
- **`context.md`** is the project's running memory (what was done and why, "deliberately not changed", numbered open questions). Consult it before changing an area and append to today's `## YYYY-MM-DD` section after a behaviour change.
- **`CHANGELOG.md` is a runtime asset** (parsed by `apps/core/changelog.py` for the "What's new" dialog and `/api/v1/changelog/`): add releases at the top, never edit old entries, keep `!CHANGELOG.md` after `*.md` in `.dockerignore`.

## Architecture

Django 6 + SQLite, server-rendered (class-based `View`s with `get`/`post`, not DRF for the web UI). `apps/` is on `sys.path` (see `core/settings.py`), so apps import as `apps.tickets`, `apps.products`, etc. The Django project package is `core/`.

### Timezone

`TIME_ZONE = "Asia/Kolkata"` (with `USE_TZ = True`) is load-bearing: lateness/penalty and day-boundary logic compare local wall-clock against `WorkShift.start_time`. Use `timezone.localtime()` / `localdate()` / `get_current_timezone()`; never hardcode offsets or `utcnow()`. Tests build punches with `timezone.make_aware(..., timezone.get_current_timezone())`.

### Multi-tenancy and access control

Two independent layers — **both** must be enforced on every view that touches tenant data:

1. **Company isolation.** `Company` + `Membership` (roles: owner, admin, developer, support, viewer). `apps/core/middleware.CurrentCompanyMiddleware` sets `request.company` and `request.company_role` on each request from the active-company id in the session (`settings.ACTIVE_COMPANY_SESSION_KEY`); the company switcher (`accounts:company_switch`) rewrites that key. `apps/core/models.TenantScopedModel` is the base for tenant-owned models (adds a `company` FK); most views filter `Model.objects.filter(company=request.company)` explicitly rather than relying on the manager.

2. **Per-product access.** `apps/products/access.py` is the source of truth: `accessible_products(user, company)`, `user_has_product_access(...)`, `require_product_access(request, product)`, plus `accessible_tickets` / `require_ticket_access` and `accessible_error_groups` / `require_error_group_access`. Owners and admins see every product; other roles need a `ProductAccess` row. **Any company-wide list, detail, or mutation view for a product-owned model (Ticket, ErrorGroup, surveys, milestones, rules) must scope its queryset to `accessible_products` and guard each object with the matching `require_*` helper** — filtering by `company` alone leaks and allows mutation across products. `apps/dashboards/service.py` follows the same rule (`get_user_dashboard_data`, `get_summary_report` scope by role).

Access checks live in the view/mixin layer. `apps/core/mixins.py`: `CompanyMemberRequiredMixin` (redirects to company setup if no company), `CompanyAdminRequiredMixin` (403 unless owner/admin).

### App layout — global vs product-scoped views

The same domain logic exists in two places and both must be kept in sync:

- **Global views:** `apps/tickets/`, `apps/errors/`, `apps/dashboards/`, `apps/feedback/`, `apps/automation/`, `apps/dsr/` — mounted at `/tickets/`, `/errors/`, etc. Operate across all products the user can access.
- **Product-scoped views:** `apps/products/views.py` + `apps/products/urls.py`, mounted at `/products/<pk>/tickets/`, `/products/<pk>/errors/`, etc. Re-implement the list/detail/create flows against `product.tickets` / `product.error_groups`, and always call `require_product_access` first.

### Ingestion API (`/api/v1/`)

`apps/ingestion/` — DRF `APIView`s for external SDKs. Auth is `APIKeyAuthentication` (`Authorization: Bearer <key>`); keys are per-`Product`, stored hashed (`APIKey.key_hash`), validated by `APIKey.validate_key`. `request.auth` is the `APIKey`, `request.user` is `None`.

- `errors/capture/` dedups by `sha256` fingerprint into `ErrorGroup` (+ one `ErrorOccurrence` per hit), bumping `occurrence_count`.
- `feedback/`, `tickets/`, `tickets/<id>/status/` — see `apps/ingestion/serializers.py`, where all the create logic lives (`serializer.create` / `.save`).

### Cross-cutting side effects

- **Discord notifications:** `apps/products/webhook.py`. `notify_ticket_created`, `notify_error_captured`, `notify_ticket_status_changed`, etc. POST an embed to the product's `discord_webhook_url` (best-effort, 5s timeout). Users with a `discord_id` get `@`-mentioned. Call these after the relevant state change.
- **Activity log:** `apps/dashboards/service.log_activity(company, event_type, title, ...)` writes an `ActivityLog` row (with a `metadata` JSON blob, typically `{"product_id": ..., "from": ..., "to": ...}`). Call it after every user-driven state change — the summary reports (`get_summary_report`) are reconstructed from `ActivityLog`, not the domain tables.
- **DSR auto-logging:** `Ticket.transition_to()` calls `apps/dsr/service.auto_log_ticket_dsr` when a ticket moves to `resolved`/`closed`, creating/updating a `DSREntry` timesheet row for each assignee.
- **Automation:** `AutoTicketRule` is **not** evaluated inline. The `evaluate_rules` management command (run on a cron) scans recent `ErrorGroup`s per rule; when `occurrence_count >= threshold_count` within `window_minutes`, it creates an `[Auto]` ticket and records an `AutoTicketLog` (which also dedups re-triggers).

### Presence (`apps/presence/`)

`/ws/presence/` (routed in `core/asgi.py`) is one WebSocket per browser tab. It is session-cookie authenticated and wrapped in `AllowedHostsOriginValidator`, so another site cannot open it with a visitor's cookies; `/ws/inbox/` (Serop) is deliberately not wrapped, since it uses a bearer token. Each tab is a `PresenceSession` row kept alive by a 25s heartbeat; `service.snapshot` lists tabs seen in the last 75s, grouped by user, and the consumer broadcasts that snapshot to the company's group. If the socket fails twice, the browser polls `POST /presence/beat/` (`apps/presence/views.py`), which writes the same `PresenceSession` row, so a proxy that drops the Upgrade header degrades to a 25 second refresh instead of a dead panel. The activity label is derived on the server from the page path (`service.activity_for`) and never contains a title or product name. The browser side is the `presence` Alpine store in `templates/core/_presence.html`.

### Notifications, search, corrections (newer pieces)

- **`apps/notifications/`.** `service.notify(user=..., company=..., kind=..., title=..., url=..., actor=...)` is the only way to create a `Notification`. It skips the actor, pushes the row down the user's open presence socket (group `notify_<user id>`, joined in `PresenceConsumer`), and sends a web push in a background thread when the user has a `PushSubscription` and `WEBPUSH_VAPID_PRIVATE_KEY` is set. `url` must be a site-relative path (`service.safe_path`). New assignees are notified from `Ticket.set_assignees(..., actor=)`, so pass the actor.
- **`apps/core/search.py`.** `/search/` goes through `accessible_tickets`, `accessible_error_groups` and `accessible_products`, so it can never return something the person could not open. People are searched for owners and admins only.
- **Attendance corrections** (`apps/attendance/corrections.py`). Rules live there, not in the views: 60 day limit, one open request per person per day, owners and admins decide, nobody decides their own unless they are the only owner or admin. Approval reuses `service.punch_problem`, the same check as the admin edit form.
- **Errors** (`apps/errors/trends.py`). `ErrorGroup` has `first_version`, `regressed_at` and `regression_count`; the ingestion serializer sets them. A resolved group that is reported again reopens, is flagged, and the owners and admins are notified once.
- **API keys.** Creating, rotating and revoking need owner, admin or developer plus access to the product. Keys can have `expires_at`, which `APIKey.validate_key` enforces. The docs page at `/products/<pk>/api/` is built from the real serializers (`apps/ingestion/docs.py`); a test fails if a serializer field has no description. A bad or missing key answers 403, not 401, and existing tests pin that.

### HR modules: attendance, leave, payroll (`apps/attendance`, `apps/leave`, `apps/payroll`)

Company-scoped (not product-scoped), mounted at `/attendance/`, `/leave/`, `/payroll/`. Business rules live in each app's `service.py` — reuse them, never re-derive in views/templates.

- **Attendance:** one `AttendanceRecord` per company+user+date; `models.punch()` is the only write path (a third punch is a no-op). `WorkShift` (one row per company, `service.shift_for` get-or-creates defaults) holds hours and lateness bands; penalties are *derived*, never stored.
- **Leave:** `service.auto_split` stores `paid_days`/`unpaid_days` on `LeaveRequest`; over-cap requests are accepted with the excess unpaid. Payroll trusts the stored split. Approvers = owners/admins + `Membership.is_leave_approver`; `LeaveApproverRequiredMixin` must decide before `super().dispatch()`.
- **Payroll:** monthly salary → day rate via `service.effective_rate`; cycle is the 27th–26th (`service.cycle_bounds`). Only unpaid leave and lateness deduct. `Payslip` is an immutable snapshot; `generate_run` deletes and recreates payslips unless the run `is_locked`. Admin views are `CompanyAdminRequiredMixin`; `/payroll/me/` is member-only and 404s (not 403) on someone else's slip.
- The personal-first home page is `dashboards.service.get_personal_dashboard_data`; tickets there must go through `accessible_tickets`.

### Templates

Project-level `templates/` (plus `APP_DIRS: True`). `core/base.html` is the app shell; the sidebar is `core/_sidebar.html`, fed by the `product_context` and `workspace_context` processors in `apps/core/context_processors.py` (these attach `product` + per-product counts, `nav_products`, and company-wide open counts). Partials are prefixed `_` and live in `<app>/partials/`. CSS is five files under `templates/core/css/` (`_tokens`, `_app`, `_components`, `_pages`, `_responsive`) included into one inline `<style>`; colors come from `_tokens.css` only. See `design-system.md`. A multi-line template note must use `{% comment %}`, because a `{# #}` spanning lines prints on the page (a test enforces this). The PWA manifest, service worker and offline page are views in `apps/core/pwa.py`, and the favicon files in `brand/favicon/` are served by `apps/core/brand.py`, because there is no static pipeline. For an htmx request (`HX-Request: true` header) a view returns a `partials/` fragment instead of the full page.

### Counts

"Open" means not `resolved`/`closed` for tickets and not `resolved`/`ignored` for errors. The sidebar badge (`workspace_context`), the list headers ("15 tickets · 9 open", computed from the filtered queryset in the global and product-scoped views) and the product cards all use it. Keep them in step if a status is ever added. User-facing how-tos are in `docs/guides/`.

### Ticket names

`Product.key` (2 to 6 capitals, unique per company, suggested from the name by `apps/products/keys.py`) plus `Ticket.number` give `ticket.key`, shown as `AUM-014`. `Ticket.save()` assigns the number from `Product.ticket_counter` in one atomic UPDATE, so numbers never repeat and are not reused after a delete; moving a ticket to another product renumbers it. URLs, the API and foreign keys still use the database id. Show `ticket.key` (not `#{{ ticket.pk }}`) in any new template or message, and `select_related("product")` on lists, because the key reads the product. A ticket with no product falls back to `#<id>`.

### Changelog

`CHANGELOG.md` is what the sidebar "What's new" dialog shows, via `apps/core/changelog.py` and `/api/v1/changelog/`. Write each release as `## [1.2.0] — date · title`, then a `> In short: ...` sentence, then `### New`, `### Better`, `### Fixed`, `### Security` lists. Start every bullet with a bold lead that is a whole sentence (`**Ticket names like AUM-014.** Detail...`), because the dialog shows that lead as the item's title. Plain words, no class or file names. A test fails if `APP_VERSION` is not the newest release tag, if either of the two newest releases has no summary, or if one of their bold leads stops mid-sentence. Cutting a release means bumping `APP_VERSION` in `core/settings.py` in the same change.

- Every mutating view must call `messages.success/.error` (toasts render from `core/base.html`; htmx fragments don't render the shell, so they must carry the payload or dispatch `django-message`). Serop JSON views are exempt.
- Choice controls use `{% dropdown %}` (`apps/core/templatetags/dropdown_tags.py`), not native `<select>`. Icons are `{% icon 'name' %}` from the vendored `apps/core/icons.py`. Sidebar active state is keyed on `request.resolver_match.url_name`, so a new route must be added to `core/_sidebar.html`'s conditions.
- `/dashboard/` is a `RedirectView`; `LOGIN_REDIRECT_URL` is the URL name `dashboards:index`. Don't include the dashboards URLconf twice.

### Auth

Custom `accounts.User` (`AbstractUser` + `discord_id`). django-allauth is installed but login/logout/signup are handled by `apps/accounts/views.py` (email + password). A user with no `Membership` is sent to `accounts:company_setup`, which creates a `Company` and an owner `Membership`.

### Serop integration (`apps/serop/`, `apps/accounts` OAuth views)

This CRM is the cloud backend for **Server Operator** ("Serop"), a separate Electron app in the parent working directory (`../CLAUDE.md`) — not just an SDK-ingesting customer, an actual dependent of this repo. Two things exist purely to serve it:

- **OAuth-ish sign-in** (`apps/accounts/views.py`: `OAuthAuthorizeView`/`OAuthTokenView`/`OAuthMeView`, models `ExternalAuthCode`/`ExternalAccessToken` in `apps/accounts/models.py`) — a loopback-redirect flow (`redirect_uri` must be `127.0.0.1`/`localhost`) since there's no self-serve signup here; Serop's Electron main process catches the redirect. `ExternalAccessToken` is the bearer token every `apps/serop/` endpoint authenticates with.
- **`apps/serop/`** — Serop's teams/shared-servers/inbox API (`/api/serop/...`, DRF `APIView`s, `ExternalTokenAuthentication` sets `request.user` to the real CRM `User`) plus the live inbox WebSocket (`apps/serop/consumers.py`, routed in `core/asgi.py`, mounted at `/ws/inbox/?token=...`). **Serop "teams" are this app's `Company`/`Membership` directly** — adding someone to a Serop team creates a real `Membership` (role `viewer` by default) in that company, which is a deliberate but easy-to-forget cross-product coupling: it grants no ticketing visibility by itself (`accessible_products` only auto-grants owners/admins), but it does mean Serop and the ticketing UI's team-membership lists are the same data. `SeropSharedServer.encrypted_password` is Fernet-encrypted with `settings.SHARED_SERVER_ENCRYPTION_KEY` — never log or return it undecrypted outside `SharedServerCredentialsView`.
- CORS is enabled (`django-cors-headers`) but scoped via `CORS_URLS_REGEX` to `^/(oauth|api/serop)/.*$` only — the rest of the CRM's session-cookie web UI is untouched.
