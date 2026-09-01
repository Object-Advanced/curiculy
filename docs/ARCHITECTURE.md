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

**CURRENT:** JWT (HS256) in `localStorage`. Parent email/password. Invite-key registration. Child PIN accounts (`child.{tenant}.{id}@kid.local`). Demo in-memory tenant. `DEV_MODE` bypass. Household user switching. Chrome extension stores a long-lived **capture credential** (`scope=evidence:write`) issued from Settings → Students. Non-dev startup requires `JWT_SECRET` from the environment and refuses known-weak placeholders.

**PROBLEM (met for register token):** `DEV_MODE` is useful locally and dangerous if left on.

**TARGET:** Keep JWT, invites, PIN children, demo, switch-user, and the upload-only capture credential. Issue a token on register (done). A child JWT may complete **their** assignments only (done). Fail closed without a strong secret in non-dev (done). Extension credential is staging-only (done).

**DEPENDENCIES:** Every parent and child route; extension; tenant session selection.

**MIGRATION:** Additive. Capture tokens are JWTs with `scope=evidence:write` plus a revocable `capture_tokens` row on `admin.db`. Child status PATCH is a permission change with tests. Rotate `JWT_SECRET` with a dual-accept window if any sessions are live.

**RISK:** Logged-in families; demo mode.

**PRIORITY:** Register token is in place. Child complete and extension token are in place.

**Capture credential lifecycle**

1. A parent (not demo, not a child) opens Settings → Students and generates a token (`POST /api/auth/capture-token`). The secret is shown once in the SPA. Status (`GET`) never returns the secret.
2. The JWT identifies the household (`tenant_uuid`), uses `sub=capture.{tenant}`, `role=evidence`, `scope=evidence:write`, and a `jti`. Lifetime defaults to 365 days (`CAPTURE_TOKEN_EXPIRE_DAYS`).
3. A `capture_tokens` row on `admin.db` stores that `jti`. Minting a new token revokes earlier rows for the tenant. Revoke is `DELETE /api/auth/capture-token`.
4. The extension pastes the token as “device token” and sends it as `Authorization: Bearer` on `POST /api/evidence/staging` only.
5. The server accepts that credential for staging writes after checking the JWT and that the row is present, unrevoked, and unexpired. `get_current_user` rejects it, so `/auth/me`, household, calendar, admin, listing/linking staging, and evidence file reads all fail.
6. Parent login JWTs can still stage (API). They must not be pasted into the extension.

---

### Multi-tenancy — KEEP

**CURRENT:** One `admin.db` (users, invites, capture tokens), one shared `catalog.db` (ISBN dictionary), one SQLite file per household (`tenant_{uuid}.db`). Demo uses process-memory SQLite keyed by JWT `jti`. Dev mode uses a shared `tenant.db`.

**PROBLEM:** Schema updates must touch every `tenant_*.db`. That is easy to get wrong as the number of families grows if a new column is added to a model without a matching patch. SQLite-per-tenant will not be the forever SaaS answer at thousands of concurrent writers — but it is the right isolation model **now**.

**TARGET:** Keep file-per-household. It matches homeschool privacy (a family’s planner is their lockbox) and backup (copy a file). Do not introduce `tenant_id` columns on every table until a single database is actually required. Fix **how schema is applied** (see Database / Alembic), not the isolation model.

**DEPENDENCIES:** Auth (`tenant_uuid` in JWT), evidence paths `{tenant_uuid}/…`, catalog vs tenant FKs.

**MIGRATION:** None for the isolation model. Schema process is a separate change.

**RISK:** Low if left as-is. High if rewritten to Postgres prematurely (every query, backup, and demo path changes).

**PRIORITY:** Keep as-is. Schema process is High.

---

### Students — KEEP

**CURRENT:** Tenant `students` with name, grade, notes, color. Parent CRUD. PIN create/clear. “Kids” dashboard is today’s checklist plus spark question. Child login is a separate `users` row in `admin.db`. A child JWT may `PATCH /assignments/{id}/status` on their own assignments.

**PROBLEM:** Spark is parent-only on `/students/{id}/spark` (router-level `require_parent`), which is fine. Color palette is duplicated in JS and Python.

**TARGET:** Student remains the child record. Color stays on the student (calendar tiles). PIN stays an admin-db user linked by `student_id`. One palette module or documented duplication. Child complete-work is in place.

**DEPENDENCIES:** Assignments, attendance, enrollments, evidence, homework help, calendar, portfolios.

**MIGRATION:** Child complete-work is an API permission change, not a model change (done).

**RISK:** Deleting a student already cascades assignments; keep that.

**PRIORITY:** Low. Child completion is in place.

---

### Households — REFACTOR (small)

**CURRENT:** `Household` row auto-created as “Default household.” The first-run wizard PATCHes `/household` so the family names it. Families that already finished setup still get a one-step name prompt while the name is the default. Settings can rename it and pick a sidebar icon (letter skips a leading “The”, or a school emoji). `get_default_household` is first-by-id. `jurisdiction_id` unused.

**PROBLEM:** Multi-household-per-file is implied by the schema but not a product. Jurisdiction is compliance leftover.

**TARGET:** **One household per tenant file** is the product rule. Make that explicit in code comments and stop threading `jurisdiction_id` until a state pack exists. Wizard rename, Settings rename, and sidebar icon (letter or school emoji) are in place.

**DEPENDENCIES:** Almost every tenant write uses the default household.

**MIGRATION:** No data migration. Ignore/drop jurisdiction when compliance is designed.

**RISK:** Low.

**PRIORITY:** Low.

---

### School years — KEEP (canonical dates on SchoolYear)

**CURRENT:** Named `SchoolYear` rows are the operational year (latest by start date, then id). `GET /settings/school-year` reads dates from that year. Weekdays and exception colors stay on `HouseholdSettings`. The year modal (`PUT /settings/school-year`) and wizard (`POST /school-years`) write the same `SchoolYear`. `PATCH /school-years/{id}` updates a named year. Settings `start_date` / `end_date` columns remain as a write-through mirror so existing `tenant_*.db` files keep their NOT NULL columns.

**PROBLEM (met):** Parents thought there was one school year while operators had two date stores. `GET /settings/school-year` used to prefer settings dates whenever a settings row existed.

**TARGET (met for reads):** One operational year:

- `SchoolYear` is the named academic period (name + start + end). Portfolios and enrollments point at it.
- `HouseholdSettings` holds **weekdays** and **exception_colors** as the live preferences. Date columns on settings are a compatibility mirror, not a second source of truth.
- Wizard and the year modal create/update the same `SchoolYear` (current = latest). Historical years remain for old portfolios.

**DEPENDENCIES:** Pacing, plan-apply, exceptions grid, enrollments, portfolios, wizard.

**MIGRATION:** If a tenant has settings dates and no `SchoolYear`, the first load creates a named year from those dates. If both exist and they differ, the named year wins (a wizard year is not overwritten by a stale settings row) and settings date columns are mirrored from the year. Columns are not dropped.

**RISK:** Low after the read-path change. Remaining work is to stop writing the settings date mirror, then drop those columns in a later schema pass.

**PRIORITY:** Done for this phase. Dropping the mirror columns is later.

---

### Enrollments — KEEP (auto-create on schedule)

**CURRENT:** Unique on student + curriculum + school year. Settings can still POST/list. Pacing commit and plan-apply insert the row in the **same transaction** as the assignments if it is missing. Preview does not. The operational (latest) `SchoolYear` is the year used. Plans have no `curriculum_id`; apply reuses a library row with the same title or creates one from the plan title.

**PROBLEM (met):** Parents scheduled a book and still had an empty reading list unless they visited Settings → Enrollments.

**TARGET (met):** Enrollment means “this child is using this program this year.” It is a side effect of auto-schedule commit and of applying a pacing guide. Settings remains the editor for edge cases (manual enroll, date overrides). Duplicate unique rows are reused, not inserted twice.

**DEPENDENCIES:** Portfolios (reading list), settings UI, curriculum delete (already cleans enrollments).

**MIGRATION:** Next commit/apply inserts if missing. No backfill of old assignments in this pass. Settings POST is unchanged (still 409 on duplicate).

**RISK:** Unique constraint races handled with a savepoint inside the assignment transaction.

**PRIORITY:** Done for this phase. Empty-reading-list copy in the UI is later.

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

**CURRENT:** The calendar event: student, title, date, status, notes, optional catalog/unit/resource ids, grade, evidence, `shared_group_uuid`. `PATCH /assignments/{id}/status` is allowed for a parent (syncs a shared group) or a child on their own row (does not sync siblings). `scheduled_work` / `evidence_captures` are not mapped. Available family files on this host had COUNT=0. Empty tables may remain on disk; `create_all` does not drop them. Student and curriculum delete still clear leftover rows.

**PROBLEM (met for ORM):** Parallel leftover `scheduled_work` models are gone.

**TARGET:** `Assignment` is the only scheduled work object. Shared groups remain for sibling co-lessons. Child may set status on own rows (done). DROP leftover tables only after an operator COUNT=0 on each `tenant_*.db`.

**DEPENDENCIES:** Calendar, dashboard, evidence, homework help, portfolios, weekly PDF, recalibrate, attendance overlay.

**MIGRATION:** No row copy. Tables were empty here. Optional later DROP.

**RISK:** Recalibrate and shared-group sync.

**PRIORITY:** Critical as the domain center. Child status is in place.

---

### Pacing — KEEP

**CURRENT:** Preview is pure arithmetic (`SyllabusGenerator`). Commit writes units, mappings, and assignments. Deadline vs pages-per-day. Skips exceptions and non-class weekdays.

**PROBLEM:** Module named `ai_generator` is not AI. Comments no longer promise an LLM on the commit path.

**TARGET:** Keep deterministic page-chunk pacing as the default (parents can edit titles before commit). Optional later: LLM titles from a TOC **behind the same preview contract**. Do not block scheduling on Ollama.

**DEPENDENCIES:** Curricula, resources, school year weekdays, exceptions, assignments.

**MIGRATION:** Rename is cosmetic; do it only when touching the file.

**RISK:** Commit transaction size (many assignments).

**PRIORITY:** Low (rename). Keep the engine.

---

### Calendar — KEEP

**CURRENT:** Per-student window (`/students/{id}/assignments`) and household “All Students” (`/calendar`, shared groups only). Day/week/month. Attendance and exceptions painted in the SPA. All Students shows an italic note: shared lessons only.

**PROBLEM (met for copy):** All-students hides private lessons by design. The calendar header says so.

**TARGET (met for copy):** Keep two views. Shared group = lesson taught together. Private = one child. Copy in the All Students view: “shared lessons only.”

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

**MIGRATION:** Move handlers into one module; keep old paths as aliases until the SPA is updated. This cleanup did not merge the routers: `app.js` still calls both URL prefixes.

**RISK:** Holiday import duplicates; toggle vs range overlap.

**PRIORITY:** Medium.

---

### Evidence — REFACTOR

**CURRENT:** Staging (`evidence_staging` + Chrome upload) → link to `assignment_evidence`. Direct upload on an assignment. Files under `{tenant_uuid}/{uuid}.webp|pdf`. `evidence_captures` is no longer mapped; available files had COUNT=0. Empty tables may remain. Files are served by authenticated `GET /api/evidence/files/{tenant}/{filename}`. The public `/evidence` StaticFiles mount is gone. Extension upload uses a capture credential, not a parent session.

**PROBLEM:** Staging + assignment evidence is the right product split (inbox vs filed).

**TARGET:** Keep staging inbox and assignment attachments. Serve files only with a parent or child JWT (done). DROP `evidence_captures` only after COUNT=0 on each tenant file.

**DEPENDENCIES:** Portfolios (attachments), calendar paperclip, extension.

**MIGRATION:** Authenticated `GET /api/evidence/files/...` is live; SPA fetches with the JWT. Public StaticFiles unmounted. Capture credential is live.

**RISK:** Low for file serving. Capture tokens must be rotated if `JWT_SECRET` is rotated.

**PRIORITY:** Medium (`evidence_captures` cleanup). File serving and extension token are in place.

---

### Portfolios — KEEP

**CURRENT:** Report types (state log, reading list, work samples, custom). HTML preview, WeasyPrint PDF, email via background SMTP. Window from school year dates. Books from enrollments (now created when work is scheduled).

**PROBLEM:** Custom report is POST-only (GET `/report` rejects custom) — fine. Older years scheduled before auto-enroll may still have empty book lists; the portfolio screen explains Settings → Enrollments.

**TARGET:** Keep server-side PDF. Do not move PDF generation to the browser (print CSS is a supplement, not a replacement for evaluator PDFs).

**DEPENDENCIES:** Assignments, attendance, enrollments, school years, evidence, mail config.

**MIGRATION:** Enrollment auto-create is in place for new commits/applies. Optional backfill of historical years later.

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

**RISK:** Background session lifecycle on PDF import — **met**. The worker opens its own tenant session from captured `tenant_uuid` / demo key; it does not keep the request Session.

**PRIORITY:** Low (optional AI). Keep the optional-AI stance.

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

**TARGET:** Catalog is the public name (`/catalog/lookup-isbn` for the SPA). `/books/*` and `POST /catalog/from-isbn` stay as API-only aliases until tests (and any external caller) move to catalog. Do not delete them because the SPA does not call them.

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

**CURRENT:** `sw.js` caches shell; IndexedDB outbox replays mutating `api()` calls. Does not cache `/api` or `/evidence`. `SHELL_VERSION` is the single cache-bust token. `index.html` and CSS query strings use that value. `SHELL_CACHE` is `curiculy-shell-${SHELL_VERSION}`, so a bump drops the previous shell.

**PROBLEM:** None for lockstep. Outbox and offline remain product features to keep.

**TARGET:** Keep shell + outbox. Single version token shared by HTML and SW (done). Never cache evidence or API JSON.

**DEPENDENCIES:** SPA `api()`, uploads.

**MIGRATION:** Bump `SHELL_VERSION` in `sw.js` and the matching `?v=` strings in `index.html` and `app.css` together. Tests fail if they drift.

**RISK:** Users stuck on old `app.js` if versions are edited separately (guarded by tests).

**PRIORITY:** Keep offline. Cache bust lockstep is in place.

---

### Chrome extension — KEEP (REFACTOR token)

**CURRENT:** MV3 capture → `POST /api/evidence/staging` with a capture credential (`scope=evidence:write`). Options: server URL + device token (the capture JWT). Toolbar and options icons are PNGs under `extension/icons/`, derived from the Curiculy logo.

**PROBLEM:** `host_permissions` are broad (needed for screenshots on arbitrary curriculum sites).

**TARGET:** Keep one-click capture into the unsorted inbox. Do not turn the extension into a second app.

**DEPENDENCIES:** Evidence staging, capture-token endpoints.

**MIGRATION:** Parent issues the token from Settings → Students (`POST /api/auth/capture-token`). Extension field stays “device token.” Generating a new token revokes the previous one.

**RISK:** Families still pasting an old parent JWT until they generate a capture token.

**PRIORITY:** Token scope is in place. Icons are in place.

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

**CURRENT:** Three SQLite files. SQLAlchemy 2. Cross-DB ids without FKs. `init_databases()` on boot runs `create_all` plus the ordered patches in `app/schema_patches.py` on catalog, admin, the shared tenant file, and every `tenant_*.db`.

**PROBLEM:** A model field without a matching patch is created on new files and missing on old tenant files. That is now one documented list, not Alembic theater plus a second list.

**TARGET:** Keep SQLite three-file layout. **One schema story:** `create_all` + `app.schema_patches`. Alembic revisions 0001–0012 stay on disk as history and are not executed. Do not add new Alembic revisions as the way to ship a column.

A later Alembic-for-real (new version trees, stamp after inspect matches models, never replay 0001) is allowed only as a dedicated session with backups.

**DEPENDENCIES:** Entire backend.

**MIGRATION:** Additive patches only. Do not change engines. Do not drop household_settings date columns.

**RISK:** Forgetting a patch on an existing tenant file.

**PRIORITY:** High (honesty of process is in place; patch discipline remains).

---

### Alembic / migrations — ARCHIVE (not the runner)

**CURRENT:** Revisions 0001–0012 remain in `alembic/versions/` as archaeology. `env.py` refuses `alembic upgrade` so those scripts cannot run. `alembic.ini` does not point at live catalog.db. Runtime schema is `init_databases()` → `create_all` + `app.schema_patches`.

**PROBLEM (met):** The tree used to look like migrations exist. They did not run. 0001 does not match live models. 0002 mixes catalog and tenant in one database. 0007 ALTERs `curriculum_plans` that the chain never created. Admin tables are absent from the chain.

**TARGET (met):** One runner. Patches-only. Do not replay 0001. Do not stamp live files as Alembic heads in this phase (there is no safe head that equals create_all without a new, unused revision tree).

**DEPENDENCIES:** Deploy/entrypoint.

**MIGRATION:** None for live data. Operators copy `tenant_*.db` to roll back a bad additive patch.

**RISK:** Someone generating a new revision and assuming it runs. `script.py.mako` and `alembic/README.md` say not to.

**PRIORITY:** Honesty of process is in place.

---

### Frontend architecture — KEEP (REFACTOR edges)

**CURRENT:** One HTML shell, one `app.js`, hash routes, global `state`, `data-action` handlers. Chart.js CDN. Logo at `static/curiculy-logo.png`. Shell assets share `SHELL_VERSION`.

**PROBLEM:** ~8500 lines in one file. No bundler — that is a **fit** for this repo (Docker bind-mounts JS; no npm in production).

**TARGET:** Stay a server-rendered shell + vanilla SPA until a second client (mobile native) exists. Split `app.js` by feature only when two people regularly collide. Do not introduce React/Vue as an architecture goal.

**DEPENDENCIES:** All UX.

**MIGRATION:** Mechanical file split later; behavior unchanged.

**RISK:** Hash routing and global state make a framework rewrite high-cost and low-value.

**PRIORITY:** Low for splitting JS. Assets/SW lockstep is in place.

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

**PROBLEM:** No documented bootstrap (first admin, first invite). Bind-mounts are good for this host, not a generic public deploy.

**TARGET:** Compose remains the homelab/SaaS-single-node shape. Secrets from env or a gitignored `.env` (see below). Document: create first admin, generate invite, set `JWT_SECRET`, optional Ollama. Add CI running pytest on the `dev` image. Reverse proxy can stay outside the repo until there are multiple services.

**DEPENDENCIES:** All runtime.

**MIGRATION:** Mail password must be rotated if it was ever committed. Reverse proxy later.

**RISK:** Mail stops until env is set (correct). Process will not boot in non-dev without a strong `JWT_SECRET`.

**PRIORITY:** High (README/bootstrap). Secrets handling for JWT and SMTP is in place.

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
| `OLLAMA_HOST` / `OLLAMA_MODEL` | No | Optional PDF parse and tutoring. |

Database URLs, `EVIDENCE_DIR`, `INDEX_HTML_PATH`, and `STATIC_DIR` are set in compose for the container layout.

---

## Target runtime shape

```text
Parents / kids / extension
        │
        ▼
   HTTPS (future proxy) → FastAPI :80
        │
        ├── JWT → admin.db (who, capture tokens) + tenant_{uuid}.db (planner)
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
