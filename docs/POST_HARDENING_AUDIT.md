# Curiculy post-hardening audit

**Date:** 2026-08-29  
**Scope:** Compare the running tree to `docs/ARCHITECTURE.md` after the architecture-hardening roadmap. Application source was not changed for this audit.

**Method**

- Read `ARCHITECTURE.md`, `CODEBASE_MAP.md`, `DOMAIN_MODEL.md`, `TECHNICAL_DEBT.md`, and `ROADMAP.md`.
- Inspect routers, `app/core/security.py`, `app/config.py`, `app/db.py`, `app/schema_patches.py`, models, SPA calls, the extension, Compose, and tests for the fourteen checks below.
- Ran the full suite: `docker compose --profile dev run --rm tests pytest -q --tb=line`.

**Suite:** all tests passed (786 collected). Only warning: Passlib `crypt` deprecation (third-party).

**Verdict:** The hardening goals for this roadmap are met. Critical privacy and calendar invariants hold. What remains is documented leftover work (Phase 4+), operator hygiene, and a few small code smells — not open holes in the fourteen checks.

---

## The fourteen checks

| # | Check | Result |
|---|---|---|
| 1 | Evidence is tenant-private | **CONFIRMED** |
| 2 | Extension credentials cannot act as parent JWTs | **CONFIRMED** |
| 3 | JWT secrets cannot silently fall back to insecure production defaults | **CONFIRMED** |
| 4 | SMTP credentials are not hardcoded | **CONFIRMED** |
| 5 | Children can complete only their own assignments | **CONFIRMED** |
| 6 | SchoolYear is the canonical operational year | **CONFIRMED** (date columns still mirrored) |
| 7 | Scheduling creates/verifies Enrollment | **CONFIRMED** |
| 8 | PDF background workers own their DB sessions | **CONFIRMED** |
| 9 | Schema management has one documented authoritative strategy | **CONFIRMED** |
| 10 | Legacy entities identified for removal were addressed appropriately | **CONFIRMED** (models gone; tables not dropped) |
| 11 | No regressions in the two curriculum intake paths | **CONFIRMED** |
| 12 | SQLite-per-household remains intact | **CONFIRMED** |
| 13 | Ollama remains optional for core scheduling | **CONFIRMED** |
| 14 | Assignment remains the sole calendar entity | **CONFIRMED** |

---

## What is now confirmed

### 1. Evidence is tenant-private

There is no public `StaticFiles` mount for work samples. `create_app()` mounts only `/static`. Files live under `{EVIDENCE_DIR}/{tenant_uuid}/{uuid}…`.

`GET /api/evidence/files/{path}` requires a JWT via `get_current_user`. `resolve_evidence_file(..., tenant_uuid=)` refuses a path whose folder is not the caller’s tenant. Children may read a file only when it is attached to one of their assignments. Capture credentials receive 403. Unauthenticated GET is 401. The old `/evidence/...` URL does not serve files. The service worker skips `/api/` and `/evidence/`. Responses use `Cache-Control: private, no-store`.

Covered by `tests/test_evidence_files_api.py` and `tests/test_capture_token.py`.

### 2. Extension credentials cannot act as parent JWTs

Capture tokens are JWTs with `role=evidence` and `scope=evidence:write`, plus a revocable `capture_tokens` row on `admin.db`. `get_current_user` rejects them with 403. `require_parent` / `require_admin` therefore reject them. Staging POST uses `require_staging_upload`, which accepts a live capture credential or a parent session.

Tests show 403 on `/auth/me`, household, students, staging list/link, admin invites, and evidence file GET. Minting a new token revokes the previous `jti`. Demo and child users cannot issue tokens.

`get_tenant_db` decodes the JWT with `user_from_token` (not `get_current_user`) so staging can open the household file. Protection for every other route is the router dependency. That is correct today; new routes must keep a parent/child dependency (see residual risk below).

### 3. JWT secrets cannot silently fall back in production

Non-dev startup (`entrypoint.sh` and app lifespan) calls `validate_runtime_configuration()`. Missing, whitespace, known placeholders, and secrets shorter than 32 characters raise `ConfigurationError`. Compose interpolates `JWT_SECRET: ${JWT_SECRET:-}` with no baked-in fallback. `DEV_MODE=true` may apply the explicit `insecure-dev-secret` placeholder; that path is tests-covered and must not be used for a real family.

Error text and `Settings.__repr__` do not print the secret.

### 4. SMTP credentials are not hardcoded

Compose interpolates empty `MAIL_USERNAME` / `MAIL_PASSWORD`. `.env.example` leaves them blank. `.env` is gitignored. `mail_connection()` uses settings as-is and does not invent a dummy mailbox password. The process still boots without mail; send fails until env is set.

If this tree was copied when a mailbox password was still in Compose, rotate that mailbox. This audit did not search git history for old secrets.

### 5. Children can complete only their own assignments

`PATCH /api/assignments/{id}/status` uses `get_current_user`. A child whose `student_id` does not match the row gets 404. Children do not sync `shared_group_uuid` siblings. PUT, delete, grade, and evidence stay `require_parent`. Homework help uses the same own-assignment check.

Covered by `tests/test_child_assignment_status.py`.

### 6. SchoolYear is the canonical operational year

`load_school_year_settings` / `require_operational_school_year` read dates from the latest named `SchoolYear` (start date, then id). Weekdays and exception colors stay on `HouseholdSettings`. The year modal (`PUT /settings/school-year`) and wizard (`POST /school-years`) write the same `SchoolYear` row. If only settings dates exist, a named year is created from them. If both exist and they differ, the named year wins and settings dates are copied from it.

`HouseholdSettings.start_date` / `end_date` remain as a write-through mirror so old `tenant_*.db` files keep NOT NULL columns. They are not the read source once a `SchoolYear` exists. Columns are not dropped.

### 7. Scheduling creates/verifies Enrollment

Pacing commit (`enroll_students`) and plan-apply (`ensure_enrollment`) insert or reuse `student + curriculum + school_year` in the **same transaction** as the assignments. Unique violations are recovered with a savepoint. Preview does not enroll. A failed commit/apply rolls back. Settings `POST /enrollments` still works and still 409s on duplicates. Plan-apply reuses or creates a library row from the plan title so the reading list has a book.

Covered by `tests/test_enrollments.py`.

### 8. PDF background workers own their DB sessions

`POST /curriculum/import-pdf` captures `tenant_uuid` and demo `jti`. `process_pdf_curriculum_background` calls `open_tenant_session` itself. It does not receive the request Session. Failures roll back the job session, then mark `failed` on a second session. Both are closed. Tests assert the HTTP handler does not pass `db` into the worker.

Portfolio email is different and also safe: the request renders the PDF, then `BackgroundTasks` sends a built `MessageSchema`. That task does not keep a SQLAlchemy session.

### 9. One schema strategy

Runtime is `init_databases()` → `create_all` + ordered idempotent patches in `app/schema_patches.py` on catalog, admin, the shared tenant file, and every `tenant_*.db`. Alembic `env.py` calls `refuse_alembic_replay()`. Revisions 0001–0012 stay on disk as archaeology. `alembic/README.md` says not to ship columns as new revisions.

Adding a column still needs a model change **and** a patch. `create_all` will not ALTER existing files. Tests cover fresh files, old files, a second apply, no row loss, leftover tables not mapped, and leftover tables not dropped.

### 10. Legacy removal was appropriate

| Item | Treatment | Appropriate? |
|---|---|---|
| `ScheduledWork` / `EvidenceCapture` models, unused read schemas, `ScheduleGrain` / `WorkStatus` | Unmapped / deleted | Yes. No write path. Available family files had COUNT=0. |
| Orphan SQLite tables | Left in place; delete of student/curriculum still clears leftover rows | Yes. `create_all` does not DROP. Do not destroy data. |
| `/books/*`, `POST /catalog/from-isbn`, `POST /curricula/import` | Kept | Yes. SPA unused; tests and API clients call them. |
| Taxonomy columns | Kept | Yes. Pacing/assignments/tests still use them. |
| Jurisdiction / compliance stubs | Kept, not called | Yes. Defer until a state form exists. |
| Dual `/exceptions` APIs | Kept | Yes. SPA uses both. Fold later with aliases. |
| Alembic 0001–0012 | Kept, refused | Yes. Replay is the wrong shape. |

### 11. Two curriculum intake paths

Both still land on `assignments`:

1. **Book auto-schedule:** SPA `POST /catalog/lookup-isbn` → save library → `/pacing/generate-preview` → `/pacing/commit`. Preview is arithmetic (`SyllabusGenerator`). Commit writes units, page mappings, assignments, and enrollments.
2. **Pacing guide:** CSV / PDF / builder → `curriculum_plans` → apply → assignments + enrollment. PDF parse may use Ollama; apply does not.

`POST /curricula/import` remains an API-only tree import. The SPA does not call it. Tests for pacing, plan apply, enrollments, and curricula still pass.

### 12. SQLite-per-household

`admin.db` (users, invites, capture tokens), `catalog.db` (ISBN cache), `tenant_{uuid}.db` per family. Demo is in-memory keyed by JWT `jti`. Dev mode uses the shared `tenant.db`. JWT `tenant_uuid` selects the file. There is no `tenant_id` on planner tables (staging stores the UUID as a path prefix inside the file). Compose still bind-mounts `./data`.

### 13. Ollama optional for core scheduling

`SyllabusGenerator` does not import or call Ollama. Pacing comments say not to wire it into commit. Ollama is used for PDF → plan lessons, homework tutor, and spark. Those paths may fail closed. Compose `OLLAMA_HOST` is optional.

### 14. Assignment is the sole calendar entity

Pacing commit and plan-apply insert `Assignment` rows. The SPA calendar reads assignments. `ScheduledWork` is not mapped. Leftover tables are not created on new files. Recalibrate and shared groups operate on assignments.

---

## What remains unresolved

These were already classified in the architecture docs. This audit agrees they are still open. None of them reverse a hardening check.

| Item | Status | Why it still matters |
|---|---|---|
| `HouseholdSettings` date columns | Mirror still written | Old files keep NOT NULL columns. Drop only in a later schema pass. |
| Dual exception HTTP APIs | SPA uses both prefixes | Fold into one router with aliases. |
| `/books/*` vs catalog | Tests still on books | Point tests at catalog, then alias. |
| Empty leftover `scheduled_work` / `evidence_captures` tables | Not DROPped | DROP after COUNT=0 on each real `tenant_*.db`. |
| Register does not return a JWT | Extra login | Additive. |
| All Students calendar is shared lessons only | By design | UI copy is missing. |
| Tests use one in-memory DB and often override the user | Gap | No JWT → `tenant_{uuid}.db` routing test. |
| No root README / CI | Operator knowledge | First admin, invite, `JWT_SECRET`, compose port 3040. |
| Health check skips tenant files | Catalog + admin only | A wedged `tenant_*.db` would not fail `/health`. |
| Mailbox password rotation | Operator | Required if the old committed password was ever used. |
| `DEV_MODE=true` skips JWT | Local-only | Dangerous if left on for a real family. |
| Historical enrollments | No backfill | Years scheduled before auto-enroll may still have empty reading lists until the next commit/apply. |
| Compliance / taxonomy product | DEFER | Correct to leave. |
| `ai_generator.py` filename | Comments fixed | Rename when the file is already being edited. |

---

## New technical debt

Found in this pass; not listed as resolved in `TECHNICAL_DEBT.md`.

### Duplicate helpers in `app/services/legacy_tables.py`

`delete_legacy_rows_for_student`, `delete_legacy_rows_for_units`, and `delete_legacy_rows_for_enrollments` are each defined twice. Python keeps the second copy. Behavior is still correct (tests pass). The first copies are dead. Clean up when that file is touched. Do not change behavior.

### Capture tokens and `get_tenant_db`

`get_tenant_db` trusts `user_from_token`, which accepts a capture credential so staging can write. Every other tenant route today also depends on `get_current_user` or `require_parent`. A future route that uses only `get_tenant_db` would let an extension token mutate the planner. Checklist for new endpoints: parent/child/staging dependency must be explicit.

### JWT strength is length + denylist, not entropy

A 32-character string of a single letter is not in the placeholder list and would be accepted in non-dev. Good enough to stop silent Compose defaults; not a cryptographic policy. Optional later: require mixed characters or a generator in the README.

### Child completion vs shared groups

A child completing their own shared-group row does not update siblings. That is the documented rule. Parents can see mixed status on a co-lesson until they PATCH as a parent. Product copy or a later sync rule — not a security hole.

### FastAPI description still says “compliance foundation”

`create_app()` title/description still advertise a compliance slice that is a stub. Cosmetic. Portfolios are the printable-record product.

### `CODEBASE_MAP.md` intro line

The map still says application source was not changed for the map. The map was updated during hardening. Harmless drift.

---

## Regressions or risks

**No test-suite regression.** Book pacing, plan apply, enrollments, school year, evidence, capture tokens, child status, and schema tests are green.

**Still high-blast-radius if edited carelessly** (unchanged by hardening):

- Recalibrate and parent shared-group sync (sibling calendars).
- Pacing/plan-apply writing hundreds of rows (one tenant transaction; catalog page-count is a second commit).
- Forgetting a `schema_patches` ALTER on a new model column (old `tenant_*.db` files lag).
- Replaying Alembic 0001 (refused, but someone generating a new revision might assume it runs).

**Operational:**

- `DEV_MODE=true` is a full parent/admin bypass.
- Families may still paste an old parent JWT into the extension until they generate a capture token.
- Empty leftover tables on disk are harmless until someone maps them again.

**Not a regression:** child My Work completing a shared lesson without sibling sync. Intended.

---

## Architecture deviations

Compared with the **TARGET** sections, not with a generic SaaS template.

| Target | Current | Kind |
|---|---|---|
| One operational year | Met for reads; settings dates still written | Documented leftover |
| One exceptions HTTP surface | Two prefixes, one table | CONSOLIDATE later |
| Catalog as the public ISBN name | SPA uses catalog; `/books/*` still live | API-only aliases |
| Assignment-only calendar | Models unmapped; empty tables may remain | DEPRECATE tables |
| Token on register | Not issued | COMPLETE later |
| All Students copy | Query is correct; UI copy missing | Copy only |
| Tenant-file integration tests | Schema file tests exist; JWT routing still in-memory | Testing gap |
| README / CI | Absent at repo root | Deployment |
| One household per tenant file | Schema still allows many; product uses `get_default_household` | Comment/rule, low |
| Drop jurisdiction threading | `jurisdiction_id` still on `Household` | DEFER with compliance |

These are **not** deviations (they match the ten decisions in `ROADMAP.md`):

- File-per-household SQLite
- Two curriculum intakes
- Vanilla `app.js` without a framework
- Ollama off the calendar write path
- Compliance/taxonomy UIs not built
- Alembic archive not used as the runner

---

## Recommended next priorities

Order is homeschool-operator value, not abstract cleanliness. Do not start Postgres, a JS framework, or compliance UI.

1. **Root README** — compose port 3040, first admin, invite key, `JWT_SECRET`, optional Ollama, rotate mail if it was ever committed. (`ROADMAP` safest #9 / Phase 5)
2. **JWT on `POST /auth/register`** — additive; one fewer login. (`ROADMAP` safest #5)
3. **All Students UI copy** — “shared lessons only.” (`ROADMAP` safest #4)
4. **One pytest** that provisions `tenant_{uuid}.db` and routes a real JWT without overriding `get_tenant_db`. (`ROADMAP` safest #10 / debt #15)
5. **Empty-reading-list copy** on portfolios for years scheduled before auto-enroll. (`ROADMAP` Phase 2 leftover)
6. **Deduplicate `legacy_tables.py`** — delete the first unused function copies. Tiny, no behavior change.
7. **One exceptions router** with aliases for `/exceptions` and `/calendar/exceptions`. Wait until `app.js` can move. (`ROADMAP` Phase 4)
8. **CI** running `docker compose --profile dev run --rm tests pytest`.
9. **DROP leftover tables** only after `SELECT COUNT(*)` is 0 on each real `tenant_*.db`.
10. **Stop writing the settings date mirror**, then drop those columns in a dedicated schema pass with backups.

Leave alone until a product requirement forces it: Postgres, React, Celery, taxonomy admin, merging curricula with plans, deleting `/books/*` while tests still call them, making auto-schedule require Ollama.

---

## How to use this document

| Question | Look at |
|---|---|
| Did hardening actually land? | The fourteen checks above |
| What should we build next? | Recommended next priorities |
| What must we not rewrite? | Architecture deviations (intentional) + `ROADMAP.md` section 4 |
| Where is leftover cleanup recorded? | Unresolved + `TECHNICAL_DEBT.md` medium/low |

If a proposal conflicts with the ten decisions in `ROADMAP.md` section 1, it is a rewrite, not a simplification.
