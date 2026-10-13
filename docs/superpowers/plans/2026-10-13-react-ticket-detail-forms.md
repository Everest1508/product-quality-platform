# React tickets, plan B: detail page, create and edit forms, comments

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the ticket detail page, the create form and the edit form (global and product-scoped URLs) to React, with every control on the detail page (status, priority, assignees, deadline, follow, comments with @mentions, delete), and delete the legacy templates, views and htmx for them in the same change. After this, the whole tickets area is React.

**Architecture:** Same pattern as plan A. Ticket actions (create, update, priority, assign, deadline, follow, comment) move into `apps/tickets/service.py` so activity log, notifications and webhooks stay in one place; new JSON endpoints under `/ui-api/v1/tickets/` call them. The five page URLs keep their paths and names; their Django views check access and return `render_shell`. React renders one `TicketDetailPage` and one `TicketFormPage`.

**Tech Stack:** Django 6 + DRF (`CompanyAPIView`), React 19, TypeScript, TanStack Query, React Router, Tailwind 4, befui, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-12-react-ui-migration-design.md`. Builds on `docs/superpowers/plans/2026-10-13-react-tickets-list-board.md` (done).

## Global Constraints

- Backend stays Python/Django; no change to models, `Ticket.transition_to`, DSR auto-logging, mention rules (`apps/tickets/mentions.py`), `/api/v1/`, `/api/serop/`, WebSockets.
- **Both access layers on every endpoint**: company isolation and `require_ticket_access` / `require_product_access`. 404, not 403, for what the user may not open.
- Page URLs and URL names unchanged: `tickets:ticket_detail` `/tickets/<pk>/`, `tickets:ticket_edit` `/tickets/<pk>/edit/`, `tickets:ticket_create` `/tickets/create/`, `products:product_ticket_detail` `/products/<pk>/tickets/<ticket_pk>/`, `products:product_ticket_create` `/products/<pk>/tickets/create/`. Many places `reverse()` them (dashboards, search, errors, dsr, notifications); they must keep working.
- **Keep, do not delete in this plan:** the legacy routes `tickets:ticket_status` and `tickets:ticket_assign` (`/tickets/<pk>/status/`, `/tickets/<pk>/assign/`). The legacy home dashboard (`templates/dashboards/partials/_my_work.html`, `_attention.html`) still `hx-post`s to them; they go when the dashboard moves. Their logic is shared with the new API through `apps/tickets/service.py`.
- Delete in this plan (only the detail page used them): routes `ticket_priority`, `ticket_deadline`, `ticket_follow`, `ticket_comment`, `ticket_delete` and their views, after the React page replaces them.
- Behaviour that must not change: assignee drop rule on create (people without access to the chosen product are skipped with a warning), `set_assignees(..., actor=)` notifications, status auto-moves (`open`→`assigned` on first assignee, back to `open` when cleared), mention resolution and the mention/comment notification split, follow/unfollow activity events, deadline activity text with `t12`, delete rights (owner/admin or creator).
- Deadlines: the company runs on `Asia/Kolkata`. The API sends and accepts the deadline as a **naive local wall-clock string** `YYYY-MM-DDTHH:MM` (`deadline_local`), never an ISO string with offset, so a browser in another timezone cannot shift it. The browser only formats it with the same wall clock.
- Show `ticket.key`; render comment and ticket text as text (React escapes), never `dangerouslySetInnerHTML`; mention highlighting is done with parts, not HTML.
- Test commands: `venv/bin/python manage.py test <label>`; `cd frontend && npm test`. Baseline: only `test_signup_creates_user` fails in the full suite.
- When a page moves, its legacy template, view, htmx and old-HTML tests are deleted in the same task. Deletion is a separate commit.
- befui parts are copied from https://befui.vercel.app (the CLI is blocked for the agent). Replace befui's `./icons` import with `lucide-react`.
- Commit after each task. End commit messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- A user without access to the ticket's product gets 404 from every new endpoint (detail, priority, assign, deadline, follow, comments, edit) and cannot create a ticket in a product they cannot open. Pinned in Tasks 2, 3, 4.
- Assigning someone who is not in the company must be ignored, not saved. Pinned in Task 3.
- A comment mentioning someone who cannot open the ticket must not notify them or store the mention. Pinned in Task 3.
- Create with an inaccessible product id is rejected; create with assignees lacking product access skips them and reports a warning. Pinned in Task 4.
- Edit validation errors come back per field and nothing is saved. Pinned in Task 4.
- Deadline: round trip `YYYY-MM-DDTHH:MM` stays the same wall clock; clearing it works; garbage is a 400. Pinned in Tasks 2, 3.
- Hostile comment text and `@` text render as text, mention highlight only for real mentioned users, no HTML injection. Pinned in Task 6.
- Product-shaped URL with a ticket from another product is 404 before the shell is served. Pinned in Task 10.
- The legacy dashboard buttons that post to `ticket_status`/`ticket_assign` still work. Pinned in Task 10.
- Double submit of a comment does not post twice; a failed submit keeps the typed text. Pinned in Task 8.

---

## File structure

| File | Responsibility |
|---|---|
| `apps/tickets/service.py` (modify) | add `create_ticket`, `update_ticket`, `set_priority`, `assign`, `set_deadline`, `toggle_follow`, `add_comment` |
| `apps/tickets/views.py` (modify) | `TicketAssignView` uses `service.assign`; later (Task 10) detail/create/edit return the shell and obsolete views are deleted |
| `apps/uiapi/tickets.py` (modify) | `TicketDetailAPIView` (GET/PATCH/DELETE), `TicketCreateAPIView`, priority/assign/deadline/follow/comment views, `ticket_detail_json` |
| `apps/products/views.py` (modify) | product detail/create return the shell |
| `frontend/src/pages/ticket/` | `TicketDetailPage.tsx`, `TicketFormPage.tsx`, `useTicket.ts`, `MentionTextarea.tsx`, `mentions.ts`, `AssigneePicker.tsx`, `CommentList.tsx`, `types.ts` |
| `frontend/src/lib/presence.ts` (modify) | `ticket_id` on `PresenceUser` |

---

### Task 1: Ticket actions into the service layer

**Files:**
- Modify: `apps/tickets/service.py`, `apps/tickets/views.py` (`TicketAssignView` only)
- Test: `apps/tickets/tests/test_service.py` (append); existing `apps.tickets`, `apps.dashboards` tests must pass unchanged

**Interfaces:**
- Produces (all in `apps.tickets.service`, each doing exactly what the matching legacy view does today, including `log_activity`, notifications and webhooks):
  - `set_priority(ticket, new_priority, actor, company) -> str | None`: `None` on success (or when unchanged), an error message for an unknown priority.
  - `assign(ticket, user_ids, actor, company) -> str`: replaces assignees with the company members among `user_ids`; applies the open↔assigned status rule; calls `notify_ticket_assigned`; writes `ticket_assigned` activity; returns the success message text legacy used (`"AUM-001 assigned to ann.[ Status is now Assigned.]"` / `"AUM-001 is now unassigned.…"`).
  - `set_deadline(ticket, deadline, actor, company) -> None`: `deadline` is an aware `datetime` or `None`; writes `ticket_deadline_changed` activity.
  - `toggle_follow(ticket, user, company) -> bool`: returns whether the user now follows; writes `ticket_followed` / `ticket_unfollowed`.
  - `add_comment(ticket, body, actor, company) -> TicketComment`: creates the comment, resolves and stores mentions via `mentions.resolve`, sends the mention and comment notifications exactly as `TicketCommentView._notify`, writes `ticket_commented`.
  - `create_ticket(data, user, company, product=None) -> (ticket | None, form, warnings)`: validates with `TicketCreateForm(data, company=company, user=user, product=...)`, saves, drops assignees without product access (collecting a warning string `"Not assigned (no access to <product>): <names>."`), `set_assignees`, `notify_ticket_created`, `ticket_created` activity. Returns `(None, form, [])` when invalid.
  - `update_ticket(data, ticket, actor, company) -> (ticket | None, form)`: `TicketEditForm`, save, `set_assignees`, `ticket_updated` activity.

- [ ] **Step 1: Write the failing tests** (append to `test_service.py`)

```python
from datetime import datetime

from django.utils import timezone

from apps.notifications.models import Notification
from apps.products.models import ProductAccess


class TicketActionServiceTest(TicketServiceTest):
    def test_set_priority_logs_and_rejects_unknown(self):
        self.assertIsNone(service.set_priority(self.ticket, "critical", self.owner, self.company))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.priority, "critical")
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_priority_changed").exists())
        self.assertIn("not a valid priority", service.set_priority(self.ticket, "huge", self.owner, self.company))

    def test_assign_moves_open_to_assigned_and_back(self):
        msg = service.assign(self.ticket, [self.dev.pk], self.owner, self.company)
        self.ticket.refresh_from_db()
        self.assertEqual((self.ticket.status, list(self.ticket.assignees.all())), ("assigned", [self.dev]))
        self.assertIn("assigned to", msg)
        self.assertIn("Status is now Assigned", msg)
        self.assertIn("unassigned", service.assign(self.ticket, [], self.owner, self.company))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "open")

    def test_assign_ignores_people_outside_the_company(self):
        stranger = User.objects.create_user("zed", "z@t.local", "pass1234")
        service.assign(self.ticket, [stranger.pk, self.dev.pk], self.owner, self.company)
        self.assertEqual(list(self.ticket.assignees.all()), [self.dev])

    def test_set_deadline_sets_and_clears_and_logs(self):
        when = timezone.make_aware(datetime(2026, 10, 20, 10, 0), timezone.get_current_timezone())
        service.set_deadline(self.ticket, when, self.owner, self.company)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.deadline, when)
        service.set_deadline(self.ticket, None, self.owner, self.company)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.deadline)
        self.assertEqual(ActivityLog.objects.filter(event_type="ticket_deadline_changed").count(), 2)

    def test_toggle_follow(self):
        self.assertTrue(service.toggle_follow(self.ticket, self.owner, self.company))
        self.assertFalse(service.toggle_follow(self.ticket, self.owner, self.company))
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_followed").exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_unfollowed").exists())

    def test_comment_stores_mentions_and_notifies_without_duplicates(self):
        ProductAccess.objects.create(company=self.company, user=self.dev, product=self.product)
        outsider = User.objects.create_user("out", "x@t.local", "pass1234")
        Membership.objects.create(user=outsider, company=self.company, role="developer")  # no product access
        self.ticket.set_assignees([self.dev])
        c = service.add_comment(self.ticket, "hi @dev and @out", self.owner, self.company)
        self.assertEqual([u.username for u in c.mentions.all()], ["dev"])          # outsider cannot open it
        kinds = {(n.user.username, n.kind) for n in Notification.objects.all()}
        self.assertIn(("dev", "mention"), kinds)
        self.assertNotIn(("dev", "comment"), kinds)                                  # nobody gets both
        self.assertFalse(Notification.objects.filter(user=outsider).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_commented").exists())

    def test_create_ticket_skips_assignees_without_product_access_and_warns(self):
        ProductAccess.objects.create(company=self.company, user=self.dev, product=self.product)
        nobody = User.objects.create_user("nb", "n@t.local", "pass1234")
        Membership.objects.create(user=nobody, company=self.company, role="developer")
        ticket, form, warnings = service.create_ticket(
            {"title": "New", "ticket_type": "bug", "priority": "high", "product": self.product.pk,
             "assignees": [self.dev.pk, nobody.pk]},
            self.owner, self.company,
        )
        self.assertEqual(list(ticket.assignees.all()), [self.dev])
        self.assertEqual(ticket.created_by, self.owner)
        self.assertEqual(ticket.source, "manual")
        self.assertIn("Not assigned (no access to App)", warnings[0])
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_created").exists())

    def test_create_ticket_invalid_returns_the_form(self):
        ticket, form, warnings = service.create_ticket({"title": ""}, self.owner, self.company)
        self.assertIsNone(ticket)
        self.assertIn("title", form.errors)

    def test_update_ticket(self):
        ticket, form = service.update_ticket(
            {"title": "Renamed", "ticket_type": "bug", "priority": "low", "status": "testing", "assignees": [self.dev.pk]},
            self.ticket, self.owner, self.company,
        )
        ticket.refresh_from_db()
        self.assertEqual((ticket.title, ticket.status), ("Renamed", "testing"))
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_updated").exists())
```

- [ ] **Step 2: Run to verify failure**: `venv/bin/python manage.py test apps.tickets.tests.test_service` (AttributeError on the new functions).

- [ ] **Step 3: Implement.** Move the bodies out of `TicketPriorityView`, `TicketAssignView`, `TicketDeadlineView`, `TicketFollowView`, `TicketCommentView` (including its `_notify`), `TicketCreateView` and `TicketEditView` into `service.py` exactly as they are today (messages stay in the views; the service returns what the view needs to build them). Keep the `log_activity` event names and `metadata` shapes byte for byte. `priority` error text: `f"'{value}' is not a valid priority."`. Make `TicketAssignView.post` call `service.assign` and use its returned message for `messages.success`; leave its htmx/redirect shell and `ticket_status` untouched. The other legacy views keep working unchanged until Task 10 (they may call the new functions too, but are not required to).

- [ ] **Step 4: Run to verify pass**: `venv/bin/python manage.py test apps.tickets apps.dashboards apps.products`.

- [ ] **Step 5: Commit** `refactor(tickets): move ticket actions into the service layer`.

---

### Task 2: Ticket detail and edit endpoints

**Files:**
- Modify: `apps/uiapi/tickets.py`, `apps/uiapi/urls.py` (replace `TicketDeleteAPIView` with `TicketDetailAPIView`; keep route name `ticket_delete` pointing at it for DELETE)
- Test: `apps/uiapi/test_ticket_detail.py` (new, reuse `Base` from `apps/uiapi/test_tickets.py`)

**Interfaces:**
- Produces `ticket_detail_json(ticket, user, role, company)`:
  ```json
  {"ticket": { ...ticket_json fields..., "description": "…", "created_at": "…", "updated_at": "…",
               "source": "manual", "source_label": "Manual", "deadline_local": "2026-10-20T10:00",
               "linked_error": {"id": 4, "title": "TypeError…", "url": "/products/3/errors/4/"} | null,
               "created_by": {"id": 1, "name": "…"} | null },
   "comments": [{"id": 1, "author": {"id": 2, "name": "Ann Lee", "initial": "A"} | null,
                 "created_at": "…", "body": "hi @dev", "mentions": ["dev"]}],
   "following": true, "watcher_count": 2,
   "members": [{"id": 5, "name": "Ann Lee", "username": "ann"}],
   "mention_candidates": [{"username": "ann", "name": "Ann Lee"}],
   "statuses": [["open","Open"],…], "priorities": [["low","Low"],…]}
  ```
  `members` are `product_users(ticket.product, company)` when the ticket has a product, else all company members (same as the legacy detail view). `mention_candidates` come from `mentions.candidates_json`. `linked_error.url` is `/products/<product>/errors/<id>/` when the ticket has a product, else `/errors/<id>/`.
- `GET /ui-api/v1/tickets/<pk>/` (name `uiapi:ticket_detail`) → the JSON above; 404 if not accessible.
- `PATCH /ui-api/v1/tickets/<pk>/` body `{title, description, ticket_type, priority, status, assignees: [ids], deadline: "YYYY-MM-DDTHH:MM" | ""}` → `200 ticket_detail_json` on success; `400 {"errors": {"title": ["…"]}, "detail": "Could not save. Title: This field is required."}` on validation failure (uses `error_summary`); nothing saved on failure.
- `DELETE` unchanged (route name `uiapi:ticket_delete` is replaced by `uiapi:ticket_detail`; update any test that reversed the old name).

- [ ] **Step 1: Write the failing tests**

```python
class TicketDetailApiTest(Base):
    def url(self, t):
        return f"/ui-api/v1/tickets/{t.pk}/"

    def test_detail_shape(self):
        t = self.make(self.p_open, "Login bug", description="Cannot sign in", created_by=self.owner)
        t.set_assignees([self.dev])
        t.watchers.add(self.dev)
        self.login("dev")
        data = self.client.get(self.url(t)).json()
        self.assertEqual(data["ticket"]["key"], t.key)
        self.assertEqual(data["ticket"]["description"], "Cannot sign in")
        self.assertEqual(data["ticket"]["created_by"]["name"], "owner")
        self.assertTrue(data["following"])
        self.assertEqual(data["watcher_count"], 1)
        self.assertEqual(data["statuses"][0], ["open", "Open"])
        self.assertIn("dev", [m["username"] for m in data["members"]])
        self.assertIn("dev", [c["username"] for c in data["mention_candidates"]])

    def test_deadline_is_the_company_wall_clock(self):
        from datetime import datetime
        from django.utils import timezone
        t = self.make(self.p_open, deadline=timezone.make_aware(datetime(2026, 10, 20, 10, 5), timezone.get_current_timezone()))
        self.login("owner")
        self.assertEqual(self.client.get(self.url(t)).json()["ticket"]["deadline_local"], "2026-10-20T10:05")

    def test_comments_come_with_their_mentions(self):
        from apps.tickets.service import add_comment
        t = self.make(self.p_open)
        add_comment(t, "hi @dev", self.owner, self.acme)
        self.login("owner")
        c = self.client.get(self.url(t)).json()["comments"][0]
        self.assertEqual((c["body"], c["mentions"], c["author"]["name"]), ("hi @dev", ["dev"], "owner"))

    def test_linked_error_url_follows_the_product(self):
        from apps.ingestion.models import ErrorGroup
        eg = ErrorGroup.objects.create(company=self.acme, product=self.p_open, fingerprint="f", title="Boom")
        t = self.make(self.p_open, linked_error_group=eg)
        self.login("owner")
        link = self.client.get(self.url(t)).json()["ticket"]["linked_error"]
        self.assertEqual(link, {"id": eg.pk, "title": "Boom", "url": f"/products/{self.p_open.pk}/errors/{eg.pk}/"})

    def test_inaccessible_and_foreign_tickets_are_404(self):
        hidden, foreign = self.make(self.p_hidden), self.make(self.p_foreign)
        self.login("dev")
        self.assertEqual(self.client.get(self.url(hidden)).status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(self.url(foreign)).status_code, 404)

    def test_a_ticket_without_a_product_lists_all_company_members(self):
        t = Ticket.objects.create(company=self.acme, title="Company-wide")
        self.login("dev")
        names = [m["username"] for m in self.client.get(self.url(t)).json()["members"]]
        self.assertEqual(sorted(names), ["dev", "owner"])


class TicketEditApiTest(Base):
    def patch(self, t, body):
        return self.client.patch(f"/ui-api/v1/tickets/{t.pk}/", body, content_type="application/json")

    def good(self, **over):
        return {"title": "Renamed", "description": "d", "ticket_type": "bug", "priority": "low", "status": "testing", "assignees": [], "deadline": "", **over}

    def test_edit_saves_and_logs(self):
        from apps.dashboards.models import ActivityLog
        t = self.make(self.p_open)
        self.login("owner")
        r = self.patch(t, self.good(assignees=[self.dev.pk], deadline="2026-10-20T10:00"))
        self.assertEqual(r.status_code, 200)
        t.refresh_from_db()
        self.assertEqual((t.title, t.status, list(t.assignees.all())), ("Renamed", "testing", [self.dev]))
        self.assertEqual(r.json()["ticket"]["deadline_local"], "2026-10-20T10:00")
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_updated").exists())

    def test_clearing_the_deadline(self):
        from django.utils import timezone
        t = self.make(self.p_open, deadline=timezone.now())
        self.login("owner")
        self.assertEqual(self.patch(t, self.good(deadline="")).status_code, 200)
        t.refresh_from_db()
        self.assertIsNone(t.deadline)

    def test_validation_errors_are_per_field_and_save_nothing(self):
        t = self.make(self.p_open, "Keep me")
        self.login("owner")
        r = self.patch(t, self.good(title="", deadline="not a date"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.json()["errors"])
        self.assertIn("deadline", r.json()["errors"])
        self.assertTrue(r.json()["detail"].startswith("Could not save."))
        t.refresh_from_db()
        self.assertEqual(t.title, "Keep me")

    def test_edit_needs_access_and_csrf(self):
        hidden = self.make(self.p_hidden)
        self.login("dev")
        self.assertEqual(self.patch(hidden, self.good()).status_code, 404)
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="owner", password="pass1234")
        t = self.make(self.p_open)
        self.assertEqual(strict.patch(f"/ui-api/v1/tickets/{t.pk}/", self.good(), content_type="application/json").status_code, 403)
```

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement**

`apps/uiapi/tickets.py`:

```python
from django.utils import timezone

from apps.tickets import mentions
from apps.tickets.forms import TicketEditForm, error_summary


def local_input(dt):
    """A deadline as the wall clock a <input type=datetime-local> wants, in the company timezone."""
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M") if dt else ""


def ticket_detail_json(ticket, user, role, company):
    base = ticket_json(ticket, user, role)
    link = None
    if ticket.linked_error_group_id:
        eg = ticket.linked_error_group
        url = f"/products/{ticket.product_id}/errors/{eg.pk}/" if ticket.product_id else f"/errors/{eg.pk}/"
        link = {"id": eg.pk, "title": eg.title, "url": url}
    members = product_users(ticket.product, company) if ticket.product_id else User.objects.filter(memberships__company=company).order_by("username")
    return {
        "ticket": {
            **base,
            "description": ticket.description,
            "created_at": ticket.created_at.isoformat(),
            "source": ticket.source,
            "source_label": ticket.get_source_display(),
            "deadline_local": local_input(ticket.deadline),
            "linked_error": link,
            "created_by": {"id": ticket.created_by_id, "name": _name(ticket.created_by)} if ticket.created_by_id else None,
        },
        "comments": [
            {
                "id": c.pk,
                "author": {"id": c.author_id, "name": _name(c.author), "initial": (c.author.username[:1] or "?").upper()} if c.author_id else None,
                "created_at": c.created_at.isoformat(),
                "body": c.body,
                "mentions": [u.username for u in c.mentions.all()],
            }
            for c in ticket.comments.select_related("author").prefetch_related("mentions").all()
        ],
        "following": ticket.watchers.filter(pk=user.pk).exists(),
        "watcher_count": ticket.watchers.count(),
        "members": [{"id": u.pk, "name": _name(u), "username": u.username} for u in members],
        "mention_candidates": mentions.candidates_json(ticket, company),
        "statuses": [list(c) for c in Ticket.Status.choices],
        "priorities": [list(c) for c in Ticket.Priority.choices],
    }
```

Replace `TicketDeleteAPIView` with:

```python
class TicketDetailAPIView(CompanyAPIView):
    def _full(self, request, ticket):
        ticket = Ticket.objects.select_related("product", "created_by", "linked_error_group").prefetch_related("assignees").get(pk=ticket.pk)
        return Response(ticket_detail_json(ticket, request.user, request.company_role, request.company))

    def get(self, request, pk):
        return self._full(request, _ticket(request, pk))

    def patch(self, request, pk):
        ticket = _ticket(request, pk)
        saved, form = ticket_service.update_ticket(request.data, ticket, request.user, request.company)
        if saved is None:
            return Response({"errors": form.errors.get_json_data() and {k: [e["message"] for e in v] for k, v in form.errors.get_json_data().items()}, "detail": error_summary(form)}, status=400)
        return self._full(request, saved)

    def delete(self, request, pk):  # body unchanged from TicketDeleteAPIView.delete
        ...
```

Route: `path("tickets/<int:pk>/", tickets.TicketDetailAPIView.as_view(), name="ticket_detail")`. `request.data` is a `dict` for JSON; `TicketEditForm(data=...)` accepts it (`assignees` list, `deadline` naive string or `""`; an empty string deadline cleans to `None`). If the form complains about a missing `assignees` key, default it to `[]` in `update_ticket`.

- [ ] **Step 4: Run to verify pass**: `venv/bin/python manage.py test apps.uiapi apps.tickets`. **Step 5: Commit** `feat(uiapi): ticket detail and edit endpoints`.

---

### Task 3: Priority, assignees, deadline, follow and comment endpoints

**Files:**
- Modify: `apps/uiapi/tickets.py`, `apps/uiapi/urls.py`
- Test: `apps/uiapi/test_ticket_detail.py` (append)

**Interfaces:**
- Each returns `200` with the **fresh `ticket_detail_json`** (so the page can replace its cache entry), except where noted; all 404 without access; invalid input is `400 {"detail": "…"}`:
  - `POST /ui-api/v1/tickets/<pk>/priority/` `{"priority": "high"}` (name `uiapi:ticket_priority`).
  - `POST /ui-api/v1/tickets/<pk>/assign/` `{"assignees": [ids]}` → also includes `"message": "AUM-001 assigned to ann."` (name `uiapi:ticket_assign`).
  - `POST /ui-api/v1/tickets/<pk>/deadline/` `{"deadline": "YYYY-MM-DDTHH:MM" | null | ""}` (name `uiapi:ticket_deadline`); an unparseable value is `400`.
  - `POST /ui-api/v1/tickets/<pk>/follow/` `{}` (name `uiapi:ticket_follow`) → includes `"message"`.
  - `POST /ui-api/v1/tickets/<pk>/comments/` `{"body": "…"}` (name `uiapi:ticket_comments`) → `201`; empty or whitespace-only body is `400 {"detail": "Comment cannot be empty."}`.

- [ ] **Step 1: Write the failing tests**

```python
class TicketActionsApiTest(Base):
    def post(self, t, action, body=None):
        return self.client.post(f"/ui-api/v1/tickets/{t.pk}/{action}/", body or {}, content_type="application/json")

    def test_priority(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post(t, "priority", {"priority": "critical"})
        self.assertEqual(r.json()["ticket"]["priority"], "critical")
        self.assertEqual(self.post(t, "priority", {"priority": "huge"}).status_code, 400)

    def test_assign_sets_status_and_ignores_strangers(self):
        t = self.make(self.p_open)
        stranger = member("zed", self.other)
        self.login("owner")
        r = self.post(t, "assign", {"assignees": [self.dev.pk, stranger.pk]})
        data = r.json()
        self.assertEqual([a["id"] for a in data["ticket"]["assignees"]], [self.dev.pk])
        self.assertEqual(data["ticket"]["status"], "assigned")
        self.assertIn("assigned to", data["message"])
        self.assertEqual(self.post(t, "assign", {"assignees": []}).json()["ticket"]["status"], "open")

    def test_deadline_set_clear_and_garbage(self):
        t = self.make(self.p_open)
        self.login("owner")
        self.assertEqual(self.post(t, "deadline", {"deadline": "2026-10-20T10:00"}).json()["ticket"]["deadline_local"], "2026-10-20T10:00")
        self.assertEqual(self.post(t, "deadline", {"deadline": None}).json()["ticket"]["deadline_local"], "")
        self.assertEqual(self.post(t, "deadline", {"deadline": "soon"}).status_code, 400)

    def test_follow_toggles(self):
        t = self.make(self.p_open)
        self.login("dev")
        r = self.post(t, "follow")
        self.assertEqual((r.json()["following"], r.json()["watcher_count"]), (True, 1))
        self.assertFalse(self.post(t, "follow").json()["following"])

    def test_comment_with_mentions(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post(t, "comments", {"body": "hello @dev"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["comments"][0]["mentions"], ["dev"])

    def test_empty_comment_is_400(self):
        t = self.make(self.p_open)
        self.login("owner")
        self.assertEqual(self.post(t, "comments", {"body": "   "}).status_code, 400)
        self.assertEqual(t.comments.count(), 0)

    def test_every_action_needs_access(self):
        hidden = self.make(self.p_hidden)
        self.login("dev")
        for action, body in [("priority", {"priority": "low"}), ("assign", {"assignees": []}), ("deadline", {"deadline": None}),
                             ("follow", {}), ("comments", {"body": "x"})]:
            self.assertEqual(self.post(hidden, action, body).status_code, 404, action)
        self.assertEqual(hidden.comments.count(), 0)
```

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** five small `CompanyAPIView`s that call `_ticket(request, pk)`, the service function, then `ticket_detail_json` (build with the shared helper `_full`; factor it into a module-level `detail_response(request, ticket, **extra)`). Parse the deadline with `django.utils.dateparse.parse_datetime` on the naive string, then `timezone.make_aware(value, timezone.get_current_timezone())`; `None`/`""` clears; a parse failure is a 400. **Step 4: Run to verify pass**: `venv/bin/python manage.py test apps.uiapi`. **Step 5: Commit** `feat(uiapi): ticket priority, assign, deadline, follow and comment endpoints`.

---

### Task 4: Create endpoint

**Files:** modify `apps/uiapi/tickets.py`, `apps/uiapi/urls.py`; test `apps/uiapi/test_ticket_detail.py` (append)

**Interfaces:**
- `POST /ui-api/v1/tickets/` (name `uiapi:ticket_create`) body `{title, description, ticket_type, priority, product: id | "" | null, assignees: [ids], deadline: "YYYY-MM-DDTHH:MM" | ""}` → `201 {"ticket": ticket_json(...), "key": "AUM-014", "url": "/products/3/tickets/14/", "warnings": ["Not assigned (no access to App): bob."]}`; `400 {"errors": {...}, "detail": "Could not save. …"}` on validation failure. A `product` the user cannot open is a validation error on `product` (the form's queryset is `accessible_products`), never a leak. `url` is the legacy detail URL via `ticket_url`.
- The meta endpoint already provides `products` and `members` for the form; no change.

- [ ] **Step 1: Write the failing tests**

```python
class TicketCreateApiTest(Base):
    url = "/ui-api/v1/tickets/"

    def post(self, body):
        return self.client.post(self.url, body, content_type="application/json")

    def good(self, **over):
        return {"title": "New bug", "description": "", "ticket_type": "bug", "priority": "high", "product": self.p_open.pk, "assignees": [], "deadline": "", **over}

    def test_create_returns_key_url_and_logs(self):
        from apps.dashboards.models import ActivityLog
        self.login("dev")
        r = self.post(self.good())
        self.assertEqual(r.status_code, 201)
        t = Ticket.objects.get(title="New bug")
        self.assertEqual((r.json()["key"], r.json()["url"]), (t.key, f"/products/{self.p_open.pk}/tickets/{t.pk}/"))
        self.assertEqual((t.created_by, t.source, t.company), (self.dev, "manual", self.acme))
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_created").exists())

    def test_cannot_create_in_a_product_the_user_cannot_open(self):
        self.login("dev")
        r = self.post(self.good(product=self.p_hidden.pk))
        self.assertEqual(r.status_code, 400)
        self.assertIn("product", r.json()["errors"])
        self.assertFalse(Ticket.objects.filter(title="New bug").exists())

    def test_cannot_create_in_another_companys_product(self):
        self.login("owner")
        self.assertEqual(self.post(self.good(product=self.p_foreign.pk)).status_code, 400)

    def test_assignees_without_product_access_are_skipped_with_a_warning(self):
        outsider = member("out", self.acme)  # company member, no access to p_open
        self.login("owner")
        r = self.post(self.good(assignees=[self.dev.pk, outsider.pk]))
        self.assertEqual([a["id"] for a in r.json()["ticket"]["assignees"]], [self.dev.pk])
        self.assertIn("Not assigned (no access to Open)", r.json()["warnings"][0])

    def test_company_wide_ticket_without_a_product(self):
        self.login("owner")
        r = self.post(self.good(product=None))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["url"], f"/tickets/{Ticket.objects.get(title='New bug').pk}/")

    def test_validation_errors(self):
        self.login("owner")
        r = self.post(self.good(title="", deadline="nope"))
        self.assertEqual(r.status_code, 400)
        self.assertTrue({"title", "deadline"} <= set(r.json()["errors"]))
        self.assertEqual(Ticket.objects.count(), 0)

    def test_csrf_and_anonymous(self):
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="owner", password="pass1234")
        self.assertEqual(strict.post(self.url, self.good(), content_type="application/json").status_code, 403)
        self.assertEqual(Client().post(self.url, self.good(), content_type="application/json").status_code, 403)
```

(`TicketListAPIView` is registered at the same URL for GET: add `post` by routing `tickets/` to one class `TicketCollectionAPIView(get=list, post=create)` or give the existing view a `post` method; keep the route name `tickets` and add `ticket_create` only if a separate name is needed. Pick the second: add `post` to `TicketListAPIView`.)

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** `post` calling `ticket_service.create_ticket(request.data, request.user, request.company)`; the product: `request.data.get("product") or None`; pass the resolved `Product` through the form only (the form restricts to `accessible_products`). Build the 400 body with a shared `form_errors(form)` helper (`{field: [messages]}` + `detail=error_summary(form)`), also used by `patch` in Task 2 (refactor it then). **Step 4: Run to verify pass**; **Step 5: Commit** `feat(uiapi): ticket create endpoint`.

---

### Task 5: Frontend plumbing: types, routes, presence viewers

**Files:**
- Create: `frontend/src/pages/ticket/types.ts`, `frontend/src/pages/ticket/useTicket.ts`, `frontend/src/pages/ticket/useTicket.test.tsx`
- Modify: `frontend/src/shell/nav.ts`, `frontend/src/shell/nav.test.ts`, `frontend/src/routes.tsx`, `frontend/src/lib/presence.ts`, `frontend/src/lib/usePresence.ts` (types only)
- Stubs: `frontend/src/pages/ticket/TicketDetailPage.tsx`, `TicketFormPage.tsx` (return a `<div>`; replaced in Tasks 8 and 9)

**Interfaces:**
- Produces:
  - `types.ts`: `TicketDetail` (the `ticket_detail_json` shape), `Comment`, `TicketInput` (`{title, description, ticket_type, priority, status?, product: number | null, assignees: number[], deadline: string}`), `FieldErrors = Record<string, string[]>`.
  - `useTicket.ts`:
    - `useTicketDetail(id)`: `['ticket', id]`, `api.get('tickets/<id>/')`.
    - `useTicketActions(id)`: mutation helpers `setStatus(status)`, `setPriority`, `assign(ids)`, `setDeadline(local | null)`, `toggleFollow()`, `addComment(body)`, `remove()`; each posts to its endpoint, on success writes the returned detail into `['ticket', id]` with `setQueryData`, invalidates `['tickets']`, `['bootstrap']`, `['product-nav']`, and toasts the success text (`Comment added.`, the server `message`, `AUM-001: priority High → Low.` etc.); on error toasts the server detail. `setStatus` uses the existing `tickets/<id>/status/` endpoint and refetches the detail.
    - `saveTicket(id | null, input)` for the form: `POST tickets/` or `PATCH tickets/<id>/`; resolves `{ key, url, warnings }` or rejects with `ApiFieldError { errors: FieldErrors, message }` (extend `lib/api.ts` so a 400 body with `errors` exposes them: `class ApiError extends Error { status; body }`, `request` throws it, existing tests keep passing).
  - `isReactPath` additionally true for `^/tickets/create/$`, `^/tickets/\d+/$`, `^/tickets/\d+/edit/$`, `^/products/\d+/tickets/create/$`, `^/products/\d+/tickets/\d+/$`.
  - Routes: `/tickets/create/`, `/tickets/:id/`, `/tickets/:id/edit/`, `/products/:pk/tickets/create/`, `/products/:pk/tickets/:id/` (put `create` before `:id` is unnecessary since `:id` is digits only at the Django side; in React Router v6 static segments outrank dynamic ones, so no ordering issue).
  - `PresenceUser.ticket_id?: number | null`.
  - `nav.ts`: Sidebar active state for these paths already resolves by longest prefix (`/tickets/` All tickets; `/products/3/tickets/` product Tickets).

- [ ] **Step 1: Write the failing tests**: `nav.test.ts` additions (`isReactPath` true for the five new shapes and false for `/tickets/5/status/`, `/tickets/5/foo/`, `/products/3/tickets/create/x/`); `useTicket.test.tsx` (mock `api`): detail fetch key and URL; each action posts to the right endpoint with the right body, updates the cache from the response, invalidates the list keys and toasts; an error toasts the server detail and leaves the cache alone; `saveTicket` posts for new and patches for existing; a 400 with `errors` rejects with those field errors; `api.patch` exists and sends `PATCH` JSON with CSRF.
- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** (add `api.patch`, `ApiError` with `body`); **Step 4: Run to verify pass** (`npm test && npm run build`); **Step 5: Commit** `feat(frontend): ticket detail plumbing, routes and hooks`.

---

### Task 6: @mentions: parsing, rendering and the comment box

**Files:**
- Create: `frontend/src/pages/ticket/mentions.ts`, `mentions.test.ts`, `MentionTextarea.tsx`, `MentionTextarea.test.tsx`, `CommentList.tsx`, `CommentList.test.tsx`

**Interfaces:**
- Produces:
  - `renderMentions(body: string, mentioned: string[]): (string | { mention: string })[]`: splits `body` into text parts and `{mention}` parts for each `@username` where `username` (case-insensitive) is in `mentioned`, using the server's boundary rules: not preceded by `[\w@.+-]` and not followed by `[\w@+-]`. Returns data, not HTML. Text that merely looks like a mention but is not in `mentioned` stays text.
  - `findMentionAt(text: string, caret: number): { query: string; start: number } | null`: the active `@query` being typed immediately before the caret (`/(?:^|[\s(])@([\w.+-]{0,30})$/` on `text.slice(0, caret)`).
  - `filterPeople(people, query)`: `username` starts with query or `name` contains it (case-insensitive), max 6.
  - `MentionTextarea({ value, onChange, people, onSubmit?, ...textareaProps })`: a controlled textarea with `role="combobox"`, a `listbox` of matches, `aria-activedescendant`; ArrowUp/Down move (wrap), Enter or Tab choose (replace `@query` with `@username ` and put the caret after it), Escape closes, click on an option chooses; Enter with no list open does nothing special (newline). Closes when the caret leaves a mention.
  - `CommentList({ comments })`: author initial + name (or "System"), "x ago" with full date in `title`, body with `renderMentions` (mention spans styled `bg-accent text-accent-foreground rounded px-1` with `title` = the person's name when known), `whitespace-pre-wrap`; empty state "No comments yet."

- [ ] **Step 1: Write the failing tests**

```ts
// mentions.test.ts
it('highlights only real mentions and keeps everything else as text', () => {
  expect(renderMentions('hi @Dev and @out.', ['dev'])).toEqual(['hi ', { mention: '@Dev' }, ' and @out.']);
});
it('respects word boundaries', () => {
  expect(renderMentions('mail dev@dev.com and @dev.', ['dev'])).toEqual(['mail dev@dev.com and ', { mention: '@dev' }, '.']);
  expect(renderMentions('@devx @dev', ['dev'])).toEqual(['@devx ', { mention: '@dev' }]);
});
it('never returns HTML', () => {
  expect(renderMentions('<img src=x onerror=alert(1)> @dev', ['dev'])).toEqual(['<img src=x onerror=alert(1)> ', { mention: '@dev' }]);
});
it('finds the mention being typed', () => {
  expect(findMentionAt('hello @an', 9)).toEqual({ query: 'an', start: 6 });
  expect(findMentionAt('hello @an and', 13)).toBeNull();
  expect(findMentionAt('mail a@b', 8)).toBeNull();
});
it('filters people by username prefix or name', () => {
  const p = [{ username: 'ann', name: 'Ann Lee' }, { username: 'bob', name: 'Bobby Ann' }, { username: 'cy', name: 'Cy' }];
  expect(filterPeople(p, 'an').map((x) => x.username)).toEqual(['ann', 'bob']);
});
```

`MentionTextarea.test.tsx`: typing `@a` opens the list with the matching people; ArrowDown/ArrowUp wrap; Enter and Tab insert `@ann ` and call `onChange` with the new value and the caret after the space; Escape closes; clicking an option inserts it; plain Enter with the list closed does not insert; the list closes when the caret moves away; `aria-activedescendant` follows the active option.
`CommentList.test.tsx`: author name and initial, "System" when no author, mention span for real mentions only, hostile body as text (no `img`/`script` element), empty state.

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** (behaviour reference: `templates/tickets/partials/_comment_form.html` and `apps/tickets/mentions.render_comment`); **Step 4: Run to verify pass**; **Step 5: Commit** `feat(frontend): @mention textarea and comment list`.

---

### Task 7: Assignee picker and deadline field

**Files:**
- Create: `frontend/src/pages/ticket/AssigneePicker.tsx`, `AssigneePicker.test.tsx`, `DeadlineField.tsx`, `DeadlineField.test.tsx`, `frontend/src/components/ui/{textarea.tsx (from input.tsx), label.tsx}` (copy befui `Textarea` is already in `input.tsx`; add `Label` if the site has it, else a plain styled `<label>`)

**Interfaces:**
- `AssigneePicker({ people, value, onChange, disabled? })`: a befui `Popover` trigger showing selected people as chips (initial + name, "Unassigned" when empty); the popover lists everyone with a checkbox, a search box when more than 8 people, and "Clear". `onChange(ids: number[])` is called on every toggle (the detail page auto-saves, debounced by the caller); `aria-label="Assignees"`.
- `DeadlineField({ value, onChange, overdue?, error?, disabled? })`: `<input type="datetime-local">` bound to a `YYYY-MM-DDTHH:MM` string; `onChange(value | null)` on blur or Enter (not on every keystroke, so a half-typed date is not sent); empty clears (`null`); shows "Overdue" in red when `overdue`; `error` text below.

- [ ] **Step 1: Write the failing tests**: picker shows chips for the selected, toggling a person calls `onChange` with the new id list (add and remove), search filters by name once there are more than 8, Clear calls `onChange([])`, disabled does not open; deadline field calls `onChange` only on blur/Enter with the typed value, `null` when cleared, shows Overdue and error text, never emits an incomplete value.
- [ ] **Step 2: Run to verify failure**; **Step 3: Implement**; **Step 4: Run to verify pass**; **Step 5: Commit** `feat(frontend): assignee picker and deadline field`.

---

### Task 8: Ticket detail page

**Files:**
- Modify: `frontend/src/pages/ticket/TicketDetailPage.tsx` (replace the stub)
- Create: `frontend/src/pages/ticket/TicketDetailPage.test.tsx`

**Interfaces:**
- Consumes: `useTicketDetail`, `useTicketActions`, `CommentList`, `MentionTextarea`, `AssigneePicker`, `DeadlineField`, `useProductNav`, `usePresence`, `AlertDialog`, `go`.
- Produces `TicketDetailPage()` for `/tickets/:id/` and `/products/:pk/tickets/:id/` (id from the route):
  - Breadcrumbs: Tickets (`/tickets/`), product name (legacy product overview `/products/<id>/` as a plain link), key. Header: `KEY` + title; "also viewing" chip listing other people whose presence `ticket_id` equals this ticket (not me), `aria-live="polite"`; actions: back link ("← <product> tickets" or "← Tickets"), Edit (`<Link to="/tickets/<id>/edit/">`, `data-shortcut="edit"` style: also `e` key goes there), Delete (only when `can_delete`; confirm "Delete ticket KEY? This cannot be undone."; on success toast and go to the board URL: `/products/<id>/tickets/` or `/tickets/`).
  - Main column: description card (type badge, product name, "Created x ago" with full date title, description `whitespace-pre-wrap`), linked-error card (plain `<a href>` to the legacy error page), comments card (count, `CommentList`, comment form: `MentionTextarea` + "Comment" button; disabled while posting so a double click posts once; the text is cleared only on success and kept on failure; ignores empty/whitespace).
  - Side panel "Details": Status select (all statuses, changing calls `setStatus`), Priority select, Assignees (`AssigneePicker`, auto-saves 600 ms after the last change, "Saving…" hint), Follow button (`Follow` / `Following`, with `· N` watchers), Deadline (`DeadlineField`), Source, Updated (x ago).
  - Loading skeleton; 404 → "Ticket not found." (with a link back to tickets); other error → "Couldn't load this ticket." with Try again. Sets `document.title` to `KEY title — PQ Platform`.
  - Optimistic feel is not required: controls disable while their request runs and show the server's result.

- [ ] **Step 1: Write the failing tests** (mock `api`, bootstrap, product nav, presence): renders key/title/description/status/priority/assignee chips/source; hostile title, description and comment render as text; status change posts to the status endpoint and refetches; priority change posts and toasts; assignee toggle auto-saves once after the debounce (fake timers: two quick toggles → one request with both); follow toggles label and count; deadline change posts the local string, clearing posts `null`; comment posts once on double click, clears on success, keeps the text and toasts on failure, ignores whitespace; Delete shows only when allowed, confirms, calls DELETE and navigates to the right board URL (`go` spy); "also viewing" appears for another user's `ticket_id` and not for me; 404 and error states; `e` navigates to the edit URL and does not fire while typing in the comment box.
- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** (reference: `templates/tickets/ticket_detail.html` and its partials); **Step 4: Run to verify pass** (`npm test && npm run build`); **Step 5: Commit** `feat(frontend): ticket detail page`.

---

### Task 9: Create and edit form page

**Files:**
- Modify: `frontend/src/pages/ticket/TicketFormPage.tsx`
- Create: `frontend/src/pages/ticket/TicketFormPage.test.tsx`

**Interfaces:**
- `TicketFormPage()` for `/tickets/create/`, `/products/:pk/tickets/create/` (create) and `/tickets/:id/edit/` (edit):
  - Create: fields Title (required, autofocus), Description, Type, Priority (default Medium), Product (global create only: select with "No product (company-wide)" plus accessible products; on a product page it is fixed and not shown), Assignees (`AssigneePicker` over `meta.members`; note under the picker when a product is chosen on the global page: people without access to it are skipped), Deadline (`datetime-local`, optional). "Create Ticket" submits `saveTicket(null, input)`; on success toast `Ticket AUM-014 created.`, show any `warnings` as warning toasts, then navigate to the returned `url` with `go` (full load to the legacy-shaped detail URL, which React serves). Cancel goes back to the board URL.
  - Edit: loads `useTicketDetail(id)`, same fields plus Status (all statuses), no Product; "Save Changes" submits `saveTicket(id, input)`; success toast `Ticket KEY updated.` then navigate to the ticket's detail URL; Cancel returns to it.
  - Field errors from a 400 show under their fields (and the form keeps its values); the submit button disables while saving (no double create); required title is also checked client-side before sending; unsaved-changes prompt is NOT required.
  - Meta: `useTicketMeta(productId)` (scoped on product pages) supplies products, members and the choice lists.

- [ ] **Step 1: Write the failing tests**: create happy path posts the exact body (including `product: null` for company-wide, `assignees` ids, `deadline` local string or `""`), toasts, warns, navigates to the returned url; product page create hides the product field and posts that product id; edit prefilled from detail, posts a PATCH with the changed values, navigates to detail; server field errors render under the right fields and keep the values; double click on submit sends one request; empty title shows the client error without a request; Cancel links; a ticket the user cannot open shows "Ticket not found."
- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** (reference: `templates/tickets/ticket_form.html`, `products/product_ticket_form.html`, `_assignee_multiselect.html`); **Step 4: Run to verify pass**; **Step 5: Commit** `feat(frontend): ticket create and edit form`.

---

### Task 10: Serve the pages from the shell and delete the legacy ones

**Files:**
- Modify: `apps/tickets/views.py`, `apps/tickets/urls.py`, `apps/products/views.py`, `apps/products/urls.py` (only if a deleted view's route is listed)
- Delete: `templates/tickets/ticket_detail.html`, `ticket_form.html`, `templates/products/product_ticket_detail.html`, `product_ticket_form.html`, and the partials only they used: `tickets/partials/_assignee_multiselect.html`, `_comment_form.html`, `_comment_list.html`, `_ticket_deadline.html`, `_ticket_follow.html`, `_ticket_priority.html`, `_ticket_viewers.html`, `_ticket_assignee.html`, `_ticket_status.html`, `_ticket_status_badge.html` (verify each with `grep -rn` first; keep any partial still included by another template, for example the dashboard's), plus `apps/tickets/templatetags/ticket_tags.py` only if nothing else uses `comment_html`
- Delete legacy view classes and routes: `TicketPriorityView`, `TicketDeadlineView`, `TicketFollowView`, `TicketCommentView`, `TicketDeleteView` (routes `ticket_priority`, `ticket_deadline`, `ticket_follow`, `ticket_comment`, `ticket_delete`)
- Keep: `TicketStatusView` (`ticket_status`) and `TicketAssignView` (`ticket_assign`) for the legacy dashboard; keep route names `ticket_detail`, `ticket_edit`, `ticket_create`, `product_ticket_detail`, `product_ticket_create`
- Modify tests: `apps/tickets/tests/*`, `apps/tickets/test_keys.py`, `apps/products/tests*`, `apps/dashboards/tests*`, `apps/errors/tests*` that assert the old HTML or POST to the deleted routes
- Test: `apps/uiapi/test_shell_ticket_pages.py`

**Interfaces:**
- The five page views run their existing checks, then `return render_shell(request)`:
  - `TicketDetailView`: `get_object_or_404(Ticket, pk=pk, company=request.company)` + `require_ticket_access`.
  - `TicketEditView`, `TicketCreateView`: member check only (edit also `require_ticket_access`; the edit view accepts GET only now, the POST path is the API).
  - `ProductTicketDetailView`: product 404 + `require_product_access` + the ticket must be `product.tickets` (404 if it belongs to another product).
  - `ProductTicketCreateView`: product 404 + `require_product_access`.

- [ ] **Step 1: Write the failing tests**

```python
class TicketPageShellTest(Base):
    def pages(self, t):
        pk = self.p_open.pk
        return [f"/tickets/{t.pk}/", f"/tickets/{t.pk}/edit/", "/tickets/create/",
                f"/products/{pk}/tickets/{t.pk}/", f"/products/{pk}/tickets/create/"]

    def test_all_five_urls_serve_the_shell(self):
        t = self.make(self.p_open)
        self.login("owner")
        for url in self.pages(t):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTemplateUsed(r, "uiapi/shell.html", msg_prefix=url)
            self.assertTemplateNotUsed(r, "core/base.html", msg_prefix=url)

    def test_inaccessible_tickets_and_products_are_404_before_the_shell(self):
        hidden = self.make(self.p_hidden)
        self.login("dev")
        for url in (f"/tickets/{hidden.pk}/", f"/tickets/{hidden.pk}/edit/",
                    f"/products/{self.p_hidden.pk}/tickets/{hidden.pk}/", f"/products/{self.p_hidden.pk}/tickets/create/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_a_product_url_with_another_products_ticket_is_404(self):
        other = self.make(self.p_hidden)
        self.login("owner")
        self.assertEqual(self.client.get(f"/products/{self.p_open.pk}/tickets/{other.pk}/").status_code, 404)

    def test_another_companys_ticket_is_404(self):
        t = self.make(self.p_foreign)
        self.login("owner")
        self.assertEqual(self.client.get(f"/tickets/{t.pk}/").status_code, 404)

    def test_anonymous_goes_to_login(self):
        t = self.make(self.p_open)
        for url in self.pages(t):
            self.assertEqual(Client().get(url).status_code, 302, url)

    def test_legacy_templates_and_routes_are_gone(self):
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template
        for name in ["tickets/ticket_detail.html", "tickets/ticket_form.html", "products/product_ticket_detail.html", "products/product_ticket_form.html"]:
            with self.assertRaises(TemplateDoesNotExist, msg=name):
                get_template(name)
        for name in ["ticket_priority", "ticket_deadline", "ticket_follow", "ticket_comment", "ticket_delete"]:
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(f"tickets:{name}", kwargs={"pk": 1})

    def test_the_dashboard_endpoints_still_work(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.client.post(f"/tickets/{t.pk}/status/", {"status": "in_progress"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.json(), {"ok": True, "status": "in_progress"})
        r = self.client.post(f"/tickets/{t.pk}/assign/", {"assignees": [self.dev.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(list(t.assignees.all()), [self.dev])
```

- [ ] **Step 2: Run to verify failure**; **Step 3: Implement** the view changes, delete the listed templates, views, routes and the dead htmx; remove `ticket_tags` only if unused. Convert old tests: HTML-asserting tests for detail/form pages are deleted when `apps/uiapi` tests already cover the behaviour (create/edit validation, comments, mentions, follow, deadline, priority, assign, delete rights, assignee drop warning); tests that POST to deleted routes are rewritten against the API or deleted; `test_mentions.py` keeps testing `mentions.py` directly (unchanged). `apps/core/tests.py` and `apps/leave/tests.py` pages used as legacy examples must still use a page that still renders `core/base.html` (they use `/dashboards/` and `/tickets/create/`: change the latter in `apps/leave/tests.py::test_no_page_is_left_with_nothing_highlighted` to another legacy "All errors" or "Products" page such as `/errors/create/` which is already listed, and drop the `/tickets/create/` row).
- [ ] **Step 4: Run to verify pass**: `venv/bin/python manage.py test apps.tickets apps.products apps.core apps.uiapi apps.dashboards apps.errors apps.dsr apps.leave`, then `grep -ro 'hx-[a-z-]*' templates apps --include='*.html' | wc -l` and record the new htmx count in the ledger.
- [ ] **Step 5: Commit** (two commits): `feat(tickets): detail, create and edit served by the React shell` then `chore(tickets): delete legacy detail/form templates, views, routes and htmx`.

---

### Task 11: Parity check, docs, release

**Files:** `context.md`, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, `core/settings.py` (version)

- [ ] **Step 1: Build and run locally against a scratch database** (`seed_data` wipes `db.sqlite3`; use a scratch settings module in the scratchpad directory, `migrate`, `seed_data`, `runserver 8010 --noreload` after `cd frontend && npm run build`). Log in as `owner` and `dev1` (seed password `testpass123`, localhost only) and verify in the browser:
  - [ ] From the board/list, a ticket opens in the new detail page at its old URL (`/tickets/<id>/` and `/products/<pk>/tickets/<id>/`); breadcrumbs, key, title, description, type, product, created time, linked error link (open one to confirm it still goes to the legacy error page).
  - [ ] Status, priority, assignee (auto-save), follow/unfollow (count changes), deadline set and clear: each shows a toast, persists after reload, and the sidebar/product counts and the board reflect it (move to Resolved lowers the open count).
  - [ ] Comments: add one, mention a teammate with `@` autocomplete (keyboard and mouse), the mention is highlighted, the mentioned user (log in as them) gets a "mentioned you" notification in the bell; whitespace-only comment is refused; double click posts once.
  - [ ] "Also viewing": open the same ticket as `owner` in one tab and `dev1` in a private window; each sees the other.
  - [ ] Edit (button and `e`): form prefilled, change fields, save, land on the detail; a blank title shows the error and keeps the values.
  - [ ] Create: from the topbar New menu, `c`, the list's New ticket button, and from a product page (product fixed); with assignees lacking product access a warning toast appears and they are not assigned; the new ticket opens.
  - [ ] Delete from the detail page (as creator and as owner; hidden for others), lands on the right board.
  - [ ] As `dev1`, a ticket in a product they cannot open is "Ticket not found." (and the legacy direct URL 404s).
  - [ ] The legacy home dashboard (`/dashboards/`) "My work"/"attention" status and assign buttons still work.
  - [ ] Phone width (375px): detail, comment box and form usable; no console errors.
- [ ] **Step 2: Full regression**: `venv/bin/python manage.py test apps > /tmp/full-suite.log 2>&1 &`, poll; expect only `test_signup_creates_user`. Also `cd frontend && npm test && npm run build`, and `docker build -t pq-test .`.
- [ ] **Step 3: Docs, release, commit**: `context.md` entry (what moved, API list, the deadline wall-clock rule, kept `ticket_status`/`ticket_assign` and why, deleted files and the htmx count before/after, known minors); update the `CLAUDE.md`/`AGENTS.md` React paragraph ("the whole tickets area is React; dashboards still hx-post to ticket_status and ticket_assign"); `CHANGELOG.md` new minor release (`> In short:` line, bold sentence leads, plain words, e.g. "**A new ticket page.** …", "**Mentions in comments are easier.** …"); bump `APP_VERSION`; run `venv/bin/python manage.py test apps.core`.

```bash
git add -A && git commit -m "docs: React ticket detail and forms; release"
```

---

## Out of scope (next plans)

- Errors (list, detail, create, convert-to-ticket) and products pages; dashboards (home, reports, audit log) which also lets us delete `ticket_status` and `ticket_assign` legacy routes; feedback, automation, DSR; accounts and company screens; attendance, leave, payroll.
- Final removal of htmx, Alpine, `django_htmx`, the legacy CSS and `core/base.html`.
