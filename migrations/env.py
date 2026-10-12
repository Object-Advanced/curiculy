"""Alembic environment: migrations run as the owner role (DATABASE_OWNER_URL)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import reveal_secret, settings
from migrations.metadata import include_object, target_metadata

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def run_migrations() -> None:
    url = config.get_main_option("sqlalchemy.url") or reveal_secret(settings.database_owner_url)
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
