# React app shell: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy Django shell (sidebar, topbar, search palette, bell, presence, company switcher, toasts, changelog dialog) with a React shell, move `/notifications/` into it, and delete the legacy notifications page. Other pages keep the legacy shell until their own plan.

**Architecture:** A standalone entry template (`uiapi/shell.html`, no legacy CSS or htmx/Alpine) mounts one React app with React Router. A new `GET /ui-api/v1/bootstrap/` supplies everything the old context processors gave templates (user, workspaces, counts, version, nav URLs, pending Django flash messages). Routes the React app owns render inside `AppShell`; every other nav item is a normal link to a legacy page. Presence and live notifications share the existing `/ws/presence/` socket through one client-side manager.

**Tech Stack:** Django 6 + DRF (existing), React 19, TypeScript, React Router, TanStack Query, Tailwind 4, befui components (copied in), Vitest + Testing Library, fake `WebSocket` in tests.

**Spec:** `docs/superpowers/specs/2026-10-12-react-ui-migration-design.md` (section "Scope update", revised order step 1a: the shell). Builds on `docs/superpowers/plans/2026-10-12-react-ui-foundation-notifications-pilot.md` (done, branch `feat/react-ui-pilot`).

## Global Constraints

- Backend stays Python/Django. No change to models, `service.py` rules, `/api/v1/`, `/api/serop/`, or the WebSocket protocol (`/ws/presence/`: client sends `{"type":"activity","path","active"}` and `{"type":"ping"}`; server sends `{"event":"presence","users":[...]}` and `{"event":"notification","notification":{...},"unread":N}`; close codes 4401/4403 mean stop retrying).
- Auth is the session cookie. New endpoints use DRF `SessionAuthentication` (CSRF enforced on POST) via `CompanyAPIView` in `apps/uiapi/views.py`. Every query is scoped to `request.user` and `request.company`; counts go through `accessible_products` exactly as `workspace_context` does today.
- `TIME_ZONE = "Asia/Kolkata"`: send ISO-8601 with offset, format in the browser.
- Test commands: `venv/bin/python manage.py test <label>` (Django runner); `cd frontend && npm test`. Baseline: the full suite has exactly one known failure, `test_signup_creates_user`.
- Nav URLs are never hardcoded in React: the bootstrap response carries them (`urls`, built with `reverse()`), so a URL change cannot drift.
- Exactly one nav item is active at a time (legacy `SidebarActiveStateTest` pinned this): longest URL-prefix match wins.
- Flash messages: the shell must show Django `messages` queued by legacy views that redirect here (bootstrap consumes them once).
- Legacy rules that stay: legacy pages and their shell are untouched in this plan, including `/notifications/feed/`, `/notifications/read-all/`, `/notifications/<id>/open/` (the legacy bell and web-push use them).
- befui components are copied into `frontend/src/components/ui/` and owned by us. The CLI (`npx github:RandomKid24/befui add`) is blocked for the agent by the sandbox; copy from the site (Task 4 step 2) or ask the user to run it.
- Commit after each task. End commit messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- Bootstrap counts must never include tickets/errors from products the user cannot access, nor another company's. Pinned in Task 1.
- Flash messages must show once, not on every refetch and not twice in StrictMode. Pinned in Task 1 (server consumes) and Task 6 (client de-dupes).
- Company switch must reject a company the user is not a member of, and must not change the session on failure. Pinned in Task 2.
- A user with no company opening `/notifications/` must be redirected to company setup, not see a broken shell. Pinned in Task 3.
- Presence: a failed WebSocket twice must fall back to HTTP polling; close code 4401/4403 must stop retrying; the socket must close on page hide. Pinned in Task 8.
- Palette: a result title containing `<script>` or `&` must render as text; empty/1-char query shows pages only; arrow keys wrap. Pinned in Task 9.
- Sidebar: exactly one active item for every URL the legacy sidebar recognised, admin section hidden for non-admins. Pinned in Task 5.
- Session lost (401/403) in any shell request must send the user to login, not leave a dead shell. Pinned in Task 4.
- Back-compat: `/notifications/?filter=unread` opens on Unread. Pinned in Task 10.

---

## File structure

| File | Responsibility |
|---|---|
| `apps/core/context_processors.py` (modify) | extract `nav_counts(user, company, role)`; `workspace_context` calls it |
| `apps/accounts/workspace.py` (create) | `activate_company(request, company_id)`: the one place a session switches company |
| `apps/accounts/views.py` (modify) | `CompanySwitchView` calls `activate_company` |
| `apps/uiapi/views.py`, `urls.py` (modify) | `BootstrapView`, `CompanySwitchAPIView` |
| `apps/uiapi/shell.py` (create) | `render_shell(request)` |
| `templates/uiapi/shell.html` (create) | standalone entry page for the React app |
| `apps/notifications/views.py` (modify) | `ListView` returns the shell; legacy list templates deleted |
| `frontend/src/shell/` | `AppShell.tsx`, `Sidebar.tsx`, `Topbar.tsx`, `nav.ts`, `CompanySwitcher.tsx`, `Bell.tsx`, `PresenceMenu.tsx`, `Palette.tsx`, `NewMenu.tsx`, `AccountMenu.tsx`, `Changelog.tsx`, `ShortcutsHelp.tsx`, `Toaster.tsx` |
| `frontend/src/lib/` | `bootstrap.ts`, `toast.ts`, `presence.ts`, `notifications.ts`, `search.ts`, `api.ts` (extend) |
| `frontend/src/main.tsx`, `routes.tsx` | router + providers |

---

### Task 1: Bootstrap endpoint

**Files:**
- Modify: `apps/core/context_processors.py`, `apps/uiapi/views.py`, `apps/uiapi/urls.py`
- Test: `apps/uiapi/tests.py` (append)

**Interfaces:**
- Produces:
  - `apps.core.context_processors.nav_counts(user, company, role) -> dict` with keys `open_tickets`, `open_errors`, `pending_corrections` (ints; `pending_corrections` is 0 for non-admins).
  - `GET /ui-api/v1/bootstrap/` (name `uiapi:bootstrap`) → `200`:
    ```json
    {"user": {"id": 1, "name": "dev1", "initial": "D", "role": "developer", "role_label": "Developer"},
     "company": {"id": 1, "name": "Acme Corp"},
     "workspaces": [{"company_id": 1, "name": "Acme Corp", "role_label": "Developer", "current": true}],
     "counts": {"open_tickets": 6, "open_errors": 7, "pending_corrections": 0},
     "is_admin": false, "version": "1.12.0", "csrf": "<token>",
     "messages": [{"text": "Switched to Acme.", "tags": "success"}],
     "urls": {"home": "/dashboards/", "...": "..."}}
    ```
  - `urls` keys (all from `reverse`): `home` (`dashboards:index`), `products` (`products:product_list`), `tickets` (`tickets:ticket_board`), `errors` (`errors:error_list`), `reports` (`dashboards:reports`), `automation` (`automation:rule_list`), `cs_hub` (`feedback:cs_hub`), `feedback` (`feedback:survey_list`), `attendance` (`attendance:my_attendance`), `leave` (`leave:my_leave`), `leave_calendar` (`leave:calendar`), `dsr` (`dsr:dsr_sheet`), `payslips` (`payroll:my_payslips`), `team_attendance`, `timesheet`, `corrections` (attendance), `leave_approvals` (`leave:approvals`), `payroll` (`payroll:run_list`), `payroll_setup` (`payroll:profiles`), `leave_policies` (`leave:policies`), `team` (`accounts:team_list`), `audit_log` (`dashboards:audit_log`), `profile` (`accounts:profile`), `logout` (`accounts:logout`), `notifications` (`notifications:list`), `ticket_create` (`tickets:ticket_create`), `leave_apply` (`leave:apply`), `correction_request` (`attendance:correction_request`), `product_create` (`products:product_create`), `search` (`/search/`), `changelog` (`/api/v1/changelog/`), `company_switch` (`uiapi:company_switch`), `bootstrap`.
  - `messages[].tags` is one of `success|error|info|warning` (Django `level_tag`, anything else coerced to `info`).

- [ ] **Step 1: Write the failing tests**

Append to `apps/uiapi/tests.py`:

```python
from django.contrib import messages as dj_messages
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket


class BootstrapTest(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = make("owner", self.acme, "owner")
        self.dev = make("dev", self.acme, "developer")
        self.p_open = Product.objects.create(company=self.acme, name="Open", key="OPN")
        self.p_hidden = Product.objects.create(company=self.acme, name="Hidden", key="HID")
        self.p_other = Product.objects.create(company=self.other, name="Foreign", key="FOR")
        ProductAccess.objects.create(user=self.dev, product=self.p_open)
        for p in (self.p_open, self.p_hidden, self.p_other):
            Ticket.objects.create(company=p.company, product=p, title="t", created_by=self.owner)
        self.url = reverse("uiapi:bootstrap")

    def login(self, name):
        self.client.login(username=name, password="pass1234")
        session = self.client.session
        session[settings.ACTIVE_COMPANY_SESSION_KEY] = self.acme.pk
        session.save()

    def test_shape_and_identity(self):
        self.login("dev")
        data = self.client.get(self.url).json()
        self.assertEqual(data["user"]["name"], "dev")
        self.assertEqual(data["user"]["initial"], "D")
        self.assertEqual(data["user"]["role_label"], "Developer")
        self.assertEqual(data["company"]["name"], "Acme")
        self.assertFalse(data["is_admin"])
        self.assertTrue(data["version"])
        self.assertTrue(data["csrf"])
        self.assertEqual(data["urls"]["tickets"], reverse("tickets:ticket_board"))
        self.assertEqual(data["urls"]["search"], "/search/")
        self.assertEqual(data["workspaces"], [{"company_id": self.acme.pk, "name": "Acme", "role_label": "Developer", "current": True}])

    def test_counts_only_cover_products_the_user_can_open(self):
        self.login("dev")
        self.assertEqual(self.client.get(self.url).json()["counts"]["open_tickets"], 1)

    def test_owner_sees_every_product_in_the_company_but_not_other_companies(self):
        self.login("owner")
        data = self.client.get(self.url).json()
        self.assertEqual(data["counts"]["open_tickets"], 2)
        self.assertTrue(data["is_admin"])

    def test_flash_messages_are_delivered_once(self):
        self.login("dev")
        # queue a message the way a legacy view would, through the session
        self.client.post(reverse("accounts:company_switch"), {"company_id": self.acme.pk})
        first = self.client.get(self.url).json()["messages"]
        again = self.client.get(self.url).json()["messages"]
        self.assertEqual([m["tags"] for m in first], ["success"])
        self.assertEqual(first[0]["text"], "Switched to Acme.")
        self.assertEqual(again, [])

    def test_anonymous_and_no_company_are_403(self):
        self.assertEqual(Client().get(self.url).status_code, 403)
        User.objects.create_user("loner", "l@t.local", "pass1234")
        c = Client(); c.login(username="loner", password="pass1234")
        self.assertEqual(c.get(self.url).status_code, 403)
```

(If `Product` or `Ticket` need other required fields, copy the minimal creation from `apps/tickets/tests/test_tickets.py` `setUp`; the assertions stay.)

- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.uiapi.tests.BootstrapTest`
Expected: FAIL, `NoReverseMatch: 'bootstrap'`.

- [ ] **Step 3: Implement**

`apps/core/context_processors.py`: add above `workspace_context`, and make `workspace_context` use it (keep its `try/except` and the `ctx` key names `nav_open_tickets`, `nav_open_errors`, `nav_pending_corrections` so legacy templates are unchanged):

```python
def nav_counts(user, company, role):
    """Sidebar badge numbers for one person in one workspace. Same rules as the
    legacy sidebar: only products the person can open, 'open' means not
    resolved/closed (tickets) or resolved/ignored (errors)."""
    from apps.attendance.models import AttendanceCorrection
    from apps.ingestion.models import ErrorGroup
    from apps.products.access import accessible_products
    from apps.tickets.models import Ticket

    products = accessible_products(user, company)
    return {
        "open_tickets": Ticket.objects.filter(company=company, product__in=products)
        .exclude(status__in=["resolved", "closed"]).count(),
        "open_errors": ErrorGroup.objects.filter(company=company, product__in=products)
        .exclude(status__in=["resolved", "ignored"]).count(),
        "pending_corrections": AttendanceCorrection.objects.filter(company=company, status="pending").count()
        if role in ("owner", "admin") else 0,
    }
```

In `workspace_context`, replace the body of the `try:` with:

```python
            counts = nav_counts(request.user, company, request.company_role)
            ctx["nav_open_tickets"] = counts["open_tickets"]
            ctx["nav_open_errors"] = counts["open_errors"]
            if request.company_role in ("owner", "admin"):
                ctx["nav_pending_corrections"] = counts["pending_corrections"]
```

`apps/uiapi/views.py`:

```python
from django.conf import settings
from django.contrib import messages as dj_messages
from django.middleware.csrf import get_token
from django.urls import reverse

from apps.core.context_processors import nav_counts

_TAGS = {"success", "error", "info", "warning"}

_URL_NAMES = {
    "home": "dashboards:index", "products": "products:product_list", "tickets": "tickets:ticket_board",
    "errors": "errors:error_list", "reports": "dashboards:reports", "automation": "automation:rule_list",
    "cs_hub": "feedback:cs_hub", "feedback": "feedback:survey_list", "attendance": "attendance:my_attendance",
    "leave": "leave:my_leave", "leave_calendar": "leave:calendar", "dsr": "dsr:dsr_sheet",
    "payslips": "payroll:my_payslips", "team_attendance": "attendance:team_attendance",
    "timesheet": "attendance:timesheet", "corrections": "attendance:corrections",
    "leave_approvals": "leave:approvals", "payroll": "payroll:run_list", "payroll_setup": "payroll:profiles",
    "leave_policies": "leave:policies", "team": "accounts:team_list", "audit_log": "dashboards:audit_log",
    "profile": "accounts:profile", "logout": "accounts:logout", "notifications": "notifications:list",
    "ticket_create": "tickets:ticket_create", "leave_apply": "leave:apply",
    "correction_request": "attendance:correction_request", "product_create": "products:product_create",
    "company_switch": "uiapi:company_switch", "bootstrap": "uiapi:bootstrap",
}


class BootstrapView(CompanyAPIView):
    """Everything the shell needs on first paint. Flash messages queued by a
    legacy view are returned once and cleared (iterating the queue marks them used)."""

    def get(self, request):
        user, company, role = request.user, request.company, request.company_role
        memberships = user.memberships.select_related("company").order_by("company__name")
        flash = [
            {"text": str(m.message), "tags": m.level_tag if m.level_tag in _TAGS else "info"}
            for m in dj_messages.get_messages(request._request)
        ]
        urls = {key: reverse(name) for key, name in _URL_NAMES.items()}
        urls["search"] = "/search/"
        urls["changelog"] = "/api/v1/changelog/"
        name = user.get_full_name() or user.username
        return Response({
            "user": {"id": user.pk, "name": name, "initial": name[:1].upper(), "role": role,
                     "role_label": dict(memberships.model.Role.choices).get(role, role or "Member")},
            "company": {"id": company.pk, "name": company.name},
            "workspaces": [
                {"company_id": m.company_id, "name": m.company.name, "role_label": m.get_role_display(),
                 "current": m.company_id == company.pk}
                for m in memberships
            ],
            "counts": nav_counts(user, company, role),
            "is_admin": role in ("owner", "admin"),
            "version": getattr(settings, "APP_VERSION", "0.0.0"),
            "csrf": get_token(request._request),
            "messages": flash,
            "urls": urls,
        })
```

`apps/uiapi/urls.py`: add `path("bootstrap/", views.BootstrapView.as_view(), name="bootstrap"),`.

(`Membership.Role` is the choices class used by `get_role_display`; if it is named differently, use `m.get_role_display()` on the user's active membership instead. The tests pin the output.)

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.uiapi apps.core apps.notifications`
Expected: PASS (the context-processor change is covered by the existing sidebar tests in `apps.core`).

- [ ] **Step 5: Commit**

```bash
git add apps/core apps/uiapi
git commit -m "feat(uiapi): bootstrap endpoint for the React shell"
```

---

### Task 2: Company switch endpoint

**Files:**
- Create: `apps/accounts/workspace.py`
- Modify: `apps/accounts/views.py` (`CompanySwitchView`), `apps/uiapi/views.py`, `apps/uiapi/urls.py`
- Test: `apps/uiapi/tests.py` (append), existing `apps/accounts` tests must still pass

**Interfaces:**
- Produces:
  - `activate_company(request, company_id) -> Membership | None`: sets `request.session[settings.ACTIVE_COMPANY_SESSION_KEY]` and queues `messages.success("Switched to <name>.")` when the user is a member; otherwise queues `messages.error("Workspace not found.")`, leaves the session untouched and returns `None`.
  - `POST /ui-api/v1/company/switch/` body `{"company_id": <int>}` (name `uiapi:company_switch`) → `200 {"company": {"id", "name"}}`; `404 {"detail": "Workspace not found."}` when not a member / invalid id.

- [ ] **Step 1: Write the failing tests**

```python
class CompanySwitchApiTest(TestCase):
    def setUp(self):
        self.a = Company.objects.create(name="A", slug="a")
        self.b = Company.objects.create(name="B", slug="b")
        self.c = Company.objects.create(name="C", slug="c")
        self.user = make("sam", self.a)
        Membership.objects.create(user=self.user, company=self.b, role="viewer")
        self.client.login(username="sam", password="pass1234")
        self.url = reverse("uiapi:company_switch")

    def test_switches_to_a_company_i_belong_to(self):
        r = self.client.post(self.url, {"company_id": self.b.pk}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["company"]["name"], "B")
        self.assertEqual(self.client.session[settings.ACTIVE_COMPANY_SESSION_KEY], self.b.pk)

    def test_rejects_a_company_i_do_not_belong_to_and_keeps_the_session(self):
        self.client.post(self.url, {"company_id": self.a.pk}, content_type="application/json")
        r = self.client.post(self.url, {"company_id": self.c.pk}, content_type="application/json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.client.session[settings.ACTIVE_COMPANY_SESSION_KEY], self.a.pk)

    def test_garbage_id_is_404_not_500(self):
        r = self.client.post(self.url, {"company_id": "abc"}, content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_csrf_is_enforced(self):
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="sam", password="pass1234")
        self.assertEqual(strict.post(self.url, {"company_id": self.b.pk}, content_type="application/json").status_code, 403)

    def test_legacy_view_still_switches(self):
        self.client.post(reverse("accounts:company_switch"), {"company_id": self.b.pk})
        self.assertEqual(self.client.session[settings.ACTIVE_COMPANY_SESSION_KEY], self.b.pk)
```

- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.uiapi.tests.CompanySwitchApiTest`
Expected: FAIL, `NoReverseMatch: 'company_switch'`.

- [ ] **Step 3: Implement**

`apps/accounts/workspace.py`:

```python
from django.conf import settings
from django.contrib import messages

from apps.accounts.models import Membership


def activate_company(request, company_id):
    """Make `company_id` the active workspace for this session if the user is a
    member. The one place a session switches company, shared by the classic view
    and the JSON API."""
    try:
        membership = Membership.objects.select_related("company").filter(
            user=request.user, company_id=int(company_id)
        ).first()
    except (TypeError, ValueError):
        membership = None
    if not membership:
        messages.error(request, "Workspace not found.")
        return None
    request.session[settings.ACTIVE_COMPANY_SESSION_KEY] = membership.company_id
    messages.success(request, f"Switched to {membership.company.name}.")
    return membership
```

`apps/accounts/views.py` `CompanySwitchView.post` becomes:

```python
    def post(self, request):
        activate_company(request, request.POST.get("company_id"))
        return redirect("accounts:dashboard")
```

(import `activate_company` from `apps.accounts.workspace`; remove now-unused imports only if nothing else uses them.)

`apps/uiapi/views.py`:

```python
from rest_framework.exceptions import NotFound
from apps.accounts.workspace import activate_company


class CompanySwitchAPIView(APIView):
    """Not a `CompanyAPIView`: switching must work even if the current company is gone."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership = activate_company(request._request, request.data.get("company_id"))
        if membership is None:
            raise NotFound("Workspace not found.")
        return Response({"company": {"id": membership.company_id, "name": membership.company.name}})
```

`apps/uiapi/urls.py`: `path("company/switch/", views.CompanySwitchAPIView.as_view(), name="company_switch"),`.

Note on the `404` case: `activate_company` queued an error message; the test asserts only status and session. The message is harmless (shown on the next page) and matches the legacy behaviour.

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.uiapi apps.accounts`
Expected: PASS (only the known signup failure may appear in `apps.accounts`).

- [ ] **Step 5: Commit**

```bash
git add apps/accounts apps/uiapi
git commit -m "feat(uiapi): company switch endpoint sharing activate_company with the classic view"
```

---

### Task 3: Shell entry page

**Files:**
- Create: `apps/uiapi/shell.py`, `templates/uiapi/shell.html`
- Modify: `apps/notifications/views.py` (`ListView`)
- Test: `apps/uiapi/tests.py` (replace the notifications switch tests)

**Interfaces:**
- Produces:
  - `render_shell(request) -> HttpResponse`: renders `uiapi/shell.html` with `frontend_built`.
  - Shell contract: `<div id="root" class="befui" data-csrf="…" data-bootstrap="/ui-api/v1/bootstrap/">` plus `<link href="/ui/app.css">` and `<script type="module" src="/ui/app.js">`. No legacy CSS, htmx or Alpine on this page.
  - `/notifications/` always returns the shell (members only: `CompanyMemberRequiredMixin` still redirects anonymous users to login and no-company users to company setup).

- [ ] **Step 1: Write the failing tests**

Replace `NotificationsPageSwitchTest` in `apps/uiapi/tests.py` with:

```python
class ShellPageTest(TestCase):
    def setUp(self):
        co = Company.objects.create(name="Acme", slug="acme")
        make("bob", co)
        self.dist = Path(tempfile.mkdtemp())
        (self.dist / "app.js").write_text("")

    def test_notifications_renders_the_standalone_shell(self):
        self.client.login(username="bob", password="pass1234")
        with override_settings(FRONTEND_DIST=self.dist):
            response = self.client.get("/notifications/")
        self.assertTemplateUsed(response, "uiapi/shell.html")
        self.assertTemplateNotUsed(response, "core/base.html")
        self.assertContains(response, 'id="root"')
        self.assertContains(response, 'data-csrf="')
        self.assertContains(response, "/ui/app.js")
        self.assertNotContains(response, "htmx")
        self.assertNotContains(response, "alpinejs")

    def test_a_missing_build_says_so(self):
        self.client.login(username="bob", password="pass1234")
        with override_settings(FRONTEND_DIST=Path("/nonexistent")):
            self.assertContains(self.client.get("/notifications/"), "frontend has not been built")

    def test_anonymous_goes_to_login(self):
        response = Client().get("/notifications/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_no_company_goes_to_company_setup(self):
        User.objects.create_user("loner", "l@t.local", "pass1234")
        c = Client(); c.login(username="loner", password="pass1234")
        response = c.get("/notifications/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/company/setup/", response["Location"])
```

- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.uiapi.tests.ShellPageTest`
Expected: FAIL (`uiapi/shell.html` not used).

- [ ] **Step 3: Implement**

`apps/uiapi/shell.py`:

```python
from django.conf import settings
from django.shortcuts import render


def render_shell(request):
    """The standalone page that boots the React app. Callers must already have
    checked the visitor (login, company); this only renders."""
    return render(request, "uiapi/shell.html", {
        "frontend_built": (settings.FRONTEND_DIST / "app.js").is_file(),
    })
```

`templates/uiapi/shell.html` (head copied from `core/base.html` lines 6-19, minus the Google font preconnect, which the React CSS does not need):

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PQ Platform</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#ffffff">
<meta name="color-scheme" content="light">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="PQ Platform">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/brand/apple-touch-icon.png">
{% if frontend_built %}<link rel="stylesheet" href="/ui/app.css">{% endif %}
</head>
<body>
{% if frontend_built %}
<div id="root" class="befui" data-csrf="{{ csrf_token }}" data-bootstrap="/ui-api/v1/bootstrap/"></div>
<script type="module" src="/ui/app.js"></script>
{% else %}
<p style="font:14px system-ui;padding:24px">
  The new frontend has not been built. Run <code>cd frontend &amp;&amp; npm run build</code>.
</p>
{% endif %}
</body>
</html>
```

`apps/notifications/views.py` `ListView.get` becomes:

```python
    def get(self, request):
        return render_shell(request)
```

with `from apps.uiapi.shell import render_shell`. Leave `templates/notifications/list.html` and `list_react.html` in place until Task 10 (the React route does not exist yet).

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.uiapi apps.notifications`
Expected: PASS. Remove or update any notifications test that asserted the old list template (they assert `notifications/list.html`); `apps/notifications/tests.py::ViewsTest` has none for the list page today, confirm with `grep -n "notifications:list" apps/notifications/tests.py`.

- [ ] **Step 5: Commit**

```bash
git add apps/uiapi apps/notifications templates/uiapi
git commit -m "feat(uiapi): standalone shell entry page; notifications list serves it"
```

---

### Task 4: Frontend foundation: router, bootstrap, befui parts

**Files:**
- Create: `frontend/src/lib/bootstrap.ts`, `frontend/src/lib/bootstrap.test.ts`, `frontend/src/routes.tsx`, `frontend/src/components/ui/{dropdown-menu,popover,dialog,tooltip,avatar,kbd}.tsx` (copied)
- Modify: `frontend/package.json` (deps), `frontend/src/main.tsx`, `frontend/src/lib/api.ts` (generic `api`), `frontend/src/index.css`

**Interfaces:**
- Consumes: `hooks.onAuthLost`, `configure` from the pilot's `api.ts`.
- Produces:
  - `type Bootstrap` (shape in Task 1) exported from `lib/bootstrap.ts`.
  - `useBootstrap(): UseQueryResult<Bootstrap>` (query key `['bootstrap']`, `refetchInterval: 60_000`, refetch on focus) and `useBootstrapData(): Bootstrap` (throws if not loaded; used inside the shell after the gate).
  - `api.get<T>(path)`, `api.post<T>(path, body?)` in `lib/api.ts`: same-origin, JSON, `X-CSRFToken`, 401/403 call `hooks.onAuthLost()`, other non-2xx throw `Error('Request failed (N)')`. `getNotifications`/`markAllRead` are re-expressed with them; their tests keep passing.
  - `routes.tsx` exports `shellRoutes: RouteObject[]` (this task: only a placeholder for `/notifications/`).

- [ ] **Step 1: Install and copy befui parts**

```bash
cd frontend
npm i react-router-dom
```

Copy these befui components (each page shows its source and its `npm i` line; install the Radix packages named there):

```text
dropdown-menu  popover  dialog (Dialog and Sheet)  tooltip  avatar  kbd
```

For each name `N`, with the Browser tool: navigate to `https://befui.vercel.app/#/components/N`, run

```js
[...document.querySelectorAll('pre')].map(p => p.innerText).filter(t => t.includes('export')).slice(-1)[0]
```

and write the result to `frontend/src/components/ui/N.tsx`. Replace any import of befui's own `./icons` with `lucide-react` icons (as was done for Button). If the user has run `cd frontend && npx github:RandomKid24/befui add dropdown-menu popover dialog tooltip avatar kbd`, use that output instead. Run `npm run build`; it must pass. Record in the ledger which route was used.

- [ ] **Step 2: Write the failing tests**

`frontend/src/lib/bootstrap.test.ts`:

```ts
import { afterEach, expect, it, vi } from 'vitest';
import { api, configure, hooks } from './api';

afterEach(() => vi.restoreAllMocks());

it('api.post sends JSON with the CSRF token', async () => {
  configure({ api: '/ui-api/v1/', csrf: 'tok' });
  const f = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
  await api.post('company/switch/', { company_id: 3 });
  const init = f.mock.calls[0][1]!;
  expect(f.mock.calls[0][0]).toBe('/ui-api/v1/company/switch/');
  expect(init.method).toBe('POST');
  expect(init.body).toBe(JSON.stringify({ company_id: 3 }));
  expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('tok');
});

it('a lost session on any call goes through the auth hook', async () => {
  const lost = vi.fn();
  hooks.onAuthLost = lost;
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 401 }));
  await expect(api.get('bootstrap/')).rejects.toThrow('401');
  expect(lost).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL, `api` is not exported.

- [ ] **Step 4: Implement**

`frontend/src/lib/api.ts`: keep the existing exports and add (refactoring `request` to serve both):

```ts
export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};
```

`frontend/src/lib/bootstrap.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export type FlashMessage = { text: string; tags: 'success' | 'error' | 'info' | 'warning' };
export type Bootstrap = {
  user: { id: number; name: string; initial: string; role: string | null; role_label: string };
  company: { id: number; name: string };
  workspaces: { company_id: number; name: string; role_label: string; current: boolean }[];
  counts: { open_tickets: number; open_errors: number; pending_corrections: number };
  is_admin: boolean;
  version: string;
  csrf: string;
  messages: FlashMessage[];
  urls: Record<string, string>;
};

export const useBootstrap = () =>
  useQuery({ queryKey: ['bootstrap'], queryFn: () => api.get<Bootstrap>('bootstrap/'), refetchInterval: 60_000, staleTime: 30_000 });

export function useBootstrapData(): Bootstrap {
  const { data } = useBootstrap();
  if (!data) throw new Error('Bootstrap not loaded');
  return data;
}
```

`frontend/src/routes.tsx` (placeholder; Task 10 fills it):

```tsx
import type { RouteObject } from 'react-router-dom';

export const shellRoutes: RouteObject[] = [];
```

`frontend/src/main.tsx` is rewritten in Task 5 (the AppShell). For now only ensure it still builds.

`frontend/src/index.css`: no change yet (cleanup happens in Task 10).

- [ ] **Step 5: Run to verify pass**

Run: `cd frontend && npm test && npm run build`
Expected: all pass; build clean.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): router, bootstrap query, api helper, befui menu/dialog parts"
```

---

### Task 5: Nav config, Sidebar and AppShell

**Files:**
- Create: `frontend/src/shell/nav.ts`, `nav.test.ts`, `Sidebar.tsx`, `AppShell.tsx`, `CompanySwitcher.tsx`, `AppShell.test.tsx`
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Consumes: `Bootstrap` and `useBootstrapData` (Task 4).
- Produces:
  - `navSections(b: Bootstrap): NavSection[]` where `NavSection = { label?: string; items: NavItem[] }`, `NavItem = { key: string; label: string; href: string; icon: LucideIcon; badge?: number; react: boolean }`. Admin section only when `b.is_admin`. `react` is true for hrefs in `REACT_PATHS` (exported `Set`, this plan: `/notifications/` only matters for the bell; no sidebar item points at it).
  - `activeKey(pathname: string, sections: NavSection[]): string | null`: item whose `href` is the longest prefix of `pathname` (ties: none); `null` if nothing matches.
  - `AppShell({ children })`: layout with `Sidebar`, `Topbar` (Task 6 to 9 fill it), and a `<main>`; sidebar collapse persisted in `localStorage['pqSidebarCollapsed']` (same key as legacy), mobile drawer (`sidebarOpen` state, backdrop, Escape closes).

- [ ] **Step 1: Write the failing tests**

`nav.test.ts`:

```ts
import { expect, it } from 'vitest';
import { activeKey, navSections } from './nav';
import type { Bootstrap } from '@/lib/bootstrap';

const urls = {
  home: '/dashboards/', products: '/products/', tickets: '/tickets/', errors: '/errors/', reports: '/dashboards/reports/',
  automation: '/automation/', cs_hub: '/feedback/', feedback: '/feedback/surveys/', attendance: '/attendance/',
  leave: '/leave/', leave_calendar: '/leave/calendar/', dsr: '/dsr/', payslips: '/payroll/me/',
  team_attendance: '/attendance/team/', timesheet: '/attendance/timesheet/', corrections: '/attendance/corrections/',
  leave_approvals: '/leave/approvals/', payroll: '/payroll/', payroll_setup: '/payroll/profiles/',
  leave_policies: '/leave/policies/', team: '/team/', audit_log: '/dashboards/audit-log/',
};
const boot = (over: Partial<Bootstrap> = {}): Bootstrap => ({
  user: { id: 1, name: 'A', initial: 'A', role: 'developer', role_label: 'Developer' },
  company: { id: 1, name: 'Acme' }, workspaces: [], counts: { open_tickets: 6, open_errors: 0, pending_corrections: 2 },
  is_admin: false, version: '1.0.0', csrf: 't', messages: [], urls, ...over,
});

it('hides the admin section from non-admins and shows it to admins', () => {
  const labels = (b: Bootstrap) => navSections(b).map((s) => s.label);
  expect(labels(boot())).not.toContain('Admin');
  expect(labels(boot({ is_admin: true }))).toContain('Admin');
});

it('puts counts on the right items and hides zero badges', () => {
  const items = navSections(boot({ is_admin: true })).flatMap((s) => s.items);
  expect(items.find((i) => i.key === 'tickets')?.badge).toBe(6);
  expect(items.find((i) => i.key === 'errors')?.badge).toBeUndefined();
  expect(items.find((i) => i.key === 'corrections')?.badge).toBe(2);
});

it('exactly one item is active, and the longest prefix wins', () => {
  const sections = navSections(boot({ is_admin: true }));
  const cases: Record<string, string> = {
    '/dashboards/': 'home', '/dashboards/reports/': 'reports', '/tickets/12/': 'tickets',
    '/attendance/': 'attendance', '/attendance/team/': 'team_attendance', '/attendance/timesheet/3/': 'timesheet',
    '/leave/': 'leave', '/leave/calendar/': 'leave_calendar', '/leave/approvals/4/': 'leave_approvals',
    '/payroll/': 'payroll', '/payroll/profiles/': 'payroll_setup', '/payroll/me/': 'payslips',
  };
  for (const [path, key] of Object.entries(cases)) expect(activeKey(path, sections), path).toBe(key);
  expect(activeKey('/somewhere/else/', sections)).toBeNull();
});
```

`AppShell.test.tsx`:

```tsx
import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './AppShell';
import * as bootstrap from '@/lib/bootstrap';
import { sampleBootstrap } from '@/test-fixtures';

it('renders the nav, marks the current page, and collapses and remembers it', async () => {
  vi.spyOn(bootstrap, 'useBootstrapData').mockReturnValue(sampleBootstrap());
  localStorage.clear();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/tickets/']}>
        <AppShell><p>content</p></AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByRole('link', { name: /all tickets/i })).toHaveAttribute('aria-current', 'page');
  expect(screen.getAllByRole('link', { current: 'page' })).toHaveLength(1);
  expect(screen.getByText('content')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /collapse/i }));
  expect(localStorage.getItem('pqSidebarCollapsed')).toBe('1');
});
```

`frontend/src/test-fixtures.ts` (create) exports `sampleBootstrap(over?)` returning the `boot()` object above plus `urls` for every key in Task 1 (so Topbar tests can reuse it).

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement**

`nav.ts`:

```ts
import { Banknote, CalendarDays, ChartColumn, CircleCheck, ClipboardList, Clock, FileText, Headset, History, House, Package, Percent, SlidersHorizontal, Sparkles, Ticket, TriangleAlert, User, Users, Wallet, type LucideIcon } from 'lucide-react';
import type { Bootstrap } from '@/lib/bootstrap';

export type NavItem = { key: string; label: string; href: string; icon: LucideIcon; badge?: number; react: boolean };
export type NavSection = { label?: string; items: NavItem[] };

// Paths the React router owns. Everything else is a normal link to a legacy page.
export const REACT_PATHS = new Set<string>([]);

const item = (b: Bootstrap, key: string, label: string, icon: LucideIcon, badge?: number): NavItem => ({
  key, label, icon, href: b.urls[key], badge: badge || undefined, react: REACT_PATHS.has(b.urls[key]),
});

export function navSections(b: Bootstrap): NavSection[] {
  const sections: NavSection[] = [
    { items: [
      item(b, 'home', 'Home', House),
      item(b, 'products', 'Products', Package),
      item(b, 'tickets', 'All tickets', Ticket, b.counts.open_tickets),
      item(b, 'errors', 'All errors', TriangleAlert, b.counts.open_errors),
      item(b, 'reports', 'Reports', ChartColumn),
      item(b, 'automation', 'All automation', Sparkles),
    ] },
    { label: 'Operations', items: [
      item(b, 'cs_hub', 'CS Hub', Headset),
      item(b, 'feedback', 'All feedback', FileText),
      item(b, 'attendance', 'My attendance', Clock),
      item(b, 'leave', 'My leave', CalendarDays),
      item(b, 'leave_calendar', 'Leave calendar', CalendarDays),
      item(b, 'dsr', 'DSR Sheet', ClipboardList),
      item(b, 'payslips', 'My payslips', Banknote),
    ] },
  ];
  if (b.is_admin) {
    sections.push({ label: 'Admin', items: [
      item(b, 'team_attendance', 'Team attendance', Users),
      item(b, 'timesheet', 'Timesheet', CalendarDays),
      item(b, 'corrections', 'Corrections', Clock, b.counts.pending_corrections),
      item(b, 'leave_approvals', 'Leave approvals', CircleCheck),
      item(b, 'payroll', 'Payroll', Wallet),
      item(b, 'payroll_setup', 'Payroll setup', Percent),
      item(b, 'leave_policies', 'Leave Policy', SlidersHorizontal),
      item(b, 'team', 'Team', User),
      item(b, 'audit_log', 'Audit log', History),
    ] });
  }
  return sections;
}

// One item is active: the one whose URL is the longest prefix of the path. A
// substring test would light several up at once (the bug the legacy sidebar had).
export function activeKey(pathname: string, sections: NavSection[]): string | null {
  let best: NavItem | null = null;
  for (const it of sections.flatMap((s) => s.items)) {
    if (pathname.startsWith(it.href) && (!best || it.href.length > best.href.length)) best = it;
  }
  return best?.key ?? null;
}
```

`Sidebar.tsx`: renders brand, `CompanySwitcher`, each section with `NavLink`-like items (`<Link>` when `item.react`, otherwise `<a href>`), `aria-current="page"` on the active one, badge pills, footer with "What's new v{version}" button (opens the Changelog dialog, Task 9), "Install app" button (Task 9), and a "Collapse" `<button aria-label="Collapse sidebar">`. Props: `{ collapsed: boolean; onToggle(): void; open: boolean; onClose(): void; onOpenChangelog(): void }`. Collapsed shows icons only with `title` tooltips (befui Tooltip). Match the legacy proportions (232px wide, 64px collapsed); use tokens only.

`CompanySwitcher.tsx`: befui `DropdownMenu` listing `workspaces` (current one disabled with a check); selecting another calls `api.post('company/switch/', { company_id })` then `window.location.assign(urls.home)`; failure shows a toast (Task 6 provides `toast`; until then `console.error`, replaced in Task 6 step 3).

`AppShell.tsx`:

```tsx
import { useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

const KEY = 'pqSidebarCollapsed';
const read = () => { try { return localStorage.getItem(KEY) === '1'; } catch { return false; } };

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(read);
  const [open, setOpen] = useState(false);
  const [changelog, setChangelog] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const toggle = () => setCollapsed((c) => {
    try { localStorage.setItem(KEY, c ? '0' : '1'); } catch { /* private mode */ }
    return !c;
  });
  return (
    <div className="flex min-h-screen bg-muted text-foreground">
      <Sidebar collapsed={collapsed} onToggle={toggle} open={open} onClose={() => setOpen(false)} onOpenChangelog={() => setChangelog(true)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenNav={() => setOpen(true)} changelogOpen={changelog} onChangelogOpenChange={setChangelog} />
        <main className="mx-auto w-full max-w-6xl flex-1 p-6 max-md:p-4">{children}</main>
      </div>
    </div>
  );
}
```

`Topbar.tsx` is created here as a stub that renders the company/product title and the burger button (`aria-label="Open navigation"`), so `AppShell` compiles; Tasks 6 to 9 add the rest. Its props `{ onOpenNav, changelogOpen, onChangelogOpenChange }` are final.

`main.tsx`:

```tsx
import './index.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { configure } from '@/lib/api';
import { useBootstrap } from '@/lib/bootstrap';
import { AppShell } from '@/shell/AppShell';
import { shellRoutes } from '@/routes';

function Gate() {
  const boot = useBootstrap();
  if (boot.isPending) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  if (boot.isError) return <div className="p-6 text-sm">Couldn’t load the app. <button className="underline" onClick={() => boot.refetch()}>Try again</button></div>;
  return (
    <AppShell>
      <Routes>
        {shellRoutes.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
        <Route path="*" element={<p className="text-sm text-muted-foreground">Page not found.</p>} />
      </Routes>
    </AppShell>
  );
}

const el = document.getElementById('root');
if (el) {
  configure({ api: '/ui-api/v1/', csrf: el.dataset.csrf ?? '' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } });
  createRoot(el).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <BrowserRouter><Gate /></BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}
```

Note: the pilot's `main.tsx` mounted by `#react-root` and `data-page`; this replaces it. The legacy `list_react.html` (which used `#react-root`) is deleted in Task 10; until then it is unreachable because `ListView` already returns the shell (Task 3).

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): nav config, sidebar, app shell with collapse and company switcher"
```

---

### Task 6: Toasts and flash messages

**Files:**
- Create: `frontend/src/lib/toast.ts`, `frontend/src/lib/toast.test.ts`, `frontend/src/shell/Toaster.tsx`, `frontend/src/shell/Toaster.test.tsx`
- Modify: `frontend/src/main.tsx` (mount `Toaster`, deliver flash messages), `frontend/src/shell/CompanySwitcher.tsx` (use `toast`), `frontend/src/pages/Notifications.tsx` (use `toast`)

**Interfaces:**
- Produces:
  - `toast(text: string, tags?: 'success' | 'error' | 'info' | 'warning'): void`; `useToasts(): Toast[]`; `dismiss(id: number)`. Auto-dismiss after 4000 ms. A tiny external store (`useSyncExternalStore`), no provider.
  - `showFlash(messages: FlashMessage[])`: shows each message once per page load, de-duplicated by a module-level `Set` of delivered bootstrap payload fingerprints (so StrictMode's double effect and bootstrap refetches do not repeat them).
  - `<Toaster />`: fixed bottom-right stack, `role="status"` / `aria-live="polite"`; colours from tokens (`success`, `destructive`, `info`, `warning`).
  - The window event `django-message` is no longer used by React code. (Legacy pages keep their own Alpine toaster.)

- [ ] **Step 1: Write the failing tests**

`toast.test.ts`:

```ts
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { _reset, dismiss, showFlash, toast, useToasts } from './toast';

beforeEach(() => { vi.useFakeTimers(); _reset(); });
afterEach(() => vi.useRealTimers());

it('shows a toast and auto-dismisses it after 4s', () => {
  const { result } = renderHook(() => useToasts());
  act(() => toast('Saved.', 'success'));
  expect(result.current.map((t) => t.text)).toEqual(['Saved.']);
  act(() => { vi.advanceTimersByTime(4001); });
  expect(result.current).toEqual([]);
});

it('dismiss removes one toast', () => {
  const { result } = renderHook(() => useToasts());
  act(() => { toast('a'); toast('b'); });
  act(() => dismiss(result.current[0].id));
  expect(result.current.map((t) => t.text)).toEqual(['b']);
});

it('flash messages are delivered once even if the same payload arrives twice', () => {
  const { result } = renderHook(() => useToasts());
  const payload = [{ text: 'Switched to Acme.', tags: 'success' as const }];
  act(() => { showFlash(payload); showFlash(payload); });
  expect(result.current).toHaveLength(1);
});

it('an empty flash list is a no-op', () => {
  const { result } = renderHook(() => useToasts());
  act(() => showFlash([]));
  expect(result.current).toEqual([]);
});
```

`Toaster.test.tsx`: render `<Toaster />`, call `toast('Hello', 'error')` inside `act`, expect `getByText('Hello')` inside a `role="status"` region.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement**

`toast.ts`:

```ts
import { useSyncExternalStore } from 'react';
import type { FlashMessage } from './bootstrap';

export type Tags = 'success' | 'error' | 'info' | 'warning';
export type Toast = { id: number; text: string; tags: Tags };

let items: Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();
const delivered = new Set<string>();
const emit = () => listeners.forEach((l) => l());

export function dismiss(id: number) {
  items = items.filter((t) => t.id !== id);
  emit();
}

export function toast(text: string, tags: Tags = 'info') {
  const id = nextId++;
  items = [...items, { id, text, tags }];
  emit();
  setTimeout(() => dismiss(id), 4000);
}

export function showFlash(messages: FlashMessage[]) {
  if (!messages.length) return;
  const fingerprint = JSON.stringify(messages);
  if (delivered.has(fingerprint)) return;
  delivered.add(fingerprint);
  messages.forEach((m) => toast(m.text, m.tags));
}

export const useToasts = () =>
  useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => items);

export function _reset() { items = []; delivered.clear(); emit(); }
```

`Toaster.tsx`: maps `useToasts()` to `<div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">` with one `<div>` per toast (`border`, `bg-card`, a coloured left bar by `tags`, a dismiss `×` button). Also registers `online`/`offline` window listeners once: offline → `toast('You are offline. Changes will not save until you reconnect.', 'error')`, online → `toast('Back online.', 'success')` (ported from base.html).

`main.tsx` `Gate`: after bootstrap loads, `useEffect(() => { showFlash(boot.data.messages) }, [boot.data])`; render `<Toaster />` next to `AppShell`. Replace `window.dispatchEvent(new CustomEvent('django-message', …))` in `Notifications.tsx` with `toast(text, tags)` and update `Notifications.test.tsx` expectations (the toast test asserts via `useToasts`/`getByText` with `<Toaster />` rendered, or via `vi.spyOn` of the module). In `CompanySwitcher.tsx`, on error call `toast('Could not switch workspace.', 'error')`.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): toast store, Toaster, flash messages from bootstrap"
```

---

### Task 7: Realtime socket manager and notifications bell

**Files:**
- Create: `frontend/src/lib/presence.ts`, `frontend/src/lib/presence.test.ts` (Task 8 extends both), `frontend/src/lib/notifications.ts`, `frontend/src/lib/notifications.test.ts`, `frontend/src/shell/Bell.tsx`, `frontend/src/shell/Bell.test.tsx`
- Modify: `frontend/src/lib/api.ts` (add `getFeed`, `markAllReadFeed` if not reusing the new API), `frontend/src/shell/Topbar.tsx`

**Interfaces:**
- Produces:
  - `lib/presence.ts` (this task: the connection core; Task 8 adds polling and activity):
    - `type PresenceUser = { user_id: number; name: string; status: 'online' | 'away' | string; activity?: string; clocked_in_at?: string | null; tickets_in_progress?: number }`.
    - `type ServerEvent = { event: 'presence'; users: PresenceUser[] } | { event: 'notification'; notification: Notice; unread: number }`.
    - `socket.subscribe(fn: (e: ServerEvent) => void): () => void`, `socket.start()`, `socket.stop()`, `socket.onStatus(fn: (s: 'connecting' | 'live' | 'polling' | 'offline') => void)`. One WebSocket to `${ws|wss}://${host}/ws/presence/` for the whole tab; reconnect with `min(30000, 1000 * 2 ** retry)` backoff; close codes 4401/4403 set `offline` and stop retrying.
  - `lib/notifications.ts`:
    - `useBell(): { unread: number; items: Notice[]; loaded: boolean; markAllRead(): void }`: initial `GET /notifications/feed/` (existing endpoint, returns `{unread, items}` with `url` = `/notifications/<id>/open/`), live updates from `socket` `notification` events (prepend, cap 15, set `unread`), and **invalidates `['notifications']`** so an open Notifications page refreshes. Mark all read POSTs `/ui-api/v1/notifications/read-all/` and sets all local items `read: true`, `unread: 0`, and invalidates `['notifications']`.
    - New-notification side effects: `toast(notification.title, 'success')`; if `document.hidden` and `Notification.permission === 'granted'`, `new Notification(title, { body, icon: '/brand/pwa-192.png' })`.
    - `usePush(): { supported: boolean; on: boolean; enable(): Promise<void> }` using the existing `/notifications/push/subscribe/` and the public VAPID key from `bootstrap.vapid_key` (add `"vapid_key": settings.WEBPUSH_VAPID_PUBLIC_KEY` to the bootstrap response in this task, with a test).
  - `Bell` component: bell button with unread badge (`99+` cap), popover with header "Notifications" and "Mark all read" (only when unread > 0), list of items (`<a href={n.url}>`), "You are all caught up." / "Loading…" empty states, footer "See all" (`<Link to={urls.notifications}>`) and "Turn on alerts" (only when push is supported and off).

- [ ] **Step 1: Write the failing tests**

`presence.test.ts` (fake WebSocket):

```ts
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { socket, _resetSocket } from './presence';

class FakeWS {
  static instances: FakeWS[] = [];
  readyState = 0; sent: string[] = [];
  onopen: (() => void) | null = null; onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor(public url: string) { FakeWS.instances.push(this); }
  send(d: string) { this.sent.push(d); }
  close() { this.readyState = 3; this.onclose?.({ code: 1000 }); }
  open() { this.readyState = 1; this.onopen?.(); }
  push(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}
beforeEach(() => { vi.useFakeTimers(); FakeWS.instances = []; vi.stubGlobal('WebSocket', FakeWS); _resetSocket(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it('connects to /ws/presence/ and relays server events to subscribers', () => {
  const seen: unknown[] = [];
  socket.subscribe((e) => seen.push(e));
  socket.start();
  FakeWS.instances[0].open();
  expect(FakeWS.instances[0].url).toMatch(/^wss?:\/\/.+\/ws\/presence\/$/);
  FakeWS.instances[0].push({ event: 'presence', users: [] });
  FakeWS.instances[0].push({ event: 'notification', notification: { id: 1 }, unread: 3 });
  expect(seen).toHaveLength(2);
});

it('ignores malformed frames', () => {
  const seen: unknown[] = [];
  socket.subscribe((e) => seen.push(e));
  socket.start();
  FakeWS.instances[0].open();
  FakeWS.instances[0].onmessage?.({ data: 'not json' });
  expect(seen).toEqual([]);
});

it('reconnects with backoff after a drop', () => {
  socket.start();
  FakeWS.instances[0].open();
  FakeWS.instances[0].onclose?.({ code: 1006 });
  vi.advanceTimersByTime(2100);
  expect(FakeWS.instances).toHaveLength(2);
});

it('stops retrying on 4401 and 4403', () => {
  const statuses: string[] = [];
  socket.onStatus((s) => statuses.push(s));
  socket.start();
  FakeWS.instances[0].onclose?.({ code: 4403 });
  vi.advanceTimersByTime(60000);
  expect(FakeWS.instances).toHaveLength(1);
  expect(statuses.at(-1)).toBe('offline');
});
```

`notifications.test.ts` (renderHook with a QueryClientProvider wrapper; mock `api.get` for the feed, `socket` for events):
- initial feed fills `items` and `unread` and sets `loaded`;
- a socket `notification` event prepends, caps at 15, sets `unread`, calls `toast`, and invalidates `['notifications']`;
- `markAllRead` calls `POST notifications/read-all/` and zeroes everything.

`Bell.test.tsx`: renders with mocked `useBell`; asserts badge `99+` for 150, no badge for 0, "Mark all read" only when unread, item links use `n.url`, "You are all caught up." when loaded and empty, and "Turn on alerts" only when push is supported and off.

Backend test (append to `BootstrapTest`): `data["vapid_key"] == settings.WEBPUSH_VAPID_PUBLIC_KEY` (use `override_settings(WEBPUSH_VAPID_PUBLIC_KEY="abc")`).

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test` and `venv/bin/python manage.py test apps.uiapi.tests.BootstrapTest`
Expected: FAIL.

- [ ] **Step 3: Implement**

`presence.ts` (connection core only; no `activity` sending yet):

```ts
import type { Notice } from './api';

export type PresenceUser = { user_id: number; name: string; status: string; activity?: string; clocked_in_at?: string | null; tickets_in_progress?: number };
export type ServerEvent =
  | { event: 'presence'; users: PresenceUser[] }
  | { event: 'notification'; notification: Notice; unread: number };
export type Status = 'connecting' | 'live' | 'polling' | 'offline';

let ws: WebSocket | null = null;
let retry = 0;
let started = false;
let status: Status = 'connecting';
let timer: ReturnType<typeof setTimeout> | undefined;
const subs = new Set<(e: ServerEvent) => void>();
const statusSubs = new Set<(s: Status) => void>();

const setStatus = (s: Status) => { status = s; statusSubs.forEach((f) => f(s)); };

function connect() {
  const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
  const sock = new WebSocket(`${proto}${location.host}/ws/presence/`);
  ws = sock;
  sock.onopen = () => { retry = 0; setStatus('live'); };
  sock.onmessage = (e) => {
    let msg: ServerEvent;
    try { msg = JSON.parse(e.data); } catch { return; }
    subs.forEach((f) => f(msg));
  };
  sock.onclose = (e) => {
    ws = null;
    if (!started) return;
    // 4401/4403: signed out or no workspace. Retrying cannot help.
    if (e.code === 4401 || e.code === 4403) { setStatus('offline'); return; }
    retry += 1;
    timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry));
  };
}

export const socket = {
  subscribe(fn: (e: ServerEvent) => void) { subs.add(fn); return () => { subs.delete(fn); }; },
  onStatus(fn: (s: Status) => void) { statusSubs.add(fn); fn(status); return () => { statusSubs.delete(fn); }; },
  send(obj: unknown) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); },
  get open() { return !!ws && ws.readyState === 1; },
  start() { if (started) return; started = true; connect(); },
  stop() { started = false; clearTimeout(timer); ws?.close(); },
};

export function _resetSocket() {
  started = false; retry = 0; clearTimeout(timer); ws = null; status = 'connecting'; subs.clear(); statusSubs.clear();
}
```

`notifications.ts` and `Bell.tsx` as specified in Interfaces. `Topbar.tsx` renders `<Bell />` and calls `socket.start()` once from a `useEffect` in `AppShell` (and `socket.stop()` on `pagehide`).

Backend: add `"vapid_key": getattr(settings, "WEBPUSH_VAPID_PUBLIC_KEY", "")` to `BootstrapView`'s response, and `vapid_key: string` to the `Bootstrap` type.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test && npm run build`; `venv/bin/python manage.py test apps.uiapi`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend apps/uiapi
git commit -m "feat(frontend): shared realtime socket and notifications bell"
```

---

### Task 8: Presence

**Files:**
- Modify: `frontend/src/lib/presence.ts`, `frontend/src/lib/presence.test.ts`
- Create: `frontend/src/shell/PresenceMenu.tsx`, `frontend/src/shell/PresenceMenu.test.tsx`
- Modify: `frontend/src/shell/Topbar.tsx`

**Interfaces:**
- Consumes: `socket` (Task 7), `api.post`.
- Produces:
  - `usePresence(): { users: PresenceUser[]; online: PresenceUser[]; away: PresenceUser[]; others: PresenceUser[]; status: Status }` (`online` = `status === 'online'`; `away` = the rest; `others` excludes the current user id from bootstrap).
  - Activity reporting, ported from `_presence.html`: every 15 s and on `visibilitychange`, send `{"type":"activity","path": location.pathname,"active": visible && idle < 5min}` only if it changed; a 25 s `{"type":"ping"}` while the socket is open; idle clock reset by `mousemove|keydown|pointerdown|scroll|touchstart`; close the socket on `pagehide`.
  - Polling fallback: after 2 failed connects (or any drop after a successful open) `status` becomes `'polling'` and the manager `POST /presence/beat/` (existing endpoint) `{tab, path, active}` every 25 s, applying `data.users`; it keeps retrying the socket in the background and stops polling when the socket opens. `tab` is a random 8-char id per page load.
  - `PresenceMenu`: topbar button showing up to 3 face initials (`user.name[0]`), the online count, and a popover listing online then away users with activity text, "clocked in at" time (`toLocaleTimeString([], {hour:'numeric', minute:'2-digit', hour12:true})`) and tickets in progress, mirroring `_presence_panel.html`; a status dot (`live`/`polling` green, otherwise grey) when nobody is listed.

- [ ] **Step 1: Write the failing tests** (extend `presence.test.ts`)

```ts
it('falls back to HTTP polling after two failed connects, and uses the beat endpoint', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ users: [{ user_id: 2, name: 'Bo', status: 'online' }] }), { status: 200 }));
  vi.stubGlobal('fetch', fetchMock);
  const users: unknown[] = [];
  socket.subscribe((e) => e.event === 'presence' && users.push(e.users));
  const statuses: string[] = [];
  socket.onStatus((s) => statuses.push(s));
  socket.start();
  FakeWS.instances[0].onclose?.({ code: 1006 });
  vi.advanceTimersByTime(2100);
  FakeWS.instances[1].onclose?.({ code: 1006 });
  await vi.advanceTimersByTimeAsync(10);
  expect(statuses).toContain('polling');
  expect(fetchMock.mock.calls[0][0]).toBe('/presence/beat/');
  expect(users.length).toBeGreaterThan(0);
});

it('reports activity only when it changes and answers visibility', () => {
  socket.start();
  const sock = FakeWS.instances[0];
  sock.open();
  const activity = () => sock.sent.filter((s) => s.includes('"activity"')).length;
  const before = activity();
  vi.advanceTimersByTime(15000);
  vi.advanceTimersByTime(15000);
  expect(activity()).toBe(before);           // unchanged payload is not resent
});

it('stops polling when the socket opens again', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"users":[]}', { status: 200 })));
  socket.start();
  FakeWS.instances[0].onclose?.({ code: 1006 });
  vi.advanceTimersByTime(2100);
  FakeWS.instances[1].onclose?.({ code: 1006 });
  await vi.advanceTimersByTimeAsync(10);
  vi.advanceTimersByTime(4100);
  FakeWS.instances.at(-1)!.open();
  const statuses: string[] = [];
  socket.onStatus((s) => statuses.push(s));
  expect(statuses.at(-1)).toBe('live');
});
```

`PresenceMenu.test.tsx`: with mocked `usePresence` returning two online and one away user, asserts the count `2`, face initials, popover lists names with activity, and the away user appears in a separate group.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL (no polling, no activity sending, no `usePresence`).

- [ ] **Step 3: Implement**

Extend `presence.ts`: add `tab`, `lastInput`, `lastSent`, the 15 s activity interval and 25 s ping, input listeners, `visibilitychange`, `pagehide` close, polling (`api.post('/presence/beat/' …)` is not under `/ui-api/`, so use `fetch('/presence/beat/', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken': csrf}, body})`, where `csrf` comes from `configure`'s stored value: export `getCsrf()` from `api.ts`), the retry counter that switches to polling after 2 failures or after any drop post-open, and `socket.users` state fed by `presence` events and poll responses (poll responses are published to subscribers as `{event:'presence', users}`). `usePresence` subscribes with `useSyncExternalStore` or a `useEffect` + state.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): presence with activity reporting and HTTP polling fallback"
```

---

### Task 9: Topbar controls, palette, help, changelog, PWA

**Files:**
- Create: `frontend/src/lib/search.ts`, `search.test.ts`, `frontend/src/shell/Palette.tsx`, `Palette.test.tsx`, `NewMenu.tsx`, `AccountMenu.tsx`, `ShortcutsHelp.tsx`, `Changelog.tsx`, `Changelog.test.tsx`, `frontend/src/lib/pwa.ts`
- Modify: `frontend/src/shell/Topbar.tsx`, `frontend/src/shell/AppShell.tsx` (global keys), `frontend/src/main.tsx` (service worker)

**Interfaces:**
- Produces:
  - `lib/search.ts`: `type SearchItem = { title: string; subtitle?: string; url: string; snippet?: string }`, `type SearchGroup = { label: string; items: SearchItem[] }`; `useSearch(query: string): { groups: SearchGroup[]; loading: boolean }` (150 ms debounce, `AbortController`, `GET {urls.search}?q=`, a failed request yields `[]`); `recentSearches` read/write in `localStorage['pq-recent-search']` (max 5); `highlight(text: string, query: string): (string | { mark: string })[]` that strips `in:|assignee:|status:` filters from the query, ignores queries under 2 chars, and never returns HTML (React renders `<mark>` for the `{mark}` parts).
  - `Palette`: opens on Ctrl/Cmd+K, or `/` when focus is not in an input/textarea/select/contenteditable; combobox semantics (`role="combobox"`, `aria-activedescendant`, `role="listbox"`/`option`); Arrow Up/Down wrap, Home/End, Enter follows the highlighted result (`window.location.assign(url)`), Escape closes; recent searches when the query is empty; tip line "Narrow it down: in:tickets assignee:me status:open"; footer hints.
  - `NewMenu`: "New" button; items New ticket (`urls.ticket_create`), Request leave (`urls.leave_apply`), Request a correction (`urls.correction_request`), and New product (`urls.product_create`, admins only).
  - `AccountMenu`: avatar + name + role; items Settings (`urls.profile`) and Sign out (a real `<form method="post" action={urls.logout}>` with a hidden `csrfmiddlewaretoken` input, so it works without JS).
  - `ShortcutsHelp`: dialog opened by `?` (outside inputs) listing the shortcuts that work now: `Ctrl K` or `/` search, `c` new ticket (navigates to `urls.ticket_create`), `?` help. (`j`/`k`/`Enter`/`e` act on ticket list/board elements and move with the tickets plan; the help text only lists what exists.)
  - `Changelog`: dialog titled "What's new in v{version}", fetching `urls.changelog` on first open (cached in react-query), showing the newest release alone with older releases one click away and type chips (New / Better / Fixed / Security) filtering the current block. Item text arrives as server-sanitised HTML (`apps/core/changelog.py` escapes everything except bold/code/link markers): render it with `dangerouslySetInnerHTML` only for that field.
  - `lib/pwa.ts`: `registerServiceWorker()` (on `load`, `/sw.js`, scope `/`), and `useInstallPrompt(): { available: boolean; install(): Promise<void> }` from `beforeinstallprompt` / `appinstalled`. The Sidebar's "Install app" button uses it (hidden unless `available`).

- [ ] **Step 1: Write the failing tests**

`search.test.ts`:

```ts
import { expect, it } from 'vitest';
import { highlight } from './search';

it('wraps matches and never emits HTML', () => {
  expect(highlight('Fix <b>login</b>', 'login')).toEqual(['Fix <b>', { mark: 'login' }, '</b>']);
});
it('ignores filters and short queries', () => {
  expect(highlight('open ticket', 'status:open ticket')).toEqual(['open ', { mark: 'ticket' }]);
  expect(highlight('abc', 'a')).toEqual(['abc']);
});
it('escapes regex characters in the query', () => {
  expect(highlight('a (b) c', '(b)')).toEqual(['a ', { mark: '(b)' }, ' c']);
});
```

`Palette.test.tsx` (mock `useSearch` to return two groups with three results, and `window.location.assign`):
- Ctrl+K opens, Escape closes; `/` opens only when the active element is not an input;
- ArrowDown x3 wraps to the first result; `aria-activedescendant` follows;
- Enter calls `location.assign` with the highlighted URL and stores the query in `pq-recent-search`;
- a result titled `<script>alert(1)</script> & co` renders as visible text (assert `container.querySelector('script')` is null and the text is present);
- empty query with stored recents shows "Recent searches" and Clear empties them.

`Changelog.test.tsx`: mock `api`/fetch to return two releases; asserts the newest shows alone, "Older releases" reveals the other, and a chip filters items.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL.

- [ ] **Step 3: Implement**

Implement `search.ts` (`highlight` splits with a case-insensitive escaped regex), `Palette.tsx` (befui Dialog as the overlay, input, grouped results; `useSearch` with `AbortController`), `NewMenu.tsx`, `AccountMenu.tsx`, `ShortcutsHelp.tsx`, `Changelog.tsx`, `pwa.ts`; wire them into `Topbar.tsx` in the legacy order: burger, title (company name), search button ("Search tickets, errors, products" + `Ctrl K`), then `NewMenu`, `PresenceMenu`, `Bell`, `AccountMenu`. `AppShell` registers one `keydown` listener for the global keys (`Ctrl/Cmd+K`, `/`, `?`, `c`, skipping when a modifier other than the palette's is held or the target is an input/textarea/select/contenteditable). `main.tsx` calls `registerServiceWorker()`.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): topbar menus, command palette, shortcuts help, changelog dialog, PWA"
```

---

### Task 10: Notifications page into the shell; delete the legacy page

**Files:**
- Modify: `frontend/src/routes.tsx`, `frontend/src/pages/Notifications.tsx`, `frontend/src/pages/Notifications.test.tsx`, `frontend/src/shell/nav.ts` (`REACT_PATHS`), `frontend/src/index.css`, `apps/notifications/views.py`, `apps/core/search.py` only if it references the list template (it does not)
- Delete: `templates/notifications/list.html`, `templates/notifications/list_react.html`
- Modify: `core/settings.py` (remove `REACT_PAGES` only if nothing else uses it; otherwise keep), `docker-compose.yml` (drop `REACT_PAGES=notifications`)
- Test: `apps/uiapi/tests.py`, `apps/notifications/tests.py`

**Interfaces:**
- Produces:
  - Route `{ path: '/notifications/', element: <Notifications /> }` in `shellRoutes`; the page reads the initial filter from the query string (`?filter=unread`), keeps it in sync with the buttons (`useSearchParams`), and sets `document.title = 'Notifications — PQ Platform'`.
  - Page needs no `Bootstrap` prop; the page's own "Mark all read" now also invalidates the bell (`['notifications']` is shared) and the Alpine `clearBell` shim is **deleted**.
  - Legacy: `ListView` stays as a thin view returning the shell; `FeedView`, `OpenView`, `MarkAllReadView`, push views are unchanged (legacy pages still use them).

- [ ] **Step 1: Write the failing tests**

Frontend (`Notifications.test.tsx`): wrap in `MemoryRouter`; add

```tsx
it('opens on Unread when the URL says so', async () => {
  const get = vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 0, items: [] });
  renderPage('/notifications/?filter=unread');
  await screen.findByText('Nothing unread');
  expect(get).toHaveBeenCalledWith('unread');
});

it('switching filter updates the URL', async () => {
  vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 0, items: [] });
  renderPage('/notifications/');
  await userEvent.click(await screen.findByRole('button', { name: 'Unread' }));
  expect(screen.getByTestId('location')).toHaveTextContent('filter=unread');
});
```

(`renderPage(url)` wraps the page and a `<LocationProbe data-testid="location">` in `MemoryRouter`.) Remove the `resets the legacy bell…` test and the `clearBell` code.

Backend: delete the `ShellPageTest.test_a_missing_build…` dependency on removed templates only if it referenced them (it does not); add to `apps/uiapi/tests.py`:

```python
    def test_old_template_names_are_gone(self):
        from django.template.loader import get_template
        from django.template import TemplateDoesNotExist
        for name in ("notifications/list.html", "notifications/list_react.html"):
            with self.assertRaises(TemplateDoesNotExist):
                get_template(name)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`; `venv/bin/python manage.py test apps.uiapi`
Expected: FAIL.

- [ ] **Step 3: Implement**

`routes.tsx`:

```tsx
import type { RouteObject } from 'react-router-dom';
import { Notifications } from '@/pages/Notifications';

export const shellRoutes: RouteObject[] = [{ path: '/notifications/', element: <Notifications /> }];
```

`nav.ts`: leave `REACT_PATHS` as `new Set<string>(['/notifications/'])` (the bell's "See all" uses `<Link>`, the sidebar has no item for it).

`Notifications.tsx`: replace `useState<Filter>('all')` with

```tsx
const [params, setParams] = useSearchParams();
const filter: Filter = params.get('filter') === 'unread' ? 'unread' : 'all';
const setFilter = (f: Filter) => setParams(f === 'unread' ? { filter: 'unread' } : {}, { replace: true });
useEffect(() => { document.title = 'Notifications — PQ Platform'; }, []);
```

and delete `clearBell`/`Bell` types and its call. `index.css`: the shell page loads no legacy CSS, so remove the `important` flag from the utilities import and the `@layer base` reset's legacy-specific rules only if the build and the visual check pass; otherwise keep them (record the decision). Delete the two legacy templates; `apps/notifications/views.py` keeps `ListView.get -> render_shell(request)`. Remove `REACT_PAGES=notifications` from `docker-compose.yml`; keep the `REACT_PAGES` setting for the next plan (ledger a note).

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test && npm run build`; `venv/bin/python manage.py test apps.uiapi apps.notifications apps.core`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: notifications page lives in the React shell; legacy notifications template removed"
```

---

### Task 11: Parity check, docs, release

**Files:**
- Modify: `context.md`, `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, `core/settings.py` (version)

**Interfaces:** consumes everything above.

- [ ] **Step 1: Build and run locally against a scratch database**

`seed_data` wipes `db.sqlite3`, so use a scratch settings module in the scratchpad directory (copy `scratch_settings.py` approach from the previous plan: `from core.settings import *; DATABASES["default"]["NAME"] = "<scratchpad>/scratch.sqlite3"`).

```bash
cd frontend && npm run build && cd ..
PYTHONPATH=<scratchpad>:. DJANGO_SETTINGS_MODULE=scratch_settings venv/bin/python manage.py migrate -v0
PYTHONPATH=<scratchpad>:. DJANGO_SETTINGS_MODULE=scratch_settings venv/bin/python manage.py seed_data
PYTHONPATH=<scratchpad>:. DJANGO_SETTINGS_MODULE=scratch_settings venv/bin/python manage.py runserver 8010 --noreload
```

Log in as `dev1` and as `owner` (seed logins, password `testpass123`; localhost dev server) and verify in the browser, comparing against a legacy page (e.g. `/tickets/`) in a second tab:

- [ ] `/notifications/` renders in the new shell; sidebar shows the same items and counts as the legacy shell; admin items only for `owner`; exactly one item active on each page.
- [ ] Collapsing the sidebar persists across reload and across the legacy shell (same localStorage key); mobile (375px) drawer opens and closes.
- [ ] Clicking a legacy item (e.g. All tickets) does a full page load to the legacy page with its own shell, and the nav counts match.
- [ ] Company switcher lists workspaces, switching reloads home with a "Switched to X." toast.
- [ ] Bell: badge, popover list, mark all read (list on the page updates at once), "See all" navigates without reload, a new notification created from the shell command appears live with a toast.
- [ ] Presence: online count and popover show other signed-in users; killing the socket (stop the server briefly) falls back and recovers.
- [ ] Ctrl K / `/` opens the palette; results match `/search/`; Enter opens; Escape closes; `?` opens help; `c` goes to New ticket.
- [ ] What's new opens and shows the newest release; Sign out works (and sends you to login).
- [ ] A flash message from a legacy redirect shows exactly once (e.g. switch company from the legacy sidebar, land on a React page).
- [ ] Console has no errors on `/notifications/`.

- [ ] **Step 2: Full regression**

```bash
venv/bin/python manage.py test apps > /tmp/full-suite.log 2>&1 &
```

Run in the background and poll the log (about 3.5 minutes). Expected: only the known `test_signup_creates_user` failure. Also `cd frontend && npm test`, and `docker build -t pq-test .`.

- [ ] **Step 3: Docs, release, commit**

- `context.md`: a `### 2026-10-12 (React shell)` entry: what exists (bootstrap, shell template, shell components, socket manager), decisions (nav URLs from bootstrap; longest-prefix active state; flash messages consumed by bootstrap; presence/notifications share one socket; befui source copied; `Toaster` is our own), what was deliberately deferred (`j/k/e` ticket shortcuts, product sub-nav `/ui-api/v1/products/<pk>/nav/`, confirm dialog, datepicker/dropdown/tooltip legacy scripts: they leave with the pages that use them), and what stays legacy (`/notifications/feed|read-all|open` used by the legacy bell and web push).
- `CLAUDE.md` and `AGENTS.md`: update the "React UI (in migration)" paragraph: React shell exists, how to add a React route (add to `shellRoutes`, `REACT_PATHS`, a `render_shell` view for the URL, delete the legacy page in the same change).
- `CHANGELOG.md`: new release `## [1.13.0]` with a `> In short:` line and bold sentence leads, e.g. "**A new look for the navigation.**" and "**Switching workspace and signing out are quicker.**"; bump `APP_VERSION` in `core/settings.py`; run `venv/bin/python manage.py test apps.core` to confirm the changelog tests.

```bash
git add -A
git commit -m "docs: React shell; release 1.13.0"
```

---

## Out of scope (next plans)

- Ticket pages (global and product-scoped list, detail, board, create/edit) and their `/ui-api/v1/` endpoints; `j`/`k`/`e` shortcuts; the product sub-navigation; deleting the legacy tickets templates and their htmx.
- Remaining areas in the spec's revised order (errors/products, dashboards/feedback/automation/DSR, accounts, HR), and the final removal of htmx, Alpine, `django_htmx` and legacy CSS.
- Dark mode, hashed asset names, HMR.
