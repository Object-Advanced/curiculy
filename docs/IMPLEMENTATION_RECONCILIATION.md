# Curiculy implementation reconciliation

**Date:** 2026-09-01  
**Scope:** Independent, read-only comparison of claimed architecture-hardening work against the source tree. Application code and tests were not modified.  
**Sources of claims:** `docs/ARCHITECTURE.md`, `docs/CODEBASE_MAP.md`, `docs/DOMAIN_MODEL.md`, `docs/TECHNICAL_DEBT.md`, `docs/ROADMAP.md`, `docs/POST_HARDENING_AUDIT.md`, `CompleteExplanation.txt`, `README.md`.  
**Method:** Inspected routers, models, services, Compose, SPA, extension, schema runner, Alembic archive, and tests. Ran the documented suite: `docker compose --profile dev run --rm tests pytest -q --tb=line`.

**Suite:** **821 collected, 821 passed, 0 failed, 0 skipped.** One third-party warning: Passlib `crypt` deprecation. The 2026-08-29 post-hardening audit reported 786 passed. The +35 tests are concentrated in paper-import and household modules that that audit did not list.

**Documentation (2026-09-01):** Architecture docs were reconciled to this audit. `docs/ARCHITECTURE.md` is the current architecture. `docs/TECHNICAL_DEBT.md` and `docs/ROADMAP.md` list only remaining work. `docs/POST_HARDENING_AUDIT.md` keeps the 2026-08-29 fourteen checks as history and points here for the 821-test baseline. This file remains the independent source-vs-docs evidence from 2026-09-01; it was not rewritten as a second architecture.

**Later:** Exception HTTP prefixes were consolidated onto `/api/exceptions` (list, create, dates, toggle, import-holidays). `/api/calendar/exceptions` was removed. Item 20 is no longer remaining work. Three tests were added (`TestExceptionRecords`); the suite became **824 passed**. Duplicate `legacy_tables.py` helpers were then collapsed to one implementation each; leftover SQLite tables are still not DROPped at boot. Capture credentials were then isolated from `get_tenant_db` (`get_staging_tenant_db` for staging only); three capture-isolation tests were added (**827 passed**). SchoolYear date-column retirement followed: `HouseholdSettings` no longer stores or writes year dates; leftover tenant columns are backfilled into `SchoolYear` when missing, then dropped on boot (**831 passed**). Book-paced historical enrollments can be reconstructed with operator script `scripts/backfill_enrollments.py` (not boot). Week/day plan-apply assignments still cannot be inferred. Leftover-table DROP tooling was then made testable (`app/services/legacy_table_drop.py`, dry-run / `--apply`, COUNT=0 only, never DELETE rows, not boot). `/books` vs catalog was investigated: same `BookResolver` / `book_editions`, different HTTP contracts; no routes removed. Dual Ollama stacks were investigated: `ollama.AsyncClient` vs `httpx` `/api/chat` differ on timeout, images, and model class; no client merge. PDF curriculum parse and homework tutoring then share `app/services/ollama_chat.py` for the primary → mistral `AsyncClient` fallback; spark and paper vision stay on `httpx`. `/api/health` was then confirmed as catalog.db + admin.db process health; household `tenant_{uuid}.db` files are excluded on purpose (not a missing probe). GitHub Actions then runs the Compose `tests` suite on push and pull request (`.github/workflows/tests.yml`). Default pytest `client` remains in-memory on purpose; JWT → `tenant_{uuid}.db` persistence and two-household isolation are covered by `auth_client`. A later pass re-verified the capture JWT boundary: `get_tenant_db` still calls `get_current_user` (refuses capture); only `POST /api/evidence/staging` uses `get_staging_tenant_db`. A further pass re-verified SchoolYear date retirement: `HouseholdSettings` has no date columns; leftover tenant columns are still backfilled then dropped by `retire_household_settings_date_columns`; production code does not read or write a settings date mirror. PDF and paper workers then write one `curriculum_plan_ready` or `curriculum_plan_failed` parent notification in the same tenant session that persists terminal plan status (not on the 202 request). New pacing commits and plan applies then stamp nullable `assignments.curriculum_id`. Operator `--apply` on this host DROPped empty leftover tables on `./data/tenant_*.db` and inserted two proven enrollments; 22 title-only assignments were skipped. Current suite: **892 passed**. The architecture-hardening / cleanup phase is closed.

**Verdict:** The fourteen post-hardening checks still hold in source. The later operator/UX items (README, register token, All Students copy, leftover-table script) also exist in source. There is no regression of JWT fail-closed, private evidence, capture-token scope, child status, SchoolYear reads, auto-enrollment, PDF worker sessions, patches-only schema, SQLite-per-household, or Assignment-as-calendar. Paper-to-plan intake is a live pacing-guide capture path (OpenCV + Ollama vision) that lands on `curriculum_plans` then assignments.

Classification labels used below:

| Label | Meaning in this pass |
|---|---|
| **CONFIRMED IMPLEMENTED** | Claimed behavior is present in source and covered by tests (or by an operator script where that is the claimed deliverable). |
| **PARTIALLY IMPLEMENTED** | Core behavior exists; a documented step or invariant is incomplete or unsafe as written. |
| **DOCUMENTATION-ONLY** | Described as done or present, with no matching source. |
| **NOT IMPLEMENTED** | Claimed as remaining work, and source agrees it is not done — or claimed done with no code. |
| **REGRESSED** | Previously claimed done and now missing or inverted. None of the twenty items. |

---

## Summary of the twenty checks

| # | Item | Classification | Docs vs source |
|---|---|---|---|
| 1 | JWT production secret enforcement | **CONFIRMED IMPLEMENTED** | Matches |
| 2 | SMTP secret handling | **CONFIRMED IMPLEMENTED** | Matches |
| 3 | Private evidence serving | **CONFIRMED IMPLEMENTED** | Matches |
| 4 | Capture-token authentication | **CONFIRMED IMPLEMENTED** | Matches |
| 5 | Child assignment completion | **CONFIRMED IMPLEMENTED** | Matches |
| 6 | SchoolYear consolidation | **CONFIRMED IMPLEMENTED** | Matches (settings date columns retired later) |
| 7 | Automatic enrollment during scheduling | **CONFIRMED IMPLEMENTED** | Matches |
| 8 | PDF worker session ownership | **CONFIRMED IMPLEMENTED** | Matches; paper worker copies the same pattern |
| 9 | Schema patch strategy | **CONFIRMED IMPLEMENTED** | Matches |
| 10 | Removal of ScheduledWork / EvidenceCapture application models | **CONFIRMED IMPLEMENTED** | Matches (ORM gone; SQLite tables not dropped) |
| 11 | SQLite-per-household isolation | **CONFIRMED IMPLEMENTED** | Matches |
| 12 | Ollama optionality | **CONFIRMED IMPLEMENTED** | Matches for calendar writes; paper/PDF still call Ollama |
| 13 | Assignment as sole calendar entity | **CONFIRMED IMPLEMENTED** | Matches |
| 14 | Service-worker cache versioning | **CONFIRMED IMPLEMENTED** | Matches |
| 15 | Missing logo / extension icons | **CONFIRMED IMPLEMENTED** | Matches |
| 16 | README / bootstrap documentation | **CONFIRMED IMPLEMENTED** after the 2026-09-01 doc pass (invite INSERT now includes `tenant_uuid`). CI added later (`.github/workflows/tests.yml`). | Matches |
| 17 | Register returning an access token | **CONFIRMED IMPLEMENTED** | Matches |
| 18 | All Students UI clarification | **CONFIRMED IMPLEMENTED** | Matches |
| 19 | Legacy-table cleanup tooling | **CONFIRMED IMPLEMENTED** | Operator script exists; no tests; not part of boot |
| 20 | Exception API duplication | **NOT IMPLEMENTED** at audit time; **consolidated later** onto `/api/exceptions` | Historical leftover; see Later note in §20 |

No item is **REGRESSED**. No item is **DOCUMENTATION-ONLY**.

---

## 1. JWT production secret enforcement

**Claimed state:** Non-dev startup refuses a missing, whitespace, placeholder, or short `JWT_SECRET`. Compose interpolates `${JWT_SECRET:-}` with no baked-in fallback. `DEV_MODE=true` may apply `insecure-dev-secret`. Error text and `Settings.__repr__` do not print the secret.

**Actual source:** Matches.

- `app/config.py`: `jwt_secret_is_insecure()`, `validate_runtime_configuration()`, `apply_dev_jwt_fallback()`, `DEV_ONLY_JWT_SECRET`, `MIN_JWT_SECRET_LENGTH = 32`, `_INSECURE_JWT_SECRETS`, `Settings.jwt_secret` as `SecretStr`, redacted `__repr__` / `model_dump`.
- `entrypoint.sh` line 4: `validate_runtime_configuration()` before `init_databases()`.
- `app/main.py` `lifespan()`: same validation.
- `docker-compose.yml`: `JWT_SECRET: ${JWT_SECRET:-}`, `DEV_MODE: ${DEV_MODE:-false}`.
- `.env.example`: empty `JWT_SECRET`, `DEV_MODE=false`.

**Endpoints / functions:** `validate_runtime_configuration`, `jwt_secret_is_insecure`, `create_access_token` / `decode_access_token` in `app/core/security.py` (sign with `reveal_secret(settings.jwt_secret)`).

**Tests:** `tests/test_config.py` — missing, whitespace, dev placeholder, compose placeholder, short secret, long secret, error text, repr, lifespan reject/allow.

**Operational observation (this host):** `docker compose up` failed with `ConfigurationError: JWT_SECRET is required when DEV_MODE is false` until a `.env` was supplied. Fail-closed is live, not only unit-tested.

**Matches documentation:** Yes. Remaining honesty note (already in `POST_HARDENING_AUDIT.md`): a 32-character string of one letter is accepted.

---

## 2. SMTP secret handling

**Claimed state:** Mail username/password come only from the environment. Compose interpolates empties. App does not invent dummy mailbox credentials. Process boots without mail; send fails until env is set.

**Actual source:** Matches.

- `docker-compose.yml`: `MAIL_USERNAME: ${MAIL_USERNAME:-}`, `MAIL_PASSWORD: ${MAIL_PASSWORD:-}`.
- `.env.example`: blank `MAIL_USERNAME` / `MAIL_PASSWORD`.
- `.gitignore`: `.env`.
- `app/config.py`: `mail_username: str = ""`, `mail_password: SecretStr = SecretStr("")`.
- `app/services/portfolio.py` `mail_connection()`: `USE_CREDENTIALS=bool(username and password)`; password from `reveal_secret(settings.mail_password)`.

No hardcoded mailbox password in Compose or Python defaults. This pass did not search git history (the tree is not a git repository).

**Tests:** `tests/test_config.py` `test_mail_connection_uses_settings_credentials`, `test_mail_connection_does_not_invent_dummy_credentials`.

**Matches documentation:** Yes. Operator rotation of a previously committed mailbox remains an ops task, not a code task.

---

## 3. Private evidence serving

**Claimed state:** No public `StaticFiles` mount for work samples. Authenticated `GET /api/evidence/files/{path}`. Tenant folder check. Children only for files on their assignments. Capture credentials 403. Unauthenticated 401. Old `/evidence/...` does not serve files. `Cache-Control: private, no-store`. Service worker skips `/api/` and `/evidence/`.

**Actual source:** Matches.

- `app/main.py` `create_app()`: mounts only `/static`. No `/evidence` mount.
- `app/routers/evidence.py`: `files_router` with `Depends(get_current_user)`; `get_evidence_file`; `_child_may_read_file`.
- `app/evidence/__init__.py`: `store_capture`, `stored_relative_path`, `resolve_evidence_file(..., tenant_uuid=)`.
- `static/js/app.js`: authenticated `/api/evidence/files/...` helper (around the `data/evidence/` strip and files URL builder).
- `sw.js`: skips `/api/` and `/evidence/`.

Capture credentials never reach the handler’s extra `is_capture_credential` check: `get_current_user` already returns 403. Behavior matches the claim.

**Tests:** `tests/test_evidence_files_api.py` (unauthenticated, parent, other tenant path, child staging/sibling, missing, traversal, legacy `/evidence/...` not 200); `tests/test_capture_token.py` `test_capture_credential_cannot_retrieve_evidence`.

**Matches documentation:** Yes.

---

## 4. Capture-token authentication

**Claimed state:** Parent `POST /api/auth/capture-token` issues a JWT (`role=evidence`, `scope=evidence:write`, `sub=capture.{tenant}`, `jti`). Shown once. `GET` never returns the secret. Minting revokes earlier `admin.db` rows. `DELETE` revokes. Extension uses Bearer on `POST /api/evidence/staging` only. `get_current_user` rejects it. Demo and child cannot issue.

**Actual source:** Matches.

- `app/models/admin.py` `CaptureToken`.
- `app/services/capture_tokens.py`: `issue_capture_token`, `revoke_active_capture_tokens`, `assert_capture_token_active`, `active_capture_token`.
- `app/routers/auth.py`: `GET/POST/DELETE /auth/capture-token` behind `require_parent`; demo 403.
- `app/core/security.py`: `user_from_token` maps evidence role/scope; `get_current_user` 403; `require_staging_upload` accepts live capture or parent.
- `app/schemas/auth.py`: `CaptureTokenIssued` vs `CaptureTokenStatusRead` (no token field).
- `extension/background.js` `uploadCapture`: `POST .../api/evidence/staging` with `Authorization`.
- `app/db.py` `get_tenant_db`: uses `user_from_token` (not `get_current_user`) so staging can open the tenant file. Residual risk documented in the post-hardening audit remains true **at audit time**.

**Later:** `get_tenant_db` calls `get_current_user` and refuses capture JWTs. Staging uses `get_staging_tenant_db` + `require_staging_upload`.

**Tests:** `tests/test_capture_token.py` (issue claims, stage allowed, parent still stages, parent APIs 403, file GET 403, garbage/expired/revoked, tenant isolation, demo/child cannot issue). Status GET asserts `"access_token" not in status.json()`.

**Matches documentation:** Yes.

---

## 5. Child assignment completion

**Claimed state:** `PATCH /api/assignments/{id}/status` uses `get_current_user`. Child only own `student_id` (404 otherwise). Child does not sync `shared_group_uuid`. PUT/delete/grade/evidence stay `require_parent`.

**Actual source:** Matches.

- `app/routers/assignments.py`: `update_assignment_status`; `_require_assignment_access`; `_sync_shared_group` skipped when `is_child(user)`.
- `app/services/child_accounts.py` `is_child`.
- Module-level router dependency is `get_current_user`; write routes other than status use `require_parent`.

**Tests:** `tests/test_child_assignment_status.py` (parent, child own in_progress then completed, sibling 404, missing 404, grade/edit/delete/evidence 403, other tenant 404). Shared-group non-sync: `tests/test_assignments_api.py` `test_a_child_completing_a_shared_assignment_does_not_mark_siblings` (overrides `get_current_user` as a child). Parent sync: `test_completing_a_shared_assignment_marks_the_siblings`.

**Matches documentation:** Yes. Child shared-group non-sync is intentional, not a hole.

---

## 6. SchoolYear consolidation

**Claimed state:** Operational dates from latest named `SchoolYear` (start date, then id). Weekdays and exception colors on `HouseholdSettings`. Wizard `POST /school-years` and year modal `PUT /settings/school-year` write the same year. Settings-only tenants get a named year backfilled. Named year wins on conflict; settings dates are a write-through mirror, not dropped.

**Actual source:** Matched at audit time. **Later:** the write-through mirror was removed. `HouseholdSettings` has no date columns. `retire_household_settings_date_columns` backfills a named year from leftover settings dates only when that household has no `school_years` row, then drops the columns. An existing named year is not overwritten.

- `app/models/__init__.py` `SchoolYear`, `HouseholdSettings` (weekdays and colors only).
- `app/services/school_year.py`: `ensure_operational_school_year`, `require_operational_school_year`, `load_school_year_settings`, `save_school_year_settings`, `create_named_school_year`, `update_named_school_year`. No `_mirror_dates_onto_settings`.
- `app/routers/settings.py`: `GET/PUT /settings/school-year` (dates from `SchoolYear`).
- `app/routers/school_years.py`: named year CRUD.
- `app/schema_patches.py`: `retire_household_settings_date_columns`.

**Tests:** `tests/test_school_years.py` (create/retrieve/update, settings GET follows year, later year becomes operational, historical year does not steal dates, year modal does not rename wizard year, pacing inside named year, recalibration weekdays, toggle on first day, portfolio window, leftover-file backfill then drop, divergent dates do not overwrite a named year). `tests/test_school_year_settings.py`. `tests/test_schema.py` asserts settings date columns are absent on fresh files and dropped on legacy files.

**Matches documentation:** Yes after the later retirement.

---

## 7. Automatic enrollment during scheduling

**Claimed state:** Pacing commit and plan-apply insert or reuse `student + curriculum + school_year` in the same tenant transaction as assignments. Preview does not. Unique violation recovered with a savepoint. Settings `POST /enrollments` still 409s on duplicates. Plan-apply reuses or creates a library row from the plan title. No historical backfill.

**Actual source:** Matches.

- `app/services/enrollments.py`: `ensure_enrollment` (nested savepoint + `IntegrityError`), `enroll_students`, `curriculum_for_plan`.
- `app/services/pacing.py` `SyllabusCommitter._write`: `enroll_students` then `flush`; `commit()` commits tenant then catalog.
- `app/services/curriculum_plan_apply.py`: `ensure_enrollment` then `add_all` assignments then `commit`; exceptions `rollback`.
- `app/routers/enrollments.py`: manual POST unchanged.

**Tests:** `tests/test_enrollments.py` (commit create/no-dupe/other student/other year, preview none, failed commit none, apply from plan title, reuse library title, empty plan none, failed apply none, reading list after commit/apply, Settings POST still works).

**Matches documentation:** Yes. Empty-reading-list UI copy is present (item 18 adjacent leftover is done): `static/js/app.js` portfolio empty-enrollment note pointing at Settings → Enrollments.

**Later:** Book-paced historical enrollments can be reconstructed by `app.services.enrollment_backfill` / `scripts/backfill_enrollments.py` (dry-run default, `--apply` to write, not boot). Plan-apply assignments still have no curriculum link and are skipped.

---

## 8. PDF worker session ownership

**Claimed state:** `POST /curriculum/import-pdf` captures `tenant_uuid` and demo `jti`. `process_pdf_curriculum_background` calls `open_tenant_session` itself. Request Session is not passed. Failure rolls back the job session, then marks `failed` on a second session. Both closed.

**Actual source:** Matches.

- `app/routers/curriculum_plans.py` `import_curriculum_pdf`: `background_tasks.add_task(process_pdf_curriculum_background, plan.id, raw, user.tenant_uuid, user.jti)`.
- `app/services/ai_curriculum_worker.py`: `process_pdf_curriculum_background`, `_mark_plan_failed`.

Undocumented sibling: `extract_handwriting_from_slices` in `app/services/paper_vision_worker.py` uses the same open/rollback/second-session-failed pattern. `tests/conftest.py` patches both workers’ `open_tenant_session`.

**Tests:** `tests/test_curriculum_pdf_import.py` `test_queues_the_worker_with_tenant_identity_not_the_request_session` (asserts `"db" not in captured`); `TestPdfWorkerOwnsItsSession` (closed request session, opener tracking, failed path). Paper analog: `tests/test_paper_vision_worker.py` `test_failure_marks_failed_on_a_fresh_session`, `test_queues_vision_after_slicing`.

**Matches documentation:** Yes for PDF. Paper worker is extra, not a contradiction of the PDF claim.

---

## 9. Schema patch strategy

**Claimed state:** Runtime is `init_databases()` → `create_all` + ordered idempotent patches in `app/schema_patches.py` on catalog, admin, shared tenant file, and every `tenant_*.db`. Alembic `env.py` refuses `upgrade`. Revisions 0001–0012 stay as archive. Adding a column needs a model change **and** a patch. Leftover tables not mapped and not dropped.

**Actual source:** Matches.

- `app/db.py` `init_databases`.
- `app/schema_patches.py`: `TENANT_COLUMN_PATCHES`, `ADMIN_COLUMN_PATCHES`, empty `CATALOG_COLUMN_PATCHES`, `refuse_alembic_replay`, `apply_*_schema`.
- `alembic/env.py`: both online and offline call `refuse_alembic_replay()`.
- `alembic/README.md`, `alembic.ini` (`sqlalchemy.url = sqlite:///:memory:`).
- `entrypoint.sh` calls `init_databases()`.

**Tests:** `tests/test_schema.py` (fresh catalog/admin/tenant match models; old tenant/admin gain columns and keep rows; reapply; discovered `tenant_*.db` upgraded; wrappers; patches name live columns; leftover tables not mapped; leftover tables not dropped; date columns not dropped; Alembic refuse; 0001/0007/admin-absent archaeology).

**Matches documentation:** Yes. Patch discipline (forget an ALTER → old files lag) remains the residual risk.

---

## 10. Removal of ScheduledWork / EvidenceCapture application models

**Claimed state:** ORM models, unused read schemas, `ScheduleGrain` / `WorkStatus` removed. No write path. Empty leftover SQLite tables may remain; `create_all` does not DROP them. Student/curriculum delete still clears leftover rows.

**Actual source:** Matches.

- `app/models/__init__.py` `__all__` has no ScheduledWork / EvidenceCapture.
- `app/models/education.py` maps `Assignment*` and `Attendance` only for events.
- `app/enums.py` has `CalendarPeriod` and `AssignmentStatus`; no `ScheduleGrain` / `WorkStatus`.
- `app/schemas/` has no `ScheduledWorkRead` / `CurriculumUnitRead`.
- `app/services/legacy_tables.py`: SQL DELETE on orphan tables if present; docstring says do not DROP.
- New files from `create_all` do not include those table names (`test_legacy_work_tables_are_not_mapped`).

**Tests:** `tests/test_schema.py` unmapped + not dropped; `tests/test_legacy_tables.py` student/unit/enrollment helpers.

**Matches documentation:** Yes.

---

## 11. SQLite-per-household isolation

**Claimed state:** `admin.db` (users, invites, capture tokens), `catalog.db` (ISBN), `tenant_{uuid}.db` per family. Demo in-memory keyed by JWT `jti`. Dev mode shared `tenant.db`. No `tenant_id` on planner tables except staging’s UUID path prefix. Compose bind-mounts `./data`.

**Actual source:** Matches.

- `app/db.py`: `tenant_file_url`, `provision_tenant`, `open_tenant_session`, `_demo_maker`, `_existing_tenant_file_urls`.
- `app/models/evidence_staging.py`: `tenant_id` stores JWT tenant UUID inside the household file.
- `docker-compose.yml`: `./data:/data`.

**Tests:** `tests/test_auth.py` `test_tenant_file_url`, `test_login_routes_to_tenant_file`, `test_register_with_invite_provisions_tenant`, `test_demo_sessions_do_not_share_data`. These **do not** override `get_tenant_db` (only `get_catalog_db`).

Default `tests/conftest.py` `client` still uses one in-memory DB and overrides `get_tenant_db` / `get_current_user`. File routing is proven in the auth fixture, not in the bulk of the suite.

**Later:** That split is intentional. `test_physical_tenant_files_persist_and_stay_isolated` writes two households through real `get_tenant_db`, then reads each `tenant_{uuid}.db` with a fresh sqlite3 connection.

**Matches documentation:** Isolation model matches. Tenant-file JWT tests exist.

---

## 12. Ollama optionality

**Claimed state:** Ollama is optional. Book auto-schedule is arithmetic (`SyllabusGenerator`). Do not put Ollama on the calendar write path. PDF import, homework tutor, and spark may fail closed.

**Actual source:** Matches for calendar generation.

- `app/services/ai_generator.py`: comments and `SyllabusGenerator` have no Ollama import. `app/services/pacing.py` does not import ollama.
- Ollama callers: `app/services/ai_curriculum_worker.py` (`ollama.AsyncClient`), `app/services/homework_help.py`, `app/services/spark.py` (`httpx` to `/api/chat`), and `app/services/paper_vision_worker.py` (`httpx` to `/api/chat`, model hardcoded `llama3.2-vision`).
- Compose: `OLLAMA_HOST` / `OLLAMA_MODEL` interpolations with host-gateway defaults.
- README: Ollama listed as optional.

Paper import is a new Ollama-dependent **plan intake**, not a calendar writer. Apply still writes assignments without Ollama.

**Tests:** Pacing suite does not mock Ollama. PDF tests mock `parse_text_with_ollama`. Paper vision tests mock `httpx.post`. Spark/homework mock the tutor.

**Matches documentation:** Yes for decision #7. Paper vision is a fourth Ollama use.

---

## 13. Assignment as sole calendar entity

**Claimed state:** Pacing commit and plan-apply insert `Assignment` rows. SPA calendar reads assignments. `ScheduledWork` is not mapped. Recalibrate and shared groups operate on assignments.

**Actual source:** Matches.

- Writes: `app/services/pacing.py`, `app/services/curriculum_plan_apply.py`.
- Reads: `app/services/assignments.py` `AssignmentQuery`; `app/routers/calendar.py` `list_shared_assignments` → `for_shared`.
- Recalibrate: `app/services/recalibration.py`.

Paper import writes `CurriculumPlan` / `CurriculumLesson` (same as PDF/CSV), then the existing apply path writes assignments. That is a new **guide intake**, not a second calendar table.

**Tests:** `tests/test_pacing.py`, `tests/test_curriculum_plans.py`, `tests/test_assignments_api.py` shared calendar `test_returns_only_assignments_with_a_shared_group`, schema unmapped leftover tables.

**Matches documentation:** Yes.

---

## 14. Service-worker cache versioning

**Claimed state:** One `SHELL_VERSION` token. Cache name `curiculy-shell-${SHELL_VERSION}`. `index.html` and CSS query strings match. Tests fail on drift. `/api` and `/evidence` not cached.

**Actual source:** Matches. Current token is `20260831-paper-import` (post-dates the 2026-08-29 audit; bumped for paper-import UI).

- `sw.js`: `SHELL_VERSION`, `SHELL_CACHE`, `SHELL_URLS`, skip `/api/` and `/evidence/`.
- `index.html`: matching `?v=20260831-paper-import` on script, CSS, favicon, logo.
- `static/css/app.css`: background image query string uses the same token (enforced by tests).

**Tests:** `tests/test_shell.py` `test_shell_cache_version_matches_html_and_css`, `test_shell_urls_are_existing_files`, `test_application_shell_loads`, `test_service_worker_script`.

**Matches documentation:** Yes. The specific version string in `CompleteExplanation.txt` (`20260829-shell`) is historical.

---

## 15. Missing logo / extension icons

**Claimed state:** `static/curiculy-logo.png` served. Extension toolbar 16/32/48/128 and `extension/icons/logo.png` present. Tests check files exist and sizes.

**Actual source:** Matches. Files on disk:

- `static/curiculy-logo.png`
- `extension/icons/icon16.png`, `icon32.png`, `icon48.png`, `icon128.png`, `logo.png`
- Root `Curiculy Logo.png` / `New Curiculy Logo.png` (source copies; app serves `static/`)

- `extension/manifest.json` references those PNG paths.
- `index.html` favicon / brand mark.

**Tests:** `tests/test_shell.py` `test_logo_is_a_png`, `test_extension_manifest_icons_exist`, `test_extension_options_logo_exists`, `test_index_html_references_existing_static_files`.

**Matches documentation:** Yes.

---

## 16. README / bootstrap documentation

**Claimed state:** Root README covers `.env`, port 3040, first invite, `JWT_SECRET`, optional Ollama, test command. CI still absent.

**Actual source:** `README.md` exists. `tests/test_shell.py` `test_readme_covers_bootstrap` asserts `JWT_SECRET`, `localhost:3040`, and `docker compose --profile dev run --rm tests pytest`.

**Later:** `.github/workflows/tests.yml` runs the Compose `tests` image on push and pull request (`docker compose --profile dev run --rm -T tests pytest -q --tb=line`). `test_github_actions_runs_the_compose_suite` locks that command. No production secrets in the workflow.

**Bootstrap SQL:** `InviteKey.tenant_uuid` is NOT NULL. The 2026-09-01 documentation pass updated the README INSERT to `INSERT INTO invite_keys (key, tenant_uuid, expires_at) VALUES ('YOUR_HEX_KEY', '', datetime('now', '+1 day'));`, matching `app/routers/admin.py` (`tenant_uuid=""`).

**Tests:** README content test and `test_github_actions_runs_the_compose_suite`. No test executes the documented sqlite INSERT.

**Matches documentation:** Yes for bootstrap presence. CI exists later (`.github/workflows/tests.yml`).

---

## 17. Register returning an access token

**Claimed state:** `POST /auth/register` returns `{access_token, token_type}` (201); SPA stores `localStorage.auth_token` and enters the app.

**Actual source:** Matches.

- `app/routers/auth.py` `register_user` → `response_model=Token`, `return token_payload(user)`.
- `app/services/child_accounts.py` `token_payload` / `token_for_account`.
- `static/js/app.js` `submitRegister`: `setAuthToken(result.access_token)` then `#/dashboard` / `enterApp()`.

**Tests:** `tests/test_auth.py` `test_register_with_invite_provisions_tenant` asserts 201, `token_type == "bearer"`, non-empty `access_token`, JWT claims, then uses that token for `/api/household` and `POST /api/students`.

**Matches documentation:** Yes.

---

## 18. All Students UI clarification

**Claimed state:** All Students header says shared lessons only; private work is on individual calendars. Query unchanged (`shared_group_uuid` only).

**Actual source:** Matches.

- `app/routers/calendar.py` `list_shared_assignments` → `AssignmentQuery.for_shared`.
- `static/js/app.js`: when `allStudents`, renders `<p class="calendar-shared-note italic">Showing shared lessons only. Private lessons appear on individual student calendars.</p>`.

**Tests:** Query behavior: `tests/test_assignments_api.py` household calendar shared-only tests. Copy itself is not asserted by pytest (string lives in `app.js` only).

**Matches documentation:** Yes.

---

## 19. Legacy-table cleanup tooling

**Claimed state:** `scripts/drop_legacy_tables.py` COUNTs `scheduled_work` and `evidence_captures` on each `tenant_*.db`, DROPs only when empty, warns if rows exist. Not run at boot. `CODEBASE_MAP.md` lists the script.

**Actual source:** Script exists. `DATA_DIR = "./data"` (relative to process cwd, not `/data` inside the container). Table names come from a constant list. No pytest module covers it. Compose `tests` service does not mount `scripts/`. `entrypoint.sh` does not call it.

Row-clear helpers (not DROP) remain in `app/services/legacy_tables.py` and **are** tested.

**Tests:** None for the DROP script. `tests/test_legacy_tables.py` for SQL DELETE helpers. `tests/test_schema.py` proves boot does not DROP leftover tables.

**Matches documentation:** The tooling exists as claimed. It is untested and cwd-sensitive. That is not a failed claim; it is operator risk (see F).

**Later:** Logic lives in `app/services/legacy_table_drop.py`. CLI is `scripts/drop_legacy_tables.py`. Default is dry-run (`--data-dir`, default `./data`). `--apply` DROPs only when `COUNT(*) = 0` and never DELETEs rows. Non-empty tables are refused. Unopenable files are reported and left unchanged. `catalog.db`, `admin.db`, and shared `tenant.db` are not scanned. Tests: `tests/test_drop_legacy_tables.py`. Compose `tests` mounts `scripts/`. `entrypoint.sh` still does not call it. Boot still does not DROP. This pass still does not COUNT live host family files.

---

## 20. Exception API duplication

**Claimed state:** One table `calendar_exceptions`. Two HTTP surfaces. Consolidation is Phase 4 / leftover. SPA uses both prefixes. This cleanup did not merge routers.

**Actual source:** Matches leftover claim. Consolidation is **not** implemented.

- `app/routers/exceptions.py` prefix `/exceptions`: list + create only (no update/delete).
- `app/routers/settings.py` `calendar_exceptions_router` prefix `/calendar/exceptions`: date set, toggle, import-holidays.
- `app/main.py` mounts both.
- `static/js/app.js`: `api("/exceptions")` for list/create; `api("/calendar/exceptions")`, `/toggle`, `/import-holidays` for the year grid.

**Tests:** `tests/test_school_year_settings.py` and `tests/test_school_years.py` hit `/api/calendar/exceptions/toggle` and import-holidays. No test asserts a unified router.

**Matches documentation:** Yes — still duplicated, as documented **at audit time**.

**Later:** Consolidated onto `/api/exceptions` (list, create, `/dates`, `/toggle`, `/import-holidays`). `calendar_exceptions_router` and `/api/calendar/exceptions` were removed. SPA and tests use the one prefix. Exception colors remain on `/api/settings/exception-colors`. There is still no PATCH/DELETE for a titled row.

---

## A. Source features that architecture docs omitted at audit time

The 2026-09-01 documentation pass added these to `ARCHITECTURE.md`, `CODEBASE_MAP.md`, `DOMAIN_MODEL.md`, and `README.md`. They remain listed here as source evidence from the audit.

### Paper-to-plan intake

A photographed week-sheet path landed after the 2026-08-29 audit (`SHELL_VERSION = "20260831-paper-import"`).

| Piece | Path |
|---|---|
| Printable template PDF | `app/services/paper_template.py`, `app/templates/paper_template.html` |
| OpenCV / ArUco / QR slice | `app/services/paper_parser.py` |
| Ollama vision worker (own tenant session) | `app/services/paper_vision_worker.py` (`OLLAMA_VISION_MODEL = "llama3.2-vision"`, not `settings.ollama_model`) |
| HTTP | `GET /api/curriculum/paper-template`, `POST /api/curriculum/import-paper` in `app/routers/curriculum_plans.py` (`paper_template`, `import_paper`) |
| SPA | `static/js/app.js` download/import/poll; `index.html` `#paper-import-input` |
| Deps | `requirements.txt`: `opencv-python-headless`, `numpy`, `qrcode`; Dockerfile `libgomp1` |
| Tests | `tests/test_paper_parser.py`, `tests/test_paper_template.py`, `tests/test_paper_vision_worker.py` |

This still lands on `curriculum_plans` then apply → `assignments`. It does not revive `scheduled_work`. It is a third **guide capture** method (CSV, PDF+Ollama, paper+vision) under the pacing-guide intake.

### Household identity tests and icon API

`tests/test_household_api.py` (12 tests) covers default household, rename, and icon. Mapped in `CODEBASE_MAP.md`.

### Auth-file JWT routing tests already exist

`tests/test_auth.py` `auth_client` does not override `get_tenant_db`. `test_login_routes_to_tenant_file` and `test_register_with_invite_provisions_tenant` provision `tenant_{uuid}.db` and call authenticated routes with a real JWT. Architecture docs record this as implemented.

### Compose test bind-mount of README

`docker-compose.yml` tests service mounts `./README.md:/app/README.md` so `test_readme_covers_bootstrap` can run. Dockerfile `dev` stage does not `COPY README.md`. Undocumented coupling.

### Duplicate `legacy_tables.py` definitions (noted in post-hardening audit)

At audit time, `delete_legacy_rows_for_student`, `delete_legacy_rows_for_units`, and `delete_legacy_rows_for_enrollments` were each defined twice. First copies used `_present_orphans`; second copies used `_table_names`. SQL DELETE statements were the same.

**Later:** One implementation of each helper remains. Table-presence uses `_present_orphans` (`sqlite_master` ∩ `ORPHAN_TABLES`). Helpers still do not DROP tables.

### FastAPI app description

`create_app()` description still says “compliance foundation.” Compliance is a stub (`app/services/compliance/__init__.py` `build_packet` raises `NotImplementedError`). Cosmetic; already flagged in the post-hardening audit.

---

## B. Documentation claims that were not supported by source at audit time

The 2026-09-01 documentation pass corrected these in `ARCHITECTURE.md`, `CODEBASE_MAP.md`, `TECHNICAL_DEBT.md`, `ROADMAP.md`, `POST_HARDENING_AUDIT.md`, and `README.md`. `CompleteExplanation.txt` remains a session log and may still contain historical “still open” paragraphs.

| Claim (before doc reconciliation) | Where it lived | Source |
|---|---|---|
| Register does not return a JWT | Historical `POST_HARDENING_AUDIT.md` unresolved list | `register_user` returns `Token` |
| All Students UI copy is missing | Historical `POST_HARDENING_AUDIT.md` | `calendar-shared-note` in `app.js` |
| No root README | Historical audit / old architecture CURRENT | `README.md` exists |
| Tests do not prove `tenant_{uuid}.db` + JWT routing | Old `TECHNICAL_DEBT.md` #15 | `tests/test_auth.py` auth_client |
| Ollama has three uses only | Old architecture AI section | Paper vision is a fourth |
| Curriculum plans = CSV, PDF, builder only | Old architecture | `import-paper` / paper-template |
| Suite size 786 as current | Historical audit suite line | 821 collected this pass |
| README sqlite INSERT omitted `tenant_uuid` | README before the doc pass | INSERT now includes `tenant_uuid ''` |

`CompleteExplanation.txt` still contains both a post-hardening “later work” block and a later section that records README / register / All Students as implemented. Treat it as a changelog, not current architecture.

---

## C. Remaining technical debt

Still accurate in source (aligned with `TECHNICAL_DEBT.md` / Phase 4+ except where noted):

| Item | Evidence |
|---|---|
| `HouseholdSettings` date mirror still written | Closed later: columns removed; leftover files backfill then drop |
| `/books/*` and `POST /catalog/from-isbn` kept as API-only | Confirmed. `/books` is dictionary HTTP; `from-isbn` creates tenant library rows. SPA uses lookup-isbn + `POST /curricula`. |
| Leftover `scheduled_work` / `evidence_captures` tables not DROPped at boot | Intentional. Operator script tested in `tests/test_drop_legacy_tables.py`. Live family files not counted here. |
| Historical enrollments not backfilled | Closed later for proven assignments (`scripts/backfill_enrollments.py`, including stored `curriculum_id`). Title-only week/day plan rows still cannot be reconstructed. |
| Default pytest client is one memory DB + dependency overrides | Intentional. `auth_client` covers JWT → `tenant_{uuid}.db` without overriding `get_tenant_db`. `test_physical_tenant_files_persist_and_stay_isolated` reads committed rows with sqlite3. |
| No CI | Closed later. `.github/workflows/tests.yml` runs `docker compose --profile dev run --rm -T tests pytest -q --tb=line`. |
| `DEV_MODE=true` skips JWT | `user_from_token` / `get_current_user` |
| Health check skips tenant files | Intentional. `GET /api/health` is `catalog.db` + `admin.db` `SELECT 1` only (`db_health.py`). Household `tenant_{uuid}.db` files are not opened. Tests in `tests/test_health.py`. |
| Homework-help test volume small | `tests/test_homework_help.py` (5 tests) |
| Color palettes duplicated JS/Python | `STUDENT_COLOR_PALETTE` in `app/models/__init__.py` vs SPA |
| `ai_generator.py` filename vs arithmetic | Comments corrected; name unchanged |
| Jurisdiction / compliance / taxonomy stubs | `NotImplementedError`; models remain |
| Pacing commit is two engines | Tenant commit then catalog page_count (`SyllabusCommitter.commit`) |
| JWT strength is length + denylist | `jwt_secret_is_insecure` |
| `get_tenant_db` accepts capture JWTs | Closed later: `get_tenant_db` uses `get_current_user`; staging uses `get_staging_tenant_db` |
| Paper vision model not using `OLLAMA_MODEL` | Intentional. `llama3.2-vision` constant. Do not point at text `OLLAMA_MODEL`. |
| Passlib `crypt` deprecation | Suite warning; third-party |

Item 16 (README invite SQL omitting `tenant_uuid`) was **fixed in the 2026-09-01 documentation pass**. Historical `TECHNICAL_DEBT.md` #15 (no tenant-file tests) and post-hardening “unresolved” README / register / All Students rows are **stale** relative to source; current `TECHNICAL_DEBT.md` and `POST_HARDENING_AUDIT.md` no longer list them as open product work.

---

## D. Potential regressions introduced by the hardening work

No test-suite regression this pass (821 passed). No inversion of the fourteen checks.

**Intended behavior that can look like a regression to operators:**

- Non-dev Compose will not boot without a strong `JWT_SECRET` (observed on this host).
- Public `/evidence/...` URLs no longer serve files; clients must use authenticated `/api/evidence/files/...`.
- Families still pasting a parent JWT into the extension keep a full parent session until they mint a capture token (documented).
- Child completing a shared lesson does not complete siblings (documented).
- Years scheduled before auto-enroll still have empty reading lists until manual enroll or a new commit/apply.

**Risks introduced or left by hardening, not failing tests:**

- Forgetting a `schema_patches` ALTER on a new model column (old `tenant_*.db` lag). Tests cover the current patch list, not future discipline.
- `alembic upgrade` is refused; generating a new revision could still mislead an operator.
- Recalibrate and parent shared-group sync remain high blast radius (unchanged by hardening; tests exist).

**Paper import (post-hardening) — not a calendar regression, but extra operational risk:**

- New native deps (OpenCV) in the runtime image.
- Background vision worker must not reuse the request Session (it does not; tests cover failure session).
- Hardcoded vision model can fail even when `OLLAMA_MODEL` is set to something else.
- Plans titled `"Paper Import"` share a title; `curriculum_for_plan` matches library rows case-insensitively on title, so apply could reuse an earlier library row.

---

## E. Suspicious or duplicated implementation that should be reviewed

1. **`app/services/legacy_tables.py` triple redefinition (closed later)** — at audit time, three functions defined twice. Later collapsed to one implementation each. Helpers still DELETE leftover rows only; they do not DROP tables.

2. **Two exception routers (closed later)** — at audit time, `exceptions.py` vs `settings.py` `calendar_exceptions_router`. Later folded into `/api/exceptions`. No PATCH/DELETE for titled rows remains.

3. **Two ISBN HTTP namespaces** — `/catalog/lookup-isbn` (SPA, flat form fields) vs `/books/*` (full `BookEditionRead`; GET by ISBN and by id have no catalog twin) vs `POST /catalog/from-isbn` (library create, resolve-or-404). Same `BookResolver` / `book_editions`. Not safe to delete or to treat as aliases without matching response shapes. Documented KEEP, not keep-as-alias.

4. **`get_tenant_db` vs `get_current_user` (closed later)** — at audit time, capture credentials could open a tenant Session via `get_tenant_db`. Later, `get_tenant_db` calls `get_current_user` (rejects capture). Staging uses `get_staging_tenant_db` + `require_staging_upload`.

5. **`files_router` double gate** — router `dependencies=[Depends(get_current_user)]` plus handler `Depends(get_current_user)` plus dead `is_capture_credential` branch. Redundant, not wrong.

6. **Two Ollama client stacks** — `ollama.AsyncClient` (PDF worker, homework) vs raw `httpx` `/api/chat` (spark, paper vision). Later investigation: the split is load-bearing. Later, PDF and homework share `app/services/ollama_chat.py` for the primary → mistral fallback; spark/vision stay on `httpx`. Do not point vision at `OLLAMA_MODEL`. Optional later: `OLLAMA_VISION_MODEL`.

7. **Pacing two-phase commit** — tenant assignments/enrollments commit, then catalog `page_count`. In-memory tests cannot see a split-brain. Documented in `TECHNICAL_DEBT.md` (#17 as of 2026-09-01).

8. **`curriculum_plans.py` module docstring** still says CSV/PDF/manual only; the same file implements paper-template and import-paper.

---

## F. Database migration / data-safety concerns

1. **Patches are additive only.** There is no reverse migration. Rollback is restore SQLite files from backup (`ARCHITECTURE.md` / `schema_patches.py` header). Forgetting a patch on an existing `tenant_*.db` leaves a column missing until the next boot that includes it.

2. **Alembic 0001–0012 must not run.** `refuse_alembic_replay()` is the guard. Replay would be the wrong shape (single DB, old `curricula.isbn`, missing admin tables, 0007 ALTERs plans the chain never created). `alembic.ini` points at `:memory:`, not live files.

3. **`household_settings.start_date` / `end_date` (closed later).** At audit time they were NOT NULL and still written. Later they were removed from the model. Boot backfills a `SchoolYear` from leftover dates only when that household has no named year, then drops the columns. Existing named years are not overwritten.

4. **Leftover `scheduled_work` / `evidence_captures` (tooling closed later; live files not counted here).** Boot will not DROP them. Later, `scripts/drop_legacy_tables.py` defaults to dry-run and `--apply` DROPs only when `COUNT(*) = 0`. It never DELETEs rows. Non-empty tables are refused. Use `--data-dir /data` in the container; relative `./data` is the host/process cwd. This pass still does not COUNT this host’s family files.

5. **Enrollment backfill (closed later for book-paced rows).** At audit time, evaluator reading lists for years scheduled only as assignments stayed empty until Settings POST or a new commit/apply. Later, `scripts/backfill_enrollments.py` reconstructs student + curriculum + year when an assignment points at a live resource/unit and its date falls in exactly one `SchoolYear`. Plan-apply title-only assignments are still refused.

6. **Pacing tenant-then-catalog commit.** A catalog commit failure after tenant commit would leave calendar complete and ISBN `page_count` stale. Not a torn assignment list.

7. **PDF / paper import:** plan row is committed `processing` on the request Session, then the worker opens a new Session. If the process dies after 202, the plan can stay `processing` until a later failure path or operator action. Empty parse marks `failed` on the job session.

8. **Capture tokens:** rotating `JWT_SECRET` invalidates live capture JWTs even if `admin.db` rows remain unrevoked. Documented in `ARCHITECTURE.md`.

9. **Invite bootstrap:** `InviteKey.tenant_uuid` is NOT NULL. README INSERT (after the 2026-09-01 doc pass) includes `tenant_uuid ''`, matching the admin API. No pytest executes that sqlite statement.

10. **This repository is not a git workspace** (per environment). Secret-history rotation cannot be verified here. `.env` is gitignored and present on this host; it was not read for this audit.

---

## Roadmap phase cross-check

| Phase | Claimed | Source |
|---|---|---|
| 0 Safety (secrets, evidence GET, SW lockstep) | done | Confirmed |
| 1 Child complete, capture token, icons | done | Confirmed |
| 2 SchoolYear, auto-enroll, empty reading-list copy | done (mirror remains) | Confirmed at 821; **Later:** settings date columns retired |
| 3 Patches-only schema, Alembic refused, PDF own session | done | Confirmed |
| 4 Fold exception/book APIs; DROP leftover tables | exception merge later; books investigated later; leftover-table DROP tooling later; this-host empty DROP later | Exception HTTP was consolidated after this audit. Leftover-table operator DROP is tested (not boot). This host’s empty leftover tables were DROPped. `/books` kept as dictionary HTTP; not aliased. |
| 5 CI, notify on PDF ready, LLM pacing titles | CI and plan-ready/failed notify later; LLM titles leftover | GitHub Actions pytest and in-app plan notifications are in source. Optional LLM pacing titles are not. README and tenant-file JWT tests are **not** remaining. |
| Safest #10 tenant-file JWT test | historical gap | **Implemented** in `tests/test_auth.py` |

Ten architectural decisions in `ROADMAP.md` section 1 all still hold, with paper import fitting under decision 3 as another pacing-guide capture method, not a third calendar object.

---

## Test suite

Command:

```text
docker compose --profile dev run --rm tests pytest -q --tb=line
```

**Result: 821 passed, 0 failed, 0 skipped.**

Warning: Passlib `crypt` deprecation (`passlib/utils/__init__.py`).

Collect-only per module (sum 821):

| Module | Count |
|---|---|
| `test_assignments_api.py` | 118 |
| `test_pacing.py` | 105 |
| `test_isbn.py` | 79 |
| `test_curriculum_import.py` | 46 |
| `test_curriculum_pdf_import.py` | 31 |
| `test_providers.py` | 31 |
| `test_education.py` | 27 |
| `test_resolver.py` | 27 |
| `test_curriculum_plans.py` | 25 |
| `test_auth.py` | 23 |
| `test_metadata.py` | 22 |
| `test_schema.py` | 21 |
| `test_books_api.py` | 18 |
| `test_config.py` | 18 |
| `test_school_year_settings.py` | 18 |
| `test_portfolios_api.py` | 16 |
| `test_enrollments.py` | 15 |
| `test_catalog_api.py` | 14 |
| `test_school_years.py` | 13 |
| `test_household_api.py` | 12 |
| `test_kid_auth.py` | 12 |
| `test_students_api.py` | 12 |
| `test_capture_token.py` | 11 |
| `test_shell.py` | 11 |
| `test_curricula_api.py` | 10 |
| `test_evidence_files_api.py` | 10 |
| `test_paper_template.py` | 10 |
| `test_attendance_api.py` | 9 |
| `test_evidence_staging_api.py` | 8 |
| `test_weekly_manifest.py` | 8 |
| `test_recalibration.py` | 7 |
| `test_child_assignment_status.py` | 6 |
| `test_paper_parser.py` | 6 |
| `test_homework_help.py` | 5 |
| `test_legacy_tables.py` | 5 |
| `test_paper_vision_worker.py` | 5 |
| `test_dashboard_api.py` | 4 |
| `test_spark.py` | 3 |

Compared with the 2026-08-29 audit (786 passed), this baseline is **821 passed**. Use 821 as the count for any later delta.

---

## How to use this document

| Question | Answer in this file |
|---|---|
| Did hardening land? | Yes. Items 1–15, 16 (after README SQL fix), 17–19 confirmed; item 20 (exception APIs) was open at audit time and consolidated later. |
| Current architecture? | `docs/ARCHITECTURE.md` after the 2026-09-01 doc pass |
| Remaining debt? | `docs/TECHNICAL_DEBT.md` / `docs/ROADMAP.md` |
| What is the suite baseline? | 821 passed, 2026-09-01, Compose `tests` profile. |
