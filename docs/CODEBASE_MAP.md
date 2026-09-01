# Curiculy Codebase Map

Map of the repository as it exists, annotated with the target architecture (`KEEP` / `CONSOLIDATE` / `REFACTOR` / `REMOVE` / `COMPLETE` / `DEFER`).

Application source was not changed for this map. Paths are relative to the repo root.

---

## How to read this map

- **Live product** means the parent SPA, child My work, extension staging, and the APIs they call.
- **Foundation leftover** means tables or modules that boot and test but are not on the live path.
- **Do not delete in the same week as a feature** — `REMOVE` items still need a data check on real `tenant_*.db` files.

---

## Top-level

| Path | Role | Disposition |
|---|---|---|
| `app/` | FastAPI application | KEEP |
| `static/js/app.js` | Entire SPA | KEEP (split later only if needed) |
| `static/css/app.css` | Styles | KEEP |
| `index.html` | Shell, auth, modals | KEEP |
| `sw.js` | PWA + outbox | KEEP |
| `extension/` | Tab capture | KEEP |
| `alembic/` | Historical DDL archive; `upgrade` refused | ARCHIVE |
| `app/schema_patches.py` | Ordered create_all + ALTER runner | KEEP |
| `tests/` | Pytest | KEEP; REFACTOR isolation coverage |
| `Dockerfile` | Image | KEEP |
| `docker-compose.yml` | Run | KEEP; secrets via `.env` |
| `README.md` | Bootstrap: `.env`, port 3040, first invite, tests | KEEP |
| `scripts/drop_legacy_tables.py` | COUNT then DROP empty leftover tables | KEEP; operator-run only |
| `entrypoint.sh` | Schema + uvicorn | KEEP |
| `requirements.txt` | Runtime deps | KEEP |
| `requirements-dev.txt` | Pytest | KEEP |
| `pytest.ini` | Pytest config | KEEP |
| `alembic.ini` | Unused url; Alembic not the runner | ARCHIVE |
| `docs/` | Architecture docs | KEEP |
| `.venv/`, `.pytest_cache/`, `data/` | Generated / runtime | Ignore as product source |
| `.gitignore` | Ignores `data/`, `.env` | KEEP |

Served brand assets: `static/curiculy-logo.png`, `extension/icons/*`. Root `Curiculy Logo.png` is the same image, not referenced by the app.

---

## Backend entry and config

| Path | Exports / role | Disposition |
|---|---|---|
| `app/main.py` | `create_app()`, router mount, `/`, `/sw.js`, `/static` | KEEP |
| `app/config.py` | `Settings` / env; fail closed on weak JWT in non-dev | KEEP |
| `app/db.py` | Three engines, tenant files, `init_databases`, `get_*_db` | KEEP isolation; schema via `schema_patches` |
| `app/schema_patches.py` | Idempotent ALTER lists after create_all | KEEP |
| `app/enums.py` | Domain enums | KEEP |
| `app/__init__.py` | Package docstring | KEEP |
| `app/core/security.py` | JWT, `CurrentUser`, `require_parent`, `require_admin`, `require_staging_upload` | KEEP |
| `app/core/__init__.py` | Empty package | KEEP |
| `app/evidence/__init__.py` | `store_capture`, path resolve | KEEP |

---

## Models

| Path | Tables / types | Disposition |
|---|---|---|
| `app/models/mixins.py` | `TimestampMixin` | KEEP |
| `app/models/admin.py` | `User`, `InviteKey`, `CaptureToken` | KEEP |
| `app/models/curriculum.py` | Catalog books + tenant library + plans | KEEP |
| `app/models/education.py` | `Assignment*`, `Attendance`, taxonomy | KEEP assignments/attendance; DEFER taxonomy |
| `app/models/homework.py` | Help sessions, notifications | KEEP |
| `app/models/evidence_staging.py` | Staging inbox | KEEP |
| `app/models/__init__.py` | Household, Student, SchoolYear, Enrollment, Exception, **Jurisdiction**, **CompliancePacket** | KEEP household/student/year/enrollment/exception; leftover `scheduled_work` / `evidence_captures` models removed (empty tables may remain on disk); **DEFER** jurisdiction/packets |

---

## Routers (HTTP)

Mounted under `/api` from `app/main.py`.

| Path | Prefix | Live SPA? | Disposition |
|---|---|---|---|
| `health.py` | `/health` | Yes | KEEP |
| `auth.py` | `/auth` | Yes | KEEP; capture token live; COMPLETE token-on-register |
| `admin.py` | `/admin` | Yes (admins) | KEEP |
| `household.py` | `/household` | Yes | KEEP; PATCH name from wizard |
| `students.py` | `/students` | Yes | KEEP |
| `school_years.py` | `/school-years` | Yes | KEEP; canonical named year |
| `enrollments.py` | `/enrollments` | Yes (settings) | KEEP; auto-create on schedule |
| `settings.py` | `/settings`, `/calendar/exceptions` | Yes | KEEP; CONSOLIDATE later with `exceptions.py` |
| `exceptions.py` | `/exceptions` | Yes | KEEP; CONSOLIDATE later |
| `catalog.py` | `/catalog` | lookup-isbn yes; from-isbn no | KEEP lookup; KEEP from-isbn as API-only |
| `books.py` | `/books` | No (tests yes) | KEEP as API-only; CONSOLIDATE later |
| `curricula.py` | `/curricula` | Yes; import API unused | KEEP; import is API-only |
| `curriculum_plans.py` | `/curriculum` | Yes | KEEP |
| `assignments.py` | mixed paths | Yes | KEEP |
| `calendar.py` | `/calendar` | Yes (all students) | KEEP |
| `attendance.py` | `/attendance` | Yes | KEEP |
| `pacing.py` | `/pacing` | Yes | KEEP |
| `recalibration.py` | `/recalibrate` | Yes | KEEP |
| `evidence.py` | `/evidence` | Yes + extension | KEEP; files GET authenticated; staging POST accepts capture credential |
| `dashboard.py` | `/dashboard` | Yes | KEEP |
| `reports.py` | `/reports` | Yes | KEEP |
| `portfolios.py` | `/portfolios` | Yes | KEEP |
| `homework_help.py` | `/homework-help` | Yes (child) | KEEP |
| `notifications.py` | `/notifications` | Yes | KEEP |

---

## Services

| Path | Role | Disposition |
|---|---|---|
| `households.py` | Default household + rename | KEEP |
| `enrollments.py` | Ensure enrollment on schedule | KEEP |
| `child_accounts.py` | PIN, switch, tokens | KEEP |
| `capture_tokens.py` | Issue / revoke capture JWTs | KEEP |
| `assignments.py` | Query, windows, catalog hydrate | KEEP |
| `pacing.py` | Engine + commit | KEEP |
| `ai_generator.py` | Page chunks (not LLM) | KEEP; rename when touched |
| `catalog.py` | Library + ISBN projection | KEEP |
| `resolver.py` | ISBN → edition | KEEP |
| `providers/` | Open Library, Google Books | KEEP |
| `curriculum_import.py` | JSON/CSV tree import | KEEP as API; no SPA |
| `curriculum_structure.py` | Tree/resources load | KEEP |
| `curriculum_plan_import.py` | CSV plans | KEEP |
| `curriculum_plan_apply.py` | Plan → assignments | KEEP |
| `ai_curriculum_worker.py` | PDF background parse | KEEP (own tenant session) |
| `pdf_parser.py` | PyMuPDF + OCR | KEEP |
| `school_year.py` | Bounds, holidays, colors | KEEP; dates from SchoolYear |
| `portfolio.py` | Report + PDF + mail | KEEP |
| `weekly_manifest.py` | Checklist PDF | KEEP |
| `recalibration.py` | Shift leftover work | KEEP |
| `homework_help.py` | Tutor + lock | KEEP |
| `notifications.py` | In-app rows | KEEP |
| `spark.py` | Short Ollama question | KEEP |
| `legacy_tables.py` | Clear leftover `scheduled_work` / `evidence_captures` rows on delete | KEEP; does not DROP tables |
| `compliance/__init__.py` | Stub | DEFER / do not call |
| `parsing/__init__.py` | Stub | DEFER / do not call |

---

## Schemas and templates

| Path | Role | Disposition |
|---|---|---|
| `app/schemas/*.py` | Request/response | KEEP |
| `app/templates/portfolio*.html`, `portfolio.css` | Evaluator PDF | KEEP |
| `app/templates/weekly_manifest.html` | Printable week | KEEP |
| `app/utils/isbn.py` | ISBN normalize | KEEP |

---

## Frontend map (`static/js/app.js`)

There is no component tree. Features are functions + `data-action` + hash routes.

| Route / UI | Functions (names) | APIs |
|---|---|---|
| Auth | login, register, demo, student PIN, switch | `/auth/*` |
| `#/dashboard` | `renderDashboard`, `loadDashboardStats` | `/dashboard/stats` |
| `#/assignments` | `renderAssignments`, `loadCalendar` | assignments or `/calendar`, attendance, exceptions |
| `#/evidence` | `renderEvidence` | staging, link, calendar drop |
| `#/students` | `renderStudents` | assignments, courses, spark, PATCH status |
| `#/curricula` | `renderCurricula`, lesson builder, apply plan | `/curricula`, `/curriculum/*`, lookup-isbn |
| `#/portfolios` | `renderPortfolios` | preview, email |
| `#/settings/*` | students, exceptions, years, enrollments, admin, household name | matching REST + PATCH `/household` |
| `#/my-work` | `renderMyWork`, homework help | assignments GET, `/homework-help/*` |
| Modals | pacing, wizard (household/year/student), school-year grid, recalibrate | household, pacing, school-years, settings, recalibrate |

`api()` is the only HTTP helper besides weekly-manifest `fetch`.

---

## Extension map

| Path | Role | Disposition |
|---|---|---|
| `extension/manifest.json` | MV3, `activeTab`, `storage`, `scripting` | KEEP |
| `extension/background.js` | Capture + upload | KEEP |
| `extension/options.html` / `options.js` / `options.css` | Server URL + token | KEEP |
| `extension/icons/` | Toolbar + options PNGs | KEEP |

---

## Tests map

| Module | What it protects | Gap vs target |
|---|---|---|
| `conftest.py` | In-memory unified DB | No real tenant files |
| `test_auth.py`, `test_kid_auth.py`, `test_config.py`, `test_capture_token.py`, `test_child_assignment_status.py` | JWT, PIN, demo, capture credential, child complete | KEEP |
| `test_students_api.py` | CRUD | KEEP |
| `test_assignments_api.py` | Calendar, shared group | KEEP |
| `test_pacing.py` | Preview/commit math | KEEP |
| `test_curriculum_plans.py`, `test_curriculum_pdf_import.py` | Plans + worker session isolation | KEEP |
| `test_catalog_api.py`, `test_books_api.py`, `test_resolver.py`, `test_isbn.py`, `test_providers.py`, `test_metadata.py` | ISBN | CONSOLIDATE books vs catalog later |
| `test_evidence_staging_api.py`, `test_evidence_files_api.py` | Inbox + authenticated file GET | KEEP |
| `test_portfolios_api.py` | Reports | KEEP |
| `test_attendance_api.py` | Attendance | KEEP |
| `test_dashboard_api.py` | Stats | KEEP |
| `test_school_year_settings.py` | Year + holidays | KEEP |
| `test_school_years.py` | Named year CRUD + operational-year migrate | KEEP |
| `test_enrollments.py` | Auto-enroll on commit/apply | KEEP |
| `test_recalibration.py` | Shift | KEEP |
| `test_homework_help.py` | Tutor | Thin — COMPLETE tests |
| `test_spark.py` | Spark | KEEP |
| `test_weekly_manifest.py` | PDF | KEEP |
| `test_education.py` | Taxonomy models | DEFER product; tests document unused model |
| `test_shell.py` | `/`, `/sw.js`, cache lockstep, logo, extension icons | KEEP |
| `test_schema.py` | Fresh/upgrade SQLite files; Alembic refused; leftover tables not mapped and not dropped | KEEP |
| `test_legacy_tables.py` | Orphan-row SQL cleanup | KEEP |
| `test_curricula_api.py`, `test_curriculum_import.py` | Library import | KEEP |

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
- Leftover `scheduled_work` / `evidence_captures` tables on disk (clear rows on delete; do not DROP)
- `POST /catalog/from-isbn` and `/books/*` unless you are consolidating APIs
- Taxonomy CRUD (does not exist)
- Alembic `upgrade()` as a deploy step (it does not migrate)

---

## Legacy cleanup classification

Do not delete something merely because the SPA does not call it.

| Candidate | Class | Why |
|---|---|---|
| `ScheduledWork` / `EvidenceCapture` ORM models, `ScheduledWorkRead`, `CurriculumUnitRead`, `TenantCurriculum`, `ScheduleGrain`, `WorkStatus` | SAFE TO REMOVE | No write path. Tree API uses `CurriculumUnitNode`. Available `data/` files had COUNT=0. |
| Orphan SQLite tables `scheduled_work` / `evidence_captures` | DEPRECATE | Empty here; `create_all` does not drop them. DROP only after each operator COUNT=0. |
| Alembic revisions 0001–0012 | KEEP | Historical archive. Replay is refused and unsafe. |
| `POST /catalog/from-isbn`, `/books/*`, `POST /curricula/import` | KEEP | SPA unused; tests and API clients call them. |
| Taxonomy models and `assignments.subject_taxonomy_id` | KEEP | Pacing, assignments, weekly manifest, and tests use them. No CRUD UI. |
| `Jurisdiction` / `CompliancePacket` / `compliance/` / `parsing/` | KEEP (DEFER) | Empty stubs until a state form exists. Do not call. |
| `/exceptions` and `/calendar/exceptions` | MIGRATE FIRST | SPA uses both prefixes on the same table. |
| `ai_generator.py` module | KEEP | Arithmetic is the real generator. Comments corrected; rename later. |
| Root `Curiculy Logo.png` | KEEP | Source asset; served copy is `static/curiculy-logo.png`. |
