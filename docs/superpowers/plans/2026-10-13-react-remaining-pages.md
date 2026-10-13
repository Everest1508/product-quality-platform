# React migration: remaining areas (master checklist)

Goal (user, 2026-10-13): the whole frontend is React; Django is only the backend (JSON API, auth, ingestion, WebSockets). Each area is done in the same pipeline as tickets/errors: service layer + `/ui-api/v1/` endpoints + React pages + shell-serving Django views + delete legacy templates/htmx + tests + docs + release + Opus review.

Done: notifications, tickets, errors, products (list, form, detail, API docs).

Order (tick when merged on the branch):
- [x] products (list/create/edit/detail/api docs; keys, versions, milestones, access)
- [x] product-scoped surveys + rules, global feedback (surveys, CS hub, public survey page), automation
- [x] dashboards (home, product dashboard, reports, audit log); `/search/` stays a JSON endpoint used by the palette
- [x] DSR
- [x] accounts (login, company setup, team, profile, Serop OAuth sign-in; `accounts:company_switch` stays for the legacy sidebar until cleanup)
- [ ] attendance
- [ ] leave
- [ ] payroll
- [ ] cleanup: remove htmx, Alpine, django_htmx, `core/base.html`, legacy CSS, partials, `HTMXRequiredMixin`, message bridge; update CLAUDE.md/AGENTS.md; remaining error/404 pages
- [ ] merge `feat/react-ui-pilot` to main (ask the user first)

The old `tickets:ticket_status`, `tickets:ticket_assign`, `errors:error_resolve`, `errors:error_ignore` routes were removed with the home dashboard (nothing used them any more).
