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

## 3. Bootstrapping the First Admin
Because registration is invite-gated, you need to manually generate the first invite key directly in the admin database to create your initial parent account. The live `invite_keys` table requires `tenant_uuid` (the admin API uses an empty string until the key is redeemed).
1. Exec into the container: `docker compose exec api bash`
2. Open the admin database: `sqlite3 /data/admin.db`
3. Insert an invite key: `INSERT INTO invite_keys (key, tenant_uuid, expires_at) VALUES ('YOUR_HEX_KEY', '', datetime('now', '+1 day'));`
4. Go to `http://localhost:3040`, click **Register**, and use your new invite key.

## 4. Development Mode
Run the full suite locally (same image and tests as CI):
`docker compose --profile dev run --rm tests pytest -q --tb=line`

GitHub Actions (`.github/workflows/tests.yml`) runs that command on every push and pull request, with `-T` because the runner has no TTY. CI does not use production secrets, SMTP credentials, an Ollama daemon, or live `/data` files. Pytest sets a local JWT signing value in `tests/conftest.py`; do not copy that into a family deploy.

The 2026-09-01 reconciliation baseline was **821 passed**. The current suite is **892 passed**, 0 failed, 0 skipped.

## 5. Optional operator scripts
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
