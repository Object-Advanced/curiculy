# Testing and CI

Four layers of checks run on every push and pull request (GitHub Actions, `.github/workflows/tests.yml`), and the same commands run locally.

| Layer | What | Command | Count (Oct 2026) |
|---|---|---|---|
| **Lint** | Python syntax errors and unused or undefined names (ruff 0.16.9, E9 + F rules) | `docker compose --profile dev run --build --rm tests ruff check app scripts tests migrations` | — |
| **Backend** | pytest against a throwaway Postgres (`db-test`) with the real migrations and roles; never touches production, the AI or mail | `docker compose --profile dev run --rm tests pytest -q --tb=line` | 952 tests in 52 files |
| **Frontend** | React app: TypeScript (strict), Vitest + Testing Library + MSW, a production build, and a check that the typed API client matches `frontend/openapi.json` | `cd frontend && npm run typecheck && npm test && npm run build` | 43 tests |
| **Browser** | Playwright 1.63 against a throwaway app in its own Compose project (`curiculy-e2e`); `e2e/run.sh` rebuilds the app image first so the React build is current | `e2e/run.sh` | 39 tests across 6 projects |

## The backend suite on Postgres
- **Real database, real rules.** `tests/conftest.py` creates the two roles and a fresh database for each run, applies the migrations, and drops the database at the end. Tests run as the app's role, so row-level security is on, exactly as in production.
- **Two ways in:**
  - `db` and `client` (most tests): one connection working as family `test`, rolled back after each test. Code that commits only releases a savepoint. Ids restart at 1 in every test.
  - `committed_db` (`auth_client` and the sign-in tests): the production path, with real commits; every row is deleted afterwards.
- **Keeping families apart** has its own tests:
  - `tests/test_database.py`: the safety check, each way it can fail, and row-level security itself (no family set, cross-family reads, writes and references, pooled connections, interleaved sessions)
  - `tests/test_cross_family_probe.py`: every API route called as Family A with Family B's ids, every list searched for B's data, and B unchanged afterwards. New routes are covered automatically.
- **Backups:** `tests/test_backup.py` runs the real nightly backup (dump, scratch restore, family copies) and restores one family.

## The browser suite (`e2e/`)
- **Projects:**
  - `setup` registers the test family ("The Okafor family"): **Ada** (PIN 2468), whose day stays fixed for read-only and screenshot tests, and **Ben** (PIN 1357), whose lessons the check-off tests change. Tests run in parallel, so only Ben's day may change.
  - `functional` covers smoke, kid, a11y, offline and metrics
  - five **visual** projects: desktop light and dark, tablet light, phone light and dark
- **Frozen clock:** `2026-10-14T15:00:00Z` (a Wednesday afternoon), so screenshots and counts don't drift.
- **Visual snapshots** live in `e2e/tests/__screenshots__/<project>/`. After an intended visual change:
  1. run `e2e/run.sh --update-snapshots`
  2. **look at the new images**
  3. commit them
- **Accessibility ratchet:** `e2e/a11y-baseline.json` caps serious and critical axe issues per screen. **Every screen is at 0**, including the kid's My work. Rewrite it with `UPDATE_A11Y_BASELINE=1 e2e/run.sh --project=functional a11y.spec.ts`.
- **Guards:** any page error or Content-Security-Policy violation fails the test.
- **Metrics:** `e2e/reports/metrics.json` records requests, kilobytes and LCP on a first visit and on reopening Home. The first visit is about 1,031 KB, most of it the 575 KB sign-in photo.
- **Why the service is called `curiculy-app`:** Chromium forces HTTPS for the whole `.app` top-level domain, so a host named `app` fails.
- **Its own Postgres:** `curiculy-db`, in memory, with the same first-start role setup as production.

## What each test file covers
See the **Tests** section of each [feature page](../2-features/README.md). The biggest backend suites:
- assignments: 93 tests
- pacing: 75
- curriculum import: 42
- PDF import: 33
- providers: 31

## Gaps
- **The legacy `app.js` has no JavaScript unit tests;** it's tested only through the browser. The React app has Vitest, Testing Library and MSW, and screens get unit tests as they move over.
- **No type checking** (pyright, tsc). Planned for Phase 7.
- **No dependency vulnerability scan.** Planned for Phase 7.
- **No load test or disaster-recovery drill.** Required before launch (M4).
