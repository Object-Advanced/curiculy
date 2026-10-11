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
cp .env.example .env          # then set a strong JWT_SECRET
docker compose up -d          # http://localhost:3040
docker compose exec api python scripts/create_invite.py --expires-days 1   # first account
```

**Optional:**
- `MAIL_*` for emailing portfolios
- `OLLAMA_HOST` / `OLLAMA_MODEL` for AI features (every AI feature has a fallback)
- `GOOGLE_BOOKS_API_KEY`

## Check your work
```
docker compose --profile dev run --rm tests pytest -q --tb=line
docker compose --profile dev run --build --rm tests ruff check app scripts tests
e2e/run.sh
```

See [Testing and CI](testing-and-ci.md).

## The React app (`frontend/`)
The new app lives in `frontend/` and is served at `/next`. See `frontend/README.md` for its layout and commands. Without Node on the server, run its checks through Docker from the repository root:
```
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/repo -w /repo/frontend node:22.23.2-alpine sh -c 'npm ci && npm run typecheck && npm test && npm run build'
```
**After an API change,** regenerate `frontend/openapi.json` and `src/api/schema.d.ts`. pytest and CI fail until you do.

## Making changes
- **A new column:** add it on the model, append a patch in `app/schema_patches.py`, and test it on a fresh file, an old file, and a second run.
- **A new color or size:** add a token in `static/css/tokens.css`, which both apps use. Never use raw hex values or one-off sizes in `app.css` or the React styles.
- **Changing app.js, app.css or index.html:** bump the cache token everywhere at once. It's in `sw.js` (`SHELL_VERSION`), `index.html`, `app.css` and `tokens.css` (for example `20261010-greeting`), so devices pick up the new files. `tests/test_shell.py` checks they match.
- **A visual change:** run `e2e/run.sh --update-snapshots`, look at the images, and commit them.
- **Kid-facing words:** guide, don't teach (see [What Curiculy is](../1-overview/what-curiculy-is.md)).

## Pull requests
- One topic per branch, a clear title, and a body that says what changed, why, and how it was tested.
- CI (lint, pytest, e2e) must be green before merging.
- Then deploy using the steps in [Production](../4-operations/production.md).
