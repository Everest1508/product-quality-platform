# Live presence and alerts

## What people see

**Online now** in the sidebar lists who has the app open and which kind of page
they are on, for example "Viewing ticket #12". It never shows a title or a
product name, because the person looking might not have access to it. A person
goes to "away" after five minutes without input or when the tab is hidden.

The badge in the panel shows how the page is connected:

| Badge | Meaning |
|---|---|
| Live | A WebSocket is open. Changes arrive at once. |
| Every 25s | The WebSocket is blocked, so the page asks the server every 25 seconds. |
| Connecting | The first attempt is still running. |
| Offline | You are signed out or have no workspace. |

## If it says "Every 25s" for good

The WebSocket needs the proxy in front of the app to pass the `Upgrade`
header. With nginx:

```nginx
location /ws/ {
    proxy_pass http://app:8011;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

The app must run under an ASGI server. The Dockerfile uses daphne. The
`docker-compose` entrypoint uses `runserver`, which also works because `daphne`
comes first in `INSTALLED_APPS`. Gunicorn without a Uvicorn or Daphne worker
cannot serve `/ws/` at all. Also check that the site's host name is in
`DJANGO_ALLOWED_HOSTS`, because the socket rejects any other Origin.

Several app processes need `REDIS_URL` set. Without it each process keeps its own
in-memory channel layer and people on different processes do not see each other
live. The 25 second fallback still works across processes, because it reads the
database.

## Alerts on your phone or computer

Open the bell and press **Turn on alerts**. The server needs the three
`WEBPUSH_VAPID_*` environment variables for this. Without them the bell works
but nothing is pushed to a closed app.
