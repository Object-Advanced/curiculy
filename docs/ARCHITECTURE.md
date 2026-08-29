# Curiculy Target Architecture

This document describes what Curiculy’s architecture **should** look like. It is based on the existing codebase, not on a generic SaaS template.

Curiculy is a homeschool planner for one family (a household) with multiple children. Parents schedule curricula, mark work, keep evidence, and produce printable records. Children sign in with a PIN and do today’s work. The product must work on a kitchen-table laptop, including when the network is flaky, and must remain simple enough for one operator to run.

Do not treat this as a rewrite plan. The running system is the source of truth. Changes should fold duplicate paths together and finish incomplete ones, not introduce a new stack.

---

## Product constraints that the architecture must preserve

These are requirements, not optional style.

| Constraint | Why it matters | Architectural consequence |
|---|---|---|
| One family, several children | Siblings share some lessons and not others | Per-student assignments plus optional `shared_group_uuid` |
| Two ways curricula arrive | Textbooks are paged; vendor guides are week/day grids | Keep **book auto-schedule** and **pacing guides** as two intake paths that both land on `assignments` |
| School-year calendar | Homeschool years are custom, not district calendars | One named year with bounds, class weekdays, and exceptions |
| Exceptions and holidays | Life happens; sick days can be one child | Household-wide and student-specific exceptions on the same table |
| Assignment generation | Parents will not type 180 lesson rows | Pacing commit and plan-apply write `assignments` |
| Evidence / work samples | Evaluators want photos and PDFs | Staging inbox → assignment attachment; files on a volume |
| Portfolios | State evaluations and reading lists | Date-window reports over assignments, attendance, books, evidence |
| Child accounts | Kids should not use the parent password | PIN users scoped to one student |
| Offline | Rural / travel / kitchen wifi | Service worker shell + outbox for safe writes |
| Barcode / ISBN | Scan a book, fill the form | Shared catalog cache, household library separate |
| AI-assisted parsing | PDFs of pacing guides are common | Background Ollama parse into `curriculum_plans`, not into a second calendar |
| Printable records | Ink-saver weekly list + evaluator PDF | WeasyPrint from the same assignment data |
| Eventual public SaaS | Invite-gated today; public later | Tenant isolation stays; do not require Postgres until scale demands it |

---

## Classification legend

| Label | Meaning |
|---|---|
| **KEEP** | Core. Do not replace. Improve in place if needed. |
| **CONSOLIDATE** | Multiple implementations of one idea. Fold into one. |
| **REFACTOR** | Right concept, messy or unsafe implementation. |
| **REMOVE** | Dead or superseded. Delete after confirming no data depends on it. |
| **COMPLETE** | Partially built and worth finishing because parents will use it. |
| **DEFER** | Valid later. Do not spend cycles now. |

---

## Domain classifications

### Authentication — REFACTOR

**CURRENT:** JWT (HS256) in `localStorage`. Parent email/password. Invite-key registration. Child PIN accounts (`child.{tenant}.{id}@kid.local`). Demo in-memory tenant. `DEV_MODE` bypass. Household user switching. Chrome extension stores a parent JWT as a “device token.”

**PROBLEM:** Default `JWT_SECRET` is weak. Register does not return a token (extra login). Children cannot `PATCH` assignment status, so they cannot check off work. Extension holds a full parent credential. `DEV_MODE` is useful locally and dangerous if left on.

**TARGET:** Keep JWT, invites, PIN children, demo, and switch-user. Issue a token on register. Allow a child JWT to complete **their** assignments only. Give the extension a long-lived **upload-only** token (staging evidence), not a parent session. Fail closed without a strong secret in non-dev.

**DEPENDENCIES:** Every parent and child route; extension; tenant session selection.

**MIGRATION:** Additive. New token type or JWT `scope=evidence:write`. Child status PATCH is a permission change with tests. Rotate `JWT_SECRET` with a dual-accept window if any sessions are live.

**RISK:** Logged-in families; extension uploads; demo mode.

**PRIORITY:** Critical (secrets and evidence token) / High (child complete).

---

### Multi-tenancy — KEEP

**CURRENT:** One `admin.db` (users, invites), one shared `catalog.db` (ISBN dictionary), one SQLite file per household (`tenant_{uuid}.db`). Demo uses process-memory SQLite keyed by JWT `jti`. Dev mode uses a shared `tenant.db`.

**PROBLEM:** Schema updates are `create_all` plus ad-hoc `ALTER` on every tenant file. That is easy to get wrong as the number of families grows. SQLite-per-tenant will not be the forever SaaS answer at thousands of concurrent writers — but it is the right isolation model **now**.

**TARGET:** Keep file-per-household. It matches homeschool privacy (a family’s planner is their lockbox) and backup (copy a file). Do not introduce `tenant_id` columns on every table until a single database is actually required. Fix **how schema is applied** (see Database / Alembic), not the isolation model.

**DEPENDENCIES:** Auth (`tenant_uuid` in JWT), evidence paths `{tenant_uuid}/…`, catalog vs tenant FKs.

**MIGRATION:** None for the isolation model. Schema process is a separate change.

**RISK:** Low if left as-is. High if rewritten to Postgres prematurely (every query, backup, and demo path changes).

**PRIORITY:** Keep as-is. Schema process is High.

---

### Students — KEEP

**CURRENT:** Tenant `students` with name, grade, notes, color. Parent CRUD. PIN create/clear. “Kids” dashboard is today’s checklist plus spark question. Child login is a separate `users` row in `admin.db`.

**PROBLEM:** Child cannot mark work complete. Spark is parent-only on `/students/{id}/spark` (router-level `require_parent`), which is fine. Color palette is duplicated in JS and Python.

**TARGET:** Student remains the child record. Color stays on the student (calendar tiles). PIN stays an admin-db user linked by `student_id`. One palette module or documented duplication.

**DEPENDENCIES:** Assignments, attendance, enrollments, evidence, homework help, calendar, portfolios.

**MIGRATION:** Child complete-work is an API permission change, not a model change.

**RISK:** Deleting a student already cascades assignments; keep that.

**PRIORITY:** High only for child completion. Otherwise Low.

---

### Households — REFACTOR (small)

**CURRENT:** `Household` row auto-created as “Default household.” `get_default_household` is first-by-id. `jurisdiction_id` unused.

**PROBLEM:** Multi-household-per-file is implied by the schema but not a product. Jurisdiction is compliance leftover.

**TARGET:** **One household per tenant file** is the product rule. Make that explicit in code comments and stop threading `jurisdiction_id` until a state pack exists. Optional later: rename household from the settings menu (display name already used in the chrome).

**DEPENDENCIES:** Almost every tenant write uses the default household.

**MIGRATION:** No data migration. Ignore/drop jurisdiction when compliance is designed.

**RISK:** Low.

**PRIORITY:** Low.

---

### School years — CONSOLIDATE

**CURRENT:** Two date ranges:

1. `school_years` — named years (wizard `POST /school-years`, settings list, enrollments, portfolios).
2. `household_settings` — `start_date`, `end_date`, `weekdays` (year modal, auto-schedule, holiday grid).

`save_school_year_settings` already copies dates onto the **latest** `SchoolYear`. Wizard can create a `SchoolYear` without writing `HouseholdSettings`. Weekdays live only on settings.

**PROBLEM:** Parents think there is one school year. Operators have two write paths. Latest-year-wins is implicit.

**TARGET:** One **operational year**:

- `SchoolYear` is the named academic period (name + start + end). It is what portfolios and enrollments point at.
- `HouseholdSettings` holds **weekdays** and **exception_colors** only (not a second start/end).
- Wizard and the year modal both create/update the same `SchoolYear` (current = latest, or an explicit `is_current` flag if multiple years are kept for history).

Historical years remain rows for old portfolios. Only one year is current for pacing and the grid.

**DEPENDENCIES:** Pacing, plan-apply, exceptions grid, enrollments, portfolios, wizard.

**MIGRATION:** Backfill: if settings dates exist and latest year differs, prefer settings dates onto that year (they already tend to sync on save). Stop writing start/end on settings in a later step; read dates from current `SchoolYear`.

**RISK:** Portfolios keyed by `school_year_id`; wizard vs modal drift during the transition.

**PRIORITY:** High.

---

### Enrollments — COMPLETE (then simplify the UI)

**CURRENT:** `enrollments` unique on student + curriculum + school year. Settings form can create them. Pacing commit does **not**. Plan-apply does **not**. Portfolios use enrollments to build the book list.

**PROBLEM:** Parents schedule a book and still have an empty reading list unless they visit Settings → Enrollments. That is a hidden second job.

**TARGET:** Enrollment means “this child is using this program this year.” It should be a **side effect** of:

- auto-schedule commit (curriculum + each student + current year)
- apply pacing guide (same, if the plan is tied to a curriculum; if not, skip or use plan title as a curriculum later)

Keep the settings list as an editor for edge cases (unenroll, date overrides). Do not make it the primary workflow.

**DEPENDENCIES:** Portfolios (reading list), settings UI, curriculum delete (already cleans enrollments).

**MIGRATION:** On next pacing/plan commits, insert enrollment if missing. Optional one-time backfill from distinct `assignments` → curriculum via resource/unit.

**RISK:** Duplicate unique constraint if both UI and auto-create race — handle with the existing 409/IntegrityError pattern.

**PRIORITY:** High (portfolio completeness). Medium (UI copy: “usually created when you schedule”).

---

### Curricula — KEEP

**CURRENT:** Tenant `curricula` is the household library (Saxon Math 3, etc.). Editions, resources, units, page mappings. Created by form (`sku`/ISBN), ISBN lookup then save, or structure import API.

**PROBLEM:** `POST /curricula/import` (JSON/CSV tree) is unused by the SPA. Catalog `POST /from-isbn` is unused; the form uses lookup + `POST /curricula`. Naming: `/curricula` vs `/curriculum/plans` is already the right split.

**TARGET:** Household library stays tenant-scoped. ISBN lookup fills the form; save creates library + catalog edition. Keep `/curricula/import` as a power-user/API path or hide it until a UI exists. Do not merge library rows into catalog.db (that would leak one family’s notes into the shared dictionary).

**DEPENDENCIES:** Auto-schedule, enrollments, catalog ISBN, unschedule/delete.

**MIGRATION:** None required for the model.

**RISK:** Low.

**PRIORITY:** Low (cleanup unused import UI later).

---

### Curriculum resources — KEEP

**CURRENT:** Components of an edition (student text, workbook, answer key) optionally pointing at `book_editions.id` in catalog.db without a cross-DB FK.

**PROBLEM:** Cross-DB integer ids cannot be enforced by SQLite. That is acceptable if the write path always creates both in one user action.

**TARGET:** Keep resources as “what the parent holds.” Auto-schedule paces against the student text’s page count. Do not move resources into catalog.db (they are household-specific: which edition they bought).

**DEPENDENCIES:** Pacing, page mappings, classifications (deferred).

**MIGRATION:** None.

**RISK:** Orphan `book_edition_id` if catalog rows are deleted — do not delete catalog editions that tenant resources reference.

**PRIORITY:** Low.

---

### Curriculum plans — KEEP

**CURRENT:** `curriculum_plans` + `curriculum_lessons` (week, day, title, time slot, category). CSV import, PDF+Ollama, manual builder, archive, apply-to-calendar.

**PROBLEM:** Easy to confuse with `curricula` / auto-schedule. They are different homeschool objects: a **guide** vs a **book**. PDF status polling is a frontend concern, not a domain bug.

**TARGET:** Keep plans as the structured-guide catalog. Apply always writes `assignments` (already). Do not generate `curriculum_units` from plans unless a future “link this guide to this book” feature needs it.

**DEPENDENCIES:** Calendar, exceptions (skipped days), students.

**MIGRATION:** None.

**RISK:** Changing apply math reshapes family calendars.

**PRIORITY:** Keep. PDF reliability is Medium.

---

### Assignments — KEEP

**CURRENT:** The calendar event: student, title, date, status, notes, optional catalog/unit/resource ids, grade, evidence, `shared_group_uuid`.

**PROBLEM:** Parallel leftover `scheduled_work`. Status PATCH is parent-only.

**TARGET:** `Assignment` is the only scheduled work object. Shared groups remain for sibling co-lessons. Child may set status on own rows.

**DEPENDENCIES:** Calendar, dashboard, evidence, homework help, portfolios, weekly PDF, recalibrate, attendance overlay.

**MIGRATION:** Do not migrate `scheduled_work` into assignments unless production DBs have rows (likely empty). Then delete the old tables.

**RISK:** Recalibrate and shared-group sync.

**PRIORITY:** Critical as the domain center. High for child status.

---

### Pacing — KEEP

**CURRENT:** Preview is pure arithmetic (`SyllabusGenerator`). Commit writes units, mappings, and assignments. Deadline vs pages-per-day. Skips exceptions and non-class weekdays.

**PROBLEM:** Module named `ai_generator` is not AI. Comments describe a future LLM TOC split — that is a later enhancement, not a missing core.

**TARGET:** Keep deterministic page-chunk pacing as the default (parents can edit titles before commit). Optional later: LLM titles from a TOC **behind the same preview contract**. Do not block scheduling on Ollama.

**DEPENDENCIES:** Curricula, resources, school year weekdays, exceptions, assignments.

**MIGRATION:** Rename is cosmetic; do it only when touching the file.

**RISK:** Commit transaction size (many assignments).

**PRIORITY:** Low (rename). Keep the engine.

---

### Calendar — KEEP

**CURRENT:** Per-student window (`/students/{id}/assignments`) and household “All Students” (`/calendar`, shared groups only). Day/week/month. Attendance and exceptions painted in the SPA.

**PROBLEM:** All-students hides private lessons by design (documented). That is a product choice, not a bug — call it out in the UI so parents are not surprised.

**TARGET:** Keep two views. Shared group = lesson taught together. Private = one child. Copy in the All Students view: “shared lessons only.”

**DEPENDENCIES:** Assignments, attendance, exceptions, students.

**MIGRATION:** UI copy only unless product wants private lessons on the family board (would be a query change).

**RISK:** Changing `/calendar` to include private lessons would clutter the family board.

**PRIORITY:** Low.

---

### Attendance — KEEP

**CURRENT:** One row per student per day. Upsert from calendar cells. Present / Absent / Sick / Vacation.

**PROBLEM:** Overlaps conceptually with exception kinds (sick, vacation). Parents can mark attendance and also paint a vacation exception.

**TARGET:** Keep both: **exceptions** mean “not a school day / don’t schedule.” **Attendance** means “what we recorded for the log.” Auto-filling attendance from exceptions is a later convenience, not a merge of tables.

**DEPENDENCIES:** Portfolios, calendar UI.

**MIGRATION:** None now.

**RISK:** Low.

**PRIORITY:** Low (auto-fill is DEFER).

---

### Exceptions — CONSOLIDATE (APIs, not tables)

**CURRENT:** One table `calendar_exceptions`. Two HTTP surfaces:

- `/exceptions` — list/create full records (settings, calendar overlay).
- `/calendar/exceptions` — date set, toggle one day, import holidays (year grid).

Student-specific rows are excluded from the household “no-school” set used by pacing (correct).

**PROBLEM:** Two APIs for one table. Toggle creates/deletes rows; the list UI creates titled ranges. Same idea, two dialects.

**TARGET:** Keep one table. Prefer one router module with:

- list/create/update/delete records
- derived `dates` for the grid
- toggle as “create or delete a one-day household holiday”
- import-holidays as bulk create

SPA can keep two screens (list vs year grid).

**DEPENDENCIES:** Pacing, plan-apply, school-year grid, calendar paint.

**MIGRATION:** Move handlers into one module; keep old paths as aliases until the SPA is updated.

**RISK:** Holiday import duplicates; toggle vs range overlap.

**PRIORITY:** Medium.

---

### Evidence — REFACTOR

**CURRENT:** Staging (`evidence_staging` + Chrome upload) → link to `assignment_evidence`. Direct upload on an assignment. Files under `{tenant_uuid}/{uuid}.webp|pdf`. Legacy `evidence_captures` unused for new writes. `/evidence` StaticFiles, no auth.

**PROBLEM:** Work samples are guessable if tenant UUID and filename leak. Staging + assignment evidence is the right product split (inbox vs filed).

**TARGET:** Keep staging inbox and assignment attachments. Serve files only with the same JWT (or short-lived signed URLs). Delete `evidence_captures` when unused. Extension uses an upload-scoped token.

**DEPENDENCIES:** Portfolios (attachments), calendar paperclip, extension.

**MIGRATION:** Add an authenticated `GET /api/evidence/files/...` and point the SPA at it; then unmount public StaticFiles.

**RISK:** Broken images in the UI during cutover; extension uploads.

**PRIORITY:** Critical (auth). Keep the inbox model.

---

### Portfolios — KEEP

**CURRENT:** Report types (state log, reading list, work samples, custom). HTML preview, WeasyPrint PDF, email via background SMTP. Window from school year dates. Books from enrollments.

**PROBLEM:** Reading list empty without enrollments. Email credentials currently in compose. Custom report is POST-only (GET `/report` rejects custom) — fine.

**TARGET:** Keep server-side PDF. After enrollments auto-create, reading lists fill. Do not move PDF generation to the browser (print CSS is a supplement, not a replacement for evaluator PDFs).

**DEPENDENCIES:** Assignments, attendance, enrollments, school years, evidence, mail config.

**MIGRATION:** Enrollment auto-create; secret handling.

**RISK:** Email deliverability; PDF layout.

**PRIORITY:** High for data completeness; Critical for mail secrets.

---

### Homework Help — KEEP

**CURRENT:** Child-only sessions, Ollama tutor that refuses answers, parent notifications, lock after redirects, parent unlock.

**PROBLEM:** Small test coverage. Depends on local Ollama. Otherwise aligned with the product.

**TARGET:** Keep as a child feature with parent oversight. Fail gracefully when Ollama is down (already logged).

**DEPENDENCIES:** Assignments, students, notifications, Ollama.

**MIGRATION:** None.

**RISK:** Prompt injection / answer leakage — treat prompt changes as product risk.

**PRIORITY:** Low (stability). Keep.

---

### AI / Ollama — KEEP (narrow)

**CURRENT:** Three uses: PDF → plan lessons (background), homework tutor, spark question (short timeout). Pacing “AI” is arithmetic.

**PROBLEM:** One daemon, three timeouts and two client libraries (`httpx` and `ollama`). Easy to assume pacing needs the GPU box.

**TARGET:** Ollama is an **optional accelerator**: PDF import and tutoring. Scheduling must work with it off. Spark stays best-effort. Do not put Ollama on the calendar write path.

**DEPENDENCIES:** Curriculum PDF import, homework help, spark.

**MIGRATION:** Document `OLLAMA_HOST` as optional. PDF import already marks `failed`.

**RISK:** Background session lifecycle on PDF import.

**PRIORITY:** Medium (PDF worker session). Keep the optional-AI stance.

---

### Catalog / ISBN — KEEP

**CURRENT:** Shared `book_editions` cache. Resolver: Open Library then Google Books. SPA: `POST /catalog/lookup-isbn` then `POST /curricula` with `sku`.

**PROBLEM:** `POST /catalog/from-isbn` duplicates “create library row from ISBN” that the form already does in two steps. Fine for API clients; confusing as two official paths.

**TARGET:** Keep shared catalog + household library. Canonical SPA path: lookup → save curricula. Keep `from-isbn` as a one-shot API or implement the SPA against it later — not both as equal UI paths.

**DEPENDENCIES:** Auto-schedule page counts, barcode extension-to-be.

**MIGRATION:** Document the two-step path as canonical.

**RISK:** Low.

**PRIORITY:** Low.

---

### Books — CONSOLIDATE (into catalog)

**CURRENT:** `/books/resolve`, `/books/isbn/{isbn}`, `/books/{id}` wrap the same resolver. SPA does not call them. Tests do.

**PROBLEM:** Two HTTP namespaces for one cache.

**TARGET:** Catalog is the public name (`/catalog/...`). Books routes can remain as aliases or be deprecated once tests use catalog. Do not build a separate “books” product surface.

**DEPENDENCIES:** Resolver, catalog lookup.

**MIGRATION:** Point tests at catalog; keep books routes until then.

**RISK:** Low.

**PRIORITY:** Low.

---

### Notifications — KEEP

**CURRENT:** In-app list for homework-help started/redirect. Mark read.

**PROBLEM:** Not a general notification platform. That is appropriate.

**TARGET:** Stay homework-help (and maybe PDF-plan-ready later). Do not add email/push until a parent asks.

**DEPENDENCIES:** Homework help; optional plan status.

**MIGRATION:** Optional: notify when PDF plan leaves `processing`.

**RISK:** Low.

**PRIORITY:** Low. COMPLETE only for “plan ready” if PDF import stays async.

---

### Offline / PWA — KEEP (REFACTOR cache bust)

**CURRENT:** `sw.js` caches shell; IndexedDB outbox replays mutating `api()` calls. Does not cache `/api` or `/evidence`.

**PROBLEM:** Cache URL query strings in `sw.js` do not match `index.html` (`widget-hug` vs `pdf-ocr`). Stale JS after deploy.

**TARGET:** Keep shell + outbox. Single version token shared by HTML and SW (or hash-based cache). Never cache evidence or API JSON.

**DEPENDENCIES:** SPA `api()`, uploads.

**MIGRATION:** Bump both strings together; or generate SW list from the same version constant.

**RISK:** Users stuck on old `app.js`.

**PRIORITY:** High (cache bust). Keep offline.

---

### Chrome extension — KEEP (REFACTOR token)

**CURRENT:** MV3 capture → `POST /api/evidence/staging`. Options: server URL + device token. Icons referenced, missing in tree.

**PROBLEM:** Token is a parent JWT. `host_permissions` are broad (needed for screenshots on arbitrary curriculum sites).

**TARGET:** Keep one-click capture into the unsorted inbox. Scoped token. Restore icons. Do not turn the extension into a second app.

**DEPENDENCIES:** Evidence staging, parent JWT today.

**MIGRATION:** New token endpoint; extension settings field stays “device token.”

**RISK:** Capture flow until tokens migrate.

**PRIORITY:** High (token). Medium (icons).

---

### Compliance — DEFER

**CURRENT:** `jurisdictions`, `compliance_packets`, `build_packet()` raises `NotImplementedError`.

**PROBLEM:** Empty tables and a stub. Portfolios already produce evaluator PDFs.

**TARGET:** Do not build a jurisdiction rules engine until a specific state form is a paying requirement. When needed, generate packets **from assignments + attendance + evidence**, same as portfolios, with a state template.

**DEPENDENCIES:** None in the live product.

**MIGRATION:** Leave tables. Do not expose UI.

**RISK:** None if deferred.

**PRIORITY:** Low. Defer.

---

### Taxonomy / classification — DEFER

**CURRENT:** Catalog `subject_taxonomies`, `reporting_categories`; tenant `curriculum_classifications`. Tests only. Assignments may store `subject_taxonomy_id`; pacing can pass it; no CRUD API.

**PROBLEM:** Transcript-ready taxonomy without a product surface.

**TARGET:** Optional subject string on curricula/assignments is enough today. Hierarchical taxonomy when a state report needs buckets. Until then, do not build a taxonomy admin UI.

**DEPENDENCIES:** Assignment optional FK, tests.

**MIGRATION:** Leave columns. Ignore in UI.

**RISK:** None if deferred.

**PRIORITY:** Low. Defer.

---

### Database architecture — REFACTOR (process, not engine)

**CURRENT:** Three SQLite files. SQLAlchemy 2. Cross-DB ids without FKs. `init_databases()` on boot.

**PROBLEM:** Schema evolution is manual ALTER lists in `db.py` plus unused Alembic files. Easy to add a model field and forget the ALTER for existing tenant files.

**TARGET:** Keep SQLite three-file layout. One **explicit** schema story:

- Either Alembic runs against catalog, admin, **and each tenant file**, or
- `create_all` + a single ordered patch module that is the documented source of truth — and **stop adding Alembic revisions that never run**.

Prefer Alembic-for-real if more than one person ships schema, because tenant glob (`tenant_*.db`) is already in `init_databases`.

**DEPENDENCIES:** Entire backend.

**MIGRATION:** See `TECHNICAL_DEBT.md`. Do not change engines.

**RISK:** Corrupt or diverging tenant files.

**PRIORITY:** High.

---

### Alembic / migrations — CONSOLIDATE

**CURRENT:** Revisions 0001–0012 describe history. `env.py` only calls `init_databases()`. `alembic.ini` points at catalog.db.

**PROBLEM:** Looks like migrations exist. They do not run. 0001 does not match live models.

**TARGET:** Pick one. Recommended: make Alembic the runner for all three bases, including a loop over `tenant_*.db`, **or** delete the false impression (archive revisions, document `db.py` patches). Do not maintain both.

**DEPENDENCIES:** Deploy/entrypoint.

**MIGRATION:** If adopting Alembic, stamp existing DBs as “head equivalent to create_all” rather than replaying 0001.

**RISK:** Replaying old revisions against live files would be destructive.

**PRIORITY:** High (honesty of process).

---

### Frontend architecture — KEEP (REFACTOR edges)

**CURRENT:** One HTML shell, one `app.js`, hash routes, global `state`, `data-action` handlers. Chart.js CDN.

**PROBLEM:** ~8500 lines in one file. Missing logo. Cache bust. No bundler — that is a **fit** for this repo (Docker bind-mounts JS; no npm in production).

**TARGET:** Stay a server-rendered shell + vanilla SPA until a second client (mobile native) exists. Split `app.js` by feature only when two people regularly collide. Fix assets and SW versions. Do not introduce React/Vue as an architecture goal.

**DEPENDENCIES:** All UX.

**MIGRATION:** Mechanical file split later; behavior unchanged.

**RISK:** Hash routing and global state make a framework rewrite high-cost and low-value.

**PRIORITY:** High for assets/SW. Low for splitting JS.

---

### API architecture — KEEP (REFACTOR duplicates)

**CURRENT:** REST `/api`, Pydantic, router-per-feature. Assignments spread across path prefixes by design.

**PROBLEM:** Duplicate exception and book/catalog surfaces. Some power endpoints unused by UI.

**TARGET:** Keep REST and FastAPI. Consolidate exception routers. Treat unused endpoints as API-only until a UI exists. Do not add GraphQL or a BFF.

**DEPENDENCIES:** SPA, extension, tests.

**MIGRATION:** Aliases then delete unused public paths if nothing external calls them.

**RISK:** Extension and any unpublished API clients.

**PRIORITY:** Medium.

---

### Testing — REFACTOR

**CURRENT:** Pytest + TestClient. One in-memory SQLite for catalog+tenant+admin. Auth often overridden.

**PROBLEM:** Does not prove `tenant_{uuid}.db` routing, invite provision, or evidence StaticFiles auth. Homework-help coverage is thin.

**TARGET:** Keep fast in-memory tests as the default. Add a small **integration** module that uses real tenant file URLs and JWT without overriding `get_tenant_db`. Test evidence file GET once it is authenticated.

**DEPENDENCIES:** CI (when added).

**MIGRATION:** Additive tests.

**RISK:** Slow suite if every test uses files — keep file tests few.

**PRIORITY:** Medium.

---

### Deployment — REFACTOR

**CURRENT:** Docker Compose, port 3040, bind-mounts, evidence on a large array, Ollama via `host.docker.internal`. No nginx, CI, or README in repo.

**PROBLEM:** Secrets in compose. No documented bootstrap (first admin, first invite). Bind-mounts are good for this host, not a generic public deploy.

**TARGET:** Compose remains the homelab/SaaS-single-node shape. Secrets from env or a file not in git. Document: create first admin, generate invite, set `JWT_SECRET`, optional Ollama. Add CI running pytest on the `dev` image. Reverse proxy can stay outside the repo until there are multiple services.

**DEPENDENCIES:** All runtime.

**MIGRATION:** Move secrets; add README; optional CI.

**RISK:** Mail stops until env is set (correct).

**PRIORITY:** Critical (secrets). High (README/bootstrap).

---

## Target runtime shape

```text
Parents / kids / extension
        │
        ▼
   HTTPS (future proxy) → FastAPI :80
        │
        ├── JWT → admin.db (who) + tenant_{uuid}.db (planner)
        ├── ISBN cache → catalog.db
        ├── files → evidence/{tenant_uuid}/
        ├── optional Ollama (PDF, tutor, spark)
        └── optional SMTP (portfolio email)

SPA: index.html + /static + /sw.js
```

Still one process. Still SQLite. Still two curriculum intakes. Still one calendar object: **assignment**.

---

## Target data flow (canonical)

```text
ISBN / title  → catalog.db (edition) → tenant curricula (library)
Book pages    → pacing preview/commit → assignments (+ enrollment)
PDF / CSV / builder → curriculum_plans → apply → assignments (+ enrollment)
Chrome shot   → evidence_staging → link → assignment_evidence
Assignments   → calendar, kid My work, dashboard, recalibrate
Assignments + attendance + evidence + enrollments → portfolio PDF
```

Anything that does not feed `assignments` or the library/plans that generate them is either settings (year, weekdays, exceptions) or deferred (compliance, taxonomy).
