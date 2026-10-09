# Curiculy post-hardening audit

This file has two layers. Do not mix them.

1. **Historical (2026-08-29):** the fourteen hardening checks and the suite count **786**. That pass did not change application source. Those fourteen checks still hold.
2. **Current:** `docs/IMPLEMENTATION_RECONCILIATION.md` re-verified the tree on 2026-09-01 (**821 passed**). Later consolidations, capture-token isolation, SchoolYear date-column retirement, enrollment backfill, leftover-table DROP, the shared Ollama AsyncClient helper, catalog/admin-only `/api/health` contract tests, GitHub Actions pytest, physical tenant persistence tests, PDF/paper plan processing notifications, and `assignments.curriculum_id` bring the suite to **892 passed, 0 failed, 0 skipped**. Architecture docs match source. The architecture-hardening / cleanup phase is **closed**. Several “unresolved” items in the historical sections below are **no longer unresolved**.

**Authoritative current architecture:** `docs/ARCHITECTURE.md`  
**Authoritative remaining debt:** `docs/TECHNICAL_DEBT.md` and `docs/ROADMAP.md`  
**Independent item-by-item evidence:** `docs/IMPLEMENTATION_RECONCILIATION.md`

---

## Current state (2026-09-01)

Hardening is complete in source. No reconciliation item is REGRESSED or DOCUMENTATION-ONLY.

| Topic | Current fact |
|---|---|
| Suite | **892 passed**, 0 failed, 0 skipped |
| README | Exists (`README.md`). Bootstrap, port 3040, `JWT_SECRET`, tests. Invite INSERT must include `tenant_uuid` (NOT NULL). |
| Register token | `POST /api/auth/register` returns `{access_token, token_type}` (201). SPA stores it. |
| All Students copy | Header states shared lessons only; private work is on individual calendars. Query unchanged. |
| Logo / extension icons | `static/curiculy-logo.png` and `extension/icons/*` present and tested. |
| Tenant-file JWT tests | `tests/test_auth.py` provisions `tenant_{uuid}.db` and routes a JWT without overriding `get_tenant_db`. Default `conftest.py` `client` stays in-memory on purpose. |
| Paper intake | Live. `GET /api/curriculum/paper-template`, `POST /api/curriculum/import-paper`. OpenCV + `qrcode` + `numpy` on the request; Ollama vision in `paper_vision_worker.py` (own session; model `llama3.2-vision`). Lands on `curriculum_plans` then apply → assignments. |
| SchoolYear dates | Named year is the only operational date store. `HouseholdSettings` has weekdays and colors. Leftover settings date columns are backfilled into `SchoolYear` when missing, then dropped on boot. |
| Enrollments | Unique on student + curriculum + year. Auto-create on pacing commit and plan-apply. New writes stamp `assignments.curriculum_id`. Operator `scripts/backfill_enrollments.py` reconstructs proven rows (stored id or resource/unit). Title-only plan rows skipped. Not boot. This host inserted 2 proven enrollments. |
| Exception APIs | One prefix: `/api/exceptions` (list, create, dates, toggle, import-holidays). `/api/calendar/exceptions` removed. Colors remain on `/api/settings/exception-colors`. |
| Legacy tables | ORM models gone. Operator script `scripts/drop_legacy_tables.py` (dry-run / `--apply`; DROP only when `COUNT(*) = 0`; never deletes rows). Boot does not DROP. This host DROPped empty leftover tables on `./data/tenant_*.db`. |
| `legacy_tables.py` | One implementation of each row-clear helper. Does not DROP tables. |
| Ollama | Optional for scheduling. Four call sites, two stacks: PDF + homework (`ollama.AsyncClient`); spark + paper vision (`httpx` `/api/chat`). Vision model is `llama3.2-vision`, not `OLLAMA_MODEL`. Stacks kept (timeout / images / model class). |
| `get_tenant_db` | Application users only (`get_current_user`). Capture JWTs are refused. Staging uses `get_staging_tenant_db` + `require_staging_upload`. |
| Health | Catalog.db + admin.db `SELECT 1` only. Household `tenant_{uuid}.db` files are excluded on purpose. |
| Plan processing notifications | PDF and paper workers create one `curriculum_plan_ready` or `curriculum_plan_failed` inbox row in the same tenant session that records terminal status. The 202 request does not notify. |
| Assignment provenance | Nullable `assignments.curriculum_id` stamped on new pacing commits and plan applies. Additive schema patch. Historical title-only rows stay NULL. |

Historical “recommended next priorities” 1–5 in the 2026-08-29 text (README, register JWT, All Students copy, tenant-file test, empty-reading-list copy) are **done**. Exception-API consolidation is **done**. `legacy_tables.py` helper deduplication is **done**. Settings date-column retirement is **done**. Enrollment backfill is **done** (operator script; this host applied proven rows). Leftover-table DROP is **done** (operator script; this host DROPped empty tables). `/books` vs catalog was investigated: same dictionary, different HTTP contracts; routes kept. Dual Ollama stacks were investigated and kept. GitHub Actions pytest is **done**. Persistent in-app notifications when a PDF or paper plan is `ready` / `failed` are **done**. New pacing/plan writes stamp `assignments.curriculum_id`. The architecture-hardening / cleanup phase is **closed**. Remaining items are optional product polish — see `docs/ROADMAP.md`.

---

## Historical audit (2026-08-29)

**Scope then:** Compare the running tree to `docs/ARCHITECTURE.md` after the architecture-hardening roadmap. Application source was not changed for that audit.

**Method then**

- Read `ARCHITECTURE.md`, `CODEBASE_MAP.md`, `DOMAIN_MODEL.md`, `TECHNICAL_DEBT.md`, and `ROADMAP.md`.
- Inspect routers, `app/core/security.py`, `app/config.py`, `app/db.py`, `app/schema_patches.py`, models, SPA calls, the extension, Compose, and tests for the fourteen checks below.
- Ran the full suite: `docker compose --profile dev run --rm tests pytest -q --tb=line`.

**Suite then:** all tests passed (**786** collected). Only warning: Passlib `crypt` deprecation (third-party).

**Verdict then:** The hardening goals for this roadmap are met. Critical privacy and calendar invariants hold. What remains is documented leftover work (Phase 4+), operator hygiene, and a few small code smells — not open holes in the fourteen checks.

The fourteen checks themselves remain **CONFIRMED** on 2026-09-01. Paper intake was added after this historical pass and is a third **guide capture** method, not a second calendar.

---

## The fourteen checks (historical; still true)

| # | Check | Result |
|---|---|---|
| 1 | Evidence is tenant-private | **CONFIRMED** |
| 2 | Extension credentials cannot act as parent JWTs | **CONFIRMED** |
| 3 | JWT secrets cannot silently fall back to insecure production defaults | **CONFIRMED** |
| 4 | SMTP credentials are not hardcoded | **CONFIRMED** |
| 5 | Children can complete only their own assignments | **CONFIRMED** |
| 6 | SchoolYear is the canonical operational year | **CONFIRMED** (settings date columns retired) |
| 7 | Scheduling creates/verifies Enrollment | **CONFIRMED** |
| 8 | PDF background workers own their DB sessions | **CONFIRMED** (paper vision worker later copied this pattern) |
| 9 | Schema management has one documented authoritative strategy | **CONFIRMED** |
| 10 | Legacy entities identified for removal were addressed appropriately | **CONFIRMED** (models gone; tables not dropped) |
| 11 | No regressions in the two curriculum intake paths | **CONFIRMED** (paper is an additional guide capture) |
| 12 | SQLite-per-household remains intact | **CONFIRMED** |
| 13 | Ollama remains optional for core scheduling | **CONFIRMED** |
| 14 | Assignment remains the sole calendar entity | **CONFIRMED** |

---

## What was confirmed in 2026-08-29 (abridged)

The body of checks 1–14 in the original audit is unchanged in substance: authenticated evidence GET, capture tokens, JWT fail-closed, env-only SMTP, child status PATCH, SchoolYear reads with settings date mirror, auto-enrollment, PDF worker own session, patches-only schema, unmapped leftover models, two book/guide intakes landing on assignments, file-per-household SQLite, Ollama off the calendar write path, Assignment as sole calendar entity.

Full original write-up of those fourteen sections is superseded for **file paths added after 2026-08-29** (paper services). Do not use this historical section as a file inventory.

---

## Historical “unresolved” list (2026-08-29) — with current status

None of these reversed a hardening check. Several are now done.

| Item | 2026-08-29 status | 2026-09-01 status |
|---|---|---|
| `HouseholdSettings` date columns | Mirror still written | **Done.** Columns removed from the model; leftover tenant columns backfilled then dropped on boot. |
| Dual exception HTTP APIs | SPA uses both prefixes | **Done.** Canonical `/api/exceptions`; `/api/calendar/exceptions` removed. |
| `/books/*` vs catalog | Tests still on books | **Investigated.** Same `BookResolver` / `book_editions`. Different HTTP contracts. GET `/books` has no catalog twin. `from-isbn` creates library rows. Routes kept. |
| Empty leftover `scheduled_work` / `evidence_captures` tables | Not DROPped | **Later:** operator script tested (COUNT=0 only). This host DROPped empty leftover tables. Boot still does not DROP. Non-empty tables stay. |
| Register does not return a JWT | Extra login | **Done.** Token on register. |
| All Students calendar is shared lessons only | UI copy missing | **Done.** Copy is in the calendar header. Query unchanged. |
| Tests use one in-memory DB | No JWT → `tenant_{uuid}.db` test | **Intentional split.** File JWT tests exist in `test_auth.py` (`auth_client`). Default `client` stays in-memory. Persistence across sqlite3 connections and two-file isolation are covered. |
| No root README / CI | Operator knowledge | **Done.** README and `.github/workflows/tests.yml` (Compose pytest on push and pull request). |
| Health check skips tenant files | Catalog + admin only | **Intentional.** Process health is `catalog.db` + `admin.db`. Household `tenant_{uuid}.db` files must not fail the probe. |
| Mailbox password rotation | Operator | **Still operator.** |
| `DEV_MODE=true` skips JWT | Local-only | **Still true.** |
| Historical enrollments | No backfill | **Later:** operator script + stored `curriculum_id` on new writes. Title-only week/day plan rows still cannot be reconstructed. |
| Compliance / taxonomy product | DEFER | **Still DEFER.** |
| `ai_generator.py` filename | Comments fixed | **Still a rename later.** |

---

## Historical “new technical debt” (2026-08-29)

These smells were real then and remain current except where noted:

- Duplicate helpers in `app/services/legacy_tables.py` — **fixed.** One implementation of each helper. Tables themselves are not DROPped.
- Capture tokens and `get_tenant_db` — **fixed.** Capture JWTs cannot open a tenant file through `get_tenant_db`. Staging uses `get_staging_tenant_db`.
- JWT strength is length + denylist — **still current.**
- Child completion vs shared groups — intended rule, not a hole.
- FastAPI description still says “compliance foundation” — **still current**, cosmetic.
- `CODEBASE_MAP.md` intro line — **fixed** in the 2026-09-01 doc pass.

---

## Historical recommended next priorities (2026-08-29)

Do **not** execute this list as if it were current.

| Then | Now |
|---|---|
| 1. Root README | Done |
| 2. JWT on register | Done |
| 3. All Students UI copy | Done |
| 4. Tenant-file JWT pytest | Done (`test_auth.py`) |
| 5. Empty-reading-list copy | Done |
| 6. Deduplicate `legacy_tables.py` | **Done.** One implementation of each helper. |
| 7. One exceptions router | **Done.** `/api/exceptions` only. |
| 8. CI | **Still remaining** |
| 9. DROP leftover tables after COUNT=0 | **Tooling done.** Script tested; operator must still run it on live files |
| 10. Stop writing the settings date mirror | **Done.** Model, writes, and leftover columns retired. |

Current remaining order: `docs/ROADMAP.md`.

---

## How to use this document

| Question | Look at |
|---|---|
| Did hardening land in 2026-08-29? | The fourteen checks (historical; still true) |
| What is the system today? | `docs/ARCHITECTURE.md` and the current-state table at the top of this file |
| What should we build next? | `docs/ROADMAP.md` (not the 2026-08-29 priority list) |
| Independent evidence | `docs/IMPLEMENTATION_RECONCILIATION.md` (821 tests) |

If a proposal conflicts with the ten decisions in `ROADMAP.md` section 1, it is a rewrite, not a simplification.
