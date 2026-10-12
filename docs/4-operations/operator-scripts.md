# Operator scripts

Command-line tools for the site owner, in `scripts/`. Run them inside the container from the production folder (`/home/objadv/curiculy`).

| Task | Command | Notes |
|---|---|---|
| **Make an invite key** for a new family | `docker compose exec api python scripts/create_invite.py --expires-days 1` | Prints the key. Add `--key` to choose it. Also available in Settings → Admin. |
| **Reset a parent's password** | `docker compose exec api python scripts/reset_password.py parent@example.com` | Prints a temporary password. Kids' PINs are changed by the parent in Settings → Students. |
| **Back up now** | `docker exec curiculy_backup python scripts/backup.py --evidence-dir /data/evidence --dest /backups` | Whole database (checked by a scratch restore), one file per family, new work samples. See [Backups](backups-and-restore.md) |
| **Restore one family** | `docker exec -it curiculy_backup python scripts/restore_family.py /backups/<snapshot>/families/<family>.json.gz` | Replaces only that family's rows; asks first. See [Backups](backups-and-restore.md) |
| **Look inside the database** | `docker exec -it curiculy_db psql -U curiculy_owner -d curiculy` | The owner role sees every family. Read only; don't change family rows by hand. |

## Notes
- **Migrations run on their own** at startup (`python -m app.db_startup`). Schema changes ship as Alembic migrations in `migrations/versions/` (see [Data model](../5-engineering/data-model.md)).
- The SQLite-era tools (`check_foreign_keys.py`, `backfill_enrollments.py`, `drop_legacy_tables.py`) were removed with the move to Postgres, which always enforces its references.
