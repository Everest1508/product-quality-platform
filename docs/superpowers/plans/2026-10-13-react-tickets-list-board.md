# React tickets, plan A: list and board (global and product-scoped)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the six ticket list/board pages to React inside the existing shell, add the product sidebar section, and delete the legacy templates, view code and htmx for those pages in the same change. Ticket detail, create/edit and comments stay legacy (plan B).

**Architecture:** One JSON endpoint serves list and board, global and product-scoped, using the existing filter helpers moved to `apps/tickets/filters.py`. Mutations (move status, delete, bulk delete) go through new service functions extracted from the legacy views, so side effects (activity log, notifications, webhook, DSR auto-log) stay in one place. The six URLs keep their names and paths; each Django view now returns `render_shell`. React Router owns them; links to the still-legacy detail/create pages are normal links.

**Tech Stack:** Django 6 + DRF (`CompanyAPIView`), React 19, TypeScript, TanStack Query, React Router, Tailwind 4, befui components, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-12-react-ui-migration-design.md` (revised order, step 1: ticket pages). Builds on `docs/superpowers/plans/2026-10-12-react-app-shell.md` (done).

## Global Constraints

- Backend stays Python/Django. No change to models, `Ticket.transition_to`, DSR auto-logging, `log_activity` events, Discord webhooks, `/api/v1/`, `/api/serop/`, WebSockets.
- **Both access layers on every endpoint.** Company isolation (`request.company`) and per-product access: list/board use `accessible_tickets(user, company)` (or `product.tickets` after `require_product_access`), mutations call `require_ticket_access`. A product the user cannot open is 404, same as the legacy views (`Http404`).
- URLs, URL names and the `?q= &type= &priority= &product= &assigned= &overdue= &status= &sort= &page=` query strings are unchanged (bookmarks keep working). The six pages: `/tickets/`, `/tickets/kanban/`, `/tickets/list/` and `/products/<pk>/tickets/`, `/products/<pk>/tickets/kanban/`, `/products/<pk>/tickets/list/` (`tickets:ticket_board|ticket_kanban|ticket_list`, `products:product_board|product_ticket_kanban|product_tickets`).
- "Open" means not `resolved`/`closed` (`OPEN_EXCLUDED`); list header "15 tickets · 9 open" is computed from the filtered queryset, as today.
- Show `ticket.key` (`AUM-014`), never `#pk`, except tickets with no product (`#12`); `select_related("product")` on lists.
- Delete rights: owner/admin, or the creator (same rule as legacy).
- `TIME_ZONE = "Asia/Kolkata"`: send ISO-8601 with offset; browser formats.
- Legacy detail page keeps working: `TicketStatusView` (htmx status control on the detail page), `TicketPriorityView` etc. stay until plan B; only their shared logic moves into `apps/tickets/service.py`.
- Test commands: `venv/bin/python manage.py test <label>`; `cd frontend && npm test`. Baseline: only `test_signup_creates_user` fails in the full suite.
- When a page moves, its legacy template, view, htmx and tests of the old HTML are deleted in the same task (spec rule). The deletion is its own commit.
- befui components are copied into `frontend/src/components/ui/` from https://befui.vercel.app (the CLI is blocked for the agent; if the user has run `npx github:RandomKid24/befui add ...`, use that output). Replace befui's `./icons` import with `lucide-react`.
- Commit after each task. End commit messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- A user without access to product P must get 404 for `/ui-api/v1/tickets/?product=P`, the product nav, and 404 (not a leak) when moving or deleting a ticket in P; `?product=<id of another company>` must return nothing. Pinned in Tasks 2, 3, 4.
- Bulk delete must skip tickets the user cannot see or may not delete and say how many were deleted (not fail the whole batch). Pinned in Task 3.
- Status move to an invalid value is 400 with a message and changes nothing; the board must roll the card back and toast the error. Pinned in Tasks 3 and 8.
- Pagination: page past the end returns the last page (legacy `Paginator.get_page`); non-numeric `page` returns page 1. Pinned in Task 2.
- Filters: `assigned=<id>` with duplicates through the M2M join must not duplicate tickets; `assigned=unassigned`; `overdue=1` excludes resolved/closed. Pinned in Task 2.
- Product sub-navigation: exactly one active item; switching product keeps the current section. Pinned in Task 5.
- A search term or title containing HTML or very long text renders as text and does not break the table/card layout. Pinned in Tasks 7 and 8.
- Drag: dropping on the same column does nothing; dropping while a request is in flight does not double-send. Pinned in Task 8.
- Legacy detail page's delete and status flows still redirect to the React board URLs and show their messages. Pinned in Task 10.

---

## File structure

| File | Responsibility |
|---|---|
| `apps/tickets/filters.py` (create) | `apply_ticket_filters`, `sort_tickets`, `SORT_MAP`, `OPEN_EXCLUDED` (moved from `views.py`) |
| `apps/tickets/service.py` (create) | `change_status`, `delete_ticket`, `can_delete_ticket` (logic moved out of the views, side effects included) |
| `apps/tickets/views.py` (modify) | import from the two modules; delete list/kanban/bulk views in Task 10 |
| `apps/uiapi/tickets.py` (create) | `TicketListAPIView`, `TicketMetaAPIView`, `TicketStatusAPIView`, `TicketDeleteAPIView`, `TicketBulkDeleteAPIView`, `ticket_json` |
| `apps/uiapi/products.py` (create) | `ProductNavAPIView` |
| `apps/uiapi/urls.py` (modify) | routes |
| `apps/products/views.py` (modify) | import filters from the new module; delete product ticket list/kanban/bulk views in Task 10 |
| `frontend/src/pages/tickets/` | `TicketsPage.tsx`, `FilterBar.tsx`, `TicketTable.tsx`, `Board.tsx`, `useTicketQuery.ts`, `useTicketKeys.ts`, `types.ts` |
| `frontend/src/shell/Sidebar.tsx`, `nav.ts` (modify) | product section, `isReactPath` |

---

### Task 1: Extract filters and ticket services

**Files:**
- Create: `apps/tickets/filters.py`, `apps/tickets/service.py`
- Modify: `apps/tickets/views.py`, `apps/products/views.py` (imports)
- Test: `apps/tickets/tests/test_service.py` (new); existing `apps.tickets` and `apps.products` tests must still pass unchanged

**Interfaces:**
- Produces:
  - `apps.tickets.filters`: `SORT_MAP`, `OPEN_EXCLUDED = ("resolved", "closed")`, `apply_ticket_filters(request, qs) -> (qs, ctx)`, `sort_tickets(request, qs, default) -> qs` (verbatim from `views.py`; `request` only needs `.GET` and `.user`).
  - `apps.tickets.service.can_delete_ticket(user, company_role, ticket) -> bool` (owner/admin or creator).
  - `apps.tickets.service.change_status(ticket, new_status, actor, company) -> str | None`: returns `None` on success after doing exactly what `TicketStatusView` does today (transition, `notify_ticket_status_changed`, `notify_many(watchers…)` with `url=f"/tickets/{ticket.pk}/"`, `log_activity("ticket_status_changed", …metadata from/to)`), or an error message string (`"'<x>' is not a valid status."`) without changing anything.
  - `apps.tickets.service.delete_ticket(ticket, actor, company) -> None`: deletes and writes `log_activity("ticket_deleted", …)` exactly as `TicketDeleteView` does.

- [ ] **Step 1: Write the failing tests**

`apps/tickets/tests/test_service.py`:

```python
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.products.models import Product
from apps.tickets import service
from apps.tickets.models import Ticket

User = get_user_model()


class TicketServiceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("owner", "o@t.local", "pass1234")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.product = Product.objects.create(company=self.company, name="App", slug="app")
        self.ticket = Ticket.objects.create(company=self.company, product=self.product, title="Bug", created_by=self.dev)

    def test_change_status_moves_logs_and_notifies(self):
        with mock.patch("apps.tickets.service.notify_ticket_status_changed") as hook:
            self.assertIsNone(service.change_status(self.ticket, "in_progress", self.owner, self.company))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_progress")
        hook.assert_called_once()
        row = ActivityLog.objects.get(event_type="ticket_status_changed")
        self.assertEqual(row.metadata["to"], "in_progress")

    def test_change_status_rejects_an_unknown_status_and_changes_nothing(self):
        msg = service.change_status(self.ticket, "bogus", self.owner, self.company)
        self.assertIn("not a valid status", msg)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "open")
        self.assertFalse(ActivityLog.objects.filter(event_type="ticket_status_changed").exists())

    def test_delete_rights(self):
        other = User.objects.create_user("x", "x@t.local", "pass1234")
        self.assertTrue(service.can_delete_ticket(self.owner, "owner", self.ticket))
        self.assertTrue(service.can_delete_ticket(self.dev, "developer", self.ticket))   # creator
        self.assertFalse(service.can_delete_ticket(other, "developer", self.ticket))

    def test_delete_ticket_removes_it_and_logs(self):
        service.delete_ticket(self.ticket, self.owner, self.company)
        self.assertFalse(Ticket.objects.filter(pk=self.ticket.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_deleted").exists())
```

(If `ActivityLog` lives elsewhere, `grep -rn "class ActivityLog" apps` and fix the import; assertions stay.)

- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.tickets.tests.test_service`
Expected: FAIL, `No module named apps.tickets.service` / `cannot import`.

- [ ] **Step 3: Implement**

Create `apps/tickets/filters.py` by moving `SORT_MAP`, `TICKET_FILTER_KEYS`, `apply_ticket_filters`, `sort_tickets` and `OPEN_EXCLUDED` out of `views.py` unchanged (needs `from django.utils import timezone`). In `views.py` replace the definitions with `from apps.tickets.filters import OPEN_EXCLUDED, SORT_MAP, TICKET_FILTER_KEYS, apply_ticket_filters, sort_tickets`. In `apps/products/views.py` change both `from apps.tickets.views import apply_ticket_filters, sort_tickets` to `from apps.tickets.filters import apply_ticket_filters, sort_tickets`.

`apps/tickets/service.py`:

```python
from apps.dashboards.service import log_activity
from apps.notifications import service as notifications
from apps.notifications.models import Notification
from apps.products.webhook import notify_ticket_status_changed


def can_delete_ticket(user, company_role, ticket):
    return company_role in ("owner", "admin") or ticket.created_by_id == user.pk


def change_status(ticket, new_status, actor, company):
    """Move a ticket. Returns None on success, or an error message and no change."""
    if not ticket.can_transition_to(new_status):
        return f"'{new_status}' is not a valid status."
    old_value = ticket.status
    old_display = ticket.get_status_display()
    ticket.transition_to(new_status, actor=actor)
    notify_ticket_status_changed(ticket, old_display)
    notifications.notify_many(
        ticket.watchers.all(),
        company=company,
        kind=Notification.Kind.COMMENT,
        title=f"{ticket.key} moved to {ticket.get_status_display()}",
        body=ticket.title,
        url=f"/tickets/{ticket.pk}/",
        actor=actor,
    )
    log_activity(
        company, "ticket_status_changed",
        f"Ticket {ticket.key} status changed",
        description=f"{old_display} → {ticket.get_status_display()}",
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={"product_id": ticket.product_id, "from": old_value, "to": ticket.status},
    )
    return None


def delete_ticket(ticket, actor, company):
    ticket_id, key, product_id, title = ticket.pk, ticket.key, ticket.product_id, ticket.title
    ticket.delete()
    log_activity(
        company, "ticket_deleted",
        f"Ticket {key} deleted",
        description=title,
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket_id,
        metadata={"product_id": product_id},
    )
    return key
```

(`delete_ticket` returns the key so callers can toast it.) Make `TicketStatusView.post` call `change_status` (keep its ajax/htmx/redirect shell and its `messages.success` text) and `TicketDeleteView` / `TicketBulkDeleteView` call `delete_ticket` and `can_delete_ticket`; remove the now-duplicated bodies and the unused imports (`notify_ticket_status_changed`, `Notification`, `service`) only if nothing else in `views.py` still uses them (`TicketCommentView` and others do use `service`/`Notification`; check with grep).

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.tickets apps.products apps.dashboards`
Expected: PASS (refactor changed nothing observable).

- [ ] **Step 5: Commit**

```bash
git add apps/tickets apps/products
git commit -m "refactor(tickets): move filters and status/delete logic into reusable modules"
```

---

### Task 2: Ticket list/board and meta API

**Files:**
- Create: `apps/uiapi/tickets.py`
- Modify: `apps/uiapi/urls.py`
- Test: `apps/uiapi/tests_tickets.py` (new; import it from `apps/uiapi/tests.py` is not needed, Django discovers `tests_*.py` only if named `test*.py`: name it `apps/uiapi/test_tickets.py`)

**Interfaces:**
- Consumes: `CompanyAPIView` (`apps/uiapi/views.py`), `apply_ticket_filters`, `sort_tickets`, `OPEN_EXCLUDED`, `accessible_tickets`, `accessible_products`, `require_product_access`, `product_users`, `can_delete_ticket`.
- Produces:
  - `ticket_json(ticket, user, role) -> dict`:
    ```json
    {"id": 1, "key": "AUM-001", "title": "…", "status": "open", "status_label": "Open",
     "priority": "high", "priority_label": "High", "type": "bug", "type_label": "Bug",
     "product": {"id": 3, "name": "App"} , "assignees": [{"id": 2, "name": "Ann Lee", "initial": "A"}],
     "deadline": "2026-10-20T10:00:00+05:30", "is_overdue": false, "updated_at": "…",
     "linked_error": false, "can_delete": true, "url": "/tickets/1/"}
    ```
    `product` is `null` for a ticket without one. `url` is the legacy detail URL (`/tickets/<pk>/`, or `/products/<product>/tickets/<pk>/` when it has a product, mirroring `_ticket_redirect`).
  - `GET /ui-api/v1/tickets/?view=list|board&product=<pk>&q&type&priority&assigned&overdue&status&sort&page` (name `uiapi:tickets`) →
    - list: `{"view":"list","items":[ticket_json…],"page":{"number":1,"num_pages":3,"count":57,"per_page":25},"open_count":40}`
    - board: `{"view":"board","columns":[{"key":"open","label":"Open","tickets":[…]}…],"total":57,"open_count":40}` (all six statuses in `Ticket.Status` order, unpaginated, like today)
    - `view` defaults to `list`. When `product` is given (path-style product scope), results are limited to that product after `require_product_access` (404 if not accessible); the `product=` query filter is otherwise the legacy "filter by product" and only matches accessible tickets.
    - Defaults: list sorts `-created_at`; board sorts `-priority, -created_at` (same as legacy).
  - `GET /ui-api/v1/tickets/meta/?product=<pk>` (name `uiapi:ticket_meta`) → `{"statuses":[["open","Open"],…],"types":[…],"priorities":[…],"products":[{"id","name"}],"members":[{"id","name"}]}`; `members` are `product_users(product, company)` when `product` is given, else all company members ordered by username; `products` are `accessible_products(user, company)` ordered by name (omitted/empty when scoped to one product).

- [ ] **Step 1: Write the failing tests**

`apps/uiapi/test_tickets.py` (shared setup helper at top):

```python
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


def member(username, company, role="developer"):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class Base(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = member("owner", self.acme, "owner")
        self.dev = member("dev", self.acme)
        self.p_open = Product.objects.create(company=self.acme, name="Open", slug="open")
        self.p_hidden = Product.objects.create(company=self.acme, name="Hidden", slug="hidden")
        self.p_foreign = Product.objects.create(company=self.other, name="Foreign", slug="foreign")
        ProductAccess.objects.create(company=self.acme, user=self.dev, product=self.p_open)

    def make(self, product, title="t", **kw):
        return Ticket.objects.create(company=product.company, product=product, title=title, **kw)

    def login(self, name):
        self.client.login(username=name, password="pass1234")
        s = self.client.session
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = self.acme.pk
        s.save()


class TicketListApiTest(Base):
    url = "/ui-api/v1/tickets/"

    def test_list_shape_and_key(self):
        t = self.make(self.p_open, "Login bug", priority="high")
        t.set_assignees([self.dev])
        self.login("dev")
        data = self.client.get(self.url).json()
        self.assertEqual(data["view"], "list")
        item = data["items"][0]
        self.assertEqual(item["key"], t.key)
        self.assertEqual(item["priority_label"], "High")
        self.assertEqual(item["product"], {"id": self.p_open.pk, "name": "Open"})
        self.assertEqual(item["assignees"][0]["initial"], "D")
        self.assertEqual(item["url"], f"/products/{self.p_open.pk}/tickets/{t.pk}/")
        self.assertEqual(data["page"]["count"], 1)

    def test_a_developer_only_sees_products_they_can_open(self):
        self.make(self.p_open, "mine")
        self.make(self.p_hidden, "secret")
        self.make(self.p_foreign, "foreign")
        self.login("dev")
        self.assertEqual([i["title"] for i in self.client.get(self.url).json()["items"]], ["mine"])
        self.login("owner")
        self.assertEqual(self.client.get(self.url).json()["page"]["count"], 2)  # never the other company's

    def test_product_scope_requires_access(self):
        self.make(self.p_hidden, "secret")
        self.login("dev")
        self.assertEqual(self.client.get(self.url, {"product": self.p_hidden.pk, "scope": "product"}).status_code, 404)

    def test_product_filter_cannot_reach_another_companys_product(self):
        self.make(self.p_foreign, "foreign")
        self.login("owner")
        self.assertEqual(self.client.get(self.url, {"product": self.p_foreign.pk}).json()["page"]["count"], 0)

    def test_filters_and_open_count(self):
        self.make(self.p_open, "alpha bug", ticket_type="bug", priority="high", status="open")
        self.make(self.p_open, "beta feature", ticket_type="feature", priority="low", status="resolved")
        self.login("owner")
        r = self.client.get(self.url, {"q": "alpha"}).json()
        self.assertEqual([i["title"] for i in r["items"]], ["alpha bug"])
        r = self.client.get(self.url, {"type": "feature"}).json()
        self.assertEqual([i["title"] for i in r["items"]], ["beta feature"])
        r = self.client.get(self.url).json()
        self.assertEqual((r["page"]["count"], r["open_count"]), (2, 1))

    def test_assignee_filters_do_not_duplicate(self):
        t = self.make(self.p_open, "two people")
        t.set_assignees([self.dev, self.owner])
        self.make(self.p_open, "nobody")
        self.login("owner")
        self.assertEqual(self.client.get(self.url, {"assigned": self.dev.pk}).json()["page"]["count"], 1)
        self.assertEqual([i["title"] for i in self.client.get(self.url, {"assigned": "unassigned"}).json()["items"]], ["nobody"])
        self.assertEqual(self.client.get(self.url, {"assigned": "me"}).json()["page"]["count"], 1)

    def test_overdue_excludes_resolved(self):
        past = timezone.now() - timedelta(days=1)
        self.make(self.p_open, "late", deadline=past)
        self.make(self.p_open, "late but done", deadline=past, status="resolved")
        self.login("owner")
        self.assertEqual([i["title"] for i in self.client.get(self.url, {"overdue": "1"}).json()["items"]], ["late"])

    def test_pagination_clamps_and_survives_garbage(self):
        for i in range(30):
            self.make(self.p_open, f"t{i}")
        self.login("owner")
        r = self.client.get(self.url, {"page": 99}).json()
        self.assertEqual((r["page"]["number"], r["page"]["num_pages"], len(r["items"])), (2, 2, 5))
        self.assertEqual(self.client.get(self.url, {"page": "abc"}).json()["page"]["number"], 1)

    def test_board_has_every_status_column(self):
        self.make(self.p_open, "a", status="open")
        self.make(self.p_open, "b", status="testing")
        self.login("owner")
        data = self.client.get(self.url, {"view": "board"}).json()
        self.assertEqual([c["key"] for c in data["columns"]], ["open", "assigned", "in_progress", "testing", "resolved", "closed"])
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["columns"][3]["tickets"]), 1)

    def test_hostile_title_is_returned_as_data(self):
        self.make(self.p_open, "<script>alert(1)</script>")
        self.login("owner")
        self.assertEqual(self.client.get(self.url).json()["items"][0]["title"], "<script>alert(1)</script>")

    def test_anonymous_and_no_company_are_403(self):
        self.assertEqual(Client().get(self.url).status_code, 403)


class TicketMetaApiTest(Base):
    def test_meta_lists_accessible_products_and_members(self):
        self.login("dev")
        data = self.client.get("/ui-api/v1/tickets/meta/").json()
        self.assertEqual([p["name"] for p in data["products"]], ["Open"])
        self.assertIn("owner", [m["name"] for m in data["members"]])
        self.assertEqual(data["statuses"][0], ["open", "Open"])

    def test_meta_scoped_to_a_product_lists_that_products_users(self):
        self.login("owner")
        data = self.client.get("/ui-api/v1/tickets/meta/", {"product": self.p_open.pk}).json()
        self.assertEqual(data["products"], [])
        self.assertIn("dev", [m["name"] for m in data["members"]])

    def test_meta_for_an_inaccessible_product_is_404(self):
        self.login("dev")
        self.assertEqual(self.client.get("/ui-api/v1/tickets/meta/", {"product": self.p_hidden.pk}).status_code, 404)
```

Design note for the tests above: the legacy `?product=` query parameter is the *filter dropdown*, while the product-scoped pages (`/products/<pk>/tickets/…`) are a *scope*. The API distinguishes them with `scope=product`: `?product=<pk>&scope=product` means "this product's page" (404 if no access); `?product=<pk>` alone is the filter. The React product pages always send `scope=product`.

- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.uiapi.test_tickets`
Expected: FAIL (404 for `/ui-api/v1/tickets/`).

- [ ] **Step 3: Implement**

`apps/uiapi/tickets.py`:

```python
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from apps.products.access import accessible_products, accessible_tickets, product_users, require_product_access
from apps.products.models import Product
from apps.tickets.filters import OPEN_EXCLUDED, apply_ticket_filters, sort_tickets
from apps.tickets.models import Ticket
from apps.tickets.service import can_delete_ticket
from apps.uiapi.views import CompanyAPIView

User = get_user_model()
PER_PAGE = 25


def _name(user):
    return user.get_full_name() or user.username


def ticket_url(ticket):
    if ticket.product_id:
        return f"/products/{ticket.product_id}/tickets/{ticket.pk}/"
    return f"/tickets/{ticket.pk}/"


def ticket_json(ticket, user, role):
    return {
        "id": ticket.pk,
        "key": ticket.key,
        "title": ticket.title,
        "status": ticket.status,
        "status_label": ticket.get_status_display(),
        "priority": ticket.priority,
        "priority_label": ticket.get_priority_display(),
        "type": ticket.ticket_type,
        "type_label": ticket.get_ticket_type_display(),
        "product": {"id": ticket.product_id, "name": ticket.product.name} if ticket.product_id else None,
        "assignees": [{"id": a.pk, "name": _name(a), "initial": (a.username[:1] or "?").upper()} for a in ticket.assignees.all()],
        "deadline": ticket.deadline.isoformat() if ticket.deadline else None,
        "is_overdue": ticket.is_overdue,
        "updated_at": ticket.updated_at.isoformat(),
        "linked_error": ticket.linked_error_group_id is not None,
        "can_delete": can_delete_ticket(user, role, ticket),
        "url": ticket_url(ticket),
    }


def scoped_product(request):
    """The product a product page is scoped to, or None. 404 if the user cannot open it."""
    if request.query_params.get("scope") != "product":
        return None
    try:
        pk = int(request.query_params.get("product", ""))
    except ValueError:
        raise Http404
    product = get_object_or_404(Product, pk=pk, company=request.company)
    require_product_access(request._request, product)
    return product


class TicketListAPIView(CompanyAPIView):
    def get(self, request):
        product = scoped_product(request)
        if product:
            qs = product.tickets.all()
        else:
            qs = accessible_tickets(request.user, request.company)
        qs = qs.select_related("product", "created_by").prefetch_related("assignees")
        qs, _ctx = apply_ticket_filters(request, qs)
        user, role = request.user, request.company_role

        if request.query_params.get("view") == "board":
            qs = sort_tickets(request, qs, default=("-priority", "-created_at"))
            columns = [
                {"key": v, "label": label, "tickets": [ticket_json(t, user, role) for t in qs.filter(status=v)]}
                for v, label in Ticket.Status.choices
            ]
            total = sum(len(c["tickets"]) for c in columns)
            open_count = sum(len(c["tickets"]) for c in columns if c["key"] not in OPEN_EXCLUDED)
            return Response({"view": "board", "columns": columns, "total": total, "open_count": open_count})

        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        qs = sort_tickets(request, qs, default=("-created_at",))
        page = Paginator(qs, PER_PAGE).get_page(request.query_params.get("page", 1))
        return Response({
            "view": "list",
            "items": [ticket_json(t, user, role) for t in page],
            "page": {"number": page.number, "num_pages": page.paginator.num_pages, "count": page.paginator.count, "per_page": PER_PAGE},
            "open_count": qs.exclude(status__in=OPEN_EXCLUDED).count(),
        })


class TicketMetaAPIView(CompanyAPIView):
    def get(self, request):
        product = scoped_product(request) if request.query_params.get("scope") == "product" else None
        if request.query_params.get("product") and product is None and request.query_params.get("scope") != "product":
            # A bare ?product= on meta behaves like the page scope: it must be accessible.
            product = get_object_or_404(Product, pk=request.query_params["product"], company=request.company)
            require_product_access(request._request, product)
        if product:
            members = product_users(product, request.company)
            products = []
        else:
            members = User.objects.filter(memberships__company=request.company).order_by("username")
            products = [{"id": p.pk, "name": p.name} for p in accessible_products(request.user, request.company).order_by("name")]
        return Response({
            "statuses": [list(c) for c in Ticket.Status.choices],
            "types": [list(c) for c in Ticket.TicketType.choices],
            "priorities": [list(c) for c in Ticket.Priority.choices],
            "products": products,
            "members": [{"id": u.pk, "name": _name(u)} for u in members],
        })
```

(Simplify the meta view when writing it: the React client always sends `scope=product` for product pages, so `TicketMetaAPIView` can just call `scoped_product(request)`; the bare-`?product=` branch above exists only because the tests call meta with `?product=` alone. Pick one: change the meta tests to send `scope=product` and delete the extra branch. The assertions stay.)

`apps/uiapi/urls.py`:

```python
    path("tickets/", tickets.TicketListAPIView.as_view(), name="tickets"),
    path("tickets/meta/", tickets.TicketMetaAPIView.as_view(), name="ticket_meta"),
```

(with `from apps.uiapi import tickets, views`).

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.uiapi`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/uiapi
git commit -m "feat(uiapi): tickets list/board and meta endpoints"
```

---

### Task 3: Ticket mutation endpoints

**Files:**
- Modify: `apps/uiapi/tickets.py`, `apps/uiapi/urls.py`
- Test: `apps/uiapi/test_tickets.py` (append)

**Interfaces:**
- Consumes: `change_status`, `delete_ticket`, `can_delete_ticket`, `require_ticket_access`, `user_has_product_access`.
- Produces:
  - `POST /ui-api/v1/tickets/<pk>/status/` body `{"status": "testing"}` (name `uiapi:ticket_status`) → `200 {"ok": true, "status": "testing"}`; invalid status → `400 {"detail": "'x' is not a valid status."}`; no access → `404`.
  - `DELETE /ui-api/v1/tickets/<pk>/` (name `uiapi:ticket_delete`) → `200 {"deleted": "AUM-001"}`; not allowed (not owner/admin and not creator) → `403`; no access → `404`.
  - `POST /ui-api/v1/tickets/bulk-delete/` body `{"ids": [1,2,3]}` (name `uiapi:ticket_bulk_delete`) → `200 {"deleted": N, "skipped": M}`; empty/invalid ids → `400 {"detail": "No tickets selected."}`. Skips (counts, no error) tickets that are missing, in another company, in an inaccessible product, or not deletable by this user.

- [ ] **Step 1: Write the failing tests**

```python
from unittest import mock

from apps.dashboards.models import ActivityLog


class TicketMutationApiTest(Base):
    def post_json(self, url, body):
        return self.client.post(url, body, content_type="application/json")

    def test_status_move_works_and_runs_the_side_effects(self):
        t = self.make(self.p_open)
        watcher = member("watcher", self.acme)
        ProductAccess.objects.create(company=self.acme, user=watcher, product=self.p_open)
        t.watchers.add(watcher)
        self.login("owner")
        with mock.patch("apps.tickets.service.notify_ticket_status_changed") as hook:
            r = self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "testing"})
        self.assertEqual(r.json(), {"ok": True, "status": "testing"})
        t.refresh_from_db()
        self.assertEqual(t.status, "testing")
        hook.assert_called_once()
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_status_changed").exists())
        from apps.notifications.models import Notification
        self.assertTrue(Notification.objects.filter(user=watcher, title__contains="moved to Testing").exists())

    def test_resolving_auto_logs_to_the_dsr(self):
        t = self.make(self.p_open)
        t.set_assignees([self.owner])
        self.login("owner")
        with mock.patch("apps.dsr.service.auto_log_ticket_dsr") as dsr:
            self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "resolved"})
        dsr.assert_called_once()

    def test_invalid_status_is_400_and_changes_nothing(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "bogus"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("not a valid status", r.json()["detail"])
        t.refresh_from_db()
        self.assertEqual(t.status, "open")

    def test_status_on_an_inaccessible_ticket_is_404(self):
        t = self.make(self.p_hidden)
        self.login("dev")
        self.assertEqual(self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "testing"}).status_code, 404)
        t.refresh_from_db()
        self.assertEqual(t.status, "open")

    def test_status_on_another_companys_ticket_is_404(self):
        t = self.make(self.p_foreign)
        self.login("owner")
        self.assertEqual(self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "testing"}).status_code, 404)

    def test_csrf_is_enforced_on_writes(self):
        t = self.make(self.p_open)
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="owner", password="pass1234")
        self.assertEqual(strict.post(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "testing"}, content_type="application/json").status_code, 403)
        self.assertEqual(strict.delete(f"/ui-api/v1/tickets/{t.pk}/").status_code, 403)

    def test_delete_by_creator_and_admin_but_not_by_a_stranger(self):
        mine = self.make(self.p_open, created_by=self.dev)
        theirs = self.make(self.p_open, created_by=self.owner)
        self.login("dev")
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{theirs.pk}/").status_code, 403)
        self.assertTrue(Ticket.objects.filter(pk=theirs.pk).exists())
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{mine.pk}/").json(), {"deleted": mine.key})
        self.assertFalse(Ticket.objects.filter(pk=mine.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_deleted").exists())
        self.login("owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{theirs.pk}/").status_code, 200)

    def test_bulk_delete_skips_what_it_must_and_counts(self):
        ok = self.make(self.p_open, created_by=self.dev)
        not_mine = self.make(self.p_open, created_by=self.owner)
        hidden = self.make(self.p_hidden, created_by=self.dev)
        foreign = self.make(self.p_foreign)
        self.login("dev")
        r = self.post_json("/ui-api/v1/tickets/bulk-delete/", {"ids": [ok.pk, not_mine.pk, hidden.pk, foreign.pk, 99999, "x"]})
        self.assertEqual(r.json(), {"deleted": 1, "skipped": 5})
        self.assertEqual(Ticket.objects.filter(pk__in=[not_mine.pk, hidden.pk, foreign.pk]).count(), 3)

    def test_bulk_delete_needs_ids(self):
        self.login("owner")
        self.assertEqual(self.post_json("/ui-api/v1/tickets/bulk-delete/", {"ids": []}).status_code, 400)
        self.assertEqual(self.post_json("/ui-api/v1/tickets/bulk-delete/", {}).status_code, 400)
```

- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.uiapi.test_tickets.TicketMutationApiTest`
Expected: FAIL, 404s.

- [ ] **Step 3: Implement**

In `apps/uiapi/tickets.py`:

```python
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.products.access import require_ticket_access, user_has_product_access
from apps.tickets import service as ticket_service


def _ticket(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related("product"), pk=pk, company=request.company)
    require_ticket_access(request._request, ticket)
    return ticket


class TicketStatusAPIView(CompanyAPIView):
    def post(self, request, pk):
        ticket = _ticket(request, pk)
        error = ticket_service.change_status(ticket, request.data.get("status"), request.user, request.company)
        if error:
            raise ValidationError({"detail": error})
        return Response({"ok": True, "status": ticket.status})


class TicketDeleteAPIView(CompanyAPIView):
    def delete(self, request, pk):
        ticket = _ticket(request, pk)
        if not ticket_service.can_delete_ticket(request.user, request.company_role, ticket):
            raise PermissionDenied("You can only delete tickets you created.")
        return Response({"deleted": ticket_service.delete_ticket(ticket, request.user, request.company)})


class TicketBulkDeleteAPIView(CompanyAPIView):
    def post(self, request):
        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            raise ValidationError({"detail": "No tickets selected."})
        deleted = 0
        for raw in ids:
            try:
                ticket = Ticket.objects.select_related("product").get(pk=int(raw), company=request.company)
            except (Ticket.DoesNotExist, ValueError, TypeError):
                continue
            if ticket.product_id and not user_has_product_access(request.user, request.company, ticket.product):
                continue
            if not ticket_service.can_delete_ticket(request.user, request.company_role, ticket):
                continue
            ticket_service.delete_ticket(ticket, request.user, request.company)
            deleted += 1
        return Response({"deleted": deleted, "skipped": len(ids) - deleted})
```

(`ValidationError({"detail": msg})` renders `{"detail": ["msg"]}` in DRF; use `rest_framework.exceptions.APIException` subclass with `status_code = 400` and `default_detail`, or return `Response({"detail": error}, status=400)` directly. Prefer the direct `Response(..., status=400)` for both 400 cases so the tests' `r.json()["detail"]` is a string.)

Routes: `tickets/<int:pk>/status/`, `tickets/<int:pk>/` (DELETE), `tickets/bulk-delete/` (declare `bulk-delete/` before the `<int:pk>/` route is unnecessary because `int` does not match, but keep `meta/` and `bulk-delete/` above for clarity).

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.uiapi apps.tickets`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/uiapi
git commit -m "feat(uiapi): ticket status, delete and bulk-delete endpoints"
```

---

### Task 4: Product navigation endpoint

**Files:**
- Create: `apps/uiapi/products.py`
- Modify: `apps/uiapi/urls.py`
- Test: `apps/uiapi/test_products.py`

**Interfaces:**
- Consumes: `_attach_product_counts` (`apps/core/context_processors.py`), `accessible_products`, `require_product_access`.
- Produces: `GET /ui-api/v1/products/<pk>/nav/` (name `uiapi:product_nav`) → `200`:
  ```json
  {"id": 3, "name": "App",
   "counts": {"errors": 2, "tickets": 5, "surveys": 1, "rules": 0},
   "urls": {"overview": "/products/3/", "errors": "/products/3/errors/", "tickets": "/products/3/tickets/", "surveys": "/products/3/surveys/", "rules": "/products/3/rules/"},
   "products": [{"id": 3, "name": "App", "url": "/products/3/tickets/"}], "all_url": "/products/"}
  ```
  `products` = `accessible_products(user, company)` ordered by name; each `url` is that product's board (`products:product_board`). `404` if the product is missing, in another company, or not accessible.

- [ ] **Step 1: Write the failing tests**

```python
from apps.uiapi.test_tickets import Base
from apps.tickets.models import Ticket


class ProductNavApiTest(Base):
    def test_counts_urls_and_switcher(self):
        self.make(self.p_open)
        self.make(self.p_open, status="resolved")
        self.login("dev")
        data = self.client.get(f"/ui-api/v1/products/{self.p_open.pk}/nav/").json()
        self.assertEqual(data["name"], "Open")
        self.assertEqual(data["counts"]["tickets"], 1)       # resolved is not open
        self.assertEqual(data["urls"]["tickets"], f"/products/{self.p_open.pk}/tickets/")
        self.assertEqual([p["name"] for p in data["products"]], ["Open"])  # dev cannot open "Hidden"

    def test_inaccessible_or_foreign_products_are_404(self):
        self.login("dev")
        self.assertEqual(self.client.get(f"/ui-api/v1/products/{self.p_hidden.pk}/nav/").status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(f"/ui-api/v1/products/{self.p_foreign.pk}/nav/").status_code, 404)
```

- [ ] **Step 2: Run to verify failure**, then **Step 3: Implement**

```python
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.response import Response

from apps.core.context_processors import _attach_product_counts
from apps.products.access import accessible_products, require_product_access
from apps.products.models import Product
from apps.uiapi.views import CompanyAPIView


class ProductNavAPIView(CompanyAPIView):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request._request, product)
        _attach_product_counts(product)
        names = {
            "overview": "products:product_detail", "errors": "products:product_errors",
            "tickets": "products:product_board", "surveys": "products:product_surveys",
            "rules": "products:product_rules",
        }
        return Response({
            "id": product.pk,
            "name": product.name,
            "counts": {"errors": product.error_count, "tickets": product.ticket_count,
                       "surveys": product.survey_count, "rules": product.rule_count},
            "urls": {k: reverse(v, kwargs={"pk": product.pk}) for k, v in names.items()},
            "products": [
                {"id": p.pk, "name": p.name, "url": reverse("products:product_board", kwargs={"pk": p.pk})}
                for p in accessible_products(request.user, request.company).order_by("name")
            ],
            "all_url": reverse("products:product_list"),
        })
```

Route: `path("products/<int:pk>/nav/", products.ProductNavAPIView.as_view(), name="product_nav")`.

- [ ] **Step 4: Run to verify pass**: `venv/bin/python manage.py test apps.uiapi`. **Step 5: Commit**: `git commit -m "feat(uiapi): product navigation endpoint"`.

---

### Task 5: Frontend plumbing: types, route patterns, product sidebar

**Files:**
- Create: `frontend/src/pages/tickets/types.ts`, `frontend/src/lib/useProductNav.ts`, `frontend/src/lib/useProductNav.test.tsx`
- Modify: `frontend/src/shell/nav.ts`, `frontend/src/shell/nav.test.ts`, `frontend/src/shell/Sidebar.tsx`, `frontend/src/shell/Topbar.tsx`, `frontend/src/routes.tsx`, `frontend/src/test-fixtures.ts`

**Interfaces:**
- Produces:
  - `types.ts`: `TicketItem` (mirrors `ticket_json`), `ListResponse`, `BoardResponse`, `TicketMeta`, `TicketFilters = { q, type, priority, product, assigned, overdue, status, sort, page }` (all optional strings).
  - `isReactPath(path: string): boolean` in `nav.ts` replacing the `REACT_PATHS` set lookup: true for exact `/notifications/` and for these regexes: `^/tickets/(kanban/|list/)?$` and `^/products/\d+/tickets/(kanban/|list/)?$`.
  - `productIdFromPath(pathname): number | null` (`/products/<id>/...`).
  - `useProductNav(pathname)`: when the path is under `/products/<id>/`, fetches `GET products/<id>/nav/` (query key `['product-nav', id]`, 60 s stale) and returns `ProductNav | undefined`.
  - `productSection(nav: ProductNav): NavSection` with items Overview, Errors, Tickets, Feedback, Automation (`key`s `p_overview|p_errors|p_tickets|p_surveys|p_rules`, badges from `nav.counts`, zero hidden); `react: true` only for Tickets.
  - Sidebar renders the product section (with a product switcher dropdown listing `nav.products`, "View all products") between the main section and "Operations" when `useProductNav` returns data. Topbar title shows the product name instead of the company when scoped.
  - `activeKey` is unchanged (longest prefix); the product items' hrefs are longer than `/products/` so exactly one item is active; Overview `/products/<id>/` is a prefix of its siblings, so a deeper item wins.

- [ ] **Step 1: Write the failing tests**

`nav.test.ts` additions:

```ts
import { isReactPath, productIdFromPath, productSection } from './nav';

it('knows which paths React owns', () => {
  for (const p of ['/notifications/', '/tickets/', '/tickets/kanban/', '/tickets/list/', '/products/3/tickets/', '/products/3/tickets/kanban/', '/products/12/tickets/list/'])
    expect(isReactPath(p), p).toBe(true);
  for (const p of ['/tickets/5/', '/tickets/create/', '/products/3/', '/products/3/errors/', '/products/3/tickets/5/', '/leave/'])
    expect(isReactPath(p), p).toBe(false);
});

it('reads the product id from the path', () => {
  expect(productIdFromPath('/products/7/tickets/list/')).toBe(7);
  expect(productIdFromPath('/products/')).toBeNull();
  expect(productIdFromPath('/tickets/')).toBeNull();
});

it('product section: one active item, badges, Tickets is the only React link', () => {
  const nav = { id: 3, name: 'App', counts: { errors: 2, tickets: 5, surveys: 0, rules: 1 },
    urls: { overview: '/products/3/', errors: '/products/3/errors/', tickets: '/products/3/tickets/', surveys: '/products/3/surveys/', rules: '/products/3/rules/' },
    products: [], all_url: '/products/' };
  const section = productSection(nav);
  const sections = [...navSections(sampleBootstrap()), section];
  expect(section.items.find((i) => i.key === 'p_tickets')?.badge).toBe(5);
  expect(section.items.find((i) => i.key === 'p_surveys')?.badge).toBeUndefined();
  expect(section.items.filter((i) => i.react).map((i) => i.key)).toEqual(['p_tickets']);
  expect(activeKey('/products/3/tickets/kanban/', sections)).toBe('p_tickets');
  expect(activeKey('/products/3/', sections)).toBe('p_overview');
  expect(activeKey('/products/3/errors/9/', sections)).toBe('p_errors');
});
```

`useProductNav.test.tsx`: mock `api.get`; asserts it fetches `products/3/nav/` for `/products/3/tickets/`, does nothing for `/tickets/`, and returns `undefined` while loading.

Sidebar test (extend `AppShell.test.tsx`): at `/products/3/tickets/` with a mocked `useProductNav`, the sidebar shows the product name, the product items, exactly one `aria-current="page"` link, and the switcher lists `nav.products`.

- [ ] **Step 2: Run to verify failure**: `cd frontend && npm test`.

- [ ] **Step 3: Implement**

`nav.ts`:

```ts
const REACT_PATH_RES = [/^\/notifications\/$/, /^\/tickets\/(kanban\/|list\/)?$/, /^\/products\/\d+\/tickets\/(kanban\/|list\/)?$/];
export const isReactPath = (p: string) => REACT_PATH_RES.some((re) => re.test(p));
export const productIdFromPath = (p: string) => {
  const m = /^\/products\/(\d+)\//.exec(p);
  return m ? Number(m[1]) : null;
};
```

Use `isReactPath(b.urls[key])` in `item()`; delete `REACT_PATHS`. `ProductNav` type in `useProductNav.ts`; `productSection` builds the five items with icons `LayoutDashboard`, `TriangleAlert`, `Ticket`, `FileText`, `Sparkles`.

`Sidebar.tsx`: after the first section render, if `productNav`, render a `ProductSwitcher` (befui `DropdownMenu`: trigger shows product name; items are `<a href={p.url}>` for `nav.products`, current item with a check, final item "View all products" `<a href={nav.all_url}>`) followed by `productSection(productNav)` rows. `Topbar.tsx` shows `productNav?.name ?? b.company.name`.

`routes.tsx` adds six routes, all `element: <TicketsPage />` (Task 6 to 9 create it; until then a stub component `export const TicketsPage = () => <div>Tickets</div>` in `pages/tickets/TicketsPage.tsx`, replaced in Task 7). Route paths: `/tickets/`, `/tickets/kanban/`, `/tickets/list/`, `/products/:pk/tickets/`, `/products/:pk/tickets/kanban/`, `/products/:pk/tickets/list/`.

- [ ] **Step 4: Run to verify pass**: `cd frontend && npm test && npm run build`. **Step 5: Commit**: `git commit -m "feat(frontend): route patterns, product sub-navigation in the sidebar"`.

---

### Task 6: Ticket query hooks, filter bar, befui parts

**Files:**
- Create: `frontend/src/pages/tickets/useTicketQuery.ts`, `useTicketQuery.test.tsx`, `FilterBar.tsx`, `FilterBar.test.tsx`, `frontend/src/components/ui/{select,checkbox,pagination}.tsx` (copied befui parts; if a name is missing on the site use the closest: Select, Checkbox, Pagination; `Input` and `Badge` already exist or are copied the same way)
- Modify: `frontend/package.json` (Radix packages the copied parts list)

**Interfaces:**
- Consumes: `api.get`, `TicketFilters`, `TicketMeta`.
- Produces:
  - `filtersFromParams(params: URLSearchParams): TicketFilters` and `paramsFromFilters(f: TicketFilters): URLSearchParams` (drops empty values and `page=1`; keeps `view`-independent keys only: `q type priority product assigned overdue status sort page`).
  - `useTicketScope(): { productId: number | null; view: 'list' | 'board' }` from the route (`useParams().pk`, pathname ends with `/kanban/` or is the bare `/tickets/` or `/products/<pk>/tickets/` => board; `/list/` => list).
  - `useTickets(view, productId, filters)`: `useQuery` on `['tickets', view, productId, filters]` calling `tickets/?view=…&scope=product&product=<id>&…` (scope only when `productId`), `placeholderData: keepPreviousData`.
  - `useTicketMeta(productId)`: `['ticket-meta', productId]`, `staleTime: 5 min`.
  - `FilterBar({ filters, onChange, meta, showStatus, showProduct })`: search input (debounced 400 ms, like the legacy `delay:400ms`), selects for status (list only), type, priority, product (only when not product-scoped), assignee (`Assigned to me`, `Unassigned`, then members), "Overdue only" checkbox, sort select (Newest first, Oldest first, Recently updated, Priority high first, Priority low first, Title A-Z), and a Clear button. Every change calls `onChange(next)` with `page` reset to undefined.

- [ ] **Step 1: Write the failing tests**

```ts
// useTicketQuery.test.tsx
it('round-trips filters through the URL and drops empty values', () => {
  const p = paramsFromFilters({ q: 'login', type: '', priority: 'high', overdue: '1', page: '1' });
  expect(p.toString()).toBe('q=login&priority=high&overdue=1');
  expect(filtersFromParams(new URLSearchParams('q=a&status=open&page=3&junk=1'))).toEqual({ q: 'a', status: 'open', page: '3' });
});

it('product pages send scope=product, global pages do not', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ view: 'list', items: [], page: { number: 1, num_pages: 1, count: 0, per_page: 25 }, open_count: 0 });
  // render useTickets('list', 3, {q:'x'}) then useTickets('board', null, {})
  expect(get).toHaveBeenNthCalledWith(1, 'tickets/?view=list&scope=product&product=3&q=x');
  expect(get).toHaveBeenNthCalledWith(2, 'tickets/?view=board');
});
```

`FilterBar.test.tsx`: typing in search calls `onChange` once after 400 ms (fake timers) with `q`; picking a priority calls `onChange` with `priority` and no `page`; the product select is absent when `showProduct=false`, the status select absent when `showStatus=false`; "Clear" calls `onChange({})`; `Overdue only` toggles `overdue: '1'`/undefined.

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** (copy befui `select`, `checkbox`, `pagination`, `input` per the Global Constraints, install Radix deps they list, then write the files; the legacy filter semantics are in `templates/tickets/partials/_ticket_filter_bar.html` and the sort labels above); **Step 4: Run to verify pass** (`npm test && npm run build`); **Step 5: Commit** `feat(frontend): ticket query hooks and filter bar`.

---

### Task 7: List view

**Files:**
- Create: `frontend/src/pages/tickets/TicketTable.tsx`, `TicketTable.test.tsx`, `TicketsPage.tsx` (replace the stub), `TicketsPage.test.tsx`, `frontend/src/components/ui/alert-dialog.tsx` (copied)
- Modify: `frontend/src/lib/toast.ts` only if a new tag is needed (it is not)

**Interfaces:**
- Consumes: Task 5 and 6 hooks, `api`, `toast`, `go`.
- Produces:
  - `TicketsPage()`: reads scope/view from the route, filters from `useSearchParams`, renders header (`Tickets` / product name + "· N tickets · M open"), view switcher (Kanban | List as `<Link>`s that keep the current filters), "New ticket" link to the legacy create URL (`urls.ticket_create`, or `/products/<id>/tickets/create/` when scoped), `FilterBar`, and the list or board.
  - `TicketTable({ items, selected, onSelect, onDelete })`: table with checkbox column, key, title (+ product name, type badge, "Linked to error"), status badge, priority, assignees (up to 3 initials + "+N", "Unassigned"), "Overdue" badge, updated "short ago" (`title` = full date), row actions Edit (link to `item.url`) and Delete (only when `can_delete`, opens `AlertDialog` "Delete ticket AUM-001? This cannot be undone."). Row click navigates to `item.url` (a plain link on the title; clicking the row elsewhere also navigates; clicks on the checkbox and action buttons do not).
  - Selection mode: a "Select" toggle button (legacy "Select" at top right) shows checkboxes and a "Delete selected (N)" button that confirms and calls `POST tickets/bulk-delete/ {ids}`; success toasts `Deleted N tickets.` (plus `, skipped M` when M > 0), invalidates `['tickets']` and `['bootstrap']` (sidebar counts).
  - Pagination (befui Pagination) updates `page` in the URL; empty state "No tickets found" with "Try a different search term." when `q` is set else "Create a ticket to start tracking work."
  - Delete one: `DELETE tickets/<id>/`, toast `Ticket AUM-001 deleted.`, invalidate as above; an error toasts the server `detail`.

- [ ] **Step 1: Write the failing tests** (`TicketTable.test.tsx`, `TicketsPage.test.tsx`)

Cases (each with real assertions): renders key/title/status/priority/assignee initials/`+2`/Unassigned/Overdue; a title `<script>alert(1)</script>` appears as text and no `script` element exists; long unbroken title has the `break-words`/`clamp` class (assert class contains `break-words`); delete button only for `can_delete`; clicking Delete opens the dialog, confirming calls `api.request`-level `DELETE` via the module's `deleteTicket` helper and toasts; cancelling does nothing; bulk selection shows count and sends the selected ids; a partial result (`deleted:1, skipped:2`) toasts `Deleted 1 ticket, skipped 2.`; pagination click sets `page=2` in the URL; empty states for search and no search; the view switcher links keep the query string; a failing list request shows "Couldn't load tickets." with Try again.

Add to `lib/api.ts` a `del` helper if needed: `api.delete<T>(path)` (method DELETE, same CSRF/401 handling) with its own test in `bootstrap.test.ts`.

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** (port the markup/behaviour from `templates/tickets/partials/_ticket_list_body.html`; `short_ago` is `Intl.RelativeTimeFormat` style like the Notifications page's `ago` helper: extract that helper into `lib/time.ts` and reuse it); **Step 4: Run to verify pass**; **Step 5: Commit** `feat(frontend): tickets list page with bulk delete`.

---

### Task 8: Board view

**Files:**
- Create: `frontend/src/pages/tickets/Board.tsx`, `Board.test.tsx`, `moveTicket.ts`, `moveTicket.test.ts`

**Interfaces:**
- Consumes: `BoardResponse`, `api.post('tickets/<id>/status/')`, `toast`.
- Produces:
  - `applyMove(data: BoardResponse, ticketId: number, to: string): BoardResponse`: pure function returning a new board with the ticket moved to the `to` column (appended), counts recomputed, `open_count`/`total` updated; unknown ticket or same column returns the input unchanged.
  - `Board({ data, filters })`: six columns with headers (status label + count), cards (checkbox, key · product, delete button when `can_delete`, title link, type badge, priority, assignees, deadline "Due Oct 20" / "Overdue · Oct 20"), "No tickets" empty column. Drag and drop with HTML5 DnD (`draggable`, `onDragStart/Over/Drop`); on drop: optimistic `queryClient.setQueryData` with `applyMove`, `POST tickets/<id>/status/ {status}`, on error roll back to the previous data and `toast(detail, 'error')`, on success toast `AUM-001: status Open → Testing.` and invalidate `['bootstrap']` only. Same-column drop does nothing; a card with a request in flight ignores further drops. Touch fallback: a "Move to…" button on each card (replaces the legacy long-press prompt) opens a befui `DropdownMenu` of the other statuses and performs the same move.

- [ ] **Step 1: Write the failing tests**

`moveTicket.test.ts`: moves between columns and recomputes `total`/`open_count` (moving into `resolved` lowers `open_count`); unknown id and same column return the same object; does not mutate the input.

`Board.test.tsx` (use `fireEvent.dragStart/dragOver/drop` with a `dataTransfer` stub): drop moves the card at once and calls the endpoint with `{status:'testing'}`; a rejected request puts the card back and toasts the server detail; a second drop on the same card while pending sends nothing; same-column drop sends nothing; the "Move to…" menu performs the move; a hostile title renders as text; overdue cards show "Overdue ·"; delete confirms then calls `DELETE`; each column shows its count and "No tickets" when empty.

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** (behaviour reference: `templates/tickets/partials/_kanban_columns.html` and `_kanban_drag.html`); **Step 4: Run to verify pass**; **Step 5: Commit** `feat(frontend): tickets board with drag to change status`.

---

### Task 9: Keyboard shortcuts for tickets

**Files:**
- Create: `frontend/src/pages/tickets/useTicketKeys.ts`, `useTicketKeys.test.tsx`
- Modify: `frontend/src/pages/tickets/TicketTable.tsx`, `Board.tsx` (add `data-ticket-row` / `data-ticket-card` and `data-url` attributes), `frontend/src/shell/ShortcutsHelp.tsx`

**Interfaces:**
- Produces: `useTicketKeys(containerRef, items: { url: string }[])`: `j`/`k` move a highlight (`aria-selected="true"` + `data-active`) through the visible rows/cards (clamped at the ends, scrolled into view), `Enter` opens the highlighted ticket (`go(url)`), `e` opens the highlighted ticket's edit page (`${url}edit/`). Ignored while typing, in menus/dialogs and with modifiers (reuse the `typing` rule from `shell/keys.ts`: export it as `isTypingTarget`). `ShortcutsHelp` lists `j / k`, `Enter`, `e` again.

- [ ] **Step 1: Write the failing tests**: `j` x2 highlights the second item, `k` goes back, clamping at both ends, Enter calls `go` with the highlighted URL, `e` calls `go` with `…/edit/`, nothing happens inside an input or a `role=menu`, and with no items nothing throws.
- [ ] **Step 2: Run to verify failure**; **Step 3: Implement**; **Step 4: Run to verify pass**; **Step 5: Commit** `feat(frontend): j/k/Enter/e shortcuts on ticket lists`.

---

### Task 10: Serve the six URLs from the shell and delete the legacy pages

**Files:**
- Modify: `apps/tickets/views.py`, `apps/products/views.py`
- Delete: `templates/tickets/ticket_kanban.html`, `templates/tickets/ticket_list.html`, `templates/tickets/partials/{_kanban_columns,_kanban_drag,_ticket_list_body,_ticket_list_results,_ticket_filter_bar}.html`, `templates/products/product_ticket_kanban.html`, `templates/products/product_ticket_list.html`, `templates/products/partials/{_product_ticket_list_body,_product_ticket_list_results,_product_kanban_columns}.html` (confirm each is unused with `grep -rn "<name>" apps templates` before deleting; keep any partial the legacy detail/form pages still include, e.g. `_ticket_status_badge.html`)
- Modify tests: `apps/tickets/tests/*`, `apps/products/tests*`, `apps/core/tests*` that assert the old HTML (grep for `ticket_kanban.html`, `ticket_list.html`, `kanban-col`, `_ticket_list_results`)
- Test: `apps/uiapi/test_shell_tickets.py`

**Interfaces:**
- Produces: the six views return `render_shell(request)` after the same member/product checks; `TicketBulkDeleteView` and `ProductTicketBulkDeleteView` and their URLs are removed (the API replaces them); URL names for the six pages and the detail/create/edit/status/priority/assign/deadline/follow/comment/delete routes are unchanged.

- [ ] **Step 1: Write the failing tests**

```python
class TicketShellPagesTest(Base):
    def test_all_six_urls_serve_the_shell_for_members(self):
        self.login("owner")
        for url in ["/tickets/", "/tickets/kanban/", "/tickets/list/",
                    f"/products/{self.p_open.pk}/tickets/", f"/products/{self.p_open.pk}/tickets/kanban/", f"/products/{self.p_open.pk}/tickets/list/"]:
            r = self.client.get(url)
            self.assertTemplateUsed(r, "uiapi/shell.html", msg_prefix=url)

    def test_product_pages_404_without_access_before_any_shell_is_served(self):
        self.login("dev")
        self.assertEqual(self.client.get(f"/products/{self.p_hidden.pk}/tickets/").status_code, 404)

    def test_anonymous_is_sent_to_login(self):
        self.assertEqual(Client().get("/tickets/").status_code, 302)

    def test_old_templates_are_gone(self):
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template
        for name in ["tickets/ticket_kanban.html", "tickets/ticket_list.html", "products/product_ticket_kanban.html", "products/product_ticket_list.html"]:
            with self.assertRaises(TemplateDoesNotExist):
                get_template(name)

    def test_the_legacy_detail_page_still_works_and_deleting_from_it_lands_on_the_board(self):
        t = self.make(self.p_open, created_by=self.owner)
        self.login("owner")
        self.assertEqual(self.client.get(f"/products/{self.p_open.pk}/tickets/{t.pk}/").status_code, 200)
        r = self.client.post(f"/tickets/{t.pk}/delete/")
        self.assertRedirects(r, f"/products/{self.p_open.pk}/tickets/", fetch_redirect_response=False)
```

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement**

In `apps/tickets/views.py` replace `TicketListView` and `TicketKanbanView` bodies with `return render_shell(request)` (keep `CompanyMemberRequiredMixin`); delete `TicketBulkDeleteView` and its URL; in `apps/products/views.py` do the same for `ProductTicketListView`/`ProductTicketKanbanView` (keep `get_object_or_404(Product…)` and `require_product_access` so inaccessible products 404 before the shell renders) and delete `ProductTicketBulkDeleteView` and its URL; remove now-unused imports and helpers (`apply_ticket_filters`, `Paginator`, `TICKET_FILTER_KEYS`) only if grep shows no other user. Delete the templates listed above. Update or delete the tests that asserted the old HTML (their behaviour is covered by `apps/uiapi/test_tickets.py`); do not weaken tests for the detail/create/edit pages.

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.tickets apps.products apps.uiapi apps.core apps.dashboards`
Expected: PASS. Then `grep -rn "hx-" templates/tickets templates/products | wc -l` and record the remaining htmx count in the ledger (it should have dropped by the list/kanban/filter files).

- [ ] **Step 5: Commit** (two commits: shell serving first, then deletions)

```bash
git add apps && git commit -m "feat(tickets): list and board URLs served by the React shell"
git add -A && git commit -m "chore(tickets): delete legacy list/board templates, views and htmx"
```

---

### Task 11: Parity check, docs, release

**Files:** `context.md`, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, `core/settings.py` (version)

- [ ] **Step 1: Build and run locally against a scratch database**

`seed_data` wipes `db.sqlite3`: use a scratch settings module in the scratchpad directory pointing `DATABASES["default"]["NAME"]` at a scratch file, then `migrate`, `seed_data`, `runserver 8010 --noreload`, with `cd frontend && npm run build` first. Log in as `owner` and `dev1` (seed password `testpass123`, localhost only). Verify in the browser, comparing against the git history copy of the legacy page if in doubt:

- [ ] `/tickets/`, `/tickets/kanban/`, `/tickets/list/` render in the shell; sidebar "All tickets" is the only active item and its badge matches the list header's "N open".
- [ ] Product pages (`/products/<id>/tickets/…`): product section appears in the sidebar with correct counts, switcher lists only accessible products (as `dev1`), Tickets is active, topbar shows the product name.
- [ ] Filters: search (debounced), type, priority, assignee (me / unassigned / a person), overdue, sort, status (list only), Clear; the URL updates and reloading the URL restores the same view; browser Back works.
- [ ] List: pagination, selection mode + bulk delete (as owner), single delete with the confirm dialog (as creator and as owner; hidden for others), row click and Edit open the legacy detail page, which still works.
- [ ] Board: drag a card to another column (card moves at once, toast, sidebar count updates for resolved/closed); drag to the same column does nothing; "Move to…" works; a forced failure (stop the server briefly) rolls the card back with an error toast.
- [ ] Shortcuts: `j`/`k`/Enter/`e` on list and board; `c` still goes to New ticket; none fire in inputs or menus.
- [ ] Phone width (375px): drawer, filter bar wraps, table scrolls inside its card, board columns scroll horizontally.
- [ ] No console errors; DSR sheet shows the entry after moving a ticket to Resolved (auto-log); the Discord webhook hook ran (check the server log for the call).

- [ ] **Step 2: Full regression**

```bash
venv/bin/python manage.py test apps > /tmp/full-suite.log 2>&1 &
```

Background and poll (about 3.5 minutes). Expected: only `test_signup_creates_user`. Also `cd frontend && npm test && npm run build`, and `docker build -t pq-test .`.

- [ ] **Step 3: Docs, release, commit**

- `context.md`: `### <date> (React tickets list/board)` entry: what moved, the API surface, the `scope=product` vs `product=` distinction, what was deleted (templates, views, htmx counts before/after), what stays legacy (detail, form, comments, assign, deadline, priority, follow, delete-from-detail), and the shortcuts now live (`j/k/Enter/e`).
- `CLAUDE.md` / `AGENTS.md`: update the "React UI" paragraph: tickets list/board done; the global-vs-product-scoped rule now has one JSON endpoint serving both (`scope=product`), still guarded by `accessible_*` / `require_product_access`.
- `CHANGELOG.md`: new release (next minor), `> In short:` line, bold sentence leads, plain words (e.g. "**The ticket board and list have a new look.**", "**Dragging a ticket to another column feels instant.**"); bump `APP_VERSION`; run `venv/bin/python manage.py test apps.core`.

```bash
git add -A && git commit -m "docs: React tickets list and board; release"
```

---

## Out of scope (plan B and later)

- Plan B: ticket detail, create/edit form (assignee multiselect, mentions in comments), priority/assign/deadline/follow controls, comment thread, product-scoped detail; then delete the remaining legacy ticket templates and htmx.
- Errors, products, dashboards, feedback, automation, DSR, accounts, HR (spec order); final removal of htmx, Alpine, `django_htmx` and the legacy CSS.
