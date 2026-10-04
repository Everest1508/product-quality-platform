# Server Operator command files

Each `.serop` file is a list of commands for the Server Operator app. A line in
square brackets starts a command, and the lines under it are what runs, in order.

```
[Deploy Full]
sudo git stash
sudo git pull
...
```

| File | What is in it |
|---|---|
| `deploy.serop` | Full and quick deploys, restart, stop, status |
| `update-changelog.serop` | Push a new `CHANGELOG.md` to the running container without a rebuild |
| `maintenance.serop` | Logs, migrate, database backup, automation rules, Django check, shell |

Notes for this project:

- The compose service is called `web`. Redis runs beside it as `redis`.
- `entrypoint.sh` runs `migrate` every time the container starts, so a deploy
  already migrates. `[Migrate]` is there for running it without a restart.
- The image copies the code in, so `CHANGELOG.md` changes need a rebuild, or
  `[Update Changelog]`, which copies the file in. The app re-reads it when its
  modified time changes, so no restart is needed.
- `db.sqlite3` and `media/` are bind-mounted from the host and are not in git, so
  `git stash` and `git pull` leave them alone. Run `[Backup Database]` first.
- `[Deploy Full]` takes the site down while it rebuilds. `[Deploy Quick]` rebuilds
  only `web` and leaves Redis running, so the outage is shorter.
- Before turning `DJANGO_DEBUG` off in `docker-compose.yml`, set
  `DJANGO_SECRET_KEY` and `SHARED_SERVER_ENCRYPTION_KEY` to your own values. The
  app refuses to start without them.
