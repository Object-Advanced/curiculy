# Production and deploys

How the live site runs, how a new version goes out, and how to roll back.

## How the live site runs
- **Address:** **https://curiculy.com**. Cloudflare handles HTTPS, then a tunnel container (`cloudflare_tunnel`) forwards traffic to `http://192.168.50.136:3040`, the home server's network address.
  - **Never bind port 3040 to `127.0.0.1`.** The tunnel reaches it over the network address, so that would take the site down.
- **App container:** `curiculy_api`, image `curiculy-api:latest`, from `docker-compose.yml` in `/home/objadv/curiculy`. It restarts automatically and has a health check (`/api/health` every 30 s).
- **Database container:** `curiculy_db`, Postgres 18.4, with its data in `./data/postgres` on the NVMe drive. It isn't published to the host or the network; only the app and backup containers reach it. Its first start creates the two roles (`docker/postgres/10-curiculy-roles.sh`). On every start, the app waits for it, applies migrations, and **refuses to start unless families are walled off** (see [Data model](../5-engineering/data-model.md)).
- **The production folder is `/home/objadv/curiculy`**, on the local branch `production`. The container uses the code straight from this folder (`./app`, `./static`, `./scripts`, `./index.html`, `./sw.js`):
  - **Changes to static files reach families immediately.**
  - Python changes take effect on restart.
  - `index.html` and `sw.js` stay fixed to the version the container started with until it's recreated.
  - **So never edit or `git switch` in the production folder except as part of a deploy.** Develop in `/home/objadv/curiculy-dev`.
- **Secrets** live in `/home/objadv/curiculy/.env` (never commit or print it):
  - `JWT_SECRET`
  - `POSTGRES_PASSWORD` (the database superuser; only for the container itself), `CURICULY_OWNER_PASSWORD`, `CURICULY_APP_PASSWORD`. Each one a long random value of letters and digits only, because they go inside database addresses where `/`, `+` or `=` would break them: `openssl rand -hex 32`.
  - `MAIL_*`
  - `FORWARDED_ALLOW_IPS=172.22.0.1`, the Docker gateway, so the app records visitors' real addresses
  - `BACKUP_HOST_DIR=/datalake/projects/curiculy/backups`
- **Backups container:** `curiculy_backup` (compose profile `backup`). See [Backups](backups-and-restore.md).
- **Never run `docker compose down` in the production folder.**

## Deploy a new version
The standard steps, used for Phase 1, Phase 2 and the greeting fix:

1. **The code is merged into `master`** on GitHub, with tests green (lint, pytest, e2e).
2. **Snapshot first:**
   ```
   docker exec curiculy_backup python scripts/backup.py --evidence-dir /data/evidence --dest /backups
   ```
3. **Keep a rollback copy** of the running image:
   ```
   docker tag curiculy-api:latest curiculy-api:pre-<name>
   ```
4. **Build the new images** from the development copy at `master`:
   ```
   cd /home/objadv/curiculy-dev && git fetch github && git switch --detach github/master
   docker build --target base -t curiculy-api:latest /home/objadv/curiculy-dev
   docker build --target backup -t curiculy-backup:latest /home/objadv/curiculy-dev
   ```
5. **Switch production and restart only the app**, back to back. Expect about 10–20 seconds of odd-looking pages; pick a quiet time.
   ```
   cd /home/objadv/curiculy && git fetch github && git switch -C production github/master
   docker compose up -d --no-build --wait api
   ```
6. **Check:**
   - `https://curiculy.com/api/health`
   - security headers (`curl -sI`)
   - that the new version token shows in `sw.js`
   - `docker logs --since 5m curiculy_api` has no errors
7. If the change bumped the cache token, families get the new version on their next visit; a refresh is enough.

**Deploying with Claude:** Claude's auto mode blocks merges and production commands by design. Claude switches the session to **Manual (ask before running)**, and you click **Allow** for each step: merge, snapshot, restart, checks.

## Roll back
```
docker tag curiculy-api:pre-<name> curiculy-api:latest
cd /home/objadv/curiculy && git switch -C production <previous commit>
docker compose up -d --no-build --wait api
```

| Last deploys | Commit | Rollback tag |
|---|---|---|
| Backend spine part 1: state and grades, subjects, Library (2026-10-12; migrations 0002–0004) | `55cbb0f` | `pre-spine1` (api and backup) → commit `4654da8` |
| The move to Postgres (2026-10-12; fresh database) | `4654da8` | `pre-postgres` (api and backup) → commit `1367cf1`, the last SQLite version |
| Sticker journal (2026-10-11) | `1367cf1` | `pre-journal` → commit `c460c43` |
| Greeting fix (2026-10-10) | `51cce3b` | `pre-greeting` → commit `55a9654` |
| Phase 2 (2026-10-10) | `55a9654` | `pre-phase2` → commit `63f716e` |
| Phase 1 (2026-10-09) | `63f716e` | `pre-phase1` |

**Migrations run on startup.** Rolling back to code from before a migration needs either that migration's downgrade (`alembic downgrade <revision>`, as the owner role) or a restore. Prefer fixing forward; keep migrations additive where possible. If data was damaged, restore a snapshot (see [Backups](backups-and-restore.md)).

## First deploy of the Postgres version (one time)
The move from one SQLite file per family to Postgres ([decision record](../6-planning/decision-records/data-tier.md)). There are no real families yet, so it **starts with an empty database**. The old SQLite files stay in `./data`, untouched, so a rollback brings the old version back as it was.

1. **Add the three database passwords to `.env`** (see Secrets above).
2. **Snapshot the old files** with the old backup container, while it still runs:
   ```
   docker exec curiculy_backup python scripts/backup.py --data-dir /data --evidence-dir /data/evidence --dest /backups
   ```
3. **Keep rollback copies:** `docker tag curiculy-api:latest curiculy-api:pre-postgres`
4. **Build both images** (step 4 above), then switch the production branch (step 5's `git switch`).
5. **Start the database, then the app:**
   ```
   cd /home/objadv/curiculy && docker compose up -d --no-build --wait db api
   ```
   `docker logs curiculy_api` should show `Database ready`. If the safety check fails, the app won't start, and the log lists why.
6. **Recreate the owner's account:** make an invite (`docker compose exec api python scripts/create_invite.py`) and register again at curiculy.com.
7. **Restart the backup container on the new image,** then run a backup and read its `manifest.json`:
   ```
   docker compose --profile backup up -d --no-build backup
   docker exec curiculy_backup python scripts/backup.py --evidence-dir /data/evidence --dest /backups
   ```
8. **Check** as in step 6 of a normal deploy.

**Roll back this deploy:** `docker tag curiculy-api:pre-postgres curiculy-api:latest`, `git switch -C production <previous commit>`, `docker compose up -d --no-build --wait api`. Anything created in Postgres in between stays in `./data/postgres`, unused.
