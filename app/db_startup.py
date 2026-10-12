"""Startup upkeep, run by entrypoint.sh before the server takes requests.

    python -m app.db_startup

1. Wait for Postgres.
2. Apply the migrations (owner role).
3. Refuse to start unless families are walled off (``app.db_safety``).
4. Mark imports a restart interrupted as failed (``plan_recovery``).
5. Delete expired demo households.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.config import validate_runtime_configuration
from app.db import app_engine, owner_engine
from app.db_safety import verify_database_safety

ROOT = Path(__file__).resolve().parents[1]


def wait_for_database(engine: Engine, timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


def run_migrations() -> None:
    command.upgrade(alembic_config(), "head")


def main() -> int:
    from app.services.demo_households import purge_stale_demo_households
    from app.services.plan_recovery import fail_interrupted_plans

    validate_runtime_configuration()
    wait_for_database(owner_engine())
    run_migrations()
    verify_database_safety(app_engine())
    failed = fail_interrupted_plans(owner_engine())
    purged = purge_stale_demo_households()
    print(f"Database ready: {failed} interrupted import(s) marked failed, {purged} demo household(s) cleared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
