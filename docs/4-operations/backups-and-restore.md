# Backups and restore

Backups are planned in layers ([decision record](../6-planning/decision-records/data-tier.md#backups-layered-not-just-nightly)). Layers 2 and 3 run today; layer 1 and the off-site copy are next (see [Open items](#open-items)).

| Layer | What | Status |
|---|---|---|
| 1. Continuous archive | Every change shipped within about a minute; restore to any minute (WAL archiving) | **Not yet** |
| 2. Nightly full copy | The whole database, **restored into a scratch database and counted** every night | **Running** |
| 3. Nightly family copies | One file per family, to restore one family without touching anyone else | **Running** |
| Off-site | Encrypted copies of the above, and the work samples, outside the house | **Not yet** |

## What's backed up, and where
- **The whole database:** `<snapshot>/curiculy.dump` (`pg_dump` custom format).
- **Each family:** `<snapshot>/families/<family>.json.gz`, every row that family owns. Demo households are skipped.
- **Work-sample files**, mirrored into `backups/evidence/`.
- **What was written and checked:** `<snapshot>/manifest.json`.
- **Location:** `/datalake/projects/curiculy/backups/`, on the big data array, a different disk from the database (NVMe).

## How it runs
**The `curiculy_backup` container** (compose profile `backup`) runs `scripts/backup.py` **every 24 hours**. Each run:
1. Dumps the whole database as the owner role.
2. **Restores that dump into a scratch database,** counts every table, checks no table is missing, then drops the scratch copy. A dump that can't be restored fails the run.
3. Exports each family as the app's role, so row-level security scopes every export to that one family.
4. Mirrors **new** work-sample files. Stored files never change, so only new ones are copied.
5. **Keeps the newest 14 snapshots.**

**It exits with an error if any step fails;** `docker compose logs backup` shows each run. The container is built from the Dockerfile's `backup` stage, which adds `pg_dump` and `pg_restore` for Postgres 18.

**Turn it on** (one time):
```bash
docker compose --profile backup up -d backup
```

**Back up right now** (always do this before a deploy):
```bash
docker exec curiculy_backup python scripts/backup.py --evidence-dir /data/evidence --dest /backups
```

## Restore one family
For example, when a parent deleted something by mistake. It replaces only that family's rows, in one transaction; everyone else is untouched.
```bash
docker exec -it curiculy_backup python scripts/restore_family.py /backups/<snapshot>/families/<family>.json.gz
```
It asks before replacing anything (`--yes` skips the question). Sign-ins aren't part of a family copy, so they aren't touched. Copy any missing work-sample files for that family back from `backups/evidence/<family>/`.

## Restore everything
For a damaged database or a new server:
1. Stop the app: `docker compose stop api`
2. Restore the dump over the live database, as the owner role:
   ```bash
   docker exec -i curiculy_db pg_restore --clean --if-exists --no-owner -U curiculy_owner -d curiculy < /datalake/projects/curiculy/backups/<snapshot>/curiculy.dump
   ```
3. Copy any missing work-sample files from `backups/evidence/` back into the evidence folder.
4. Start the app: `docker compose start api`. Startup applies any newer migrations and runs the safety check before it accepts requests.

**On a new server,** start the `db` service first (its first start creates the two roles), then restore as above.

## Practice
Every nightly run already restores the full dump into a scratch database. Now and then, also restore one family into a test copy with `scripts/restore_family.py`. Before the public launch, run a full drill: rebuild on a spare machine from backups alone, and record how long it took and how much would have been lost (Phase 8).

## Open items
- **Off-site copy.** The backups sit in the same building as the server, so a fire or theft loses both. Copy `/datalake/projects/curiculy/backups` off-site, encrypted (for example restic to Backblaze B2). **This is the most important ops gap.** It needs a cloud account.
- **Continuous archive (layer 1):** WAL archiving with pgBackRest or WAL-G, so a restore can reach any minute rather than last night.
- **The old SQLite files** in `./data` (`admin.db`, `catalog.db`, `tenant_*.db`, `curiculy.db`) are no longer used after the move to Postgres. Keep them until the first Postgres backups are confirmed, then archive them.
- **An older `./backups` folder** (about 5 MB) from before the data array was used still sits in the production folder. It's safe to delete once an off-site copy exists.
