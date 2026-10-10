# Backups and restore

## What's backed up, and where
- **Every database:**
  - `admin.db`
  - `catalog.db`
  - each family's `tenant_….db`
  - the legacy `tenant.db` and `curiculy.db`
- **Work-sample files**, mirrored.
- **Location:** `/datalake/projects/curiculy/backups/`, on the big data array, a different disk from the databases (NVMe).

## How it runs
- **The `curiculy_backup` container** (compose profile `backup`) runs `scripts/backup.py` **every 24 hours**:
  1. Copies each database with SQLite's online backup, which is consistent even while the app is writing.
  2. Checks each copy with `PRAGMA integrity_check` and lists them in `manifest.json`.
  3. Mirrors **new** work-sample files into `backups/evidence/`. Stored files never change, so only new ones are copied.
  4. **Keeps the newest 14 snapshots.**
- **It exits with an error if any copy fails its check.** `docker compose logs backup` shows each run.
- **The log check reports the latest snapshots** and their check results (see [Monitoring](monitoring.md)).

**Turn it on** (one time):
```
docker compose --profile backup up -d backup
```

**Back up right now** (always do this before a deploy):
```
docker exec curiculy_backup python scripts/backup.py --data-dir /data --evidence-dir /data/evidence --dest /backups
```

## Restore a snapshot
1. `docker compose stop api`
2. Copy the snapshot's databases over the live ones, and delete leftover write-ahead files so SQLite doesn't replay an old log:
   ```
   sudo cp /datalake/projects/curiculy/backups/<snapshot>/*.db data/ && sudo rm -f data/*.db-wal data/*.db-shm
   ```
3. Copy any missing work-sample files from `backups/evidence/` back into the evidence folder.
4. `docker compose start api`

**Practice on a scratch copy now and then:** copy a snapshot into an empty folder and run `python3 scripts/check_foreign_keys.py --data-dir <that folder>`. Every file should say OK.

## Open items
- **No off-site copy yet.** The backups sit in the same building as the server, so a fire or theft loses both. Copy `/datalake/projects/curiculy/backups` off-site with restic, rclone or an external drive. **This is the most important ops gap.**
- **An older `./backups` folder** (about 5 MB) from before the data array was used still sits in the production folder. It's safe to delete once an off-site copy exists; until then it's a harmless extra copy.
- **Run a restore drill** before the public launch, and record the target recovery time and acceptable data loss (Phase 8).
