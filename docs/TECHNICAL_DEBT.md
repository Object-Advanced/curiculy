# Curiculy Technical Debt

Ordered by **importance to a homeschool product**, not by abstract purity.

Confidence: **CONFIRMED** / **LIKELY** / **POSSIBLE** as in the audit.

---

## Critical

### 1. SMTP credentials must stay out of git

**CONFIRMED (fixed).** Compose interpolates `MAIL_USERNAME` and `MAIL_PASSWORD` from the environment. `app/config.py` has no dummy mailbox password; `mail_connection()` uses those settings as-is. Copy `.env.example` to `.env` (gitignored).

**Why it matters:** Those values were previously committed. Rotate the mailbox password if this tree was ever copied or pushed before the rewrite.

**Target:** Env or a gitignored secret file only. Never put real passwords in `docker-compose.yml`.

---

### 2. `/evidence` is public StaticFiles

**CONFIRMED (fixed).** `GET /api/evidence/files/{tenant}/{filename}` requires a JWT. Parents may read files in their household folder. Children may read only files attached to their own assignments. The public StaticFiles mount is gone.

**Why it matters:** Work samples are the most sensitive family data after passwords. UUID filenames are not access control.

**Target:** Authenticated file route or signed URLs. Then remove the public mount.

---

### 3. Weak JWT secret defaults

**CONFIRMED (fixed).** Non-dev startup (`entrypoint.sh` and app lifespan) refuses a missing, placeholder, or short `JWT_SECRET`. Compose no longer supplies a fallback secret. `DEV_MODE=true` still allows an explicit local placeholder when `JWT_SECRET` is unset.

**Why it matters:** Tokens are household keys (planner + evidence + children).

**Target:** Refuse to boot in non-dev without a strong secret.

---

## High

### 4. Schema evolution is informal

**RESOLVED (runner).** Boot runs `create_all` plus the ordered, idempotent lists in `app/schema_patches.py` for catalog, admin, and every `tenant_*.db`. Alembic `env.py` refuses to replay 0001–0012. Historical revision files are kept and are not authoritative.

**Why it mattered:** The tree pretended Alembic was the source of truth while live files used ad-hoc ALTER. Replaying `0001` would be the wrong shape.

**Target (met):** One process. Adding a column still requires a model change **and** a patch (create_all will not ALTER existing files). Tests cover fresh files, old files, a second apply, and no row loss.

**Remaining:** Forget the patch and old tenant files lag. That is patch discipline, not dual runners.

---

### 5. Extension stores a parent JWT

**RESOLVED.** Capture uses `Authorization: Bearer` with a capture credential (`scope=evidence:write`). Parent login JWTs are rejected for everything except staging writes, and the extension is instructed to paste the capture token from Settings → Students.

**Why it mattered:** A school Chromebook token was a full parent session (calendar, students, mail trigger, etc.).

**Target (met):** Token that can only `POST /api/evidence/staging`. Revocable on `admin.db`. Not accepted as a parent session.

---

### 6. Children cannot complete assignments

**RESOLVED.** `PATCH /api/assignments/{id}/status` allows a parent (any household assignment, shared-group sync) or a child (own `student_id` only, no sibling sync). PUT/delete/grade/evidence stay parent-only. My Work has the same complete checkbox as the parent Kids checklist.

**Why it mattered:** “My work” was a viewer, not a checklist. Homeschool kids checking boxes is a core loop.

**Target (met):** Child may PATCH status (and only status) on their `student_id`.

---

### 7. Two school-year date sources

**RESOLVED (columns remain).** Named `SchoolYear` rows are the read source for operational dates. `GET /settings/school-year` no longer prefers `household_settings` dates. Weekdays and exception colors stay on settings. Settings start/end are still written as a mirror and are not dropped.

**Why it mattered:** Pacing/grid used settings dates; portfolios used `SchoolYear` ids. Drift meant the PDF window and the generated lessons could disagree.

**Later:** Stop writing the settings date mirror, then drop those columns in a real schema pass. Do not drop them from live `tenant_*.db` files in this phase.

---

### 8. Enrollments not created when work is scheduled

**RESOLVED.** Pacing commit and plan-apply insert or reuse `enrollments` in the same transaction as the assignments. Preview does not. Settings POST still works and still 409s on duplicates.

**Why it mattered:** Parents who only auto-schedule got empty book lists on state logs.

**Later:** Optional backfill from historical assignments; UI copy that Settings is the override, not the primary path.

---

### 9. Service worker cache bust mismatch

**RESOLVED.** `sw.js` declares `SHELL_VERSION`. `index.html` and `app.css` query strings use that same token. `SHELL_CACHE` is named from it, so a bump deletes the previous shell. Tests fail if the strings drift.

**Why it mattered:** After deploy, the SW could keep old JS while HTML asked for new (or the reverse), producing “fixed in code, not on the iPad” bugs.

**Target (met):** One version string for the application shell.

---

### 10. Missing brand and extension icons

**RESOLVED.** `static/curiculy-logo.png` is the served logo (same image as the root `Curiculy Logo.png` source). Extension toolbar sizes 16/32/48/128 and `extension/icons/logo.png` are present. Tests check the files exist and the app serves them.

**Why it mattered:** Broken favicon; Chrome may refuse or ugly-default the extension.

**Target (met):** Add assets or remove references.

---

## Medium

### 11. Dual exception HTTP APIs

**CONFIRMED (MIGRATE FIRST).** `/exceptions` vs `/calendar/exceptions` on the same table. The SPA uses both: settings list/create on `/exceptions`, year-grid dates/toggle/holidays on `/calendar/exceptions`.

**Why it matters:** Two places to get toggle vs titled range wrong.

**Next step:** One router module with aliases for the current paths. Do not delete either prefix until `app.js` is updated.

---

### 12. PDF import reuses the request Session in a background task

**RESOLVED.** `POST /curriculum/import-pdf` captures `tenant_uuid` and demo `jti`, then the worker calls `open_tenant_session` itself. It does not receive the request Session. Exceptions roll back that job session and mark `failed` on a second session. Success commits `ready` plus lessons on the job session. Both sessions are closed.

**Why it mattered:** FastAPI may close the yield-session when the request ends. Failed or half-written plans.

**Target (met):** Open a new tenant session inside the worker from `tenant_uuid` / plan id.

---

### 13. Dead parallel work/evidence tables

**RESOLVED (ORM).** `ScheduledWork` and `EvidenceCapture` models, unused read schemas, and `WorkStatus` / `ScheduleGrain` are gone. Available `data/` tenant files had COUNT=0 on both tables. Empty tables may still exist on disk; boot does not DROP them. Delete of a student or curriculum still clears leftover rows.

**Why it mattered:** Next feature may “complete” the old model by mistake.

**Target (met for code):** Stop mapping the old calendar. DROP TABLE later only after COUNT=0 on every real `tenant_*.db`.

---

### 14. Unused public endpoints

**CONFIRMED (API-only, keep).** SPA never calls `POST /catalog/from-isbn`, `/books/*`, `POST /curricula/import`. Tests and OpenAPI do. Architecture: do not delete because the SPA is quiet.

**Why it matters:** Two ways to do ISBN → library. Confusing as two official UI paths; fine as API.

**Next step:** Point tests at `/catalog/lookup-isbn` + `POST /curricula`, then consider aliases or deprecation. Do not remove `/curricula/import` until a UI or a decision that tree-import is retired.

---

### 15. Tests do not prove tenant files

**CONFIRMED.** `conftest.py` uses one memory DB and often overrides the current user.

**Why it matters:** Provisioning `tenant_{uuid}.db` and JWT routing can break without a red test.

**Target:** A few integration tests with real file URLs.

---

### 16. `ai_generator` name vs behavior

**RESOLVED (comments).** Arithmetic page split. Module comments no longer promise an LLM on commit. Filename can wait.

**Why it mattered:** Future contributors will wire Ollama into commit and make scheduling depend on a daemon.

**Target (met for comments):** Keep math as default; LLM titles optional later.

---

### 17. Compliance and taxonomy stubs

**CONFIRMED.** `NotImplementedError` modules; taxonomy tests without APIs.

**Why it matters:** Looks like unfinished MVP. It is leftover foundation.

**Target:** Defer. Do not build admin UIs.

---

## Low

### 18. Color palettes duplicated in JS and Python

**LIKELY** drift if one side changes.

### 19. Health check skips tenant DB

**CONFIRMED.** Catalog + admin only.

### 20. Register does not return a JWT

**RESOLVED.** `POST /auth/register` returns the same `{access_token, token_type}` body as login. The SPA stores it and enters the app without a second password submit.

**Why it mattered:** Extra login step after a successful invite.

**Target (met):** Issue a token on register.

---

### 21. All Students calendar shows shared lessons only

**RESOLVED (copy).** The query is unchanged. The All Students calendar header now says private lessons are on individual calendars.

**Why it mattered:** Parents could think siblings’ private work was missing.

**Target (met):** Documentation/copy, not a merge of queries.

---

### 22. No README / CI in repo

**RESOLVED (README).** Root `README.md` covers `.env`, compose port 3040, first invite, and the test command. CI is still absent.

**Why it mattered:** Bootstrap of first admin + invite was tribal knowledge.

**Target:** README (met). CI later.

### 23. Homework-help test volume

**CONFIRMED** small module. Prompts are high-risk if changed without tests.

### 24. Cross-DB integer ids without FK

**CONFIRMED** and **intentional**. Debt is operational: never delete catalog editions that tenants reference.

### 25. Pacing commit is two engines, not one transaction

**CONFIRMED.** `SyllabusCommitter` writes assignments, units, and enrollments on the tenant session and commits that first. It then commits the catalog session, which today only persists a book `page_count` bump from `_sync_page_count`. Plan-apply is a single tenant `commit()`.

**Why it matters:** If the catalog commit failed after the tenant commit, the calendar would still be complete; only shared ISBN page-count could lag. Tests use one memory DB, so this split is invisible there. Not a torn assignment list.

**Target:** Later session. Do not wrap catalog and tenant in one transaction (they are different SQLite files). Retry or accept catalog page-count drift.

---

## What is not debt

These look messy in a generic audit and are **correct for Curiculy**:

| Item | Why keep |
|---|---|
| SQLite per family | Isolation, backup, privacy |
| Two curriculum intakes | Books vs vendor grids |
| Vanilla `app.js` | No npm in the image; bind-mount deploys |
| Demo in-memory DB | Try-before-invite without leftover files |
| Invite-only registration | Matches current go-to-market |
| String grades | Homeschool scores are not one numeric scale |
| Staging evidence inbox | Extension captures are not yet lessons |

---

## Suggested burn-down order

See `docs/ROADMAP.md`. Do not mix a schema-engine rewrite with a UI redesign. Dual school-year dates and auto-enrollment on schedule are in place; empty-reading-list copy is next if still needed.


