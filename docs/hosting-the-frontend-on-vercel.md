# Hosting the front end on Vercel (optional)

By default Django serves the React app itself, so you host one thing. This page is for the other way: the **app on Vercel**
(or any static host) and **Django on your server**. Nothing here changes the default; you can still run `docker compose up`
and use the site at your server's address.

## The one rule: both addresses must share a parent domain

Your login is a cookie set by Django. If the app is on `app.example.com` and Django is on `crm.example.com`, the browser treats
them as the **same site**, so the cookie works. If the app is on `something.vercel.app` and Django on a different domain, the
cookie is "third-party" and Safari and Chrome block it, so people cannot stay signed in. **Use a subdomain of the domain you
already own** for the app (for example `app.beforth.in` next to `crm.beforth.in`).

## 1. Django server

Set these environment variables for the `web` container (in `docker-compose.yml`, under `environment`) and restart it:

| Variable | Example | What it does |
|---|---|---|
| `FRONTEND_ORIGINS` | `https://app.beforth.in` | The address of the hosted app. Allows it to call the API with the login cookie, trusts it for CSRF, and lets it open the WebSockets. Comma-separate more than one. |
| `COOKIE_DOMAIN` | `.beforth.in` | The parent domain, with a leading dot. Shares the login and CSRF cookies between `app.` and `crm.`. |
| `DJANGO_ALLOWED_HOSTS` | `crm.beforth.in,localhost` | As before. The app's hostname is added to it automatically from `FRONTEND_ORIGINS`. |
| `DJANGO_DEBUG` | `False` | Recommended. Then also set your own `DJANGO_SECRET_KEY` and `SHARED_SERVER_ENCRYPTION_KEY`. |

With `FRONTEND_ORIGINS` set and `DJANGO_DEBUG=False`, the cookies are also marked Secure (HTTPS only), so the server must be
reached over HTTPS.

Optionally `COOKIE_SAMESITE` (default `Lax`). `None` allows an unrelated domain but, as above, many browsers block that.

## 2. Vercel

1. Create a project from the GitHub repository. In **Settings → General** set **Root Directory** to `frontend`.
2. The repository already has `frontend/vercel.json` with the build command (`npm run build:hosted`), the output folder
   (`dist-hosted`) and the rewrite that sends every URL to `index.html` so links and refreshes work.
3. In **Settings → Environment Variables** add `VITE_API_ORIGIN` = your Django address, for example `https://crm.beforth.in`
   (no trailing slash). It is read when the app is built, so redeploy after changing it.
4. In **Settings → Domains** add `app.beforth.in`, and in your DNS add the `CNAME` record Vercel shows you.

## 3. Check it

Open `https://app.beforth.in`, sign in, then open a page and add something. In the browser's developer tools, Network tab,
requests should go to `https://crm.beforth.in/ui-api/v1/...` and succeed. The "Online now" badge should say **Live**.

## What differs when the app is hosted this way

- **Pages:** the app handles its own addresses (`/dsr/`, `/tickets/`). If you are not signed in, it sends you to `/login/` itself.
- **Signing in and out, and adding data:** done through the API. The app fetches a CSRF token from `/ui-api/v1/auth/csrf/`.
- **Live presence and notifications:** the browser opens a WebSocket straight to `wss://crm.beforth.in/ws/...`. Vercel cannot proxy
  WebSockets, which is why it connects to Django directly.
- **Notifications:** clicking one marks it read in the background and opens the page on the app's address.
- **Install-to-phone and offline page:** these come from the Django site (the service worker and manifest belong to its address),
  so they are switched off on the hosted app. People can still use the site normally.
- **Serop (the desktop app):** unaffected. Its sign-in and API stay on the Django address, which still serves its own copy of the app.
- **CSV exports and payslip printing:** CSV downloads come from the Django address; printing works as before.

## If it does not work

| What you see | Likely cause |
|---|---|
| Signing in works but you are sent back to the sign-in page. | The cookie is not shared. Check `COOKIE_DOMAIN` (with the leading dot), that both addresses are on the same parent domain, and that both use HTTPS. |
| "CSRF verification failed" or a 403 when saving. | `FRONTEND_ORIGINS` is missing or has a typo (it must match exactly, with `https://` and no trailing slash). |
| The browser console shows a CORS error. | Same: the origin is not in `FRONTEND_ORIGINS`, or the server was not restarted after setting it. |
| "Online now" says **Every 25s**, not **Live**. | The WebSocket is blocked. Check the proxy in front of Django passes the `Upgrade` header, and that the app's hostname is allowed (it is added from `FRONTEND_ORIGINS` automatically). |
| Every page says the app could not load. | `VITE_API_ORIGIN` was not set when Vercel built the app. Set it and redeploy. |
