# Curiculy Roadmap (architecture only)

Remaining work only. Completed hardening is described in `docs/ARCHITECTURE.md`. The 2026-09-01 reconciliation recorded 821 tests; the current suite is **892 tests passed**. The architecture-hardening / cleanup phase is **closed**.

Do not implement from this file until a given item is scheduled as work. Goal: simplify without breaking families who already have `tenant_*.db` files and evidence on disk.

---

## 1. The 10 most important architectural decisions

These stand. Reversing them later is expensive.

1. **Isolation stays file-per-household SQLite** until a real multi-tenant operational need (many writers, hosted HA) appears. Do not “prepare for Postgres” by adding `tenant_id` everywhere now.

2. **`Assignment` is the only calendar event.** Do not revive `scheduled_work` for new features.

3. **Two curriculum intakes remain:** book auto-schedule (pages) and pacing guides (week/day). Guide capture includes CSV, PDF+Ollama, paper sheet (OpenCV + Ollama vision), and the manual builder. Both intakes write assignments.

4. **One operational school year** for scheduling: named `SchoolYear` dates + settings weekdays/colors. `HouseholdSettings` does not store year dates.

5. **Enrollment is a side effect of scheduling**, not a required Settings ritual, so portfolios tell the truth.

6. **Evidence is private.** Files are never world-readable. The extension gets an upload-scoped credential, not a parent session.

7. **Ollama is optional for scheduling.** Calendar generation must not require it. PDF parse, paper handwriting, tutoring, and spark may degrade.

8. **The SPA stays a FastAPI-served vanilla shell** until there is a second client. No framework migration as an architecture goal.

9. **Schema changes have one runner** (`create_all` + `app.schema_patches` on all DBs). Alembic 0001–0012 are archive only; `alembic upgrade` is refused.

10. **Compliance packets and taxonomy UIs wait** for a concrete state form. Portfolios are the printable-record product.

---

## 2. Remaining high-risk items

These can still leak data, lock families out, or destroy calendars.

1. Forgetting a `schema_patches` ALTER on a new model column (old `tenant_*.db` files lag).
2. Recalibrate / parent shared-group assignment updates (easy to desync siblings).
3. Pacing/plan-apply writing hundreds of rows (partial commit = torn year). Catalog `page_count` is a second commit after the tenant calendar.
4. Replaying historical Alembic `0001` against live databases (wrong shape). `alembic upgrade` is refused; generating a new revision could still mislead.
5. `DEV_MODE=true` left on for a real family (full JWT bypass).
6. DROP leftover `scheduled_work` / `evidence_captures` without COUNT=0 on each real tenant file. This host’s empty leftover tables were already DROPped.

Mail secrets, public `/evidence`, weak Compose JWT defaults, parent JWT in the extension, PDF worker request-Session reuse, SW/HTML version drift, capture tokens opening a tenant file through `get_tenant_db`, and the `household_settings` date mirror are **already addressed** in source. Do not treat them as open roadmap items.

---

## 3. Remaining work (current)

Low-to-medium blast radius unless noted.

### Fold duplicates

| Work | Domain | Status |
|---|---|---|
| Catalog as the ISBN HTTP name; `/books/*` as alias | Catalog / Books | Investigated, not started. `/books/resolve` shares the resolver with lookup-isbn but not the response shape. GET `/books/isbn/{isbn}` and GET `/books/{id}` have no catalog twin. `POST /catalog/from-isbn` creates library rows; it is not a books alias. Do not delete. |

### Operator data

| Work | Domain | Status |
|---|---|---|
| Run leftover-table DROP against live family `tenant_*.db` files | Assignments leftover | **Done on this host.** Empty `scheduled_work` / `evidence_captures` DROPped on `./data/tenant_*.db`. Script remains for other disks (`COUNT(*) = 0` only, never deletes rows, not boot). |
| Optional backfill of enrollments for years scheduled before auto-enroll | Portfolios | **Done on this host** for proven rows (2 inserted). New pacing/plan writes stamp `assignments.curriculum_id`. Title-only historical plan rows stay skipped. |

### Product polish (when needed)

| Work | Domain | Status |
|---|---|---|
| Optional LLM titles in pacing **preview**, still commitable offline | Pacing / AI | Not implemented. Do not put Ollama on commit. |
| Attendance auto-suggest from vacation exceptions | Attendance | DEFER if busy. |
| Align paper vision with `OLLAMA_MODEL` (today hardcoded `llama3.2-vision`) | Paper intake | **Do not.** Text vs vision models. Optional later: separate `OLLAMA_VISION_MODEL` defaulting to `llama3.2-vision`. |

Tenant-file JWT tests, register access token, All Students copy, logo/extension icons, README, capture tokens, child status PATCH, paper intake, exception API consolidation, `legacy_tables.py` helper deduplication, capture isolation from `get_tenant_db`, SchoolYear date-column retirement, enrollment backfill (script + this-host apply), leftover-table DROP (script + this-host empty DROP), the shared PDF/homework `ollama_chat` fallback, catalog/admin-only `/api/health`, GitHub Actions pytest, persistent in-app notifications when a PDF or paper plan is `ready` / `failed`, and `assignments.curriculum_id` on new pacing/plan writes **are already in source**. They are not remaining hardening work.

---

## 4. What NOT to refactor yet

Leave these alone unless a product requirement forces them.

- Migrating SQLite → Postgres / a single shared tenant schema
- Rewriting `app.js` in React/Vue/Svelte
- Introducing Celery, Redis, or a job queue (BackgroundTasks is enough)
- Building jurisdiction / compliance packet UI
- Building subject taxonomy admin
- Merging `curricula` and `curriculum_plans` into one table
- Merging attendance into exceptions (different meanings)
- Deleting `/books/*` or `/catalog/from-isbn` (SPA-quiet is not proof of no caller; GET `/books` has no catalog twin; `from-isbn` is not `POST /curricula`)
- Dropping `scheduled_work` tables before a `SELECT COUNT` on real tenant files (models are already unmapped)
- Changing `/calendar` to include private lessons without a product decision
- Splitting the monolith into microservices
- GraphQL
- Replacing WeasyPrint with a browser print-only workflow
- Making auto-schedule require Ollama for titles
- Merging `ollama.AsyncClient` and raw `httpx` `/api/chat` into one generic client
- Pointing paper vision at `OLLAMA_MODEL` (text vs vision)
- Failing `GET /api/health` because one `tenant_{uuid}.db` is malformed or locked
- Converting the default pytest `client` from in-memory SQLite to per-test `tenant_{uuid}.db` files
- Turning paper intake into a second calendar object

---

## 5. SaaS scale (not now)

Only when invite-gated hosting is not enough:

- Reverse proxy and TLS in or next to compose
- Backup job for `admin.db`, `catalog.db`, `tenant_*.db`, evidence volume
- Postgres **if** SQLite file count or write contention is measured, not imagined
- Compliance templates **if** a state is a customer

---

## Classification summary (current)

| Domain | Label | Remaining |
|---|---|---|
| Authentication | KEEP | `DEV_MODE`; JWT denylist vs entropy |
| Multi-tenancy | KEEP | Patch discipline |
| Students | KEEP | Palette duplication |
| Households | KEEP | One-household rule is product, not schema |
| School years | KEEP | Date source is SchoolYear only |
| Enrollments | KEEP | Title-only historical plan rows stay skipped |
| Curricula | KEEP | API-only import unused by SPA |
| Curriculum resources | KEEP | Cross-DB ids |
| Curriculum plans | KEEP | Vision model stays distinct from `OLLAMA_MODEL` |
| Assignments | KEEP | Recalibrate / shared-group sync; nonempty leftover tables on other disks |
| Pacing | KEEP | Filename; two-engine commit |
| Calendar | KEEP | Shared-only is by design |
| Attendance | KEEP | Auto-fill DEFER |
| Exceptions | KEEP | Optional titled-row edit/delete UI later |
| Evidence | KEEP | Nonempty leftover capture tables on other disks |
| Portfolios | KEEP | Title-only historical plan rows |
| Homework Help | KEEP | Thin tests |
| AI / Ollama | KEEP | Two HTTP stacks on purpose; optional for scheduling |
| Catalog / ISBN | KEEP | lookup-isbn is SPA; `from-isbn` API-only library create |
| Books | KEEP | Dictionary HTTP; GET routes have no catalog twin |
| Notifications | KEEP | Email/push not requested |
| Offline / PWA | KEEP | Lockstep already tested |
| Chrome extension | KEEP | Broad host_permissions |
| Compliance | DEFER | Stub |
| Taxonomy | DEFER | No CRUD UI |
| Database architecture | KEEP | Additive patches plus the settings-date retirement |
| Alembic | ARCHIVE | Not the runner |
| Frontend | KEEP | Do not framework-rewrite |
| API | KEEP | `/books` dictionary HTTP kept; not aliased onto catalog |
| Testing | KEEP | Homework-help coverage is thin |
| Deployment | KEEP | GitHub Actions pytest; no in-repo proxy |

---

## How to use this with the other docs

| Doc | Use when |
|---|---|
| `ARCHITECTURE.md` | What the system is today |
| `CODEBASE_MAP.md` | Finding the file to change |
| `DOMAIN_MODEL.md` | Naming things in UI and schema |
| `TECHNICAL_DEBT.md` | Current unresolved debt only |
| `ROADMAP.md` | Choosing the next remaining slice |
| `IMPLEMENTATION_RECONCILIATION.md` | Independent verification vs source (821 at that pass) |
| `POST_HARDENING_AUDIT.md` | Historical 2026-08-29 findings, then current-state note |

If a proposal conflicts with the ten decisions in section 1, it is probably a rewrite, not a simplification.
