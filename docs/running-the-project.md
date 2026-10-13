# Running the project

This page gets PQ Platform running on your machine, explains how the pieces fit, and lists what to set up when you
put it on a server. For what the app does, see the [README](../README.md) and the [user guides](guides/README.md).

## The short version

You need **Python 3.12 or newer**, **Node 22 or newer** and **Git**. From a fresh clone:

```bash
python3 -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
(cd frontend && npm ci && npm run build)               # the React app, built into frontend/dist
./bootstrap.sh                                         # migrate + demo data + a superuser
python manage.py runserver 8010
```

Open <http://localhost:8010> and sign in as `owner` with the password `testpass123`.
The other demo users are `admin`, `dev1`, `dev2`, `support` and `viewer`, with the same password.

If you skip `./bootstrap.sh`, run `python manage.py migrate` and then `python manage.py seed_data` instead.

## How the pieces fit

| Piece | What it is | Where it runs |
|---|---|---|
| **Django** (`apps/`, `core/`) | Login, the JSON API (`/ui-api/v1/` for the app, `/api/v1/` for SDKs), WebSockets, background commands. | `runserver` is an ASGI server (daphne) so it serves WebSockets too. |
| **React app** (`frontend/`) | Every screen. Built by Vite into `frontend/dist`. | Django serves the built files at `/ui/`, so there is no second server to start. |
| **SQLite** (`db.sqlite3`) | The database. Created by `migrate`. | A file in the project folder. |
| **Redis** (optional) | Carries live updates between several server processes. | Not needed for one process. |

Django renders only the one page that boots React (`templates/uiapi/shell.html`) and an offline page. Everything else
is React talking to the JSON API, so a change to a screen is a change under `frontend/`, and the browser needs a rebuilt
`frontend/dist` to see it.

## Step by step

### 1. Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The project's commands are written `python manage.py ...`. If you do not activate the virtualenv, use
`venv/bin/python manage.py ...` instead.

### 2. The front end

```bash
cd frontend
npm ci            # installs exactly what package-lock.json says
npm run build     # type-checks, then builds into frontend/dist
cd ..
```

Without `frontend/dist` every page shows only the message "The new frontend has not been built".

### 3. Database and demo data

```bash
./bootstrap.sh              # migrate, reseed the "Acme Corp" demo workspace, create a superuser
./bootstrap.sh --keep       # same, but keep demo data that already exists
./bootstrap.sh --no-seed    # migrate and the superuser only
```

`bootstrap.sh` also creates a superuser named `root` (password `testpass123`, change it with `SUPERUSER_PASSWORD=...`).
The app has no admin site, so you only need it for the Django shell. The demo people are listed in the
[README](../README.md#-demo-accounts--personas).

To start over, delete `db.sqlite3` and run `./bootstrap.sh` again.

### 4. Start it

```bash
python manage.py runserver 8010
```

Sign in at <http://localhost:8010>. A user with no company is sent to **Company setup** to create one.

## Working on the front end

Two terminals:

```bash
# terminal 1: Django
python manage.py runserver 8010

# terminal 2: rebuild the React app whenever a file changes
cd frontend && npm run dev
```

`npm run dev` runs `vite build --watch`, so after each save refresh the browser to see the change. Other commands:

| Command (in `frontend/`) | What it does |
|---|---|
| `npm test` | Runs the component and page tests (Vitest). |
| `npx tsc --noEmit` | Type-checks without building. |
| `npm run build` | Type-checks and builds `frontend/dist`. |

The components come from [befui](https://befui.vercel.app) and are copied into `frontend/src/components/ui`.
Add one with `python scripts/befui_add.py <name>`.

## Running the tests

```bash
python manage.py test apps                       # everything, about 5 minutes
python manage.py test apps.tickets               # one app
python manage.py test apps.core.tests.ReleaseNameTest   # one test class
(cd frontend && npm test)                        # the React tests
```

One backend test, `test_signup_creates_user`, fails on a clean checkout because the self-serve signup route does not
exist. It is not a regression. `python manage.py check` should report only the `staticfiles.W004` warning.

## Background jobs

Some features only work if a command runs on a schedule. Nothing in the project starts them for you, so add them to
cron (or your platform's scheduler) wherever you run the app:

| Command | How often | What it does |
|---|---|---|
| `python manage.py evaluate_rules` | every 5 minutes | Files tickets when an error crosses an automation rule's threshold. |
| `python manage.py send_attendance_reminders` | every 5 to 10 minutes | Reminds people to check in and out. |
| `python manage.py notify_todos` | every morning | One reminder a day about overdue to-dos. |
| `python manage.py fix_dsr_hours --dry-run` | once, after upgrading | Lists old auto-logged DSR rows with more than a working day of hours. Run it without `--dry-run` to cap them. |

Most commands take `--dry-run` to show what they would do first.

## Settings you can change

Everything is read from environment variables. With none set, the defaults suit local development.

| Variable | Default | Use |
|---|---|---|
| `DJANGO_DEBUG` | `True` | Set to `False` in production. Then the two secrets below are required. |
| `DJANGO_SECRET_KEY` | a public dev key | Signs sessions. Set your own in production. |
| `SHARED_SERVER_ENCRYPTION_KEY` | a public dev key | Encrypts shared-server passwords. Generate one: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames the site answers to. |
| `CSRF_TRUSTED_ORIGINS` | the project's own host and `localhost:8011` | Comma-separated origins (with `https://`) allowed to post forms. Add your domain. |
| `REDIS_URL` | not set | For example `redis://localhost:6379/0`. Needed only when more than one server process runs. |
| `WEBPUSH_VAPID_PUBLIC_KEY`, `WEBPUSH_VAPID_PRIVATE_KEY`, `WEBPUSH_VAPID_SUBJECT` | not set | Turns on phone and desktop push notifications. The settings file says how to generate the keys. |

There is no `.env` file support; export the variables or put them in your service definition.

## Docker

```bash
docker-compose up --build
```

This builds the React app in a Node stage, starts Redis, runs the migrations and serves the site on
<http://localhost:8011>. The database file `db.sqlite3` and the `media/` folder are mounted from the project folder, so
they survive a rebuild. To load the demo data into the container:

```bash
docker-compose exec web python manage.py seed_data
```

Change `DJANGO_SECRET_KEY` and the other values in `docker-compose.yml` before using it for anything real.

## Putting it on a server

1. Set `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`, `SHARED_SERVER_ENCRYPTION_KEY`, `DJANGO_ALLOWED_HOSTS` and
   `CSRF_TRUSTED_ORIGINS`.
2. Build the front end (`npm ci && npm run build` in `frontend/`) on the server, or use the Docker image, which does it.
3. Run it with an ASGI server so WebSockets work: `daphne -b 0.0.0.0 -p 8011 core.asgi:application`.
   Do not use plain gunicorn with the WSGI app for the real site, because live presence and notifications need WebSockets.
4. Put a proxy such as nginx in front with HTTPS, and pass the `Upgrade` header for `/ws/` (see
   [Live presence and alerts](guides/presence-and-alerts.md)).
5. Set `REDIS_URL` if you run more than one process.
6. Add the scheduled commands from the table above.
7. Back up `db.sqlite3`. For heavier use, switch to PostgreSQL in `core/settings.py`.

The `.server-operator/` folder has deploy and maintenance scripts for the Server Operator tool, if you use it.

## If something goes wrong

| What you see | Likely cause and fix |
|---|---|
| The page says "The new frontend has not been built", or `/ui/...` files are not found. | The front end is not built. Run `cd frontend && npm ci && npm run build`. |
| A change to a screen does not show. | Rebuild with `npm run build` (or keep `npm run dev` running) and refresh. |
| "Online now" says **Every 25s**, or `/ws/...` is a 404. | The server is not an ASGI server, or the proxy drops the `Upgrade` header. Use `runserver`/`daphne` and see the presence guide. |
| Sign-in or a form says CSRF verification failed. | Your address is not in `CSRF_TRUSTED_ORIGINS`. |
| `ImproperlyConfigured: ... must be set when DJANGO_DEBUG is off`. | Set `DJANGO_SECRET_KEY` and `SHARED_SERVER_ENCRYPTION_KEY`. |
| `DisallowedHost`. | Add the hostname to `DJANGO_ALLOWED_HOSTS`. |
| Everything redirects to **Company setup**. | That user has no company yet. Create one, or use a demo user. |
| Reminders, rules or to-do alerts never arrive. | The scheduled commands are not running. See *Background jobs*. |
| Port already in use. | Pick another: `python manage.py runserver 8020`. |
