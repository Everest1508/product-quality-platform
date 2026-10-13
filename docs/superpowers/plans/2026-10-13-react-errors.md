# React errors area: implementation plan

> Executed natively (inline), then one Opus review of the branch. Same pipeline as the tickets plans.

**Goal:** Move the six error pages (`/errors/`, `/errors/create/`, `/errors/<pk>/`, `/products/<pk>/errors/`, `.../errors/create/`, `.../errors/<error_pk>/`) to React and delete their legacy templates, view code and htmx. URLs and URL names stay.

**Spec:** `docs/superpowers/specs/2026-10-12-react-ui-migration-design.md` (order step 2).

## Decisions
- One list endpoint `GET /ui-api/v1/errors/` for global and product pages (`scope=product&product=<pk>`, like tickets). Filters: product, status, severity, q, regressed, sort, page (25).
- Rules move to `apps/errors/service.py` (`set_status`, `convert_to_ticket`, `delete_error`); the legacy `error_resolve` / `error_ignore` views stay (the home dashboard hx-posts to them) but call the service.
- Resolve and ignore are just `status` values on `POST errors/<pk>/status/`; they keep their own activity events (`error_resolved`, `error_ignored`), other moves log `error_status_changed`.
- Create reuses `ErrorCreateForm`; access always via `accessible_error_groups` / `require_error_group_access` / `accessible_products`.
- Delete stays owner/admin only. Removed routes: `error_status`, `error_convert_to_ticket`, `error_delete`, `product_error_convert_to_ticket`.

## Tasks
1. **Service + legacy views.** `service.py`, tests, legacy resolve/ignore call it.
2. **API.** `apps/uiapi/errors.py` list/meta/create/detail/status/convert/delete + `test_errors.py` (isolation, product access, roles, side effects).
3. **Shell serving.** The six views return `render_shell`; delete legacy views, routes, templates (`templates/errors/*` except `_error_status_badge.html`, `templates/products/product_error_*`, `_product_error_list_body.html`), `test_shell_errors.py`; convert legacy HTML tests.
4. **React pages.** `frontend/src/pages/errors/*` (list with tabs/filters/sparklines/flags, detail with trend chart/occurrences/linked tickets/actions, report form), routes, `REACT_PATH_RES`, tests.
5. **Docs and release.** `context.md`, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md` 1.16.0, `APP_VERSION`, parity check in the browser, full suites, Opus review, fixes.
