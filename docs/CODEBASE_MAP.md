# Curiculy Codebase Map

Map of the repository **as it exists** (2026-09-01). Disposition labels match `docs/ARCHITECTURE.md`. Paths are relative to the repo root.

Verified baseline: **892 tests passed**. Independent audit: `docs/IMPLEMENTATION_RECONCILIATION.md` (821 at that pass; later exception-record, capture-isolation, SchoolYear date-retirement, enrollment-backfill, leftover-table DROP, shared Ollama AsyncClient helper, catalog/admin health-contract, GitHub Actions workflow, physical tenant persistence tests, plan processing notifications, and assignment `curriculum_id`).

---

## How to read this map

- **Live product** means the parent SPA, child My work, extension staging, paper/PDF/CSV plan capture, and the APIs they call.
- **Foundation leftover** means tables or modules that boot and test but are not on the live path.
- **Do not delete in the same week as a feature** — leftover SQLite tables on live family files still need an operator COUNT=0 DROP (`scripts/drop_legacy_tables.py`); boot never DROPs them.

---

## Top-level

| Path | Role | Disposition |
|---|---|---|
| `app/` | FastAPI application | KEEP |
| `static/js/app.js` | Entire SPA | KEEP (split later only if needed) |
| `static/css/app.css` | Styles | KEEP |
| `index.html` | Shell, auth, modals, paper file input | KEEP |
| `sw.js` | PWA + outbox; `SHELL_VERSION` lockstep | KEEP |
| `extension/` | Tab capture | KEEP |
| `alembic/` | Historical DDL archive; `upgrade` refused | ARCHIVE |
| `app/schema_patches.py` | Ordered create_all + ALTER runner; retires leftover settings date columns | KEEP |
| `tests/` | Pytest (892 collected) | KEEP |
| `Dockerfile` | Image (WeasyPrint, Tesseract, OpenCV runtime libs) | KEEP |
| `docker-compose.yml` | Run; secrets via `.env`; `tests` profile for pytest | KEEP |
| `.github/workflows/tests.yml` | GitHub Actions: Compose `tests` pytest on push and pull request | KEEP |
| `README.md` | Bootstrap: `.env`, port 3040, first invite, tests, CI | KEEP |
| `scripts/drop_legacy_tables.py` | Dry-run / `--apply` DROP of empty leftover tables | KEEP; operator-run only; not boot; COUNT=0 only; never deletes rows |
| `scripts/backfill_enrollments.py` | Dry-run / `--apply` enrollment reconstruction from book-paced assignments | KEEP; operator-run only; not boot |
| `entrypoint.sh` | JWT validate + schema + uvicorn | KEEP |
| `requirements.txt` | Runtime deps including `opencv-python-headless`, `numpy`, `qrcode` | KEEP |
| `requirements-dev.txt` | Pytest | KEEP |
| `pytest.ini` | Pytest config | KEEP |
| `alembic.ini` | Unused live url; Alembic not the runner | ARCHIVE |
| `docs/` | Architecture + reconciliation | KEEP |
| `.venv/`, `.pytest_cache/`, `data/` | Generated / runtime | Ignore as product source |
| `.gitignore` | Ignores `data/`, `.env` | KEEP |

Served brand assets: `static/curiculy-logo.png`, `extension/icons/*`. Root `Curiculy Logo.png` / `New Curiculy Logo.png` are the same image, not referenced by the app.

---

## Backend entry and config

| Path | Exports / role | Disposition |
|---|---|---|
| `app/main.py` | `create_app()`, router mount, `/`, `/sw.js`, `/static` only (no `/evidence` mount) | KEEP |
| `app/config.py` | `Settings` / env; fail closed on weak JWT in non-dev | KEEP |
| `app/db.py` | Three engines, tenant files, `init_databases`, `get_tenant_db` (application users), `get_staging_tenant_db` (parent or capture) | KEEP isolation; schema via `schema_patches` |
| `app/schema_patches.py` | Idempotent ALTER lists after create_all | KEEP |
| `app/enums.py` | Domain enums (`AssignmentStatus`, `UserRole.EVIDENCE`, …) | KEEP |
| `app/__init__.py` | Package docstring | KEEP |
| `app/core/security.py` | JWT, `CurrentUser`, `get_current_user`, `require_parent`, `require_admin`, `require_staging_upload` | KEEP |
| `app/core/__init__.py` | Empty package | KEEP |
| `app/evidence/__init__.py` | `store_capture`, `resolve_evidence_file` | KEEP |

---

## Models

| Path | Tables / types | Disposition |
|---|---|---|
| `app/models/mixins.py` | `TimestampMixin` | KEEP |
| `app/models/admin.py` | `User`, `InviteKey` (`tenant_uuid` NOT NULL), `CaptureToken` | KEEP |
| `app/models/curriculum.py` | Catalog books + tenant library + plans | KEEP |
| `app/models/education.py` | `Assignment*`, `Attendance`, taxonomy | KEEP assignments/attendance; DEFER taxonomy |
| `app/models/homework.py` | Help sessions, notifications | KEEP |
| `app/models/evidence_staging.py` | Staging inbox (`tenant_id` = JWT UUID string) | KEEP |
| `app/models/__init__.py` | Household, Student, SchoolYear, Enrollment, Exception, **Jurisdiction**, **CompliancePacket** | KEEP household/student/year/enrollment/exception; leftover `scheduled_work` / `evidence_captures` **models removed** (physical tables may remain on older tenant files); **DEFER** jurisdiction/packets |

There is no `ScheduledWork` or `EvidenceCapture` class. Those names must not be reintroduced.

---

## Routers (HTTP)

Mounted under `/api` from `app/main.py`.

| Path | Prefix | Live SPA? | Disposition |
|---|---|---|---|
| `health.py` | `/health` | Yes | KEEP; catalog.db + admin.db only (household `tenant_{uuid}.db` excluded on purpose) |
| `auth.py` | `/auth` | Yes | KEEP; capture token; register returns access token |
| `admin.py` | `/admin` | Yes (admins) | KEEP; invite insert uses `tenant_uuid=""` |
| `household.py` | `/household` | Yes | KEEP; PATCH name/icon |
| `students.py` | `/students` | Yes | KEEP |
| `school_years.py` | `/school-years` | Yes | KEEP; canonical named year |
| `enrollments.py` | `/enrollments` | Yes (settings) | KEEP; auto-create also on schedule |
| `settings.py` | `/settings` | Yes | KEEP; school-year dates/weekdays + exception colors |
| `exceptions.py` | `/exceptions` | Yes | KEEP; list, create, dates, toggle, import-holidays |
| `catalog.py` | `/catalog` | lookup-isbn yes; from-isbn no | KEEP lookup (SPA); KEEP from-isbn as API-only (library create, not a `/books` alias) |
| `books.py` | `/books` | No (tests + OpenAPI yes) | KEEP dictionary HTTP (`BookEdition` only). GET routes have no catalog twin. |
| `curricula.py` | `/curricula` | Yes; import API unused | KEEP; import is API-only |
| `curriculum_plans.py` | `/curriculum` | Yes | KEEP; CSV, PDF, **paper-template**, **import-paper**, apply |
| `assignments.py` | mixed paths | Yes | KEEP |
| `calendar.py` | `/calendar` | Yes (all students, shared only) | KEEP |
| `attendance.py` | `/attendance` | Yes | KEEP |
| `pacing.py` | `/pacing` | Yes | KEEP |
| `recalibration.py` | `/recalibrate` | Yes | KEEP |
| `evidence.py` | `/evidence` | Yes + extension | KEEP; files GET authenticated; staging POST uses `require_staging_upload` + `get_staging_tenant_db` |
| `dashboard.py` | `/dashboard` | Yes | KEEP |
| `reports.py` | `/reports` | Yes | KEEP |
| `portfolios.py` | `/portfolios` | Yes | KEEP |
| `homework_help.py` | `/homework-help` | Yes (child) | KEEP |
| `notifications.py` | `/notifications` | Yes | KEEP |

Paper HTTP (same router as plans):

- `GET /api/curriculum/paper-template` — printable week PDF
- `POST /api/curriculum/import-paper` — 202; OpenCV on request, vision in background

---

## Services

| Path | Role | Disposition |
|---|---|---|
| `households.py` | Default household + rename | KEEP |
| `enrollments.py` | Ensure enrollment on schedule | KEEP |
| `enrollment_backfill.py` | Reconstruct proven enrollments (stored `curriculum_id` or resource/unit) | KEEP; operator script only |
| `child_accounts.py` | PIN, switch, tokens | KEEP |
| `capture_tokens.py` | Issue / revoke capture JWTs | KEEP |
| `assignments.py` | Query, windows, catalog hydrate | KEEP |
| `pacing.py` | Engine + commit; stamps `curriculum_id` | KEEP |
| `curriculum_plan_apply.py` | Plan → assignments; stamps `curriculum_id` | KEEP |
| `ai_generator.py` | Page chunks (not LLM) | KEEP; rename when touched |
| `catalog.py` | Library + ISBN projection | KEEP |
| `resolver.py` | ISBN → edition | KEEP |
| `providers/` | Open Library, Google Books | KEEP |
| `curriculum_import.py` | JSON/CSV tree import | KEEP as API; no SPA |
| `curriculum_structure.py` | Tree/resources load | KEEP |
| `curriculum_plan_import.py` | CSV plans | KEEP |
| `curriculum_plan_apply.py` | Plan → assignments; stamps `curriculum_id` | KEEP |
| `ai_curriculum_worker.py` | PDF background parse (`ollama_chat.chat_with_model_fallback`; own session; one plan-ready/failed notification on terminal status) | KEEP |
| `ollama_chat.py` | Shared `AsyncClient` primary → mistral fallback for PDF and homework | KEEP |
| `pdf_parser.py` | PyMuPDF + OCR | KEEP |
| `paper_template.py` | Printable week PDF; ArUco + `qrcode` | KEEP |
| `paper_parser.py` | OpenCV flatten + QR (`numpy`) | KEEP |
| `paper_vision_worker.py` | Ollama vision OCR (`httpx`; own session; hardcoded `llama3.2-vision`; same terminal-status notification as PDF) | KEEP; not `OLLAMA_MODEL` |
| `school_year.py` | Bounds, holidays, colors; dates only on SchoolYear; weekdays/colors on settings | KEEP |
| `portfolio.py` | Report + PDF + mail | KEEP |
| `weekly_manifest.py` | Checklist PDF | KEEP |
| `recalibration.py` | Shift leftover work | KEEP |
| `homework_help.py` | Tutor + lock (`ollama_chat`; canned hint if Ollama is down) | KEEP |
| `notifications.py` | In-app rows (homework help + curriculum-plan ready/failed) | KEEP |
| `spark.py` | Short Ollama question (`httpx`; 2.5s timeout; `OLLAMA_MODEL`) | KEEP |
| `db_health.py` | Read-only `SELECT 1` for catalog + admin health | KEEP |
| `legacy_tables.py` | Clear leftover `scheduled_work` / `evidence_captures` rows on delete | KEEP; does not DROP; one implementation of each helper |
| `legacy_table_drop.py` | Operator COUNT=0 DROP of leftover tables | KEEP; not called from boot |
| `compliance/__init__.py` | Stub | DEFER / do not call |
| `parsing/__init__.py` | Stub | DEFER / do not call |

---

## Schemas and templates

| Path | Role | Disposition |
|---|---|---|
| `app/schemas/*.py` | Request/response (`CurriculumPlanPaperImportRead`, capture token schemas, …) | KEEP |
| `app/templates/portfolio*.html`, `portfolio.css` | Evaluator PDF | KEEP |
| `app/templates/weekly_manifest.html` | Printable week checklist | KEEP |
| `app/templates/paper_template.html` | Paper-intake week sheet | KEEP |
| `app/utils/isbn.py` | ISBN normalize | KEEP |

---

## Frontend map (`static/js/app.js`)

There is no component tree. Features are functions + `data-action` + hash routes.

| Route / UI | Functions (names) | APIs |
|---|---|---|
| Auth | login, register (stores `access_token`), demo, student PIN, switch | `/auth/*` |
| `#/dashboard` | `renderDashboard`, `loadDashboardStats` | `/dashboard/stats` |
| `#/assignments` | `renderAssignments`, `loadCalendar` | assignments or `/calendar`, attendance, exceptions; All Students shared-lessons copy |
| `#/evidence` | `renderEvidence` | staging, link, calendar drop; files via authenticated `/evidence/files` |
| `#/students` | `renderStudents` | assignments, courses, spark, PATCH status |
| `#/curricula` | `renderCurricula`, lesson builder, apply plan, paper template/import | `/curricula`, `/curriculum/*` including paper-template and import-paper, lookup-isbn |
| `#/portfolios` | `renderPortfolios` | preview, email; empty-enrollment copy |
| `#/settings/*` | students, exceptions, years, enrollments, admin, household name/icon, capture token | matching REST + PATCH `/household` |
| `#/my-work` | `renderMyWork`, homework help | assignments GET, `/homework-help/*` |
| Modals | pacing, wizard (household/year/student), school-year grid, recalibrate | household, pacing, school-years, settings, recalibrate |

`api()` is the only HTTP helper besides weekly-manifest `fetch` and paper-template `fetch`.

SPA exception calls: list/create on `/exceptions`; year-grid dates/toggle/holidays on `/exceptions/dates`, `/exceptions/toggle`, `/exceptions/import-holidays`. Colors stay on `/settings/exception-colors`.

---

## Extension map

| Path | Role | Disposition |
|---|---|---|
| `extension/manifest.json` | MV3, `activeTab`, `storage`, `scripting`; icon sizes 16/32/48/128 | KEEP |
| `extension/background.js` | Capture + upload to `/api/evidence/staging` | KEEP |
| `extension/options.html` / `options.js` / `options.css` | Server URL + capture token | KEEP |
| `extension/icons/` | `icon16.png` … `icon128.png`, `logo.png` | KEEP |

---

## Tests map

Default `conftest.py` `client`: one in-memory DB; overrides `get_tenant_db` / `get_staging_tenant_db` / `get_current_user`. Intentional for the bulk of the suite. JWT → `tenant_{uuid}.db` is `auth_client`, not missing.

| Module | What it protects | Notes |
|---|---|---|
| `conftest.py` | In-memory unified DB; patches PDF/paper `open_tenant_session` | Default `client` (intentional) |
| `test_auth.py` | JWT, register token, **real `tenant_{uuid}.db` routing without overriding `get_tenant_db`**, demo isolation, on-disk persist + two-file isolation | KEEP |
| `test_kid_auth.py`, `test_config.py`, `test_capture_token.py`, `test_child_assignment_status.py` | PIN, JWT fail-closed, capture upload-only vs parent/child routes, child complete | KEEP |
| `test_household_api.py` | Default household, rename, icon | KEEP |
| `test_students_api.py` | CRUD | KEEP |
| `test_assignments_api.py` | Calendar, shared group, child shared-group non-sync | KEEP |
| `test_pacing.py` | Preview/commit math | KEEP |
| `test_curriculum_plans.py`, `test_curriculum_pdf_import.py` | Plans + PDF worker session isolation + plan-ready/failed notifications | KEEP |
| `test_paper_parser.py`, `test_paper_template.py`, `test_paper_vision_worker.py` | Paper geometry, template PDF, vision worker session + plan-ready/failed notifications | KEEP |
| `test_catalog_api.py`, `test_books_api.py`, `test_resolver.py`, `test_isbn.py`, `test_providers.py`, `test_metadata.py` | ISBN dictionary + lookup/from-isbn/curricula save | KEEP; books tests cover `BookEditionRead` and GET routes catalog tests do not |
| `test_evidence_staging_api.py`, `test_evidence_files_api.py` | Inbox + authenticated file GET | KEEP |
| `test_portfolios_api.py` | Reports | KEEP |
| `test_attendance_api.py` | Attendance | KEEP |
| `test_dashboard_api.py` | Stats | KEEP |
| `test_school_year_settings.py` | Year, holidays, exception list/create/dates/toggle | KEEP |
| `test_school_years.py` | Named year CRUD + leftover settings-date backfill/drop | KEEP |
| `test_enrollments.py` | Auto-enroll on commit/apply; plan-apply stamps `curriculum_id` | KEEP |
| `test_enrollment_backfill.py` | Proven reconstruction (stored id or resource/unit); skips unlinked title-only plan rows | KEEP |
| `test_recalibration.py` | Shift | KEEP |
| `test_homework_help.py` | Tutor; canned hint if Ollama is down | KEEP |
| `test_health.py` | `/api/health` is catalog + admin; household files do not fail the probe | KEEP |
| `test_ollama_chat.py` | Shared AsyncClient primary → mistral fallback | KEEP |
| `test_spark.py` | Spark | KEEP |
| `test_weekly_manifest.py` | PDF | KEEP |
| `test_education.py` | Taxonomy models | DEFER product |
| `test_shell.py` | `/`, `/sw.js`, cache lockstep, logo, extension icons, README bootstrap, GitHub Actions compose command | KEEP |
| `test_schema.py` | Fresh/upgrade SQLite files; Alembic refused; leftover tables not mapped and not dropped; settings date columns retired | KEEP |
| `test_legacy_tables.py` | Orphan-row SQL cleanup (not the DROP script) | KEEP |
| `test_drop_legacy_tables.py` | Operator DROP helper: empty/nonempty/dry-run/malformed/idempotent | KEEP |
| `test_curricula_api.py`, `test_curriculum_import.py` | Library import | KEEP |

`scripts/drop_legacy_tables.py` is tested via `app.services.legacy_table_drop` in `tests/test_drop_legacy_tables.py`. `scripts/backfill_enrollments.py` is tested via `app.services.enrollment_backfill` in `tests/test_enrollment_backfill.py`.

---

## Alembic versions (historical archive)

These files describe an older single-DB shape. They are **not** the runtime schema. `alembic upgrade` is refused.

| Revision | Topic | vs live models |
|---|---|---|
| `0001_initial` | Household, old curricula.isbn, scheduled_work | Unsafe to replay |
| `0002_curriculum_catalog` | Catalog + tenant in one DB; FK to publishers | Not the three-file layout |
| `0003_education_core` | Assignments + taxonomy; cross-DB FKs | Not live FK policy |
| `0004`–`0012` | Shared group, color, attendance, plan ALTERs, settings, staging | Partial; 0007 ALTERs tables the chain never created |

Treat as archaeology. Runtime is `create_all` + `app.schema_patches`.

---

## Central files (change with care)

Many features import these. Prefer additive changes.

1. `app/db.py` — tenant routing and `init_databases`
2. `app/schema_patches.py` — additive schema on existing files
3. `app/core/security.py` — every request
4. `app/models/education.py` — `Assignment`
5. `app/services/assignments.py` — calendar reads
6. `app/services/pacing.py` — writes many rows
7. `static/js/app.js` — all UX
8. `app/main.py` — mounts and router list

---

## Safe to ignore when implementing product features

- `app/services/compliance/`
- `app/services/parsing/`
- Leftover `scheduled_work` / `evidence_captures` **tables on disk** (clear matching rows on student/curriculum delete; operator DROP only when empty; do not DROP from boot). These are not live ORM models.
- `POST /catalog/from-isbn` and `/books/*` unless you are adding catalog GET twins that return the same `BookEditionRead`
- Taxonomy CRUD (does not exist)
- Alembic `upgrade()` as a deploy step (it does not migrate)

---

## Legacy cleanup classification

Do not delete something merely because the SPA does not call it.

| Candidate | Class | Why |
|---|---|---|
| `ScheduledWork` / `EvidenceCapture` ORM models, unused read schemas, `ScheduleGrain`, `WorkStatus` | Already removed from application code | Do not re-map |
| Orphan SQLite tables `scheduled_work` / `evidence_captures` | DEPRECATE | ORM gone. `create_all` / boot do not drop them. Operator `scripts/drop_legacy_tables.py` DROPs only when `COUNT(*) = 0`. Non-empty tables are refused. Live family files are not verified by this repo. |
| Duplicate function bodies in `legacy_tables.py` | Already removed | One implementation of each row-clear helper. Tables themselves are not DROPped. |
| Alembic revisions 0001–0012 | KEEP | Historical archive. Replay is refused and unsafe. |
| `POST /catalog/from-isbn`, `/books/*`, `POST /curricula/import` | KEEP | SPA unused. Tests and OpenAPI call them. `/books` is ISBN dictionary HTTP; `from-isbn` creates household library rows; import builds a unit tree. Not interchangeable. |
| Taxonomy models and `assignments.subject_taxonomy_id` | KEEP | Pacing, assignments, weekly manifest, and tests use them. No CRUD UI. |
| `Jurisdiction` / `CompliancePacket` / `compliance/` / `parsing/` | KEEP (DEFER) | Empty stubs until a state form exists. Do not call. |
| `/exceptions` (list, create, dates, toggle, import-holidays) | KEEP | Canonical CalendarException HTTP. `/calendar/exceptions` removed. |
| `ai_generator.py` module | KEEP | Arithmetic is the real generator. Rename later. |
| Root `Curiculy Logo.png` | KEEP | Source asset; served copy is `static/curiculy-logo.png`. |
