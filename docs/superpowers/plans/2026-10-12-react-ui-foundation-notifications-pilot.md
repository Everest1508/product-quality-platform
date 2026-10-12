# React UI foundation + notifications pilot: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the React + befui frontend pipeline and migrate the `/notifications/` page as the first page, behind a per-page switch that defaults to the legacy page.

**Architecture:** A `frontend/` Vite + React + TypeScript app builds to `frontend/dist/app.js` and `app.css`. Django serves them at `/ui/<name>` and a thin shell template (extending `core/base.html`, so sidebar/topbar/toasts stay legacy) mounts React into `#react-root`. React talks to new session-authenticated JSON endpoints in a new `apps/uiapi` app at `/ui-api/v1/`, which reuse `apps/notifications/service.py`. A setting `REACT_PAGES` chooses legacy or React per page.

**Tech Stack:** Django 6 + DRF (existing), Vite, React 18, TypeScript, Tailwind 4, befui components (copied in, Radix underneath), TanStack Query, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-12-react-ui-migration-design.md`

## Global Constraints

- Backend stays Python/Django; no change to models, `service.py` rules, or the `/api/v1/` and `/api/serop/` APIs.
- Auth is the existing session cookie. `/ui-api/v1/` uses DRF `SessionAuthentication` (CSRF enforced on POST). Not API keys, not bearer tokens, no CORS.
- Every endpoint is scoped to `request.user` and `request.company` (company isolation). Notifications are per-recipient, so no product-access check applies.
- `TIME_ZONE = "Asia/Kolkata"`: the API sends ISO-8601 with offset (`isoformat()` of an aware datetime); the browser formats it. No hardcoded offsets.
- Run tests with `venv/bin/python manage.py test <label>` (Django runner, not pytest). Baseline: the full suite has exactly one known failure, `accounts.tests.test_tenant_isolation ... test_signup_creates_user`.
- Legacy page stays the default until the React page passes the parity checklist (Task 5). Default `REACT_PAGES` is empty.
- No new Python dependencies. No Node in production (build in a Docker stage only).
- Legacy and React styling must not collide: legacy defines `--border`, `--accent` and many other CSS variables on `:root`, so befui's theme variables are scoped to a `.befui` container and Tailwind's global reset (preflight) is not loaded.
- Toasts on a React page use the legacy event: `window.dispatchEvent(new CustomEvent('django-message', { detail: { text, tags } }))` (`tags` is `success` | `error` | `info`).
- Commit after each task. End commit messages with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- A user in company A must never see or mark read company B's notifications, even when both companies have the same user (switch via `ACTIVE_COMPANY_SESSION_KEY`). Pinned in Task 1.
- `read-all` must not touch other users' rows or other companies' rows. Pinned in Task 1.
- A POST without a CSRF token must be rejected (403), not silently accepted. Pinned in Task 1.
- An anonymous request must get 401/403 JSON, not a 302 to the HTML login page. Pinned in Task 1.
- A user with no company must get a clear 403 JSON, not a 500. Pinned in Task 1.
- The static-file view must not serve anything outside `frontend/dist` (e.g. `..%2f` or a subfolder). Pinned in Task 2.
- A missing build (`frontend/dist` absent) with the switch on must show a visible error, not a blank page. Pinned in Task 2.
- Empty state, loading state and a failed fetch must each render something sensible. Pinned in Task 4.

---

## File structure

| File | Responsibility |
|---|---|
| `apps/uiapi/__init__.py`, `apps.py`, `urls.py`, `views.py`, `tests.py` | JSON endpoints for the React UI (this plan: notifications only) |
| `apps/notifications/service.py` (modify) | add `mine(user, company)` queryset helper |
| `apps/notifications/views.py` (modify) | `_mine` delegates to `service.mine`; `ListView` picks React or legacy template |
| `apps/core/ui_assets.py` | serve built files from `frontend/dist` at `/ui/<name>` |
| `core/settings.py`, `core/urls.py` (modify) | `REACT_PAGES`, `FRONTEND_DIST`, `apps.uiapi`, routes |
| `templates/notifications/list_react.html` | shell: extends base, mounts React |
| `frontend/` | Vite app: `src/main.tsx`, `src/index.css`, `src/lib/{utils,api}.ts`, `src/components/ui/*` (befui), `src/pages/Notifications.tsx` |
| `Dockerfile`, `.dockerignore`, `.gitignore` (modify) | Node build stage, ignore `node_modules` and `dist` |

---

### Task 1: Notifications JSON API

**Files:**
- Create: `apps/uiapi/__init__.py` (empty), `apps/uiapi/apps.py`, `apps/uiapi/urls.py`, `apps/uiapi/views.py`, `apps/uiapi/tests.py`
- Modify: `apps/notifications/service.py` (add `mine`), `apps/notifications/views.py` (`_mine` delegates), `core/settings.py` (INSTALLED_APPS), `core/urls.py`

**Interfaces:**
- Produces:
  - `service.mine(user, company) -> QuerySet[Notification]` (that user's, that company's, `select_related("actor")`, default ordering newest first).
  - `GET /ui-api/v1/notifications/?filter=unread|all` → `200 {"unread": int, "items": [Notification.as_json() + {"kind_label": str}]}`, newest first, max 100 items. `unread` is the company-wide unread count for this user, independent of the filter.
  - `POST /ui-api/v1/notifications/read-all/` → `200 {"unread": 0}`.
  - Errors are JSON: not signed in → `403 {"detail": ...}` (DRF session auth behaviour); signed in but no company → `403 {"detail": "No active company."}`.
  - URL names `uiapi:notifications` and `uiapi:notifications_read_all`.

- [ ] **Step 1: Write the failing tests**

Create `apps/uiapi/tests.py`:

```python
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.notifications import service
from apps.notifications.models import Notification

User = get_user_model()


def make(username, company, role="developer"):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class NotificationsApiTest(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.ann = make("ann", self.acme, "owner")
        self.bob = make("bob", self.acme)
        # bob also belongs to the other company
        Membership.objects.create(user=self.bob, company=self.other, role="viewer")
        self.mine = service.notify(user=self.bob, company=self.acme, kind="comment", title="Mine", url="/tickets/9/", actor=self.ann)
        self.read = service.notify(user=self.bob, company=self.acme, kind="assigned", title="Old", actor=self.ann)
        Notification.objects.filter(pk=self.read.pk).update(read_at=self.read.created_at)
        self.hers = service.notify(user=self.ann, company=self.acme, kind="comment", title="Hers", actor=self.bob)
        self.elsewhere = service.notify(user=self.bob, company=self.other, kind="system", title="Elsewhere")
        self.client.login(username="bob", password="pass1234")
        self.url = reverse("uiapi:notifications")

    def test_lists_only_my_notifications_in_the_active_company(self):
        data = self.client.get(self.url).json()
        self.assertEqual([i["title"] for i in data["items"]], ["Old", "Mine"])  # newest first
        self.assertEqual(data["unread"], 1)
        item = next(i for i in data["items"] if i["title"] == "Mine")
        self.assertEqual(item["kind_label"], "New comment")
        self.assertEqual(item["url"], f"/notifications/{self.mine.pk}/open/")
        self.assertFalse(item["read"])

    def test_company_switch_changes_what_is_listed(self):
        session = self.client.session
        session[settings.ACTIVE_COMPANY_SESSION_KEY] = self.other.pk
        session.save()
        titles = [i["title"] for i in self.client.get(self.url).json()["items"]]
        self.assertEqual(titles, ["Elsewhere"])

    def test_unread_filter_hides_read_rows_but_count_is_unchanged(self):
        data = self.client.get(self.url, {"filter": "unread"}).json()
        self.assertEqual([i["title"] for i in data["items"]], ["Mine"])
        self.assertEqual(data["unread"], 1)

    def test_list_is_capped_at_100(self):
        for i in range(105):
            service.notify(user=self.bob, company=self.acme, kind="system", title=f"n{i}")
        self.assertEqual(len(self.client.get(self.url).json()["items"]), 100)

    def test_anonymous_gets_json_403_not_a_redirect(self):
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_signed_in_without_a_company_gets_403(self):
        loner = User.objects.create_user("loner", "l@t.local", "pass1234")
        c = Client(); c.login(username="loner", password="pass1234")
        response = c.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "No active company.")

    def test_read_all_marks_only_my_rows_in_this_company(self):
        response = self.client.post(reverse("uiapi:notifications_read_all"))
        self.assertEqual(response.json(), {"unread": 0})
        self.assertEqual(Notification.objects.filter(user=self.bob, company=self.acme, read_at__isnull=True).count(), 0)
        self.hers.refresh_from_db(); self.elsewhere.refresh_from_db()
        self.assertFalse(self.hers.is_read)        # someone else's
        self.assertFalse(self.elsewhere.is_read)   # another company

    def test_post_without_csrf_token_is_rejected(self):
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="bob", password="pass1234")
        self.assertEqual(strict.post(reverse("uiapi:notifications_read_all")).status_code, 403)
        self.mine.refresh_from_db()
        self.assertFalse(self.mine.is_read)
```
- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.uiapi`
Expected: error, `apps.uiapi` is not an installed app / `uiapi` namespace not found.

- [ ] **Step 3: Implement**

`apps/uiapi/apps.py`:

```python
from django.apps import AppConfig


class UiapiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.uiapi"
```

`apps/notifications/service.py`, add below `unread_count`:

```python
def mine(user, company):
    """One person's notifications in one workspace, newest first."""
    return Notification.objects.filter(user=user, company=company).select_related("actor")
```

`apps/notifications/views.py`, replace `_mine` body so both UIs share it:

```python
def _mine(request):
    return service.mine(request.user, request.company)
```

`apps/uiapi/views.py`:

```python
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications import service

LIMIT = 100


class CompanyAPIView(APIView):
    """Session-cookie JSON view. CSRF is enforced on writes by SessionAuthentication.
    Every subclass works on `request.company`, set by CurrentCompanyMiddleware."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.company:
            raise PermissionDenied("No active company.")


class NotificationListView(CompanyAPIView):
    def get(self, request):
        rows = service.mine(request.user, request.company)
        if request.query_params.get("filter") == "unread":
            rows = rows.filter(read_at__isnull=True)
        items = [{**n.as_json(), "kind_label": n.get_kind_display()} for n in rows[:LIMIT]]
        return Response({"unread": service.unread_count(request.user, request.company), "items": items})


class NotificationReadAllView(CompanyAPIView):
    def post(self, request):
        service.mark_read(request.user, request.company)
        return Response({"unread": 0})
```
`apps/uiapi/urls.py`:

```python
from django.urls import path

from apps.uiapi import views

app_name = "uiapi"

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/read-all/", views.NotificationReadAllView.as_view(), name="notifications_read_all"),
]
```

`core/settings.py`: add `"apps.uiapi",` after `"apps.notifications",` in `INSTALLED_APPS`.
`core/urls.py`: add `path("ui-api/v1/", include("apps.uiapi.urls")),` next to the other `api/` includes.

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.uiapi apps.notifications`
Expected: all pass (existing notifications tests prove the `_mine` refactor changed nothing).

- [ ] **Step 5: Commit**

```bash
git add apps/uiapi apps/notifications core/settings.py core/urls.py
git commit -m "feat(uiapi): session JSON API for notifications"
```

---

### Task 2: Switch, asset serving, and shell template

**Files:**
- Create: `apps/core/ui_assets.py`, `templates/notifications/list_react.html`, `apps/core/tests_ui_assets.py`
- Modify: `core/settings.py`, `core/urls.py`, `apps/notifications/views.py` (`ListView`)
- Test: `apps/core/tests_ui_assets.py`, `apps/uiapi/tests.py` (append)

**Interfaces:**
- Consumes: `service.unread_count`.
- Produces:
  - `settings.REACT_PAGES: set[str]` from env `REACT_PAGES` (comma separated), default empty. Page key for this plan: `"notifications"`.
  - `settings.FRONTEND_DIST = BASE_DIR / "frontend" / "dist"`.
  - `GET /ui/<name>` serves a file directly inside `FRONTEND_DIST` (names `app.js`, `app.css`), `Cache-Control: no-cache`; 404 otherwise.
  - Shell contract for the React app: element `<div id="react-root" class="befui" data-page="notifications" data-api="/ui-api/v1/" data-csrf="<token>">`.

- [ ] **Step 1: Write the failing tests**

`apps/core/tests_ui_assets.py`:

```python
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings


class UiAssetsTest(TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "app.js").write_text("console.log(1)")
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "x.js").write_text("secret")
        self.override = override_settings(FRONTEND_DIST=self.dir)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_serves_a_built_file_without_caching(self):
        response = self.client.get("/ui/app.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"console.log(1)")
        self.assertEqual(response["Cache-Control"], "no-cache")

    def test_unknown_file_is_404(self):
        self.assertEqual(self.client.get("/ui/nope.js").status_code, 404)

    def test_nothing_outside_the_dist_root_is_served(self):
        self.assertEqual(self.client.get("/ui/sub").status_code, 404)
        self.assertEqual(self.client.get("/ui/..%2Fsettings.py").status_code, 404)
        self.assertEqual(self.client.get("/ui/sub/x.js").status_code, 404)
```

Append to `apps/uiapi/tests.py`:

```python
from django.test import override_settings


class NotificationsPageSwitchTest(TestCase):
    def setUp(self):
        co = Company.objects.create(name="Acme", slug="acme")
        make("bob", co)
        self.client.login(username="bob", password="pass1234")

    def test_default_is_the_legacy_page(self):
        response = self.client.get("/notifications/")
        self.assertTemplateUsed(response, "notifications/list.html")
        self.assertNotContains(response, 'id="react-root"')

    @override_settings(REACT_PAGES={"notifications"})
    def test_switch_on_renders_the_react_shell(self):
        response = self.client.get("/notifications/")
        self.assertTemplateUsed(response, "notifications/list_react.html")
        self.assertContains(response, 'id="react-root"')
        self.assertContains(response, 'data-page="notifications"')
        self.assertContains(response, 'data-csrf="')
        self.assertContains(response, "/ui/app.js")

    @override_settings(REACT_PAGES={"notifications"}, FRONTEND_DIST="/nonexistent")
    def test_switch_on_with_no_build_says_so(self):
        self.assertContains(self.client.get("/notifications/"), "frontend has not been built")
```

- [ ] **Step 2: Run to verify failure**

Run: `venv/bin/python manage.py test apps.core.tests_ui_assets apps.uiapi`
Expected: FAIL (404s on `/ui/...`, template not used).

- [ ] **Step 3: Implement**

`core/settings.py` (near `APP_VERSION`):

```python
# Pages served by the React frontend instead of the legacy template, e.g.
# REACT_PAGES=notifications,tickets. Empty means everything is legacy.
REACT_PAGES = {p.strip() for p in os.environ.get("REACT_PAGES", "").split(",") if p.strip()}
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
```

`apps/core/ui_assets.py`:

```python
"""Serve the built React files (frontend/dist/app.js, app.css) at /ui/<name>.

Same approach as brand.py: no static pipeline, so a view serves the few named
files. `name` is a single path segment and must be a real file directly inside
the dist folder. `no-cache` makes the browser revalidate, so a new build shows
up without a hard refresh (the file is not content-hashed).
"""

import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404


def ui_file(request, name):
    root = settings.FRONTEND_DIST
    path = root / name
    if path.parent != root or not path.is_file():
        raise Http404
    response = FileResponse(open(path, "rb"), content_type=mimetypes.guess_type(name)[0])
    response["Cache-Control"] = "no-cache"
    return response
```

`core/urls.py`: `from apps.core.ui_assets import ui_file` and `path("ui/<str:name>", ui_file),` beside the `brand/` route.

`apps/notifications/views.py`: add `from django.conf import settings` and change `ListView.get`'s render:

```python
        template = "notifications/list_react.html" if "notifications" in settings.REACT_PAGES else "notifications/list.html"
        return render(request, template, {
            "notifications": rows[:100],
            "only_unread": only_unread,
            "unread": service.unread_count(request.user, request.company),
            "frontend_built": (settings.FRONTEND_DIST / "app.js").is_file(),
        })
```

`templates/notifications/list_react.html`:

```html
{% extends "core/base.html" %}

{% block title %}Notifications — PQ Platform{% endblock %}

{% block extra_head %}
{% if frontend_built %}<link rel="stylesheet" href="/ui/app.css">{% endif %}
{% endblock %}

{% block content %}
{% if frontend_built %}
<div id="react-root" class="befui" data-page="notifications" data-api="/ui-api/v1/" data-csrf="{{ csrf_token }}"></div>
<script type="module" src="/ui/app.js"></script>
{% else %}
<div class="card" style="padding:16px;">
  The new frontend has not been built. Run <code>cd frontend &amp;&amp; npm run build</code>, or remove
  <code>notifications</code> from <code>REACT_PAGES</code> to use the classic page.
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run to verify pass**

Run: `venv/bin/python manage.py test apps.core.tests_ui_assets apps.uiapi apps.notifications`
Expected: PASS. Then `venv/bin/python manage.py check` (expect only `staticfiles.W004`).

- [ ] **Step 5: Commit**

```bash
git add apps/core core apps/notifications apps/uiapi templates/notifications
git commit -m "feat(core): REACT_PAGES switch, /ui/ asset view, notifications React shell"
```

---

### Task 3: Frontend scaffold with befui theme

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/index.css`, `frontend/src/lib/utils.ts`, `frontend/src/lib/api.ts`, `frontend/src/main.tsx`, `frontend/src/pages/Notifications.tsx` (placeholder `<div>Notifications</div>` for now), `frontend/src/components/ui/*` (befui, added here)
- Modify: `.gitignore` (add `frontend/node_modules/`, `frontend/dist/`)

**Interfaces:**
- Produces:
  - `cn(...inputs: ClassValue[]): string` in `src/lib/utils.ts` (befui's helper, verbatim).
  - `api` in `src/lib/api.ts` (see Task 4 for its tests): `getNotifications(filter: "all" | "unread"): Promise<NotificationsResponse>`, `markAllRead(): Promise<{ unread: number }>`, `type Notice`, `type NotificationsResponse`. Defined fully in Task 4; Task 3 only creates the file with those exports.
  - Build output: `frontend/dist/app.js` and `frontend/dist/app.css` (stable names).
  - `main.tsx` reads `#react-root` `data-page`, `data-api`, `data-csrf` and mounts the page for that key.

- [ ] **Step 1: Scaffold and install**

```bash
mkdir -p frontend/src/lib frontend/src/pages frontend/src/components/ui
cd frontend
npm init -y >/dev/null
npm i react react-dom @tanstack/react-query tailwindcss @tailwindcss/vite clsx tailwind-merge class-variance-authority lucide-react
npm i -D vite @vitejs/plugin-react typescript @types/react @types/react-dom vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Set `package.json` `"name": "pq-frontend"`, `"private": true`, `"type": "module"`, and scripts: `"dev": "vite build --watch"`, `"build": "tsc --noEmit && vite build"`, `"test": "vitest run"`.

`vite.config.ts`:

```ts
import path from 'path';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: 'src/main.tsx',
      output: { entryFileNames: 'app.js', assetFileNames: 'app[extname]' },
    },
  },
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test-setup.ts'] },
});
```

`src/test-setup.ts`: `import '@testing-library/jest-dom/vitest';`

`tsconfig.json`: `strict: true`, `jsx: "react-jsx"`, `module/moduleResolution: "bundler"`, `target: "ES2022"`, `paths: {"@/*": ["./src/*"]}`, `types: ["vitest/globals"]`, `include: ["src"]`.

`src/lib/utils.ts`: the `cn` helper exactly as in the befui getting-started page.

- [ ] **Step 2: Scoped befui theme**

`src/index.css` follows the befui getting-started page (colour variables, `@theme inline` mapping, keyframes) with these deliberate changes so it cannot disturb the legacy shell:

1. Replace `@import 'tailwindcss' source('.');` with the layered imports that skip preflight:
   ```css
   @layer theme, base, components, utilities;
   @import 'tailwindcss/theme.css' layer(theme);
   @import 'tailwindcss/utilities.css' layer(utilities) source('.');
   ```
2. Put the light colour variables on `.befui` instead of `:root, .light`. Set `--primary` and `--ring` to the legacy accent (`#3b82f6` is befui's default; use the value of `--blue-500` from `templates/core/css/_tokens.css`). Drop the `.dark` block for now (legacy is light only).
3. Drop befui's global `@layer base` block (`* { border-color }`, `html`, `body`, scrollbar, `button` cursor) and replace it with a scoped mini-reset so Tailwind border utilities work without preflight:
   ```css
   .befui, .befui *, .befui *::before, .befui *::after { box-sizing: border-box; border: 0 solid var(--border); }
   .befui { font-family: var(--font-sans); color: var(--foreground); }
   .befui button:not(:disabled), .befui [role='button']:not([aria-disabled='true']) { cursor: pointer; }
   ```
4. Keep the keyframes and `--animate-*` entries, the slider and icon-draw rules.

- [ ] **Step 3: Add befui components**

From `frontend/`, add what the pilot page needs. Try the CLI first:

```bash
npx befui add button card badge skeleton empty-state segmented-control relative-time
```

Expected: files appear in `src/components/ui/`. **If the CLI fails** (the library is new and unverified), open each component's page at https://befui.vercel.app, copy its single file into `src/components/ui/<name>.tsx`, and note in the commit message that the CLI was not used. Either way, run `npm run build` afterwards; fix any import path to use `@/lib/utils`. Open each added file and note its exact props, because Task 4 passes props to them.

If a component name above does not exist in befui, use the closest one from the site's list (Tabs for Segmented control, a `<time>` with `Intl.RelativeTimeFormat` for Relative time) and record the substitution in the commit message.

- [ ] **Step 4: Entry, placeholder page, and a first build**

`src/lib/api.ts` (final content; tested in Task 4):

```ts
export type Notice = {
  id: number;
  kind: string;
  kind_label: string;
  title: string;
  body: string;
  url: string;
  actor: string;
  created_at: string;
  read: boolean;
};
export type NotificationsResponse = { unread: number; items: Notice[] };
export type Filter = 'all' | 'unread';

type Config = { api: string; csrf: string };
let config: Config = { api: '/ui-api/v1/', csrf: '' };
export const configure = (c: Config) => { config = c; };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(config.api + path, {
    credentials: 'same-origin',
    ...init,
    headers: { Accept: 'application/json', 'X-CSRFToken': config.csrf, ...init?.headers },
  });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json() as Promise<T>;
}

export const getNotifications = (filter: Filter) =>
  request<NotificationsResponse>(`notifications/${filter === 'unread' ? '?filter=unread' : ''}`);

export const markAllRead = () =>
  request<{ unread: number }>('notifications/read-all/', { method: 'POST' });
```

`src/main.tsx`:

```tsx
import './index.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { configure } from '@/lib/api';
import { Notifications } from '@/pages/Notifications';

const pages: Record<string, () => JSX.Element> = { notifications: Notifications };

const el = document.getElementById('react-root');
const Page = el && pages[el.dataset.page ?? ''];
if (el && Page) {
  configure({ api: el.dataset.api ?? '/ui-api/v1/', csrf: el.dataset.csrf ?? '' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } });
  createRoot(el).render(
    <StrictMode>
      <QueryClientProvider client={client}>
        <Page />
      </QueryClientProvider>
    </StrictMode>,
  );
}
```

`src/pages/Notifications.tsx` placeholder: `export const Notifications = () => <div>Notifications</div>;`

Run: `cd frontend && npm run build`
Expected: `dist/app.js` and `dist/app.css` exist, no TypeScript errors.

- [ ] **Step 5: Verify no style collision, then commit**

Tailwind's theme layer writes variables on `:root`. Confirm none clash with legacy tokens:

```bash
grep -o -- '--[a-z0-9-]*:' templates/core/css/_tokens.css | sort -u > /tmp/legacy_vars.txt
grep -o -- '--[a-z0-9-]*:' frontend/dist/app.css | sort -u > /tmp/react_vars.txt
comm -12 /tmp/legacy_vars.txt /tmp/react_vars.txt
```

Expected: no output. For any name printed, rename it in `index.css` (or drop it from the theme) until the output is empty, because a shared name would restyle the legacy shell once both CSS files are on one page.

```bash
git add frontend .gitignore
git commit -m "feat(frontend): Vite + React + Tailwind 4 scaffold with scoped befui theme"
```

(`package-lock.json` is committed; `node_modules` and `dist` are ignored.)

---

### Task 4: Notifications page in React

**Files:**
- Modify: `frontend/src/pages/Notifications.tsx`
- Create: `frontend/src/lib/api.test.ts`, `frontend/src/pages/Notifications.test.tsx`

**Interfaces:**
- Consumes: `getNotifications`, `markAllRead`, `Notice`, `Filter`, `configure` (Task 3); befui `Button`, `Card`, `Badge`, `Skeleton`, `EmptyState`, segmented control (props as recorded in Task 3).
- Produces: `Notifications` page component, no props. Parity with `templates/notifications/list.html`: heading with unread count, All/Unread filter, "Mark all read" (only when unread > 0), rows linking to `Notice.url` (which marks read then redirects), unread dot, kind badge, relative time with full-date tooltip, empty states.

- [ ] **Step 1: Write the failing tests**

`src/lib/api.test.ts`:

```ts
import { afterEach, expect, it, vi } from 'vitest';
import { configure, getNotifications, markAllRead } from './api';

afterEach(() => vi.restoreAllMocks());

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

it('asks for unread only when filtered, with the session cookie', async () => {
  configure({ api: '/ui-api/v1/', csrf: 'tok' });
  const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => ok({ unread: 0, items: [] }));
  await getNotifications('unread');
  expect(f.mock.calls[0][0]).toBe('/ui-api/v1/notifications/?filter=unread');
  expect(f.mock.calls[0][1]?.credentials).toBe('same-origin');
});

it('sends the CSRF token when marking all read', async () => {
  configure({ api: '/ui-api/v1/', csrf: 'tok' });
  const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => ok({ unread: 0 }));
  await markAllRead();
  const init = f.mock.calls[0][1]!;
  expect(init.method).toBe('POST');
  expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('tok');
});

it('throws on an error status', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(new Response('', { status: 403 })));
  await expect(getNotifications('all')).rejects.toThrow('403');
});
```

`src/pages/Notifications.test.tsx`:

```tsx
import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as api from '@/lib/api';
import { Notifications } from './Notifications';

afterEach(() => vi.restoreAllMocks());

const notice = (over: Partial<api.Notice> = {}): api.Notice => ({
  id: 1, kind: 'comment', kind_label: 'New comment', title: 'Ann commented', body: 'Looks good',
  url: '/notifications/1/open/', actor: 'Ann', created_at: new Date().toISOString(), read: false, ...over,
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Notifications /></QueryClientProvider>);
}

it('shows rows, the unread count, and links each row to its open URL', async () => {
  vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 1, items: [notice()] });
  renderPage();
  const row = await screen.findByRole('link', { name: /Ann commented/ });
  expect(row).toHaveAttribute('href', '/notifications/1/open/');
  expect(screen.getByText(/1 unread/)).toBeInTheDocument();
  expect(screen.getByText('New comment')).toBeInTheDocument();
});

it('shows an empty state for All and a different one for Unread', async () => {
  const get = vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 0, items: [] });
  renderPage();
  expect(await screen.findByText('No notifications yet')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Unread' }));
  expect(await screen.findByText('Nothing unread')).toBeInTheDocument();
  expect(get).toHaveBeenLastCalledWith('unread');
});

it('hides Mark all read when nothing is unread', async () => {
  vi.spyOn(api, 'getNotifications').mockResolvedValue({ unread: 0, items: [notice({ read: true })] });
  renderPage();
  await screen.findByText('Ann commented');
  expect(screen.queryByRole('button', { name: /mark all read/i })).not.toBeInTheDocument();
});

it('marks all read, refreshes, and raises the legacy toast', async () => {
  const get = vi.spyOn(api, 'getNotifications')
    .mockResolvedValueOnce({ unread: 1, items: [notice()] })
    .mockResolvedValue({ unread: 0, items: [notice({ read: true })] });
  const mark = vi.spyOn(api, 'markAllRead').mockResolvedValue({ unread: 0 });
  const toast = vi.fn();
  window.addEventListener('django-message', toast);
  renderPage();
  await userEvent.click(await screen.findByRole('button', { name: /mark all read/i }));
  await waitFor(() => expect(mark).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByText(/0 unread/)).toBeInTheDocument());
  expect((toast.mock.calls[0][0] as CustomEvent).detail).toEqual({ text: 'All notifications marked as read.', tags: 'success' });
  expect(get.mock.calls.length).toBeGreaterThan(1);
  window.removeEventListener('django-message', toast);
});

it('shows a retryable error when loading fails', async () => {
  vi.spyOn(api, 'getNotifications').mockRejectedValue(new Error('Request failed (500)'));
  renderPage();
  expect(await screen.findByText(/couldn.t load notifications/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
});

it('shows loading placeholders before data arrives', () => {
  vi.spyOn(api, 'getNotifications').mockReturnValue(new Promise(() => {}));
  renderPage();
  expect(screen.getByTestId('notifications-loading')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`
Expected: `api.test.ts` passes (api.ts exists from Task 3); `Notifications.test.tsx` FAILS (placeholder page has none of this).

- [ ] **Step 3: Implement the page**

`src/pages/Notifications.tsx`. Use the befui components you added; the prop names below follow the common `variant`/`size` convention, so adjust to the props you recorded in Task 3 if a copied file differs. Keep logic exactly as written, since the tests pin it.

```tsx
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getNotifications, markAllRead, type Filter, type Notice } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const toast = (text: string, tags: 'success' | 'error') =>
  window.dispatchEvent(new CustomEvent('django-message', { detail: { text, tags } }));

const ago = (iso: string) => {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [['day', 86400], ['hour', 3600], ['minute', 60]];
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  for (const [unit, size] of units) if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  return 'just now';
};

function Row({ n }: { n: Notice }) {
  return (
    <a
      href={n.url}
      className={cn('flex items-start gap-3 border-b px-4 py-3 last:border-b-0 hover:bg-muted', !n.read && 'bg-accent/40')}
    >
      <span aria-hidden className={cn('mt-2 size-2 shrink-0 rounded-full', n.read ? 'bg-transparent' : 'bg-primary')} />
      <span className="min-w-0 flex-1">
        <strong className="block text-sm font-medium">{n.title}</strong>
        {n.body && <span className="block truncate text-sm text-muted-foreground">{n.body}</span>}
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1">
        <Badge>{n.kind_label}</Badge>
        <time className="text-xs text-muted-foreground" dateTime={n.created_at} title={new Date(n.created_at).toLocaleString()}>
          {ago(n.created_at)}
        </time>
      </span>
    </a>
  );
}

export function Notifications() {
  const [filter, setFilter] = useState<Filter>('all');
  const client = useQueryClient();
  const list = useQuery({ queryKey: ['notifications', filter], queryFn: () => getNotifications(filter) });
  const readAll = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notifications'] });
      toast('All notifications marked as read.', 'success');
    },
    onError: () => toast('Could not mark notifications as read.', 'error'),
  });

  const unread = list.data?.unread ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            Notifications <span className="ml-2 text-sm font-normal text-muted-foreground">{unread} unread</span>
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">Assignments, mentions, comments, leave and attendance decisions.</p>
        </div>
        <div className="flex items-center gap-2">
          {(['all', 'unread'] as const).map((f) => (
            <Button key={f} size="sm" variant={filter === f ? 'default' : 'outline'} onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : 'Unread'}
            </Button>
          ))}
          {unread > 0 && (
            <Button size="sm" variant="outline" disabled={readAll.isPending} onClick={() => readAll.mutate()}>
              Mark all read
            </Button>
          )}
        </div>
      </div>

      <Card className="overflow-hidden p-0">
        {list.isPending && (
          <div data-testid="notifications-loading" className="space-y-3 p-4">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        )}
        {list.isError && (
          <div className="p-6 text-center">
            <p className="text-sm">Couldn’t load notifications.</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => list.refetch()}>Try again</Button>
          </div>
        )}
        {list.data && list.data.items.length === 0 && (
          <div className="p-8 text-center">
            <h3 className="font-medium">{filter === 'unread' ? 'Nothing unread' : 'No notifications yet'}</h3>
            <p className="mt-1 text-sm text-muted-foreground">You will see assignments, mentions and decisions here.</p>
          </div>
        )}
        {list.data?.items.map((n) => <Row key={n.id} n={n} />)}
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test && npm run build`
Expected: all tests pass; build clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): notifications page on befui components"
```

---

### Task 5: Docker, parity check, docs, and flip

**Files:**
- Modify: `Dockerfile`, `.dockerignore`, `docker-compose.yml` (only if needed), `context.md`, `AGENTS.md` and `CLAUDE.md` (one short "React UI" paragraph each)

**Interfaces:** Consumes everything above. Produces a production image that contains `frontend/dist`, and the decision to set `REACT_PAGES=notifications`.

- [ ] **Step 1: Node build stage in the Dockerfile**

Add before the existing `FROM python:3.12-slim`:

```dockerfile
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
```

and after `COPY . .` in the Python stage:

```dockerfile
COPY --from=frontend /frontend/dist /app/frontend/dist
```

Add `frontend/node_modules/` and `frontend/dist/` to `.dockerignore` so the local copies are not sent as build context.

- [ ] **Step 2: Build and run the image**

Run: `docker build -t pq-test .`
Expected: succeeds; `docker run --rm pq-test ls /app/frontend/dist` shows `app.js app.css`.

- [ ] **Step 3: Parity check in the browser (local)**

```bash
cd frontend && npm run build && cd ..
REACT_PAGES=notifications venv/bin/python manage.py runserver 8010
```

Log in as `dev1 / testpass123` (after `seed_data`), create a few notifications (assign dev1 a ticket from `owner`), then verify on `/notifications/` against the legacy page (open it in a second tab with the switch off):

- [ ] Heading shows the same unread count; All/Unread filter match.
- [ ] Each row shows title, body, kind label, relative time; unread rows are highlighted.
- [ ] Clicking a row opens the ticket and marks it read (it uses the existing `/notifications/<id>/open/` link).
- [ ] "Mark all read" works, shows the green toast, and the list refreshes without a page reload.
- [ ] Sidebar, topbar, bell dot and presence still look and behave exactly as before (no style bleed from Tailwind).
- [ ] Switching company (company switcher) then reloading shows that company's notifications only.
- [ ] Phone width (375px) is usable; keyboard Tab reaches filters, the button and rows.
- [ ] Browser console has no errors.

- [ ] **Step 4: Full regression**

Run in the background and poll the log (about 3.5 minutes):

```bash
venv/bin/python manage.py test apps > /tmp/full-suite.log 2>&1 &
```

Expected: only the known `test_signup_creates_user` failure. Run `cd frontend && npm test` too.

- [ ] **Step 5: Docs, flip, commit**

- Append to today's `## 2026-10-12` section of `context.md`: what was added (uiapi, `REACT_PAGES`, `/ui/`, `frontend/`), the scoped-theme decision (why befui variables live on `.befui` and preflight is skipped), and "legacy notifications template deliberately kept until the React page has run in production for a while".
- Add a short "React UI (in migration)" paragraph to `CLAUDE.md` and `AGENTS.md`: where `frontend/` lives, build/test commands, `REACT_PAGES`, that `/ui-api/v1/` endpoints must reuse `service.py` and the `accessible_*` helpers, and that new pages need parity with the legacy template before the switch is flipped.
- Set `REACT_PAGES=notifications` in the deployment environment (and `docker-compose.yml` `environment`) only after Step 3 passes.
- This is user-visible, so cut a release per CLAUDE.md: add a `CHANGELOG.md` entry at the top (new minor version, `> In short:` line, bold sentence leads, plain words, e.g. "**The notifications page has a fresh new look.**") and bump `APP_VERSION` in `core/settings.py` in the same commit; run `venv/bin/python manage.py test apps.core` to confirm the changelog tests pass.

```bash
git add Dockerfile .dockerignore docker-compose.yml context.md CLAUDE.md AGENTS.md CHANGELOG.md core/settings.py
git commit -m "build: Node stage for the React frontend; docs; release notes"
```

---

## Out of scope (next plans)

- React app shell (sidebar, topbar, bell, toasts) and `/ui-api/v1/bootstrap/` (deferred from the spec's step 1: the pilot runs inside the legacy shell, so nothing needs it yet; it arrives with the first full-page React section).
- Dark mode, hashed asset filenames, and a Vite dev server with HMR (`npm run dev` is a watch build for now; add HMR when iterating on UI becomes slow).
- Remaining pages, in the order the spec lists.
