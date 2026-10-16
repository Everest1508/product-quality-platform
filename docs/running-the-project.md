# Running the project

This page gets PQ Platform running on your machine, explains how the pieces fit, and lists what to set up when you
put it on a server. For what the app does, see the [README](../README.md) and the [user guides](guides/README.md).

## The short version

You need **Python 3.12 or newer** and **Git**. From a fresh clone:

```bash
python3 -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
./bootstrap.sh                                         # migrate + demo data + a superuser
python manage.py runserver 8010
```

Open <http://localhost:8010> and sign in as `owner` with the password `testpass123`.
The other demo users are `admin`, `dev1`, `dev2`, `support` and `viewer`, with the same password.

If you skip `./bootstrap.sh`, run `python manage.py migrate` and then `python manage.py seed_data` instead.

## How the pieces fit

| Piece | What it is | Where it runs |
|---|---|---|
| **Django** (`apps/`, `core/`) | Pages, login, the ingestion API (`/api/v1/` for SDKs), WebSockets, background commands. | `runserver` is an ASGI server (daphne) so it serves WebSockets too. |
| **Pages** | Server-rendered templates in `templates/`, with HTMX and Alpine.js for the interactive parts and plain CSS in `templates/core/css/`. | Django renders them; there is nothing to build. |
| **SQLite** (`db.sqlite3`) | The database. Created by `migrate`. | A file in the project folder. |
| **Redis** (optional) | Carries live updates between several server processes. | Not needed for one process. |

Every page is a Django view that renders a template. To change how a page looks, edit its template or the CSS under `templates/core/css/` and refresh the browser.

## Step by step

### 1. Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The project's commands are written `python manage.py ...`. If you do not activate the virtualenv, use
`venv/bin/python manage.py ...` instead.

### 2. Database and demo data

```bash
./bootstrap.sh              # migrate, reseed the "Acme Corp" demo workspace, create a superuser
./bootstrap.sh --keep       # same, but keep demo data that already exists
./bootstrap.sh --no-seed    # migrate and the superuser only
```

`bootstrap.sh` also creates a superuser named `root` (password `testpass123`, change it with `SUPERUSER_PASSWORD=...`).
It can also sign in to the Django admin at `/admin/`. The demo people are listed in the
[README](../README.md#-demo-accounts--personas).

To start over, delete `db.sqlite3` and run `./bootstrap.sh` again.

### 3. Start it

```bash
python manage.py runserver 8010
```

Sign in at <http://localhost:8010>. On an empty install the first user, or any staff account, is sent to **Company setup** to create the first company. Once a company exists, anyone else with no company (for example a member who was removed) is told to ask an owner or admin to add them.

## Running the tests

```bash
python manage.py test apps                       # everything, about 5 minutes
python manage.py test apps.tickets               # one app
python manage.py test apps.core.tests.ReleaseNameTest   # one test class
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

This builds the Python image, starts Redis, runs the migrations and serves the site with daphne on
<http://localhost:8011>. The database file `db.sqlite3` and the `media/` folder are mounted from the project folder, so
they survive a rebuild. To load the demo data into the container:

```bash
docker-compose exec web python manage.py seed_data
```

Change `DJANGO_SECRET_KEY` and the other values in `docker-compose.yml` before using it for anything real.

## Putting it on a server

1. Set `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`, `SHARED_SERVER_ENCRYPTION_KEY`, `DJANGO_ALLOWED_HOSTS` and
   `CSRF_TRUSTED_ORIGINS`.
2. Run it with an ASGI server so WebSockets work: `daphne -b 0.0.0.0 -p 8011 core.asgi:application`.
   Do not use plain gunicorn with the WSGI app for the real site, because live presence and notifications need WebSockets.
3. Put a proxy such as nginx in front with HTTPS, and pass the `Upgrade` header for `/ws/` (see
   [Live presence and alerts](guides/presence-and-alerts.md)).
4. Set `REDIS_URL` if you run more than one process.
5. Add the scheduled commands from the table above.
6. Back up `db.sqlite3`. For heavier use, switch to PostgreSQL in `core/settings.py`.

The `.server-operator/` folder has deploy and maintenance command files for the Server Operator tool (deploys, health check, backups, dry runs of the scheduled commands) and a crontab example; see its README.

## If something goes wrong

| What you see | Likely cause and fix |
|---|---|
| "Online now" says **Every 25s**, or `/ws/...` is a 404. | The server is not an ASGI server, or the proxy drops the `Upgrade` header. Use `runserver`/`daphne` and see the presence guide. |
| Sign-in or a form says CSRF verification failed. | Your address is not in `CSRF_TRUSTED_ORIGINS`. |
| `ImproperlyConfigured: ... must be set when DJANGO_DEBUG is off`. | Set `DJANGO_SECRET_KEY` and `SHARED_SERVER_ENCRYPTION_KEY`. |
| `DisallowedHost`. | Add the hostname to `DJANGO_ALLOWED_HOSTS`. |
| Everything redirects to **Company setup**. | That user has no company yet and is staff, or the install has no company at all. Create one, or use a demo user. Any other user with no company is signed out with a message instead. |
| Reminders, rules or to-do alerts never arrive. | The scheduled commands are not running. See *Background jobs*. |
| Port already in use. | Pick another: `python manage.py runserver 8020`. |
