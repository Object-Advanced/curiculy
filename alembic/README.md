# Alembic archive

These revision files are **not** applied at runtime.

`entrypoint.sh` calls `init_databases()`, which runs SQLAlchemy `create_all` and then the ordered patches in `app/schema_patches.py`. That is the only schema process.

Do **not**:

- `alembic upgrade` against live `catalog.db`, `admin.db`, or `tenant_*.db`
- Replay `0001_initial` (wrong `curricula` shape, single-database layout)
- Treat `alembic.ini` `sqlalchemy.url` as a live database

`alembic upgrade` is configured to raise rather than execute these scripts.

To add a column: change the model, append an idempotent ALTER in `app/schema_patches.py`, add a test. Do not add a new revision as the shipping mechanism.
