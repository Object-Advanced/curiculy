# Decision record: the data tier

| | |
|---|---|
| **Question** | Keep one SQLite file per family, or move to Postgres? |
| **Status** | **Proposed, waiting for the owner's decision** (written 2026-10-11) |
| **Recommendation** | **Postgres: one database, every family's rows walled off by the database itself (row-level security)** |
| **Decide by** | Now: before the backend spine (subjects, curricula, courses) is built |

## Why decide now
- **There are no real users,** so nothing has to be migrated: the two household files on the server (about 300 KB each) are test data.
- **The spine redesigns the family tables anyway** (curricula, guides, courses, lessons, subjects, activities, work samples, requirements). Whatever the data tier, those tables get rewritten. Rewriting them twice, once for SQLite and later for Postgres, is the expensive path.
- **The spine adds a lot of data shared between families:**
  - community guides and the curriculum programs behind them
  - chapter lists
  - state requirement packs and base packs
  - counts like "used by 14 families"
  - average lesson minutes
  - billing
  
  Where that shared data lives, and how it connects to each family's own data, is exactly what this decision settles.

## What the data tier has to do
From the [Product spine](../product-spine.md) and the launch plan:
1. **Keep each family's data apart,** reliably: one family must never see another's.
2. **Connect family data to shared data:** a family's course follows a shared guide; a scanned ISBN finds the community's guides; a state pack applies to a family.
3. **Answer questions across families:** usage counts, average minutes, support and admin views, billing.
4. **Keep everything for a child's whole education,** with backups that survive the loss of the server, and restore to a point in time.
5. **Export or delete one family** completely, on request (the lifetime archive; COPPA).
6. **Change the schema safely** as the product grows, with one developer.
7. **Run cheaply on the home server today** and move to a cloud host later without a rewrite.
8. **Scale past one server** if the public service grows.

## How it works today
- **Three kinds of SQLite file** (see [Data model](../../5-engineering/data-model.md)):
  - `admin.db`: sign-ins
  - `catalog.db`: the shared book cache
  - one `tenant_<household>.db` per family
- **`app/db.py`** opens the right family file for each request, keeping up to 256 open at once. Every query in the app assumes its session holds exactly one family, so tenant tables have no `household_id` column to filter on.
- **Schema changes** are additive `ALTER TABLE` patches (`app/schema_patches.py`), applied at startup to **every** family file.
- **Backups** (`scripts/backup.py`) copy each file with SQLite's backup API every night. There's **no off-site copy yet.**
- **Demo mode** makes a throwaway SQLite file per demo visitor.
- **Tests (858)** run the catalog, tenant and admin tables together in **one in-memory database.** The code already works with everything in one database.

## The options

### A. Keep SQLite, one file per family (today's design)
Add continuous off-site replication for every file, and lazy per-file migrations (`PRAGMA user_version`). Shared spine data goes into `catalog.db`.
- **Good:**
  - It's already built, tested and backed up.
  - The strongest isolation there is: a missing filter can't leak data, because other families aren't in the file.
  - Exporting, deleting or restoring one family is a file copy.
  - Nothing to run but the app.
- **Hard:**
  - **Family data can't link to shared data in the database.** A course pointing at a community guide is an id across two files, with no foreign key and no join. Shared data gets copied into family files or looked up in a second query.
  - **Cross-family questions mean opening every file,** or writing everything twice (once to the family file and once to the shared file) and keeping both in step.
  - **Every schema change runs on every file.** At startup today; lazily later. A change that fails halfway leaves families on different versions.
  - **The files must sit on the server's own disk,** so the app is tied to one machine. Replicating thousands of files off-site needs tooling for many databases.
  - Managed database services don't host SQLite files.

### B. Postgres, one database, with row-level security (recommended)
All families in one database. Every family table carries `household_id`. **Row-level security** (RLS) makes Postgres itself return only the current family's rows.
- **The programming model stays the same:** each request's session is scoped to one family, by `SET LOCAL app.household_id = …` at the start of its transaction. `household_id` defaults to that setting, so existing queries and inserts work without adding filters.
- **Good:**
  - Family data and shared data live together, with real foreign keys (a course → a shared guide) and plain SQL for "used by N families".
  - **One schema change, run once,** in a transaction (Alembic).
  - Standard backups with **point-in-time recovery**, off-site.
  - Runs in Docker on the home server today, and moves to a managed Postgres or a cloud host without code changes. More than one app server can share it later.
  - Fits what a public service needs: billing, admin, support, analytics.
- **Hard:**
  - **There's a database server to run** (or pay for): backups, upgrades, monitoring.
  - **Isolation becomes a rule the database enforces, not separate files.** It has to be set up carefully (below), and tested.
  - **Restoring one family from backup** takes a script: restore to a scratch database, then copy that family's rows back. The same per-family export and import is needed anyway for the lifetime archive.
  - **Tests move to Postgres,** a service container in CI and in local Docker, so they're a little slower.

### C. A hybrid: Postgres for shared data, SQLite per family
- **Good:** keeps file-per-family isolation and gets a real database for shared data.
- **Hard:** two database systems to run, back up and migrate, and family data still can't join shared data. **The costs of both, with the main benefit of neither.** Not recommended.

### Also ruled out
- **One SQLite file for every family:** one writer at a time for the whole service, and none of A's isolation. It gains nothing over B.
- **A Postgres schema per family:** every migration runs once per family, which brings back A's migration problem.
- **Hosted per-family SQLite services:** ties Curiculy to one vendor's platform before the hosting decision is made.

## Side by side
| What's needed | A. SQLite per family | B. Postgres + RLS | C. Hybrid |
|---|---|---|---|
| 1. Families kept apart | **Best** (separate files) | **Strong** (enforced by the database; must be tested) | Best |
| 2. Family data linked to shared data | Weak (ids across files) | **Best** (foreign keys, joins) | Weak |
| 3. Questions across families | Weak (open every file, or write twice) | **Best** (plain SQL) | Partial |
| 4. Point-in-time backups, off-site | Per file, needs tooling | **Standard** | Both kinds |
| 5. Export or delete one family | **Best** (one file) | Good (by `household_id`, with cascades) | Best |
| 6. Safe schema changes | Weak (every file) | **Best** (once, in a transaction) | Two systems |
| 7. Cheap on the home server, portable later | **Best** today; tied to one disk | Good (one container; managed later) | Worst (two systems) |
| 8. More than one app server | No | **Yes** | Partly |
| Work to adopt now | None | About 1–2 weeks* | More than B |

\* A rough estimate for one developer with AI help. Most of it is test setup, backups and demo mode, not queries, because the redesigned tables are being written anyway.

## Recommendation
**Option B: Postgres, one database, row-level security, decided now.** The spine is built on shared data (guides, packs, counts) that has to connect to each family's own records. A public service needs one schema to change, standard point-in-time backups, and room to grow past one machine. Option A's real strengths, isolation and one-file export, can largely be kept. Row-level security gives database-enforced isolation, and the per-family export that the lifetime archive needs anyway covers export, delete and restore.

## How B is done safely
- **The app connects as its own role,** which doesn't own the tables and can't bypass row-level security. Every family table gets a policy (`household_id = current_setting('app.household_id')`) and **`FORCE ROW LEVEL SECURITY`**, so even the owner is held to it.
- **Each request sets its household in its transaction** (`SET LOCAL`), so it can't leak into the next request on a pooled connection. A session with no household set sees **nothing**.
- **Shared tables** (guides, programs, packs, the book catalog) have no household policy. They're read by everyone and written only through deliberate paths, like "Share this guide".
- **Admin and background jobs** use a separate role, kept to scripts and jobs, never request handlers.
- **Tests prove isolation:**
  - Family A can't read, change or delete Family B's rows through any route.
  - A session without a household sees no rows.
  - Inserting with the wrong household fails.
- **Backups:**
  - WAL archiving for point-in-time recovery, plus a nightly dump, both to the backup array **and off-site** (this also closes today's off-site gap)
  - a restore drill before launch
- **Per-family export and import** (JSON plus work-sample files). One tool serves the lifetime archive, a parent's access and deletion requests, restoring one family, seeding demos, and moving between environments.
- **Versions are pinned:** a Postgres major release and drivers (psycopg 3) that are established, not brand new (the project's version rule).

## What changes if B is approved
| Area | Change |
|---|---|
| `app/db.py` | One engine and pool; a household-scoped session per request (`SET LOCAL`); the per-file engine cache, file paths and tenant-file listing are removed |
| Models | Family tables get `household_id` (defaulting from the session) as the spine rewrites them; `CatalogBase`, `TenantBase` and `AdminBase` become one database |
| Schema changes | Alembic, from a fresh baseline of the redesigned models; `app/schema_patches.py` and the legacy-table scripts retire |
| Tests | Postgres in CI (a service container) and locally (Docker); each test rolls back; new isolation tests |
| Demo mode | Demo households become ordinary households with an expiry, deleted by a cleanup job |
| Backups | `scripts/backup.py`'s SQLite path is replaced by WAL archiving and a nightly dump, off-site; the evidence mirror stays |
| Operations | A `postgres` service in `docker-compose.yml`, with its data on the NVMe drive and archives on the data array |
| Today's data | Start fresh; export the owner's test household first only if wanted |
| Docs | [Data model](../../5-engineering/data-model.md), [Backups](../../4-operations/backups-and-restore.md), [How it works](../../1-overview/how-it-works.md); the principle "each family has its own database file" becomes "each family's rows are walled off by the database, with point-in-time backups" |

Work-sample files (photos, PDFs) stay on disk either way; moving them to object storage is the separate Phase 8 storage work.

## If A is chosen instead
Keep today's files and add:
- continuous off-site replication for every file
- lazy per-file migrations (`PRAGMA user_version`)
- a write-twice path from family files to `catalog.db` for counts and averages
- copies of shared guides inside each family file, with a link back by id

Revisit when the service needs a second server or cross-family features outgrow the write-twice path.

## Decision
*Waiting for the owner.* When it's made, record it here and in [Decisions](../decisions.md).
