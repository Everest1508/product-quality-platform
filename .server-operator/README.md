# Server Operator command files

Each `.serop` file is a list of commands for the Server Operator app. A line in
square brackets starts a command, and the lines under it are what runs, in order.

| File | What is in it |
|---|---|
| `deploy.serop` | `[Deploy Full]`: pull, take everything down, build and start again |
| `maintenance.serop` | `[Logs]`, `[Backup Database]`, the three scheduled jobs run by hand, and `[Shell]` |

## Deploying

`[Deploy Full]` is three commands:

```
sudo git pull --ff-only
sudo docker compose down
sudo docker compose up -d --build
```

The app is server-rendered Django with HTMX and Alpine (no Node, no front-end build), so a deploy is
just a rebuild of the Python image. `entrypoint.sh` runs `migrate` every time the container starts, so
a deploy also migrates. `git pull --ff-only` stops with a message instead of silently discarding local
edits on the server; if it stops, look at `git status` on the server.

Run `[Backup Database]` first when a release changes the database (the changelog says so).

## Scheduling

Server Operator runs a command when you click it. These need to run on their own, so add them to
the server's crontab (`-T` because cron has no terminal):

```
*/10 * * * * cd /path/to/product-quality-platform && docker compose exec -T web python manage.py send_attendance_reminders
*/5  * * * * cd /path/to/product-quality-platform && docker compose exec -T web python manage.py evaluate_rules
0 9  * * *   cd /path/to/product-quality-platform && docker compose exec -T web python manage.py notify_todos
```

## Other notes

- The compose service is called `web`. Redis runs beside it as `redis`.
- `db.sqlite3` and `media/` are bind-mounted from the host and are not in git. `[Backup Database]`
  copies the file into `backups/`.
- The "What's new" text comes from `CHANGELOG.md` inside the image, so a changelog change ships with
  a normal deploy.
- Run git on the server with `sudo`, as these commands do: earlier deploys created root-owned files,
  and a plain `git pull` as another user stops halfway.
- Before turning `DJANGO_DEBUG` off in `docker-compose.yml`, set `DJANGO_SECRET_KEY` and
  `SHARED_SERVER_ENCRYPTION_KEY` to your own values. The app refuses to start without them.
