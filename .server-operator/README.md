# Server Operator command files

Each `.serop` file is a list of commands for the Server Operator app. A line in
square brackets starts a command, and the lines under it are what runs, in order.

| File | What is in it |
|---|---|
| `deploy.serop` | Full and quick deploys, a health check, reset to latest main, restart, stop, status |
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

1. `[Dry Run Fix DSR Hours]` shows old auto-logged rows with more than a working day of hours. `[Fix DSR Hours]` makes them stop counting while keeping their open-for time; it is optional (see below).
2. `[Dry Run Reminders]` during working hours to see how many reminders would go out.
3. `[Dry Run Automation Rules]` to see which rules would file tickets.

## Reading the DSR fix

`[Dry Run Fix DSR Hours]` prints one line per row, for example
`65 [Neomed] #9: Delivery Boy Tracking is not working: open for 1567.38h -> counts 0h, open-for time kept`: the row id,
the product, the ticket and how long it was open. The last line says how many would stop counting. Every row it lists
was logged automatically when a ticket was resolved and holds more than one working day, which is the old behaviour
of counting a whole open ticket as worked time.

`[Fix DSR Hours]` backs up the database, then moves each of those hours into the row's **open-for** time (still shown
on the DSR, marked "not counted") and sets the counted hours to 0, so nobody's DSR total is inflated. It runs the dry run
again afterwards and should find nothing. It never touches hours a person typed in. Two lines with the same ticket are
usually two people (one row per assignee). Reports and payslips already made are not recalculated. Running it is
optional: until you do, those old rows keep counting their full hours. New tickets behave this way on their own.

## When a pull fails

Run git with `sudo` in this folder, as these commands do: earlier deploys created root-owned files, and a
plain `git pull` as another user stops halfway and leaves a half-updated folder. `[Reset To Latest Main]`
repairs that. It saves `docker-compose.yml` to `~/compose.bak`, makes every tracked file match `origin/main`
(this **discards edits to tracked files made on the server**, but not `db.sqlite3` or `media/`), and
shows a `diff` of the saved compose file so you can put back any settings of your own. Rebuild after it.

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
