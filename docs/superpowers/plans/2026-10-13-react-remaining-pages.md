# React migration: remaining areas (master checklist)

Goal (user, 2026-10-13): the whole frontend is React; Django is only the backend (JSON API, auth, ingestion, WebSockets). Each area is done in the same pipeline as tickets/errors: service layer + `/ui-api/v1/` endpoints + React pages + shell-serving Django views + delete legacy templates/htmx + tests + docs + release + Opus review.

Done: notifications, tickets, errors, products (list, form, detail, API docs).

Order (tick when merged on the branch):
- [x] products (list/create/edit/detail/api docs; keys, versions, milestones, access)
- [ ] product-scoped surveys + rules, global feedback (surveys, CS hub), automation
- [ ] dashboards (home, product dashboard, reports, audit log) and `/search/`
- [ ] DSR
- [ ] accounts (login, company setup/switch, team, profile, Serop OAuth screens)
- [ ] attendance
- [ ] leave
- [ ] payroll
- [ ] cleanup: remove htmx, Alpine, django_htmx, `core/base.html`, legacy CSS, partials, `HTMXRequiredMixin`, message bridge; update CLAUDE.md/AGENTS.md; remaining error/404 pages
- [ ] merge `feat/react-ui-pilot` to main (ask the user first)

Kept on purpose until their last user moves: `tickets:ticket_status`, `tickets:ticket_assign`, `errors:error_resolve`, `errors:error_ignore` (home dashboard hx-posts).
