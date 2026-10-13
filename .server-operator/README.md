# Server Operator command files

Each `.serop` file is a list of commands for the Server Operator app. A line in
square brackets starts a command, and the lines under it are what runs, in order.

| File | What is in it |
|---|---|
| `deploy.serop` | Full and quick deploys, a health check, restart, stop, status |
| `maintenance.serop` | Logs, migrate, database backup, the scheduled commands (each with a dry run), Django check, shell |

## How a deploy works now

The React front end is built inside the image (the `Dockerfile` has a Node stage), so a deploy
is just a rebuild: no separate front-end host, no `collectstatic`. `entrypoint.sh` runs
`migrate` every time the container starts, so a deploy also migrates.

- **`[Deploy Quick]`** pulls and rebuilds only `web`. Redis keeps running, so the outage is short.
- **`[Deploy Full]`** backs up `db.sqlite3` first, then takes everything down and rebuilds. Use it
  when `docker-compose.yml` or the Redis service changed.
- Both use `git pull --ff-only`, which stops with a message instead of silently discarding local
  edits on the server (the old command stashed them). If it stops, look at `git status` on the server.
- **`[Health Check]`** after a deploy: the login page and `/ui/app.js` should both answer `200`.
  A missing `/ui/app.js` means the front end was not built into the image.

## After the first deploy of a new release

1. `[Dry Run Fix DSR Hours]`, read the list, then `[Fix DSR Hours]` once. It caps old auto-logged
   DSR rows that show more than a working day of hours.
2. `[Dry Run Reminders]` during working hours to see how many reminders would go out.
3. `[Dry Run Automation Rules]` to see which rules would file tickets.

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
  a normal deploy. (The old `update-changelog.serop` copied the file into a running container, which
  no longer fits: a release also changes the version number in the code, and the "show once" window
  keys off that version.)
- Before turning `DJANGO_DEBUG` off in `docker-compose.yml`, set `DJANGO_SECRET_KEY` and
  `SHARED_SERVER_ENCRYPTION_KEY` to your own values. The app refuses to start without them.
