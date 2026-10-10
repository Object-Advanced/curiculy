# Operator scripts

Command-line tools for the site owner, in `scripts/`. Run them inside the container from the production folder (`/home/objadv/curiculy`).

| Task | Command | Notes |
|---|---|---|
| **Make an invite key** for a new family | `docker compose exec api python scripts/create_invite.py --expires-days 1` | Prints the key. Add `--key` to choose it. Also available in Settings → Admin. |
| **Reset a parent's password** | `docker compose exec api python scripts/reset_password.py parent@example.com` | Prints a temporary password. Kids' PINs are changed by the parent in Settings → Students. |
| **Back up now** | `docker exec curiculy_backup python scripts/backup.py --data-dir /data --evidence-dir /data/evidence --dest /backups` | See [Backups](backups-and-restore.md) |
| **Check database links** | `python3 scripts/check_foreign_keys.py --data-dir <folder>` | Read-only; use it on restore drills |
| **Rebuild missing course enrollments** | `docker compose run --rm --no-deps -e PYTHONPATH=/app --entrypoint python api scripts/backfill_enrollments.py --data-dir /data` | Dry run by default; add `--apply`. Only when a lesson clearly ties a child to a book and year; it never guesses from titles. |
| **Drop old empty tables** (`scheduled_work`, `evidence_captures`) | `docker compose exec api python scripts/drop_legacy_tables.py --data-dir /data` | Dry run by default; `--apply` drops only **empty** tables, never rows. Back up first. |

## Notes
- The last two are **one-time cleanups** for older family files. Once production confirms there's nothing left to do (both dry runs report nothing), they can be retired in Phase 5.
- **Never run old Alembic migrations.** That chain was removed in October 2026. Schema changes ship in `app/schema_patches.py`.
