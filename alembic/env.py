"""Alembic is not Curiculy's schema runner.

Historical revision files live in ``versions/`` for archaeology. They must
never be executed against catalog.db, admin.db, or tenant_*.db. Boot applies
SQLAlchemy ``create_all`` plus ``app.schema_patches`` via ``init_databases``.
"""

from logging.config import fileConfig

from alembic import context

from app.schema_patches import refuse_alembic_replay

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    refuse_alembic_replay()


def run_migrations_online() -> None:
    refuse_alembic_replay()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
