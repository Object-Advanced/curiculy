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
| `sw.js` | PWA + outbox | KEEP; REFACTOR cache URLs |
| `extension/` | Tab capture | KEEP; REFACTOR token; restore icons |
| `alembic/` | Historical DDL | CONSOLIDATE with real schema process |
| `tests/` | Pytest | KEEP; REFACTOR isolation coverage |
| `Dockerfile` | Image | KEEP |
| `docker-compose.yml` | Run | KEEP; secrets via `.env` |
| `entrypoint.sh` | Schema + uvicorn | KEEP |
| `requirements.txt` | Runtime deps | KEEP |
| `requirements-dev.txt` | Pytest | KEEP |
| `pytest.ini` | Pytest config | KEEP |
| `alembic.ini` | Alembic (misleading url) | CONSOLIDATE |
| `docs/` | Architecture docs | KEEP |
| `.venv/`, `.pytest_cache/`, `data/` | Generated / runtime | Ignore as product source |
| `.gitignore` | Ignores `data/`, `.env` | KEEP |

Missing from tree but referenced: `static/curiculy-logo.png`, `extension/icons/*`.

---

## Backend entry and config

| Path | Exports / role | Disposition |
|---|---|---|
| `app/main.py` | `create_app()`, router mount, `/`, `/sw.js`, `/static`, `/evidence` | KEEP; REFACTOR unauthenticated `/evidence` |
| `app/config.py` | `Settings` / env | KEEP; REFACTOR default JWT secret |
| `app/db.py` | Three engines, tenant files, `init_databases`, `get_*_db` | KEEP isolation; REFACTOR schema patches |
| `app/enums.py` | Domain enums | KEEP |
| `app/__init__.py` | Package docstring | KEEP |
| `app/core/security.py` | JWT, `CurrentUser`, `require_parent`, `require_admin` | KEEP; REFACTOR scopes |
| `app/core/__init__.py` | Empty package | KEEP |
| `app/evidence/__init__.py` | `store_capture` | KEEP |

---

## Models

| Path | Tables / types | Disposition |
|---|---|---|
| `app/models/mixins.py` | `TimestampMixin` | KEEP |
| `app/models/admin.py` | `User`, `InviteKey` | KEEP |
| `app/models/curriculum.py` | Catalog books + tenant library + plans | KEEP |
| `app/models/education.py` | `Assignment*`, `Attendance`, taxonomy | KEEP assignments/attendance; DEFER taxonomy |
| `app/models/homework.py` | Help sessions, notifications | KEEP |
| `app/models/evidence_staging.py` | Staging inbox | KEEP |
| `app/models/__init__.py` | Household, Student, SchoolYear, Enrollment, Exception, **ScheduledWork**, **EvidenceCapture**, **Jurisdiction**, **CompliancePacket** | KEEP household/student/year/enrollment/exception; **REMOVE** scheduled_work + evidence_captures after data check; **DEFER** jurisdiction/packets |

---

## Routers (HTTP)

Mounted under `/api` from `app/main.py`.

| Path | Prefix | Live SPA? | Disposition |
|---|---|---|---|
| `health.py` | `/health` | Yes | KEEP |
| `auth.py` | `/auth` | Yes | KEEP; COMPLETE token-on-register |
| `admin.py` | `/admin` | Yes (admins) | KEEP |
| `household.py` | `/household` | Yes | KEEP |
| `students.py` | `/students` | Yes | KEEP; COMPLETE child complete-work lives on assignments |
| `school_years.py` | `/school-years` | Yes | CONSOLIDATE with settings year |
| `enrollments.py` | `/enrollments` | Yes (settings) | COMPLETE auto-create from schedule |
| `settings.py` | `/settings`, `/calendar/exceptions` | Yes | CONSOLIDATE exceptions with `exceptions.py` |
| `exceptions.py` | `/exceptions` | Yes | CONSOLIDATE |
| `catalog.py` | `/catalog` | lookup-isbn yes; from-isbn no | KEEP lookup; CONSOLIDATE from-isbn |
| `books.py` | `/books` | No | CONSOLIDATE into catalog |
| `curricula.py` | `/curricula` | Yes; import API unused | KEEP; import is API-only |
| `curriculum_plans.py` | `/curriculum` | Yes | KEEP |
| `assignments.py` | mixed paths | Yes | KEEP; COMPLETE child PATCH status |
| `calendar.py` | `/calendar` | Yes (all students) | KEEP |
| `attendance.py` | `/attendance` | Yes | KEEP |
| `pacing.py` | `/pacing` | Yes | KEEP |
| `recalibration.py` | `/recalibrate` | Yes | KEEP |
| `evidence.py` | `/evidence` | Yes + extension | KEEP; REFACTOR file serving |
| `dashboard.py` | `/dashboard` | Yes | KEEP |
| `reports.py` | `/reports` | Yes | KEEP |
| `portfolios.py` | `/portfolios` | Yes | KEEP |
| `homework_help.py` | `/homework-help` | Yes (child) | KEEP |
| `notifications.py` | `/notifications` | Yes | KEEP |

---

## Services

| Path | Role | Disposition |
|---|---|---|
| `households.py` | Default household | KEEP |
| `child_accounts.py` | PIN, switch, tokens | KEEP |
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
| `ai_curriculum_worker.py` | PDF background parse | KEEP; REFACTOR session use |
| `pdf_parser.py` | PyMuPDF + OCR | KEEP |
| `school_year.py` | Bounds, holidays, colors | CONSOLIDATE dates onto SchoolYear |
| `portfolio.py` | Report + PDF + mail | KEEP |
| `weekly_manifest.py` | Checklist PDF | KEEP |
| `recalibration.py` | Shift leftover work | KEEP |
| `homework_help.py` | Tutor + lock | KEEP |
| `notifications.py` | In-app rows | KEEP |
| `spark.py` | Short Ollama question | KEEP |
| `compliance/__init__.py` | Stub | DEFER / do not call |
| `parsing/__init__.py` | Stub | DEFER / do not call |

---

## Schemas and templates

| Path | Role | Disposition |
|---|---|---|
| `app/schemas/*.py` | Request/response | KEEP |
| `app/schemas/core.py` `ScheduledWorkRead` | Leftover | REMOVE with scheduled_work |
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
| `#/settings/*` | students, exceptions, years, enrollments, admin | matching REST |
| `#/my-work` | `renderMyWork`, homework help | assignments GET, `/homework-help/*` |
| Modals | pacing, wizard, school-year grid, recalibrate | pacing, school-years, settings, recalibrate |

`api()` is the only HTTP helper besides weekly-manifest `fetch`.

---

## Extension map

| Path | Role | Disposition |
|---|---|---|
| `extension/manifest.json` | MV3, `activeTab`, `storage`, `scripting` | KEEP |
| `extension/background.js` | Capture + upload | KEEP; REFACTOR auth header |
| `extension/options.html` / `options.js` / `options.css` | Server URL + token | KEEP |
| `extension/icons/` | Referenced, missing | COMPLETE assets |

---

## Tests map

| Module | What it protects | Gap vs target |
|---|---|---|
| `conftest.py` | In-memory unified DB | No real tenant files |
| `test_auth.py`, `test_kid_auth.py` | JWT, PIN, demo | KEEP |
| `test_students_api.py` | CRUD | KEEP |
| `test_assignments_api.py` | Calendar, shared group | KEEP |
| `test_pacing.py` | Preview/commit math | KEEP |
| `test_curriculum_plans.py`, `test_curriculum_pdf_import.py` | Plans | KEEP |
| `test_catalog_api.py`, `test_books_api.py`, `test_resolver.py`, `test_isbn.py`, `test_providers.py`, `test_metadata.py` | ISBN | CONSOLIDATE books vs catalog later |
| `test_evidence_staging_api.py` | Inbox | Add file-auth when implemented |
| `test_portfolios_api.py` | Reports | KEEP |
| `test_attendance_api.py` | Attendance | KEEP |
| `test_dashboard_api.py` | Stats | KEEP |
| `test_school_year_settings.py` | Year + holidays | KEEP |
| `test_recalibration.py` | Shift | KEEP |
| `test_homework_help.py` | Tutor | Thin — COMPLETE tests |
| `test_spark.py` | Spark | KEEP |
| `test_weekly_manifest.py` | PDF | KEEP |
| `test_education.py` | Taxonomy models | DEFER product; tests document unused model |
| `test_shell.py` | `/sw.js` | KEEP |
| `test_curricula_api.py`, `test_curriculum_import.py` | Library import | KEEP |

---

## Alembic versions (historical)

These files describe an older single-DB shape. They are **not** the runtime schema.

| Revision | Topic | vs live models |
|---|---|---|
| `0001_initial` | Household, old curricula.isbn, scheduled_work | Superseded |
| `0002_curriculum_catalog` | Catalog tables | Partially reflected in models |
| `0003_education_core` | Assignments | Live |
| `0004`–`0012` | Shared group, color, attendance, plans, settings, colors, staging, status, time_slot | Live via create_all/ALTER |

Treat as archaeology until Alembic actually runs.

---

## Central files (change with care)

Many features import these. Prefer additive changes.

1. `app/db.py` — tenant routing and schema patches
2. `app/core/security.py` — every request
3. `app/models/education.py` — `Assignment`
4. `app/services/assignments.py` — calendar reads
5. `app/services/pacing.py` — writes many rows
6. `static/js/app.js` — all UX
7. `app/main.py` — mounts and router list

---

## Safe to ignore when implementing product features

- `app/services/compliance/`
- `app/services/parsing/`
- `ScheduledWork` / `EvidenceCapture` write paths (only delete-cleanup today)
- `POST /catalog/from-isbn` and `/books/*` unless you are consolidating APIs
- Taxonomy CRUD (does not exist)
- Alembic `upgrade()` as a deploy step (it does not migrate)
