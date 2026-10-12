# Development setup

## Where to work
- **Never in the production folder** (`/home/objadv/curiculy`). It's live; see [Production](../4-operations/production.md).
- **Work in the development copy:** `/home/objadv/curiculy-dev`, a git worktree of the same repository.
  ```
  cd /home/objadv/curiculy-dev
  git fetch github
  git switch -c <topic> github/master
  ```
- The GitHub remote is named **`github`** (not `origin`): `git@github.com:Object-Advanced/curiculy.git`. The main branch is `master`.

## Run it locally
Only Docker is needed.
```
cp .env.example .env          # then set JWT_SECRET and the three database passwords
docker compose up -d db api   # http://localhost:3040; Postgres starts first
docker compose exec api python scripts/create_invite.py --expires-days 1   # first account
```
The `db` service is Postgres 18. Its first start creates the two roles (`docker/postgres/10-curiculy-roles.sh`). The app runs the migrations and its safety check every time it starts (`python -m app.db_startup`). See [Data model](data-model.md).

**Optional:**
- `MAIL_*` for emailing portfolios
- `OLLAMA_HOST` / `OLLAMA_MODEL` for AI features (every AI feature has a fallback)
- `GOOGLE_BOOKS_API_KEY`

## Check your work
```
docker compose --profile dev run --rm tests pytest -q --tb=line
docker compose --profile dev run --build --rm tests ruff check app scripts tests migrations
e2e/run.sh
```
The pytest run starts its own throwaway Postgres (`db-test`, in memory). Compose still asks for the three database passwords from `.env`; any values work for tests.

See [Testing and CI](testing-and-ci.md).

## The React app (`frontend/`)
The new app lives in `frontend/` and is served at `/next`. See `frontend/README.md` for its layout and commands. Without Node on the server, run its checks through Docker from the repository root:
```
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/repo -w /repo/frontend node:22.23.2-alpine sh -c 'npm ci && npm run typecheck && npm test && npm run build'
```
**After an API change,** regenerate `frontend/openapi.json` and `src/api/schema.d.ts`. pytest and CI fail until you do.

## Making changes
- **A schema change:** change the model, then `docker compose --profile dev run --rm tests alembic revision --autogenerate -m "what changed"`, and read what it wrote. **A new family table** also needs `tenancy.protect_family_table(...)` and `tenancy.add_family_reference(...)` in that migration (`migrations/tenancy.py`); the safety check and `tests/test_database.py` fail without them.
- **Never query family data on the owner engine** (it bypasses row-level security). Requests use `get_tenant_db`; upkeep jobs find families with the owner role, then work on each through `open_family_session`.
- **A new color or size:** add a token in `static/css/tokens.css`, which both apps use. Never use raw hex values or one-off sizes in `app.css` or the React styles.
- **Changing app.js, app.css or index.html:** bump the cache token everywhere at once. It's in `sw.js` (`SHELL_VERSION`), `index.html`, `app.css` and `tokens.css` (for example `20261010-greeting`), so devices pick up the new files. `tests/test_shell.py` checks they match.
- **A visual change:** run `e2e/run.sh --update-snapshots`, look at the images, and commit them.
- **Kid-facing words:** guide, don't teach (see [What Curiculy is](../1-overview/what-curiculy-is.md)).

## Pull requests
- One topic per branch, a clear title, and a body that says what changed, why, and how it was tested.
- CI (lint, pytest, e2e) must be green before merging.
- Then deploy using the steps in [Production](../4-operations/production.md).
