# Curiculy
Curiculy is a local-first, multi-child homeschool planner designed to run on a single family node. It handles curriculum pacing, family calendars, work-sample evidence (via Chrome extension), and printable portfolios.

## 1. Configuration (`.env`)
Before starting the application, you must configure your environment secrets. Copy the example file:
`cp .env.example .env`

Edit `.env` and provide a strong `JWT_SECRET`. **The application will refuse to start in production mode if this is missing, weak, or set to a known placeholder.**

Optional configurations:
* `MAIL_USERNAME` / `MAIL_PASSWORD`: Required only if you want to email evaluator PDFs. (Do not commit these).
* `OLLAMA_HOST` / `OLLAMA_MODEL`: Required only for background PDF parse, the homework-help tutor, or spark questions. Book auto-schedule does not use Ollama. Paper-sheet handwriting uses a separate vision model (`llama3.2-vision`) after you print a week template and photograph it (`GET /api/curriculum/paper-template`, `POST /api/curriculum/import-paper`).

## 2. Starting the Application
Curiculy runs via Docker Compose.
`docker compose up -d`
The UI will be available at `http://localhost:3040`. *(Note: Code directories are bind-mounted. Evidence files and databases are stored in the `./data` directory on the host).*

### Behind a proxy or tunnel
If a reverse proxy or Cloudflare Tunnel forwards traffic to port 3040, set `FORWARDED_ALLOW_IPS` in `.env` to the address that traffic arrives from (for a tunnel reaching the published port, the Docker gateway: `docker network inspect curiculy_default`). The app then uses each visitor's real address, from `X-Forwarded-For`, for rate limits and logs, and still ignores that header from anyone else.

## 3. Bootstrapping the First Admin
Registration is invite-gated, so the first parent account needs an invite key made from the command line:

```
docker compose exec api python scripts/create_invite.py --expires-days 1
```

It prints the key. Go to `http://localhost:3040`, click **Create Account**, and use it. Run it again whenever you need another key (`--key` picks a specific value).

## 4. Development Mode
Run the full suite locally (same image and tests as CI):
`docker compose --profile dev run --rm tests pytest -q --tb=line`

GitHub Actions (`.github/workflows/tests.yml`) runs that command on every push and pull request, with `-T` because the runner has no TTY. CI does not use production secrets, SMTP credentials, an Ollama daemon, or live `/data` files. Pytest sets a local JWT signing value in `tests/conftest.py`; do not copy that into a family deploy.

Lint (syntax errors and pyflakes; the same check CI runs):
`docker compose --profile dev run --build --rm tests ruff check app scripts tests`

### Browser tests (Playwright)
`e2e/run.sh` starts a throwaway app (empty databases, no Ollama, a test-only signing key) and runs the Playwright suite against it from Microsoft's Playwright image. Only Docker is needed. It runs as a separate Compose project, so it never touches the real `api` container.

* `e2e/run.sh --project=functional` runs the smoke, kid sign-in, accessibility, and metrics tests.
* Visual snapshots of the main screens (phone, tablet, desktop; light and dark) live in `e2e/tests/__screenshots__`. After an intended visual change, run `e2e/run.sh --update-snapshots` and commit the new images.
* `e2e/a11y-baseline.json` caps serious and critical axe violations per screen. Lower the numbers as screens improve; `UPDATE_A11Y_BASELINE=1 e2e/run.sh --project=functional` rewrites it.
* `e2e/reports/metrics.json` records requests, bytes, and LCP when a parent opens Home.

## 5. Backups and restore
Turn on nightly backups (a separate container; off until you run this once):

```
docker compose --profile backup up -d backup
```

Every 24 hours it snapshots each database into `BACKUP_HOST_DIR` (default `./backups`; set it in `.env` to use another disk), checks every copy with `PRAGMA integrity_check`, mirrors new evidence files into `backups/evidence/`, and keeps the newest 14 snapshots. `docker compose logs backup` shows each run. Copy `BACKUP_HOST_DIR` off this machine as well (restic, rclone, or an external drive); a backup on the same disk does not survive that disk.

Back up right now:

```
docker compose --profile backup run --rm --entrypoint python backup scripts/backup.py --data-dir /data --evidence-dir /data/evidence --dest /backups
```

Restore a snapshot:

1. `docker compose stop api`
2. Copy the snapshot's databases over the live ones and delete leftover write-ahead files (otherwise SQLite may replay an old log onto the restored file): `sudo cp backups/<snapshot>/*.db data/ && sudo rm -f data/*.db-wal data/*.db-shm`
3. Copy any missing evidence files from `backups/evidence/` back into the evidence directory.
4. `docker compose start api`

Practice it occasionally on a scratch copy: copy a snapshot into an empty directory and run `python3 scripts/check_foreign_keys.py --data-dir <that directory>`; every file should report OK.

## 6. Optional operator scripts
A parent who forgot their password (self-serve reset comes later):

```
docker compose exec api python scripts/reset_password.py parent@example.com
```

It prints a temporary password to give them. Kids sign in with PINs, which a parent changes in Settings → Students.

Historical enrollments can be reconstructed when an assignment already proves student + curriculum + school year (stored `curriculum_id`, or a live curriculum resource/unit). Title-only week/day plan lessons are not guessed:

```
docker compose run --rm --no-deps -e PYTHONPATH=/app --entrypoint python api scripts/backfill_enrollments.py --data-dir /data
```

That command is a dry-run. Add `--apply` to insert missing rows. It does not run at startup. It does not modify assignments, curricula, or school years. Duplicate student + curriculum + year rows are skipped. New pacing commits and plan applies stamp `curriculum_id` on the assignment. Older title-only plan rows stay unlinked; add those books in Settings → Enrollments if needed.

Leftover SQLite tables `scheduled_work` and `evidence_captures` (ORM models are gone; physical tables may remain on older `tenant_*.db` files) can be inspected and, when empty, dropped. Application boot never drops them. Backup the tenant files first. Restore is copying the backup back over the live file.

Dry-run (no changes):

```
docker compose exec api python scripts/drop_legacy_tables.py --data-dir /data
```

Apply (DROP a leftover table only when `COUNT(*) = 0`; never deletes rows; non-empty tables are left in place):

```
docker compose exec api python scripts/drop_legacy_tables.py --data-dir /data --apply
```

Safe to run repeatedly. A file that cannot be opened is skipped; nothing in that file is dropped. `catalog.db`, `admin.db`, and the shared `tenant.db` are not scanned.
