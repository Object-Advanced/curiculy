# Codebase map

What each folder and important file does. Sizes are as of October 2026.

```
curiculy/
├── README.md                 Start here: what it is, quick start; links into docs/
├── docs/                     This handbook (everything for humans)
├── app/                      The server (Python, FastAPI)
│   ├── main.py               Builds the app: middleware, routers, the web page and the service worker
│   ├── config.py             Settings from the environment; refuses to start with a weak JWT_SECRET
│   ├── db.py                 Postgres engines; TenantSession (one family per transaction); shared sessions
│   ├── db_safety.py          Refuses to start unless families are walled off (roles, policies, references)
│   ├── db_startup.py         Startup upkeep: wait for Postgres, migrate, safety check, recovery, demo cleanup
│   ├── enums.py              Every status and kind (lesson status, days-off kinds, report types…)
│   ├── core/                 Cross-cutting pieces
│   │   ├── security.py       Passwords, sign-in tokens, who's signed in, parent and admin guards
│   │   ├── deps.py           "Signed-in user plus their family's database" dependency
│   │   ├── middleware.py     Security headers, request size cap, selective gzip
│   │   ├── idempotency.py    Retried writes are applied once
│   │   └── rate_limit.py     Sign-in attempt limits
│   ├── routers/              One file per area of the API (25 files, about 100 endpoints)
│   ├── services/             The rules behind the routers (pacing, recalibrate, portfolios, AI…); family_data.py (export, delete, restore one family), demo_households.py
│   │   └── providers/        ISBN lookups: Open Library, Google Books
│   ├── models/               Database tables (SQLAlchemy 2)
│   ├── schemas/              Request and response shapes (Pydantic)
│   ├── evidence/             Storing and serving work-sample files safely
│   ├── templates/            HTML and CSS for PDFs: portfolio, weekly checklist, paper week sheet
│   └── utils/isbn.py         ISBN-10 and ISBN-13 checks and conversion
├── frontend/                 The new React app (Vite + TypeScript), served at /next; see frontend/README.md
│   ├── src/routes/           Screens: TrailPage (My trail)
│   ├── src/components/       TrailMap (SVG), StopList, StickerPanel, BonusChest…
│   ├── src/lib/              Pure logic: map layout, stickers, the daily puzzle, dates
│   ├── src/api/              Typed API client (generated from openapi.json) and queries
│   └── openapi.json          The API description the client is built from
├── index.html                The legacy web app's single page, including the sign-in page and wizard (694 lines)
├── sw.js                     Service worker: keeps the app's files on the device
├── static/
│   ├── js/app.js             The legacy web app (9,500 lines; React replaces it screen by screen)
│   ├── js/theme-boot.js      Runs before the first paint: theme, sign-in state, kid look
│   ├── css/tokens.css        Design tokens (colors, type, spacing, kid look, seasons)
│   ├── css/app.css           Styles (4,460 lines; uses tokens only)
│   ├── fonts/                Self-hosted Figtree, Newsreader, Fredoka, Nunito (+ licenses)
│   ├── vendor/chartjs-4.5.1/ Chart.js, bundled and pinned
│   ├── curiculy-logo.png     The logo
│   └── night-mountains.jpg   Sign-in page background
├── extension/                The "Curiculy Capture" Chrome extension (Manifest V3)
├── migrations/               Alembic migrations (versions/), tenancy.py (row-level security steps)
├── docker/postgres/          The database container's first-start role setup
├── scripts/                  Operator tools: backup, restore one family, invites, password reset
├── tests/                    Backend tests (pytest on Postgres, 52 files, 952 tests)
├── e2e/                      Browser tests (Playwright): functional, visual snapshots, accessibility, offline, metrics
├── .github/workflows/        CI: lint, pytest, e2e on every push and pull request
├── Dockerfile                The app image: a Node stage builds frontend/, then Python 3.12, WeasyPrint, Tesseract
├── docker-compose.yml        api, backup (profile "backup") and tests (profile "dev")
├── entrypoint.sh             Startup: check config → prepare databases → run uvicorn behind the proxy
├── requirements*.txt         Python packages (pinned)
├── .env.example              Settings template (copy to .env; never commit .env)
├── pytest.ini, ruff.toml     Test and lint settings
└── .dockerignore, .gitignore
```

## Routers → features
| Router | Feature page |
|---|---|
| `auth.py`, `admin.py` | [Accounts and sign-in](../2-features/01-accounts-and-sign-in.md) |
| `household.py`, `students.py`, `settings.py`, `enrollments.py` | [Household and Settings](../2-features/02-household-setup-and-settings.md) |
| `dashboard.py` | [Home](../2-features/03-home.md) |
| `assignments.py`, `calendar.py` | [Calendar and lessons](../2-features/04-calendar-and-lessons.md) |
| `homework_help.py` | [Stuck? nudges](../2-features/07-stuck-nudges.md) |
| `curricula.py`, `catalog.py`, `books.py` | [Library and books](../2-features/08-library-and-books.md) |
| `pacing.py`, `curriculum_plans.py` | [Pacing and lesson plans](../2-features/09-pacing-and-lesson-plans.md) |
| `recalibration.py` | [Recalibrate](../2-features/10-recalibrate.md) |
| `school_years.py`, `exceptions.py` | [School year and days off](../2-features/11-school-year-and-days-off.md) |
| `attendance.py` | [Attendance](../2-features/12-attendance.md) |
| `evidence.py` | [Evidence and capture](../2-features/13-evidence-and-capture.md) |
| `portfolios.py`, `reports.py` | [Portfolios and reports](../2-features/14-portfolios-and-reports.md) |
| `notifications.py` | [Notifications](../2-features/15-notifications.md) |
| `health.py` | [Monitoring](../4-operations/monitoring.md) |

## Conventions
- **Imports run one way:** `core/security` uses `db`, never the reverse. `tests/test_import_order.py` guards this; a circular import once crashed startup.
- **"Today" is always `household_today(db)`**, never `date.today()`.
- **Schema changes are Alembic migrations;** a new family table needs the steps in `migrations/tenancy.py` (the safety check enforces it).
- **Family data only through a family session** (`get_tenant_db`, `open_tenant_session`, `open_family_session`). The owner engine bypasses row-level security, so it's for upkeep and backups only, and never reads family rows for a request.
- **Colors and sizes only through `tokens.css`** (enforced by tests).
- **Kid-facing copy follows "guide, don't teach"** (see [What Curiculy is](../1-overview/what-curiculy-is.md)).
