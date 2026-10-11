# Decision record: the data tier

| | |
|---|---|
| **Question** | Keep one SQLite file per family, or move to Postgres? |
| **Status** | **Decided 2026-10-11: option B, Postgres with row-level security** |
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
- **A Postgres database per family** (a per-customer setup like the one the owner describes at TankTrack):
  - **Good:** real separation, and a natural nightly backup per customer.
  - **Hard:** every migration runs once per family, connections multiply, and family data can't join shared data. Those are option A's trade-offs.
  - **Fit:** it suits a business app with tens or hundreds of customers better than a family app aiming for thousands. Option B gets the per-family nightly copy another way (below).
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
- **Backups:** in layers, off-site, and tested every night. See [Backups](#backups-layered-not-just-nightly).
- **Per-family export and import** (JSON plus work-sample files). One tool serves the lifetime archive, a parent's access and deletion requests, restoring one family, seeding demos, and moving between environments.
- **Versions are pinned:** a Postgres major release and drivers (psycopg 3) that are established, not brand new (the project's version rule).

## Could one family see another family's data?
This is the most important risk of a shared database, and the owner's main concern. **Separate files are physical separation; row-level security is separation the database enforces by rule.** A rule can be misconfigured, so B is only safe with guardrails that check the setup automatically, rather than relying on anyone remembering.

**How a leak could happen, and what stops it:**
| How a leak could happen | SQLite per family | Postgres + row-level security |
|---|---|---|
| A query forgets to filter by family | Can't leak: other families aren't in the file | Can't leak: the database adds the filter itself |
| The request is tied to the **wrong family** at sign-in | **Leaks** (the wrong file opens) | **Leaks** (the wrong family is set) |
| A new table is added without its protection | Can't happen | **Stopped by a test:** every family table must have row-level security on and forced, and every table without `household_id` must be on a short, explicit list of shared tables |
| The app connects with an account that can bypass the rules | Can't happen | **Stopped at startup:** the app refuses to run if its account owns the tables, is a superuser, or can bypass row-level security |
| One request's family "sticks" to a pooled connection | Can't happen | **Stopped by design:** the family is set per transaction (`set_config(..., true)`, which is `SET LOCAL`), at the start of every transaction; tested with interleaved requests |
| A view or function quietly skips the rules | Can't happen | **Stopped by a test:** views must use `security_invoker`, and no `SECURITY DEFINER` functions on family tables (both are known Postgres traps) |
| A "unique" rule reveals that another family has something | Can't happen | **Design rule:** uniqueness on family tables always includes `household_id` |
| Background jobs or admin scripts | Open any file they're given | Use a separate account, kept out of request handlers; they name the family explicitly |
| Private details copied into shared data (like a shared guide) | Possible on the write-to-catalog path | Possible on the "Share this guide" path; in both, the share path copies structure only, and tests check it |

**The leak both designs share is the most likely one in practice:** tying a request to the wrong family. That's guarded by sign-in and its tests either way. For everything else, B needs **several independent safeguards to fail at once** before anything shows.

**Checks that run on every change, whichever option is chosen:**
- **A cross-family probe suite:**
  1. Make two families with data.
  2. Call every API route as Family A, using Family B's ids.
  3. Expect "not found" every time, B's data unchanged, and none of B's rows in any list.
- **A database check** (B only): connected as the app with no family set, every family table returns zero rows; with Family A set, only A's rows.
- **The coverage check above:** every table is either protected, or on the shared list.
- **The planned penetration test before launch** includes cross-family access.

## Backups: layered, not just nightly
Today Curiculy copies each family file once a night. A failure late in the day loses that day's work, and **nothing is off-site yet.** Option B keeps a nightly copy and adds continuous protection. It follows the 3-2-1 rule: three copies, on two kinds of storage, one of them off-site.

| Layer | What it is | What it's for |
|---|---|---|
| **1. Continuous archive** | Every change is shipped to the backup array within a minute or so (WAL archiving with pgBackRest or WAL-G), plus a weekly base backup | Restore the whole database to **any minute** in the last 30 days: "just before the bad update at 2:14 pm" |
| **2. Nightly full copy** | A complete dump of the database every night, kept 14 nights plus one a month | A simple, separate "image" of everything, if the archive itself has a problem |
| **3. Nightly family copies** | Every family exported to its own file each night (the same export that makes the lifetime archive) | **Restore one family without touching anyone else.** This is the per-customer nightly image, like TankTrack's. |
| **Off-site** | Layers 1–3 and the work-sample files, **encrypted**, copied to cloud storage (for example Backblaze B2 or S3) | A fire, theft or dead server at home loses nothing |

**A backup that's never restored isn't trusted:**
- **Every night,** a job restores the latest full copy into a scratch database, checks row counts and integrity, and **alerts on any failure.**
- **Before launch and then every quarter,** a full restore drill rebuilds the service on a spare machine from off-site copies alone (already a launch milestone).
- **Alerts** go off if the continuous archive falls behind or a nightly job fails, through the same log check and uptime monitor as the rest of the site.

**What a restore looks like:**
| What went wrong | What we do | Lost |
|---|---|---|
| The server dies | Rebuild from the base backup and replay the archive | About a minute of changes |
| A bad update damages data at 2:14 pm | Restore the whole database to 2:13 pm | Only changes after 2:13 |
| One family needs yesterday back | Import their nightly family copy (or pull just their rows from a point-in-time restore) | Nothing for anyone else |
| Fire or theft at home | Restore everything from the off-site copies onto new hardware | About a minute, plus rebuild time |

**Size and cost:** the database is small (text and numbers). Photos and videos are the bulk, and they're already mirrored as files. Off-site storage at Curiculy's size costs a few dollars a month.

## Quality: is Postgres more error-prone?
**No. For data quality it's stricter than SQLite,** so it catches mistakes SQLite lets through silently:
- **Types are enforced.** SQLite will store the text "abc" in a number column, and it doesn't enforce lengths like `String(255)`. Postgres refuses both.
- **Dates are real dates,** not text that happens to look like one.
- **Foreign keys are always on.** In SQLite they're on only because every connection turns them on, which is why `scripts/check_foreign_keys.py` exists.
- **Schema changes run in a transaction:** one either fully applies or doesn't apply at all, instead of a patch running file by file.

The new risks are the ones in the table above, and each has a test or a startup check.

## What changes if B is approved
| Area | Change |
|---|---|
| `app/db.py` | One engine and pool; a household-scoped session per request (`SET LOCAL`); the per-file engine cache, file paths and tenant-file listing are removed |
| Models | Family tables get `household_id` (defaulting from the session) as the spine rewrites them; `CatalogBase`, `TenantBase` and `AdminBase` become one database |
| Schema changes | Alembic, from a fresh baseline of the redesigned models; `app/schema_patches.py` and the legacy-table scripts retire |
| Tests | Postgres in CI (a service container) and locally (Docker); each test rolls back; new isolation tests |
| Demo mode | Demo households become ordinary households with an expiry, deleted by a cleanup job |
| Backups | `scripts/backup.py`'s SQLite path is replaced by the [three layers](#backups-layered-not-just-nightly): continuous archive, nightly full copy, nightly family copies, all copied off-site and encrypted, plus a nightly restore test. The evidence mirror stays and also goes off-site. |
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
**2026-10-11: option B, Postgres with row-level security.** The owner was concerned about leaks between families and about backups; both are answered above (the leak table and guardrails, and the layered backups). The owner's TankTrack product already runs on Postgres. Recorded in [Decisions](../decisions.md).
