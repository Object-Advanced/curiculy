# Curiculy Architecture

This document describes Curiculy’s architecture **as it exists**. It is based on the running source tree. The 2026-09-01 reconciliation collected 821 tests; after later consolidations the suite is **892 passed**, 0 failed, 0 skipped (`docker compose --profile dev run --rm tests pytest`). The architecture-hardening / cleanup phase is **closed**.

Curiculy is a homeschool planner for one family (a household) with multiple children. Parents schedule curricula, mark work, keep evidence, and produce printable records. Children sign in with a PIN and do today’s work. The product must work on a kitchen-table laptop, including when the network is flaky, and must remain simple enough for one operator to run.

Do not treat this as a rewrite plan. The running system is the source of truth. Changes should fold duplicate paths together and finish incomplete ones, not introduce a new stack.

---

## Product constraints that the architecture must preserve

These are requirements, not optional style.

| Constraint | Why it matters | Architectural consequence |
|---|---|---|
| One family, several children | Siblings share some lessons and not others | Per-student assignments plus optional `shared_group_uuid` |
| Two curriculum objects | Textbooks are paged; vendor guides are week/day grids | **Book auto-schedule** (pages) and **pacing guides** (week/day). Guide capture: CSV, PDF+Ollama, paper sheet (OpenCV + Ollama vision), or manual builder. Both objects land on `assignments` |
| School-year calendar | Homeschool years are custom, not district calendars | One named `SchoolYear` with bounds; class weekdays and exception colors on settings |
| Exceptions and holidays | Life happens; sick days can be one child | Household-wide and student-specific exceptions on the same table |
| Assignment generation | Parents will not type 180 lesson rows | Pacing commit and plan-apply write `assignments` |
| Evidence / work samples | Evaluators want photos and PDFs | Staging inbox → assignment attachment; files on a volume; authenticated GET |
| Portfolios | State evaluations and reading lists | Date-window reports over assignments, attendance, books, evidence |
| Child accounts | Kids should not use the parent password | PIN users scoped to one student; child may PATCH own assignment status |
| Offline | Rural / travel / kitchen wifi | Service worker shell + outbox for safe writes |
| Barcode / ISBN | Scan a book, fill the form | Shared catalog cache, household library separate |
| AI-assisted parsing | PDFs and handwritten week sheets are common | Background Ollama into `curriculum_plans`, not into a second calendar. Scheduling does not require Ollama |
| Printable records | Ink-saver weekly list + evaluator PDF | WeasyPrint from the same assignment data |
| Eventual public SaaS | Invite-gated today; public later | Tenant isolation stays; do not require Postgres until scale demands it |

---

## Classification legend

| Label | Meaning |
|---|---|
| **KEEP** | Core. Do not replace. Improve in place if needed. |
| **CONSOLIDATE** | Multiple implementations of one idea. Fold into one. |
| **REFACTOR** | Right concept, messy or unsafe leftover. |
| **REMOVE** | Dead or superseded. Delete after confirming no data depends on it. |
| **COMPLETE** | Partially built and worth finishing because parents will use it. |
| **DEFER** | Valid later. Do not spend cycles now. |

---

## Domain classifications

### Authentication — KEEP (small leftover: `DEV_MODE`)

**CURRENT:** JWT (HS256) in `localStorage`. Parent email/password. Invite-key registration. `POST /api/auth/register` returns `{access_token, token_type}` (201); the SPA stores it and enters the app. Child PIN accounts (`child.{tenant}.{id}@kid.local`). Demo in-memory tenant. `DEV_MODE` bypass. Household user switching. Chrome extension stores a long-lived **capture credential** (`scope=evidence:write`) issued from Settings → Students. Non-dev startup requires `JWT_SECRET` from the environment and refuses known-weak placeholders (missing, whitespace, known list, or shorter than 32 characters).

**REMAINING:** `DEV_MODE` is useful locally and dangerous if left on. JWT strength is length plus a denylist, not an entropy policy.

**DEPENDENCIES:** Every parent and child route; extension; tenant session selection.

**Capture credential lifecycle**

1. A parent (not demo, not a child) opens Settings → Students and generates a token (`POST /api/auth/capture-token`). The secret is shown once in the SPA. Status (`GET`) never returns the secret.
2. The JWT identifies the household (`tenant_uuid`), uses `sub=capture.{tenant}`, `role=evidence`, `scope=evidence:write`, and a `jti`. Lifetime defaults to 365 days (`CAPTURE_TOKEN_EXPIRE_DAYS`).
3. A `capture_tokens` row on `admin.db` stores that `jti`. Minting a new token revokes earlier rows for the tenant. Revoke is `DELETE /api/auth/capture-token`.
4. The extension pastes the token as “device token” and sends it as `Authorization: Bearer` on `POST /api/evidence/staging` only.
5. The server accepts that credential for staging writes after checking the JWT and that the row is present, unrevoked, and unexpired. `get_current_user` rejects it, so `/auth/me`, household, calendar, admin, listing/linking staging, and evidence file reads all fail.
6. Tenant sessions are split: `get_tenant_db` calls `get_current_user` (parent, child, demo) and refuses capture JWTs. Staging uses `get_staging_tenant_db`, which calls `require_staging_upload`. Opening a household file is not itself authorization. A route that depends only on `get_tenant_db` cannot be mutated by the extension.
7. Parent login JWTs can still stage (API). They must not be pasted into the extension.

**TESTS:** `tests/test_capture_token.py` (physical `auth_client`). Capture may `POST /evidence/staging`. It is 403 on `/auth/me`, household, students, spark, curricula, assignments, homework-help, portfolios, notifications, calendar, dashboard, staging list/link, evidence file GET, capture-token mint, switchable-users, school-years, and enrollments. Child status PATCH still works with a child JWT. Forged/expired/revoked tokens and JWT claim swaps are 401.

---

### Multi-tenancy — KEEP

**CURRENT:** One `admin.db` (users, invites, capture tokens), one shared `catalog.db` (ISBN dictionary), one SQLite file per household (`tenant_{uuid}.db`). Demo uses process-memory SQLite keyed by JWT `jti`. Dev mode uses a shared `tenant.db`. JWT `tenant_uuid` selects the file. Planner tables do not carry a `tenant_id` column; `evidence_staging.tenant_id` stores the JWT UUID as a path prefix inside the household file.

**REMAINING:** Schema updates must touch every `tenant_*.db`. A model field without a matching patch in `app/schema_patches.py` is created on new files and missing on old ones. SQLite-per-tenant will not be the forever SaaS answer at thousands of concurrent writers — it is the right isolation model **now**.

Do not introduce `tenant_id` columns on every table until a single database is actually required.

**DEPENDENCIES:** Auth (`tenant_uuid` in JWT), evidence paths `{tenant_uuid}/…`, catalog vs tenant FKs.

**TESTS:** `tests/test_auth.py` provisions `tenant_{uuid}.db` and routes a real JWT without overriding `get_tenant_db` (`test_login_routes_to_tenant_file`, `test_register_with_invite_provisions_tenant`, `test_physical_tenant_files_persist_and_stay_isolated`). The default `conftest.py` `client` stays in-memory on purpose.

---

### Students — KEEP

**CURRENT:** Tenant `students` with name, grade, notes, color. Parent CRUD. PIN create/clear. “Kids” dashboard is today’s checklist plus spark question. Child login is a separate `users` row in `admin.db`. A child JWT may `PATCH /assignments/{id}/status` on their own assignments (404 for a sibling’s row). Children do not sync `shared_group_uuid` siblings. PUT/delete/grade/evidence stay parent-only.

**REMAINING:** Color palette is duplicated in JS and Python. Spark is parent-only on `/students/{id}/spark` (`require_parent`), which is fine.

**DEPENDENCIES:** Assignments, attendance, enrollments, evidence, homework help, calendar, portfolios.

---

### Households — KEEP (schema leftover)

**CURRENT:** `Household` row auto-created as “Default household.” The first-run wizard PATCHes `/household` so the family names it. Settings can rename it and pick a sidebar icon (letter skips a leading “The”, or a school emoji). `get_default_household` is first-by-id. Product rule is **one household per tenant file**. `jurisdiction_id` is unused.

**REMAINING:** The schema still allows many households in one file. Ignore/drop `jurisdiction_id` when a state pack exists.

**DEPENDENCIES:** Almost every tenant write uses the default household.

---

### School years — KEEP (canonical dates on SchoolYear)

**CURRENT:** Named `SchoolYear` rows are the operational year (latest by start date, then id). `GET /settings/school-year` reads dates from that year and weekdays from `HouseholdSettings`. The year modal (`PUT /settings/school-year`) and wizard (`POST /school-years`) write the same `SchoolYear`. `PATCH /school-years/{id}` updates a named year. `HouseholdSettings` stores class weekdays and exception colors only.

Existing `tenant_*.db` files that still have leftover `household_settings.start_date` / `end_date` columns are upgraded on boot: if that household has no `school_years` row, one is created from those dates; an existing named year is not overwritten. The leftover columns are then dropped. Fresh files never receive those columns.

**REMAINING:** None for the date source. Do not add year bounds back onto settings.

**DEPENDENCIES:** Pacing, plan-apply, exceptions grid, enrollments, portfolios, wizard.

**TESTS:** `tests/test_school_years.py`, `tests/test_school_year_settings.py`, `tests/test_schema.py`. Settings GET/PUT read and write `SchoolYear` dates and `HouseholdSettings` weekdays. Leftover tenant files with settings date columns backfill a named year only when none exists, then drop the columns. Divergent leftover dates do not overwrite an existing year. Production Python (outside `schema_patches.py`) does not pair `household_settings` with year dates.

---

### Enrollments — KEEP (auto-create on schedule)

**CURRENT:** Unique on student + curriculum + school year. Settings can still POST/list (409 on duplicate). Pacing commit and plan-apply insert or reuse the row in the **same tenant transaction** as the assignments if it is missing. Unique violations are recovered with a savepoint. Preview does not enroll. Direct curriculum create does not enroll. The operational (latest) `SchoolYear` is the year used at schedule time. Plans have no `curriculum_id`; apply reuses a library row with the same title or creates one from the plan title, and stamps that id onto each new assignment.

Historical work can be reconciled by `scripts/backfill_enrollments.py` when an assignment proves the trio: stored `curriculum_id`, or a live resource/unit whose edition still points at `curricula`, and `scheduled_date` in exactly one named year. Title-only plan-apply rows (no stored id, no resource/unit) are still refused. Default is dry-run; `--apply` writes. It is not part of boot.

**REMAINING:** Title-only historical plan assignments stay unlinked by design. Do not infer a curriculum from titles.

**DEPENDENCIES:** Portfolios (reading list), settings UI, curriculum delete (already cleans enrollments).

---

### Curricula — KEEP

**CURRENT:** Tenant `curricula` is the household library (Saxon Math 3, etc.). Editions, resources, units, page mappings. Created by the form (`POST /curricula` with optional `sku` after `POST /catalog/lookup-isbn`), by API `POST /catalog/from-isbn`, or by `POST /curricula/import`. `/books/*` does not create library rows.

**REMAINING:** `POST /curricula/import` (JSON/CSV tree) is unused by the SPA. Catalog `POST /from-isbn` is unused by the SPA; the form uses lookup + `POST /curricula`. Keep those as API-only until a UI exists or they are retired. Do not merge library rows into catalog.db.

**DEPENDENCIES:** Auto-schedule, enrollments, catalog ISBN, unschedule/delete.

---

### Curriculum resources — KEEP

**CURRENT:** Components of an edition (student text, workbook, answer key) optionally pointing at `book_editions.id` in catalog.db without a cross-DB FK.

**REMAINING:** Orphan `book_edition_id` if catalog rows are deleted — do not delete catalog editions that tenant resources reference.

**DEPENDENCIES:** Pacing, page mappings, classifications (deferred).

---

### Curriculum plans — KEEP

**CURRENT:** `curriculum_plans` + `curriculum_lessons` (week, day, title, time slot, category). Capture methods:

| Method | HTTP | What runs |
|---|---|---|
| Manual builder | plan CRUD under `/api/curriculum` | Parent edits lessons |
| CSV | `POST /api/curriculum/import-csv` | Inline insert |
| PDF | `POST /api/curriculum/import-pdf` (202) | Background `process_pdf_curriculum_background`: extract text, Ollama → lessons. Worker opens its own tenant session. Terminal `ready` / `failed` commits one in-app parent notification in that same session |
| Paper sheet | `GET /api/curriculum/paper-template` then `POST /api/curriculum/import-paper` (202) | Request: OpenCV ArUco flatten + QR (`parse_paper_upload`). Background: `extract_handwriting_from_slices` via Ollama vision (`llama3.2-vision` over `httpx`), own tenant session. Same terminal-status notification as PDF |

Apply (`POST /api/curriculum/plans/{id}/apply`) always writes `assignments` (+ enrollment). Apply does not call Ollama.

Runtime deps for paper: `opencv-python-headless`, `numpy`, `qrcode` (`requirements.txt`). Template HTML: `app/templates/paper_template.html`.

**REMAINING:** Do not generate `curriculum_units` from plans unless a future “link this guide to this book” feature needs it. Paper vision must keep a **vision** model (`llama3.2-vision` today); pointing it at `OLLAMA_MODEL` (default `llama3.1`) would be wrong.

**DEPENDENCIES:** Calendar, exceptions (skipped days), students, optional Ollama.

---

### Assignments — KEEP

**CURRENT:** The calendar event: student, title, date, status, notes, optional tenant `curriculum_id` / resource / unit ids, grade, evidence, `shared_group_uuid`. New pacing commits and plan applies stamp `curriculum_id` (nullable integer, no FK; same pattern as Enrollment). Historical rows stay NULL. `PATCH /assignments/{id}/status` is allowed for a parent (syncs a shared group) or a child on their own row (does not sync siblings).

`ScheduledWork` / `EvidenceCapture` ORM models, unused read schemas, `ScheduleGrain`, and `WorkStatus` are **gone**. The live calendar is `assignments` only. Physical leftover SQLite tables `scheduled_work` / `evidence_captures` may still exist in older `tenant_*.db` files on other disks. `create_all` and boot schema patches do not drop those tables. Student and curriculum delete still clear leftover **rows** via `app/services/legacy_tables.py` (one implementation of each helper); that path never DROPs the tables.

Operator retirement is `scripts/drop_legacy_tables.py` (helper `app/services/legacy_table_drop.py`). Default is dry-run. `--apply` DROPs a leftover table only when `COUNT(*) = 0`. It never DELETEs rows to empty a table. Non-empty tables are left untouched and reported as refused. Unopenable files are skipped (nothing in that file is dropped). Repeat runs are safe. Backup `tenant_*.db` before `--apply`; restore is copy-the-file-back. This host’s `./data/tenant_*.db` empty leftover tables were DROPped.

**REMAINING:** Recalibrate and parent shared-group sync remain high blast radius. Non-empty leftover tables on other family disks stay until a separate data decision.

**DEPENDENCIES:** Calendar, dashboard, evidence, homework help, portfolios, weekly PDF, recalibrate, attendance overlay.

---

### Pacing — KEEP

**CURRENT:** Preview is pure arithmetic (`SyllabusGenerator` in `app/services/ai_generator.py` — not an LLM). Commit writes units, mappings, assignments, and enrollments. Deadline vs pages-per-day. Skips exceptions and non-class weekdays. Comments say not to wire Ollama into commit.

**REMAINING:** Module filename `ai_generator.py` is misleading. Optional later: LLM titles from a TOC **behind the same preview contract**, still commitable with Ollama off. Tenant commit then catalog `page_count` commit are two engines (not one transaction).

**DEPENDENCIES:** Curricula, resources, school year weekdays, exceptions, assignments.

---

### Calendar — KEEP

**CURRENT:** Per-student window (`/students/{id}/assignments`) and household “All Students” (`GET /api/calendar`, rows with `shared_group_uuid` only). Day/week/month. Attendance and exceptions painted in the SPA. All Students header copy: shared lessons only; private lessons appear on individual student calendars.

**REMAINING:** Changing `/calendar` to include private lessons would clutter the family board. That is a product decision, not a bug.

**DEPENDENCIES:** Assignments, attendance, exceptions, students.

---

### Attendance — KEEP

**CURRENT:** One row per student per day. Upsert from calendar cells. Present / Absent / Sick / Vacation.

**REMAINING:** Auto-filling attendance from vacation exceptions is a later convenience, not a merge of tables. Exceptions mean “not a school day / don’t schedule.” Attendance means “what we recorded for the log.”

**DEPENDENCIES:** Portfolios, calendar UI.

---

### Exceptions — KEEP

**CURRENT:** One table `calendar_exceptions`. One HTTP prefix `/api/exceptions` (`app/routers/exceptions.py`, parent-only):

- `GET /api/exceptions` — list full records (settings list and calendar paint)
- `POST /api/exceptions` — create a titled range
- `GET /api/exceptions/dates` — household no-school date set (year grid; student-specific rows excluded)
- `POST /api/exceptions/toggle` — add or remove one household day
- `POST /api/exceptions/import-holidays` — public holidays into that date set

Exception colors stay on `/api/settings/exception-colors`. There is no `PATCH`/`DELETE` for a titled row; the year-grid toggle can split a range. `/api/calendar` is the All Students assignment board and does not serve exceptions.

Student-specific rows are excluded from the household “no-school” set used by pacing (correct).

**REMAINING:** None for HTTP prefixes. Optional later: update/delete of titled ranges if Settings needs an edit UI.

**DEPENDENCIES:** Pacing, plan-apply, school-year grid, calendar paint.

---

### Evidence — KEEP (staging + authenticated files)

**CURRENT:** Staging (`evidence_staging` + Chrome upload) → link to `assignment_evidence`. Direct upload on an assignment. Files under `{tenant_uuid}/{uuid}.webp|pdf`. Files are served by authenticated `GET /api/evidence/files/{tenant}/{filename}`. The public `/evidence` StaticFiles mount is gone. Extension upload uses a capture credential, not a parent session. Children may read only files attached to their assignments. Capture credentials receive 403 on file GET. Responses use `Cache-Control: private, no-store`.

`evidence_captures` is not mapped. Physical leftover tables may remain on older tenant files until an operator dry-run / `--apply` (COUNT=0 only; never DELETE rows; not boot).

**REMAINING:** Non-empty leftover capture tables stay until a separate data decision. Capture tokens must be rotated if `JWT_SECRET` is rotated.

**DEPENDENCIES:** Portfolios (attachments), calendar paperclip, extension.

---

### Portfolios — KEEP

**CURRENT:** Report types (state log, reading list, work samples, custom). HTML preview, WeasyPrint PDF, email via background SMTP. Window from school year dates. Books from enrollments (created when work is scheduled). Empty-enrollment copy points at Settings → Enrollments.

**REMAINING:** Title-only historical plan-apply rows (no `curriculum_id`) still will not appear as books until Settings POST. Custom report is POST-only (GET `/report` rejects custom) — fine.

**DEPENDENCIES:** Assignments, attendance, enrollments, school years, evidence, mail config.

---

### Homework Help — KEEP

**CURRENT:** Child-only sessions, Ollama tutor that refuses answers, parent notifications, lock after redirects, parent unlock. Failures are logged; the path does not block scheduling.

**REMAINING:** Small test coverage (`tests/test_homework_help.py`). Prompt changes are product risk.

**DEPENDENCIES:** Assignments, students, notifications, Ollama.

---

### AI / Ollama — KEEP (optional accelerator)

**CURRENT:** Ollama is **not** on the calendar write path. `SyllabusGenerator` / `pacing.py` do not import it. Boot and `GET /api/health` do not ping Ollama. Four call sites, two HTTP stacks:

| Use | Client | Model | Timeout / sync | On failure |
|---|---|---|---|---|
| PDF → plan lessons | `ollama.AsyncClient` via `ollama_chat.py` from `ai_curriculum_worker.py` | `settings.ollama_model` then `mistral` | Async; SDK default; background | Plan `failed` on a fresh session. HTTP 202 already returned |
| Homework tutor | same helper from `homework_help.py` | Same fallback list | Async; on the child message request | Returns a canned hint; still commits the chat |
| Spark question | `httpx` POST `/api/chat` in `spark.py` | `settings.ollama_model` only | Sync; 2.5s / 0.4s connect | `source=none`; dashboard does not wait on a long generate |
| Paper handwriting | `httpx` POST `/api/chat` in `paper_vision_worker.py` | Hardcoded `llama3.2-vision` | Sync sequential; 120s; `images[]` | Plan `failed`. OpenCV slice already succeeded |

The two stacks are **intentional**. Spark cannot share the SDK’s long default timeout. Vision cannot share `OLLAMA_MODEL` (text). Vision posts `images` and must not overlap calls on a small GPU. PDF/homework share `app/services/ollama_chat.py` (`AsyncClient`, `format=` JSON schema, `OLLAMA_MODEL` then `mistral`). Spark/vision stay on `httpx`.

`OLLAMA_HOST` / `OLLAMA_MODEL` are optional. Config has no vision-model setting. Paper import geometry (OpenCV) does not need Ollama; transcription does.

**REMAINING:** Do not merge the stacks into one generic client. Do not set paper vision to `OLLAMA_MODEL`. Optional later: `OLLAMA_VISION_MODEL` (default `llama3.2-vision`).

**DEPENDENCIES:** Curriculum PDF import, paper import, homework help, spark. Not book auto-schedule.

---

### Catalog / ISBN — KEEP

**CURRENT:** Shared `catalog.db` ISBN dictionary (`works`, `book_editions`, publishers, authors). Resolver: Open Library then Google Books (`app/services/resolver.py`). Two HTTP prefixes sit on that dictionary:

- `POST /catalog/lookup-isbn` — parent-only. Same `BookResolver.resolve` as `/books/resolve`, then projects a flat `ISBNLookupRead` for the Add curriculum form. Writes a cached `BookEdition` on a miss (commit on success). SPA calls this, then `POST /curricula` with `sku`.
- `POST /catalog/from-isbn` — parent-only, API-only. Resolve with `commit=False`, then `create_curriculum_from_edition` (tenant `curricula` + `curriculum_editions` + student-text `curriculum_resources`). 404 if the identifier is not a resolvable ISBN / already-cached SKU. Does **not** create a manual SKU the way `POST /curricula` can. Tests call it (`tests/test_catalog_api.py`). SPA does not.

Household library create for the form is `POST /curricula` (`app/services/catalog.py` `create_curriculum`), not `/catalog/from-isbn`.

**REMAINING:** `from-isbn` is a one-shot API client path, not an equal UI path and not a `/books` alias. Keep it until a caller inventory outside this repo exists. Do not merge library rows into `catalog.db`.

**DEPENDENCIES:** Auto-schedule page counts (`CurriculumResource.book_edition_id` → `BookEdition.page_count`).

---

### Books — KEEP (ISBN dictionary HTTP; not the household library)

**CURRENT:** Parent-only `/books` on `catalog.db` `BookEdition` only. Does not create `Curriculum`, editions, resources, units, or assignments.

| Method | Path | Writes | Response |
|---|---|---|---|
| POST | `/books/resolve` | Cache `BookEdition` (+ work/authors/publisher) on a miss | Full `BookEditionRead` |
| GET | `/books/isbn/{isbn}` | None | Full `BookEditionRead` |
| GET | `/books/{id}` | None | Full `BookEditionRead` |

SPA, extension, and operator scripts do not call these. Tests do (`tests/test_books_api.py`). FastAPI OpenAPI documents them. Resolver fallback and cache behavior are also tested without HTTP in `tests/test_resolver.py`.

`POST /books/resolve` shares `BookResolver` with `POST /catalog/lookup-isbn` but **not** the response shape. The two GET routes have **no** `/catalog` twin.

**REMAINING:** Do not delete `/books/*` because the SPA is quiet. Do not point existing books tests at lookup-isbn (that would drop GET coverage and change the asserted body). Optional later: catalog GET twins that return the same `BookEditionRead`, then `/books/*` as aliases. That is an API project, not a domain merge.

**DEPENDENCIES:** Resolver. Pacing reads `book_id` from `GET /curricula/{id}/resources`, not from `/books/{id}`.

---

### Notifications — KEEP

**CURRENT:** In-app list for homework-help started/redirect and for PDF/paper plan `ready` / `failed`. Plan rows are written in the worker’s tenant session when status leaves `processing` (not on the 202 request). `student_id` and `assignment_id` are null. Inbox click on a plan notification opens `#/curricula` on the pacing-guides tab. Mark read.

**REMAINING:** Do not add email/push until a parent asks.

**DEPENDENCIES:** Homework help; PDF and paper curriculum workers.

---

### Offline / PWA — KEEP

**CURRENT:** `sw.js` caches shell; IndexedDB outbox replays mutating `api()` calls. Does not cache `/api` or `/evidence`. `SHELL_VERSION` is the single cache-bust token (currently `20260831-paper-import`). `index.html` and CSS query strings use that value. `SHELL_CACHE` is `curiculy-shell-${SHELL_VERSION}`. Tests fail if the strings drift.

**DEPENDENCIES:** SPA `api()`, uploads.

---

### Chrome extension — KEEP

**CURRENT:** MV3 capture → `POST /api/evidence/staging` with a capture credential (`scope=evidence:write`). Options: server URL + device token (the capture JWT). Toolbar and options icons are PNGs under `extension/icons/` (16/32/48/128 plus `logo.png`).

**REMAINING:** `host_permissions` are broad (needed for screenshots on arbitrary curriculum sites). Families still pasting an old parent JWT keep a full parent session until they generate a capture token.

**DEPENDENCIES:** Evidence staging, capture-token endpoints.

---

### Compliance — DEFER

**CURRENT:** `jurisdictions`, `compliance_packets`, `build_packet()` raises `NotImplementedError`. `create_app()` description still says “compliance foundation” (cosmetic). Portfolios already produce evaluator PDFs.

**REMAINING:** Do not build a jurisdiction rules engine until a specific state form is a paying requirement.

**DEPENDENCIES:** None in the live product.

---

### Taxonomy / classification — DEFER

**CURRENT:** Catalog `subject_taxonomies`, `reporting_categories`; tenant `curriculum_classifications`. Tests only. Assignments may store `subject_taxonomy_id`; pacing can pass it; no CRUD API.

**REMAINING:** Hierarchical taxonomy when a state report needs buckets. Until then, free-text `subject` is enough. Do not build a taxonomy admin UI.

**DEPENDENCIES:** Assignment optional FK, tests.

---

### Database architecture — KEEP (process leftover: patch discipline)

**CURRENT:** Three SQLite files. SQLAlchemy 2. Cross-DB ids without FKs. `init_databases()` on boot runs `create_all` plus the ordered patches in `app/schema_patches.py` on catalog, admin, the shared tenant file, and every `tenant_*.db`. Column patches are additive. One documented retirement drops leftover `household_settings` date columns after backfilling `SchoolYear` when a household has dates and no named year. It does not DROP leftover `scheduled_work` / `evidence_captures` (that is an operator script, never boot).

**REMAINING:** A model field without a matching patch is missing on old tenant files. That is patch discipline, not a second runner.

**DEPENDENCIES:** Entire backend.

---

### Alembic / migrations — ARCHIVE (not the runner)

**CURRENT:** Revisions 0001–0012 remain in `alembic/versions/` as archaeology. `env.py` refuses `alembic upgrade`. `alembic.ini` `sqlalchemy.url` is `sqlite:///:memory:`. Runtime schema is `init_databases()` → `create_all` + `app.schema_patches`.

**REMAINING:** Someone generating a new revision might assume it runs. `alembic/README.md` says not to. A later Alembic-for-real is allowed only as a dedicated session with backups; never replay 0001.

**DEPENDENCIES:** Deploy/entrypoint.

---

### Frontend architecture — KEEP

**CURRENT:** One HTML shell, one `app.js`, hash routes, global `state`, `data-action` handlers. Chart.js CDN. Logo at `static/curiculy-logo.png`. Shell assets share `SHELL_VERSION`. No bundler — a fit for this repo (Docker bind-mounts JS; no npm in production).

**REMAINING:** Split `app.js` by feature only when two people regularly collide. Do not introduce React/Vue as an architecture goal.

**DEPENDENCIES:** All UX.

---

### API architecture — KEEP

**CURRENT:** REST `/api`, Pydantic, router-per-feature. Assignments spread across path prefixes by design. Calendar exceptions live only under `/api/exceptions`.

**REMAINING:** `/books` and `/catalog` share the ISBN dictionary but not HTTP contracts (see Catalog / Books). Unused power endpoints (`from-isbn`, `POST /curricula/import`) stay until a UI or an explicit retirement.

**DEPENDENCIES:** SPA, extension, tests.

---

### Testing — KEEP (in-memory API client; file JWT tests separate)

**CURRENT:** Pytest + TestClient. Baseline **892 passed, 0 failed, 0 skipped**. Default `conftest.py` `client` is an in-memory catalog+tenant+admin DB (`StaticPool`) and overrides `get_tenant_db` / `get_current_user`. That is the bulk of the suite and is intentional. `auth_client` in `tests/test_auth.py` uses real `admin.db` + `tenant_{uuid}.db` under pytest `tmp_path` without overriding `get_tenant_db` (login, register, persistence across a fresh sqlite3 connection, two-household isolation). Capture, child status, kid auth, and homework-help HTTP tests reuse that fixture. Schema tests and leftover-table DROP use throwaway SQLite files. Evidence file GET is tested authenticated. Paper intake has `test_paper_parser.py`, `test_paper_template.py`, `test_paper_vision_worker.py`. Household identity: `test_household_api.py`. Shell/README/icons/CI: `test_shell.py`. Process health: `tests/test_health.py`. GitHub Actions runs the Compose `tests` service.

**REMAINING:** Homework-help coverage is thin.

**DEPENDENCIES:** Compose `tests` profile (bind-mounts `README.md`, `extension/`, `sw.js`, `.github/`).

---

### Deployment — KEEP (Compose + GitHub Actions tests)

**CURRENT:** Docker Compose, port 3040, bind-mounts, evidence on a volume, Ollama via `host.docker.internal`. Secrets from env or a gitignored `.env`. Root `README.md` documents `.env`, `JWT_SECRET`, compose port 3040, first invite (`tenant_uuid` required on `invite_keys`), and the test command. `GET /api/health` is unauthenticated process health: `SELECT 1` on `catalog.db` and `admin.db` only (`app/routers/health.py`, `app/services/db_health.py`). It does not open household `tenant_{uuid}.db` files, the shared `tenant.db`, or Ollama. Compose and the Dockerfile do not define a `healthcheck`. No nginx in repo. GitHub Actions (`.github/workflows/tests.yml`) runs `docker compose --profile dev run --rm -T tests pytest -q --tb=line` on push and pull request. That image is Python 3.12 (`Dockerfile` `dev` target). CI does not inject production secrets, SMTP, or Ollama; `tests/conftest.py` sets a local JWT signing value. Tenant SQLite files are created in pytest tmp paths.

**REMAINING:** Reverse proxy can stay outside the repo. Rotate the mailbox password if an old committed password was ever used.

**DEPENDENCIES:** All runtime.

---

## Environment variables

Copy `.env.example` to `.env` (gitignored). Compose interpolates these into the `api` container. Do not put real passwords or keys in `docker-compose.yml`.

| Variable | Required | Notes |
|---|---|---|
| `JWT_SECRET` | Yes, when `DEV_MODE` is false | Long random string, at least 32 characters. Known placeholders and the development default are rejected. Never log this value. |
| `DEV_MODE` | No (default `false`) | Local-only. Skips JWT auth and allows an empty `JWT_SECRET` (explicit development signing key). Do not enable for a real family. |
| `MAIL_USERNAME` | No | SMTP user for portfolio email. Empty disables authenticated send. |
| `MAIL_PASSWORD` | No | SMTP password. Comes only from the environment. Never log this value. |
| `MAIL_SERVER` | No | Defaults to `smtp-relay.brevo.com` in compose. |
| `MAIL_PORT` | No | Defaults to `587` in compose. |
| `MAIL_FROM` / `MAIL_FROM_NAME` | No | Envelope identity, not a secret. |
| `GOOGLE_BOOKS_API_KEY` | No | Improves ISBN lookup rate limits. Never log this value. |
| `CAPTURE_TOKEN_EXPIRE_DAYS` | No (default `365`) | Lifetime of a newly issued Chrome capture credential. |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | No | Optional PDF parse, tutoring, spark (text). Paper vision uses hardcoded `llama3.2-vision`, not `OLLAMA_MODEL`. |

Database URLs, `EVIDENCE_DIR`, `INDEX_HTML_PATH`, and `STATIC_DIR` are set in compose for the container layout.

---

## Runtime shape

```text
Parents / kids / extension
        │
        ▼
   HTTPS (future proxy) → FastAPI :80
        │
        ├── JWT → admin.db (who, capture tokens) + tenant_{uuid}.db (planner)
        ├── ISBN cache → catalog.db
        ├── files → evidence/{tenant_uuid}/
        ├── optional Ollama (PDF, paper vision, tutor, spark)
        └── optional SMTP (portfolio email)

SPA: index.html + /static + /sw.js
```

Still one process. Still SQLite. Still two curriculum objects (book vs guide). Still one calendar object: **assignment**.

---

## Data flow (canonical)

```text
ISBN / title  → catalog.db (edition) → tenant curricula (library)
Book pages    → pacing preview/commit → assignments (+ enrollment)
CSV / PDF / paper sheet / builder → curriculum_plans → apply → assignments (+ enrollment)
Chrome shot   → evidence_staging → link → assignment_evidence
Assignments   → calendar, kid My work, dashboard, recalibrate
Assignments + attendance + evidence + enrollments → portfolio PDF
```

Paper sheet detail:

```text
GET /api/curriculum/paper-template  → printable PDF (ArUco + qrcode)
POST /api/curriculum/import-paper   → OpenCV slice on the request
                                  → Ollama vision in a background worker
                                  → curriculum_lessons on a new tenant Session
                                  → parent Apply → assignments
```

Anything that does not feed `assignments` or the library/plans that generate them is either settings (year, weekdays, exceptions) or deferred (compliance, taxonomy).
