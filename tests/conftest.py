"""Shared database and API fixtures.

Default ``client`` is a fast in-memory API harness: catalog, tenant, and admin
tables share one StaticPool SQLite. That is intentional. It does **not**
exercise JWT → admin ``users.tenant_uuid`` → ``tenant_{uuid}.db``.

Production file routing is ``auth_client`` in ``tests/test_auth.py`` (and tests
that pull that fixture). Schema patches and leftover-table DROP use throwaway
files under pytest ``tmp_path``, never ``./data``.
"""

from collections.abc import Iterator
import os

# Isolate tests from a host .env. Set before importing app.config.Settings.
os.environ["DEV_MODE"] = "false"
os.environ.setdefault(
    "JWT_SECRET",
    "pytest-local-jwt-secret-not-used-in-production",
)

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every mapper before create_all)
import app.models.admin  # noqa: F401
from app.core.security import CurrentUser, get_current_user, require_staging_upload
from app.db import AdminBase, CatalogBase, TenantBase, get_admin_db, get_catalog_db, get_staging_tenant_db, get_tenant_db
from app.main import create_app


def _test_user() -> CurrentUser:
    return CurrentUser(email="test@local", tenant_uuid="test", jti="test")


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    CatalogBase.metadata.create_all(engine)
    TenantBase.metadata.create_all(engine)
    AdminBase.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session, engine: Engine) -> Iterator[TestClient]:
    """In-memory API client. Overrides tenant/admin routing and current user.

    ``StaticPool`` keeps the TestClient worker thread on the same memory DB.
    Use ``auth_client`` for JWT → physical ``tenant_{uuid}.db``.
    """
    application = create_app()
    application.dependency_overrides[get_catalog_db] = lambda: db
    application.dependency_overrides[get_tenant_db] = lambda: db
    application.dependency_overrides[get_staging_tenant_db] = lambda: db
    application.dependency_overrides[get_admin_db] = lambda: db
    application.dependency_overrides[get_current_user] = _test_user
    application.dependency_overrides[require_staging_upload] = _test_user
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _background_tenant_session(tenant_uuid: str, demo_key: str | None = None) -> Session:
        return factory()

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
