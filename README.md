# Curiculy

A homeschool planner for families. Parents plan lessons from whatever curriculum they use, see each child's day, keep work samples, and print records for evaluators. Kids sign in on their own tablet to see their lessons, check them off, and get a nudge when they're stuck.

**Curiculy guides; it doesn't teach.** The parent owns the curriculum and the teaching.

**📖 Everything else is in the [Curiculy Handbook](docs/README.md)**:
- what it is
- every feature's scope and review
- design
- operations
- engineering
- the roadmap

## Quick start
Only Docker is needed.

1. **Configure:** `cp .env.example .env`, then set a strong `JWT_SECRET`. The app refuses to start in production mode if it's missing, weak, or a placeholder. `MAIL_*` (portfolio email) and `OLLAMA_HOST` / `OLLAMA_MODEL` (AI features) are optional.
2. **Start:** `docker compose up -d`. The app is at `http://localhost:3040`.
3. **First account:** registration needs an invite key:
   ```
   docker compose exec api python scripts/create_invite.py --expires-days 1
   ```
   Then open `http://localhost:3040`, click **Create Account**, and use the key.

## Tests
```
docker compose --profile dev run --rm tests pytest -q --tb=line
docker compose --profile dev run --build --rm tests ruff check app scripts tests
e2e/run.sh
```
CI runs the same three on every push and pull request. See [Testing and CI](docs/5-engineering/testing-and-ci.md).

## Running it for real
- [Production and deploys](docs/4-operations/production.md)
- [Backups and restore](docs/4-operations/backups-and-restore.md)
- [Operator scripts](docs/4-operations/operator-scripts.md): invites, password reset, cleanups
- Behind a proxy or tunnel, set `FORWARDED_ALLOW_IPS` in `.env` to the proxy's address, so rate limits and logs use visitors' real addresses.
