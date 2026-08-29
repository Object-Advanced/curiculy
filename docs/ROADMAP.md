# Curiculy Roadmap (architecture only)

This is an implementation **order**, not a commitment to rewrite. Do not implement from this file until a given item is scheduled as work.

Goal: simplify toward the target in `ARCHITECTURE.md` without breaking families who already have `tenant_*.db` files and evidence on disk.

---

## 1. The 10 most important architectural decisions

Make these explicitly. Reversing them later is expensive.

1. **Isolation stays file-per-household SQLite** until a real multi-tenant operational need (many writers, hosted HA) appears. Do not “prepare for Postgres” by adding `tenant_id` everywhere now.

2. **`Assignment` is the only calendar event.** Do not revive `scheduled_work` for new features.

3. **Two curriculum intakes remain:** book auto-schedule (pages) and pacing guides (week/day). Both write assignments.

4. **One operational school year** for scheduling: named `SchoolYear` dates + settings weekdays/colors. Stop dual start/end.

5. **Enrollment is a side effect of scheduling**, not a required Settings ritual, so portfolios tell the truth.

6. **Evidence is private.** Files are never world-readable. The extension gets an upload-scoped credential, not a parent session.

7. **Ollama is optional.** Calendar generation must not require it. PDF parse and tutoring may degrade.

8. **The SPA stays a FastAPI-served vanilla shell** until there is a second client. No framework migration as an architecture goal.

9. **Schema changes have one runner** (`create_all` + `app.schema_patches` on all DBs). Alembic 0001–0012 are archive only; `alembic upgrade` is refused.

10. **Compliance packets and taxonomy UIs wait** for a concrete state form. Portfolios are the printable-record product.

---

## 2. The 10 highest-risk technical issues

These can leak data, lock families out, or destroy calendars.

1. SMTP password was previously in compose — treat as leaked until rotated; keep it in `.env` only (**env-only is in place**).
2. Unauthenticated `/evidence` mount (**authenticated file GET is in place**).
3. Guessable/weak `JWT_SECRET` in production-like compose (**fail-closed in non-dev is in place**).
4. Parent JWT on a child’s Chromebook (extension) (**capture credential is in place**).
5. Informal schema patches missing a column on old `tenant_*.db` files (**one patch module is in place**; forgetting a new ALTER is still the risk).
6. Recalibrate / shared-group assignment updates (easy to desync siblings).
7. Pacing/plan-apply writing hundreds of rows (partial commit = torn year).
8. PDF worker using a request-scoped SQLAlchemy session after the HTTP response (**own tenant session is in place**).
9. Stale service worker serving old `app.js` (silent “bug that was already fixed”) (**SHELL_VERSION lockstep is in place**).
10. Replaying historical Alembic `0001` against live databases (wrong shape) (**`alembic upgrade` is refused**).

---

## 3. The 10 safest improvements

Low blast radius, high clarity. Good first PRs.

1. Move mail (and JWT) secrets to environment; stop committing passwords. Rotate mail.
2. Align `sw.js` and `index.html` cache-query versions (one token) (**done**).
3. Add missing logo / extension icons, or drop the `src`/`icons` entries (**done**; files were already on disk, now tested).
4. Document in UI that All Students shows **shared** lessons only. (**done**)
5. Return a JWT from `POST /auth/register` (additive). (**done**)
6. Auto-insert `enrollments` on pacing commit / plan apply (IntegrityError = already enrolled) (**done**).
7. Allow child `PATCH` status on own assignments (with tests) (**done**).
8. Rename comments on `ai_generator.py` so nobody wires Ollama into commit “to finish it.” (**done**)
9. Add README: compose port 3040, first invite, `JWT_SECRET`, optional Ollama. (**done**)
10. Pytest: one test that provisions `tenant_{uuid}.db` and routes a JWT without overriding `get_tenant_db`.

---

## 4. What NOT to refactor yet

Leave these alone until the critical/high items above are done — or until a product requirement forces them.

- Migrating SQLite → Postgres / a single shared tenant schema
- Rewriting `app.js` in React/Vue/Svelte
- Introducing Celery, Redis, or a job queue (BackgroundTasks is enough)
- Building jurisdiction / compliance packet UI
- Building subject taxonomy admin
- Merging `curricula` and `curriculum_plans` into one table
- Merging attendance into exceptions (different meanings)
- Deleting `/books/*` or `/catalog/from-isbn` before checking for external callers
- Dropping `scheduled_work` tables before a `SELECT COUNT` on real tenant files (models are already unmapped)
- Changing `/calendar` to include private lessons without a product decision
- Splitting the monolith into microservices
- GraphQL
- Replacing WeasyPrint with a browser print-only workflow
- Making auto-schedule require Ollama for titles

---

## 5. Recommended implementation order

Phases are sequential. Do not start phase 3 while phase 1 secrets are still in git.

### Phase 0 — Safety (days)

| Work | Domain |
|---|---|
| Rotate mail credentials; env-only secrets | Deployment — **done** (rotate the mailbox if it was ever committed) |
| Require strong `JWT_SECRET` when `DEV_MODE` is false | Auth — **done** |
| Authenticate evidence file reads; keep write paths | Evidence — **done** |
| SW / HTML cache version lockstep | Offline — **done** |

**Exit:** No secrets in compose; work samples not publicly fetchable; deploys actually update JS.

### Phase 1 — Child and extension trust (days–week)

| Work | Domain |
|---|---|
| Child PATCH own assignment status | Assignments / Students — **done** |
| Staging-only device token for extension | Auth / Extension — **done** |
| Restore extension icons | Extension — **done** |

**Exit:** Chromebook capture token cannot load `/admin` or email portfolios (**done**). Kid can check off today (**done**).

### Phase 2 — One school year, honest portfolios (week)

| Work | Domain |
|---|---|
| Wizard + year modal write the same `SchoolYear` | School years — **done** |
| Stop using settings as a second date range (weekdays/colors only) | School years — **done** (date columns remain as a mirror) |
| Auto-enrollment on schedule/apply | Enrollments — **done** |
| Copy/help on empty reading list if still no enrollment | Portfolios — **done** |

**Exit:** One year on the grid and on the PDF; scheduling a book fills the reading list.

### Phase 3 — Schema honesty (week, ops-heavy)

| Work | Domain |
|---|---|
| Decide Alembic-real vs patches-only; document it | Database / Alembic — **done (patches-only)** |
| Stamp existing DBs; never run 0001 on prod | Alembic — **0001 cannot run** (`alembic upgrade` refused; no stamp) |
| Open a fresh Session in PDF background worker | AI / plans — **done** |
| Optional: tenant-file integration test | Testing — schema upgrade tests in `test_schema.py` |

**Exit:** Adding a column has a checklist that updates every `tenant_*.db`.

### Phase 4 — Fold duplicates (ongoing, opportunistic)

| Work | Domain |
|---|---|
| One exceptions router; aliases for old paths | Exceptions / API |
| Catalog as the ISBN HTTP name; books as alias | Catalog / Books |
| Drop unused tables after COUNT=0 | Assignments leftover (**models unmapped**; DROP TABLE later) |
| Exception API module merge | API |

**Exit:** Fewer ways to do the same write.

### Phase 5 — Product polish (when needed)

| Work | Domain |
|---|---|
| Notify parent when PDF plan is `ready` / `failed` | Notifications |
| Optional LLM titles in pacing **preview**, still commitable offline | Pacing / AI |
| Attendance auto-suggest from vacation exceptions | Attendance (DEFER if busy) |
| CI: `docker compose run tests` | Deployment / Testing |
| First-admin bootstrap documented | Deployment |

### Phase 6 — SaaS scale (not now)

Only when invite-gated hosting is not enough:

- Reverse proxy and TLS in or next to compose
- Backup job for `admin.db`, `catalog.db`, `tenant_*.db`, evidence volume
- Postgres **if** SQLite file count or write contention is measured, not imagined
- Compliance templates **if** a state is a customer

---

## Classification summary (all analyzed domains)

| Domain | Label | Priority |
|---|---|---|
| Authentication | REFACTOR | Critical / High |
| Multi-tenancy | KEEP | — |
| Students | KEEP | Child complete **done** |
| Households | REFACTOR | Low |
| School years | KEEP | Operational year **done**; drop settings date columns later |
| Enrollments | KEEP | Auto-create on schedule **done** |
| Curricula | KEEP | Low |
| Curriculum resources | KEEP | Low |
| Curriculum plans | KEEP | PDF worker session **done** |
| Assignments | KEEP | Critical (center) |
| Pacing | KEEP | Low |
| Calendar | KEEP | Low |
| Attendance | KEEP | Low |
| Exceptions | CONSOLIDATE | Medium |
| Evidence | REFACTOR | Critical |
| Portfolios | KEEP | High (data + mail) |
| Homework Help | KEEP | Low |
| AI / Ollama | KEEP | Medium |
| Catalog / ISBN | KEEP | Low |
| Books | CONSOLIDATE | Low |
| Notifications | KEEP | Low |
| Offline / PWA | KEEP + REFACTOR | High |
| Chrome extension | KEEP + REFACTOR | High |
| Compliance | DEFER | Low |
| Taxonomy | DEFER | Low |
| Database architecture | REFACTOR process | Patch runner **done**; engines unchanged |
| Alembic | ARCHIVE | Not the runner; 0001–0012 kept |
| Frontend | KEEP + REFACTOR edges | High (assets) / Low (split) |
| API | KEEP + REFACTOR dupes | Medium |
| Testing | REFACTOR | Medium |
| Deployment | REFACTOR | Critical |

---

## How to use this with the other docs

| Doc | Use when |
|---|---|
| `ARCHITECTURE.md` | Debating whether to add a table or a new intake path |
| `CODEBASE_MAP.md` | Finding the file to change |
| `DOMAIN_MODEL.md` | Naming things in UI and schema |
| `TECHNICAL_DEBT.md` | Writing a PR description for a cleanup |
| `ROADMAP.md` | Choosing the next slice |

If a proposal conflicts with the ten decisions in section 1, it is probably a rewrite, not a simplification.
