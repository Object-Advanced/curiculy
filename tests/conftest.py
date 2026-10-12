"""Shared database and API fixtures, on a real Postgres.

Tests use Postgres with the real migrations and the real roles, so each
family's rows are walled off by row-level security exactly as in production.
``TEST_DATABASE_ADMIN_URL`` must name a superuser on a throwaway server (the
compose ``tests`` service starts one). This file creates the two roles if they
are missing, a fresh database for the run, migrates it, and drops it at the end.

Two ways in:

- ``db`` and ``client`` (most tests): one connection whose outer transaction
  works as family ``test`` and is rolled back after the test. Code that
  commits only releases a savepoint. Fast, and nothing leaks between tests.
- ``committed_db`` (``auth_client`` and the tests that sign in for real): the
  production path. Sessions open on the app's own engine and really commit;
  every row is deleted afterwards.
"""

from collections.abc import Iterator
import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

# Isolate tests from a host .env. Set before importing app.config.Settings.
os.environ["DEV_MODE"] = "false"
os.environ.setdefault(
    "JWT_SECRET",
    "pytest-local-jwt-secret-not-used-in-production",
)

ADMIN_URL = os.environ.get("TEST_DATABASE_ADMIN_URL", "").replace(
    "postgresql+psycopg://", "postgresql://", 1
)
if not ADMIN_URL:
    raise RuntimeError(
        "TEST_DATABASE_ADMIN_URL is not set. Run the suite with "
        "`docker compose --profile dev run --rm tests`, which starts a throwaway Postgres; "
        "see docs/5-engineering/testing-and-ci.md."
    )

TEST_DB = f"curiculy_test_{os.getpid()}"
OWNER_PASSWORD = "test-owner-password"
APP_PASSWORD = "test-app-password"


def _url(user: str, password: str) -> str:
    parts = urlsplit(ADMIN_URL)
    netloc = f"{user}:{password}@{parts.hostname}:{parts.port or 5432}"
    return urlunsplit(("postgresql+psycopg", netloc, f"/{TEST_DB}", "", ""))


def _bootstrap_database() -> None:
    """Roles (if missing) and a fresh database, as docker/postgres/10-curiculy-roles.sh does."""
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        for role, password, attributes in (
            ("curiculy_owner", OWNER_PASSWORD, "LOGIN BYPASSRLS CREATEDB"),
            ("curiculy_app", APP_PASSWORD, "LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"),
        ):
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(
                sql.SQL(f"{verb} ROLE {{}} {attributes} PASSWORD {{}}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB)))
        conn.execute(
            sql.SQL("CREATE DATABASE {} OWNER curiculy_owner").format(sql.Identifier(TEST_DB))
        )
    test_db_as_superuser = urlunsplit(urlsplit(ADMIN_URL)._replace(path=f"/{TEST_DB}"))
    with psycopg.connect(test_db_as_superuser, autocommit=True) as conn:
        name = sql.Identifier(TEST_DB)
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(name))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO curiculy_app").format(name))
        conn.execute("GRANT USAGE ON SCHEMA public TO curiculy_app")
        conn.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE curiculy_owner IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO curiculy_app"
        )
        conn.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE curiculy_owner IN SCHEMA public "
            "GRANT USAGE, SELECT ON SEQUENCES TO curiculy_app"
        )


_bootstrap_database()
os.environ["DATABASE_URL"] = _url("curiculy_app", APP_PASSWORD)
os.environ["DATABASE_OWNER_URL"] = _url("curiculy_owner", OWNER_PASSWORD)

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Connection, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: F401,E402  (registers every mapper)
import app.models.admin  # noqa: F401,E402
from app.core.deps import get_staging_tenant_db, get_tenant_db  # noqa: E402
from app.core.security import (  # noqa: E402
    CurrentUser,
    get_current_user,
    require_staging_upload,
)
from app.db import (  # noqa: E402
    app_engine,
    dispose_engines,
    get_admin_db,
    get_catalog_db,
    owner_engine,
    set_tenant,
)
from app.db_startup import run_migrations  # noqa: E402
from app.main import create_app  # noqa: E402

TEST_TENANT = "test"

run_migrations()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    dispose_engines()
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB))
        )


def reset_sequences() -> None:
    """Ids start at 1 in every test, as they did with a fresh database file."""
    with owner_engine().begin() as conn:
        sequences = conn.execute(
            text("SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'")
        ).scalars().all()
        if sequences:
            conn.execute(
                text("SELECT " + ", ".join(f"setval('{name}', 1, false)" for name in sequences))
            )


def delete_all_rows() -> None:
    """Empty every table (owner role; DELETE, so an open test transaction can't block it)."""
    from app.services.family_data import family_tables

    with owner_engine().begin() as conn:
        family = [table.name for table in reversed(family_tables())]
        everything = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename <> 'alembic_version' ORDER BY 1"
            )
        ).scalars().all()
        for name in [*family, *(name for name in everything if name not in family)]:
            conn.execute(text(f'DELETE FROM "{name}"'))


def _test_user() -> CurrentUser:
    return CurrentUser(email="test@local", tenant_uuid=TEST_TENANT, jti="test")


@pytest.fixture(autouse=True)
def _fresh_ids() -> None:
    reset_sequences()


@pytest.fixture
def engine(db: Session) -> Connection:
    """What background-worker tests open their own sessions on: the test's
    connection, so those sessions see the test's rows (bind them with
    ``join_transaction_mode="create_savepoint"``)."""
    return db.bind


@pytest.fixture
def db() -> Iterator[Session]:
    """A session working as family ``test``, rolled back after the test."""
    connection = app_engine().connect()
    transaction = connection.begin()
    set_tenant(connection, TEST_TENANT)
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def session_like(db: Session) -> Session:
    """Another session on the test's connection (sees the same uncommitted rows)."""
    return Session(bind=db.bind, join_transaction_mode="create_savepoint", autoflush=False)


@pytest.fixture
def as_family(db: Session):
    """Switch the ``db`` transaction to another family: ``as_family("other")``."""

    def switch(tenant_id: str) -> None:
        db.flush()
        set_tenant(db.connection(), tenant_id)

    return switch


@pytest.fixture
def committed_db() -> Iterator[None]:
    """The real app path: sessions commit for real; every row is deleted afterwards."""
    try:
        yield
    finally:
        dispose_engines()
        delete_all_rows()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """API client working as family ``test`` on the ``db`` transaction."""
    application = create_app()
    application.dependency_overrides[get_catalog_db] = lambda: db
    application.dependency_overrides[get_tenant_db] = lambda: db
    application.dependency_overrides[get_staging_tenant_db] = lambda: db
    application.dependency_overrides[get_admin_db] = lambda: db
    application.dependency_overrides[get_current_user] = _test_user
    application.dependency_overrides[require_staging_upload] = _test_user

    def _background_tenant_session(tenant_uuid: str, demo_key: str | None = None) -> Session:
        return session_like(db)

    try:
        with (
            patch(
                "app.services.ai_curriculum_worker.open_tenant_session",
                side_effect=_background_tenant_session,
            ),
            patch(
                "app.services.paper_vision_worker.open_tenant_session",
                side_effect=_background_tenant_session,
            ),
        ):
            yield TestClient(application)  # no context manager: skip lifespan evidence mkdir
    finally:
        application.dependency_overrides.clear()
