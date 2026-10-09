# Curiculy Technical Debt

The architecture-hardening / cleanup phase is **closed**. Dual exception HTTP prefixes were consolidated under `/api/exceptions`. Duplicate helpers in `app/services/legacy_tables.py` were removed. Capture JWTs cannot open a tenant file through `get_tenant_db`; staging uses `get_staging_tenant_db`. School-year dates live only on `SchoolYear`; leftover `household_settings` date columns are retired on boot after a safe backfill. New pacing commits and plan applies stamp `assignments.curriculum_id`. Operator scripts exist for historical book-paced (and stored-id) enrollments and for COUNT=0 leftover-table DROP; this host’s `./data/tenant_*.db` empty leftover tables were DROPped and two proven enrollments were inserted. Title-only historical plan assignments remain unlinked by design. Resolved hardening items live in `docs/ARCHITECTURE.md` and `docs/IMPLEMENTATION_RECONCILIATION.md`. Do not re-list them here as open.

What remains is **ongoing operational caution** and **optional product polish**, not an open hardening backlog.

Ordered by **importance to a homeschool product**, not by abstract purity.

Confidence: **CONFIRMED** unless noted.

---

## High

### 4. Schema patch discipline

Runtime is `create_all` + `app.schema_patches`. Forgetting an ALTER on a new model column leaves old `tenant_*.db` files lagging. Dual Alembic/patch runners are **not** the remaining problem (`alembic upgrade` is refused).

**Why it matters:** A family file can miss a column the code expects.

**Next step:** Every new column: model + patch + test (fresh file, old file, second apply, rows kept).

---

## Medium

### 7. Two ISBN HTTP namespaces; unused import APIs

Not two product concepts. `/books/*` and `POST /catalog/lookup-isbn` both wrap `BookResolver` over `catalog.db` `book_editions`. “Book” here means a shared `BookEdition` (ISBN/barcode dictionary), not a household `Curriculum`.

- SPA: `POST /catalog/lookup-isbn` (flat form fields) then `POST /curricula` with `sku`.
- `/books/resolve` returns full `BookEditionRead`. `GET /books/isbn/{isbn}` and `GET /books/{id}` have no catalog twin.
- `POST /catalog/from-isbn` is a one-shot **library** create (resolve-or-404). `POST /curricula` can also save a custom SKU without providers. They are not equivalent.
- `POST /curricula/import` builds a unit tree. SPA unused; tests use it.

**Why it matters:** Deleting `/books/*` because the SPA is quiet would remove the only GET dictionary reads and change OpenAPI. Pointing books tests at lookup-isbn would drop GET coverage and assert a different body.

**Next step:** Keep all three HTTP surfaces. Optional later: catalog GET twins with the same `BookEditionRead`, then `/books/*` as aliases. Do not remove `/curricula/import` until a UI or a retirement decision.

---

### 8. Dual Ollama HTTP stacks (intentional) and a hardcoded vision model

PDF worker and homework help share `app/services/ollama_chat.py` (`ollama.AsyncClient`, JSON-schema `format=`, `OLLAMA_MODEL` then `mistral`). Spark and paper vision use raw `httpx` POST `/api/chat` because they need timeouts and payloads the SDK path does not use: spark 2.5s/0.4s fail-open; vision 120s, `images[]`, sequential, `llama3.2-vision`.

**Why it matters:** Forcing one generic client could block the kid spark GET or send a text model at photographed cells. Setting vision to `OLLAMA_MODEL` (`llama3.1` by default) would break handwriting OCR even when text extras work.

**Next step:** Do not wire Ollama into `SyllabusGenerator`. Do not merge the two stacks. Optional later: `OLLAMA_VISION_MODEL` defaulting to `llama3.2-vision`.

---

## Low

### 13. Color palettes duplicated in JS and Python

**LIKELY** drift if one side changes.

### 14. `ai_generator.py` filename vs arithmetic

Comments are correct. Rename when the file is already being edited.

### 15. Homework-help test volume

Small module. Prompts are high-risk if changed without tests.

### 16. Cross-DB integer ids without FK

**Intentional.** Never delete catalog editions that tenant resources reference. Tenant `assignments.curriculum_id` and `enrollments.curriculum_id` are the same pattern (integer, no FK, tenant `curricula`).

### 17. Pacing commit is two engines, not one transaction

`SyllabusCommitter` commits the tenant session (assignments, units, enrollments) then the catalog session (book `page_count`). If the catalog commit failed, the calendar would still be complete. Tests share one memory DB, so the split is invisible there.

Do not wrap catalog and tenant in one transaction (they are different SQLite files).

### 18. JWT strength is length + denylist, not entropy

A 32-character string of a single letter is accepted in non-dev. Good enough to stop silent Compose defaults.

### 19. `DEV_MODE=true` skips JWT

Full parent/admin bypass. Local-only. Dangerous if left on for a real family.

### 20. FastAPI description still says “compliance foundation”

`create_app()` title/description. Cosmetic. Portfolios are the printable-record product. Compliance `build_packet()` raises `NotImplementedError`.

### 21. Compliance and taxonomy stubs

`NotImplementedError` modules; taxonomy tests without APIs. **DEFER.** Do not build admin UIs.

### 22. Passlib `crypt` deprecation

Suite warning from third-party `passlib`. Not Curiculy code.

### 23. Operator mailbox rotation

If this tree was copied when a mailbox password was still in Compose, rotate that mailbox. Not a code defect today.

---

## What is not debt

These look messy in a generic audit and are **correct for Curiculy**:

| Item | Why keep |
|---|---|
| SQLite per family | Isolation, backup, privacy |
| `/api/health` is catalog.db + admin.db | Process liveness, not household-file health. One wedged `tenant_{uuid}.db` must not 500 the probe, hide the SPA as down, or (if a container probe is added later) restart every family. Shared `tenant.db` is DEV_MODE only and is also not pinged. |
| Two curriculum objects (book vs week/day guide, including paper capture) | Books vs vendor grids vs handwritten sheets |
| Vanilla `app.js` | No npm in the image; bind-mount deploys |
| Demo in-memory DB | Try-before-invite without leftover files |
| Default pytest `client` is in-memory | Intentional. Fast API tests share one StaticPool DB and override `get_tenant_db`. JWT → admin user → `tenant_{uuid}.db` is `auth_client` (`test_auth.py` and plugins). Schema patches and leftover DROP use `tmp_path` files. Do not convert the suite. |
| Capture JWT can open a tenant file | Not equivalent to a parent session. `get_current_user` and therefore `get_tenant_db` refuse `role=evidence` / `scope=evidence:write`. Only `POST /api/evidence/staging` uses `get_staging_tenant_db` + `require_staging_upload`. |
| Invite-only registration | Matches current go-to-market |
| String grades | Homeschool scores are not one numeric scale |
| Staging evidence inbox | Extension captures are not yet lessons |
| Child completing a shared lesson without sibling sync | Documented rule |
| All Students showing shared lessons only | Documented query + UI copy |
| Boot not DROPping leftover `scheduled_work` / `evidence_captures` | Operator COUNT=0 script; nonempty tables must be refused. This host’s empty leftover tables were DROPped. |
| `HouseholdSettings` start/end date columns | Already removed from the model. Leftover physical columns on old `tenant_*.db` files are backfilled into `SchoolYear` (only when that household has no named year) and then dropped on boot. Weekdays and exception colors stay on settings. |
| Title-only historical plan assignments | Cannot prove a curriculum. New applies stamp `curriculum_id`. Do not infer from titles. |

---

## Suggested burn-down order

See `docs/ROADMAP.md`. Hardening/cleanup is closed. GitHub Actions runs the Compose pytest suite. `/books` vs catalog and dual Ollama stacks are documented KEEP. Remaining items are optional product polish and the cautions above. Do not mix a schema-engine rewrite with a UI redesign.
