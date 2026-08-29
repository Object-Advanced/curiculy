# Curiculy Technical Debt

Ordered by **importance to a homeschool product**, not by abstract purity.

Confidence: **CONFIRMED** / **LIKELY** / **POSSIBLE** as in the audit.

---

## Critical

### 1. SMTP credentials must stay out of git

**CONFIRMED (fixed in tree).** Compose now interpolates `MAIL_USERNAME` and `MAIL_PASSWORD` from the environment. Copy `.env.example` to `.env` (gitignored).

**Why it matters:** Those values were previously committed. Rotate the mailbox password if this tree was ever copied or pushed before the rewrite.

**Target:** Env or a gitignored secret file only. Never put real passwords in `docker-compose.yml`.

---

### 2. `/evidence` is public StaticFiles

**CONFIRMED.** `app/main.py` mounts the evidence directory with no JWT.

**Why it matters:** Work samples are the most sensitive family data after passwords. UUID filenames are not access control.

**Target:** Authenticated file route or signed URLs. Then remove the public mount.

---

### 3. Weak JWT secret defaults

**CONFIRMED.** `app/config.py` defaults `jwt_secret` to `insecure-dev-secret`. Compose uses a placeholder if `JWT_SECRET` is unset.

**Why it matters:** Tokens are household keys (planner + evidence + children).

**Target:** Refuse to boot in non-dev without a strong secret.

---

## High

### 4. Schema evolution is informal

**CONFIRMED.** Boot runs `create_all` plus `ALTER` lists in `app/db.py`. Alembic `env.py` does not replay revisions. Existing `tenant_*.db` files only gain columns if the ALTER list includes them.

**Why it matters:** The next column added in a model will work on new tenants and silently miss old ones unless someone updates `_ensure_tenant_schema`.

**Target:** One process — real Alembic over catalog, admin, and every `tenant_*.db`, **or** a single documented patch module and no Alembic theater.

**Risk:** Replaying revision `0001` against live files would be wrong (old shape).

---

### 5. Extension stores a parent JWT

**CONFIRMED.** Capture uses `Authorization: Bearer` with the options “device token.”

**Why it matters:** A school Chromebook token is a full parent session (calendar, students, mail trigger, etc.).

**Target:** Token that can only `POST /api/evidence/staging` (and maybe GET health).

---

### 6. Children cannot complete assignments

**CONFIRMED.** `PATCH /api/assignments/{id}/status` uses `require_parent`. Kid UI has no complete checkbox that can succeed.

**Why it matters:** “My work” is a viewer, not a checklist. Homeschool kids checking boxes is a core loop.

**Target:** Child may PATCH status (and only status) on their `student_id`.

---

### 7. Two school-year date sources

**CONFIRMED.** `school_years` and `household_settings` both store start/end. Wizard writes years; the modal writes settings and then copies onto the latest year.

**Why it matters:** Pacing uses settings weekdays + dates; portfolios use `SchoolYear` ids. Drift = wrong window on evaluator PDFs vs generated lessons.

**Target:** See `ARCHITECTURE.md` — year dates on `SchoolYear`; settings keep weekdays and colors.

---

### 8. Enrollments not created when work is scheduled

**CONFIRMED.** Pacing and plan-apply do not insert `enrollments`. Portfolios build reading lists from enrollments.

**Why it matters:** Parents who only auto-schedule get empty book lists on state logs.

**Target:** Insert enrollment on commit/apply; keep the settings form as override.

---

### 9. Service worker cache bust mismatch

**CONFIRMED.** `sw.js` shells `app.js?v=20260828-widget-hug`; `index.html` loads `?v=20260828-pdf-ocr`.

**Why it matters:** After deploy, the SW may keep old JS while HTML asks for new (or the reverse), producing “fixed in code, not on the iPad” bugs.

**Target:** One version string.

---

### 10. Missing brand and extension icons

**CONFIRMED.** HTML and extension manifest reference PNG files not in the tree.

**Why it matters:** Broken favicon; Chrome may refuse or ugly-default the extension.

**Target:** Add assets or remove references.

---

## Medium

### 11. Dual exception HTTP APIs

**CONFIRMED.** `/exceptions` vs `/calendar/exceptions` on the same table.

**Why it matters:** Two places to get toggle vs titled range wrong.

**Target:** One router, two SPA screens.

---

### 12. PDF import reuses the request Session in a background task

**CONFIRMED** by comments in `ai_curriculum_worker.py`.

**Why it matters:** FastAPI may close the yield-session when the request ends, depending on version/behavior. Failed or half-written plans.

**Target:** Open a new tenant session inside the worker from `tenant_uuid` / plan id.

---

### 13. Dead parallel work/evidence tables

**CONFIRMED.** `ScheduledWork`, `EvidenceCapture` are cleaned on delete but not written by pacing/UI. `ScheduledWorkRead` has no router.

**Why it matters:** Next feature may “complete” the old model by mistake.

**Target:** After confirming empty tables in real DBs, drop models and delete-cleanup branches.

---

### 14. Unused public endpoints

**CONFIRMED.** SPA never calls `POST /catalog/from-isbn`, `/books/*`, `POST /curricula/import`.

**Why it matters:** Two ways to do ISBN → library. Tests keep books routes alive.

**Target:** Document API-only vs canonical SPA path; eventually alias books under catalog.

---

### 15. Tests do not prove tenant files

**CONFIRMED.** `conftest.py` uses one memory DB and often overrides the current user.

**Why it matters:** Provisioning `tenant_{uuid}.db` and JWT routing can break without a red test.

**Target:** A few integration tests with real file URLs.

---

### 16. `ai_generator` name vs behavior

**CONFIRMED.** Arithmetic page split. Comments still promise an LLM.

**Why it matters:** Future contributors will wire Ollama into commit and make scheduling depend on a daemon.

**Target:** Keep math as default; LLM titles optional later.

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

**CONFIRMED.** Extra login step.

### 21. All Students calendar shows shared lessons only

**CONFIRMED** by design. Debt is **documentation/copy**, not a merge of queries.

### 22. No README / CI in repo

**CONFIRMED.** Bootstrap of first admin + invite is tribal knowledge.

### 23. Homework-help test volume

**CONFIRMED** small module. Prompts are high-risk if changed without tests.

### 24. Cross-DB integer ids without FK

**CONFIRMED** and **intentional**. Debt is operational: never delete catalog editions that tenants reference.

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

See `docs/ROADMAP.md`. Do not mix a schema-engine rewrite with a UI redesign. Secrets and evidence auth first.
