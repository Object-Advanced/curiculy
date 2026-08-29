from logging.config import fileConfig

from alembic import context

from app.config import settings
from app.db import init_databases

config = context.config
config.set_main_option("sqlalchemy.url", settings.catalog_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    init_databases()


def run_migrations_online() -> None:
    # Catalog and tenant schemas live on separate SQLite files. Historical
    # version scripts assumed a single database, so schema is created from the
    # two declarative metadatas instead of replaying those revisions.
    init_databases()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
