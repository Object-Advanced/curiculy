"""Shared database and API fixtures.

Each test gets a fresh in-memory schema. ``StaticPool`` keeps every connection
pointing at the same memory database, which matters because the API runs request
handlers on a worker thread while the test holds the session.

Catalog and tenant tables share that memory database in tests so mixed seeds
stay on one session; production binds each metadata to its own SQLite file.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every mapper before create_all)
import app.models.admin  # noqa: F401
from app.core.security import CurrentUser, get_current_user
from app.db import AdminBase, CatalogBase, TenantBase, get_admin_db, get_catalog_db, get_tenant_db
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
def client(db: Session) -> Iterator[TestClient]:
    # Instantiated without the context manager so the app lifespan, which
    # provisions evidence directories on disk, stays out of the test run.
    application = create_app()
    application.dependency_overrides[get_catalog_db] = lambda: db
    application.dependency_overrides[get_tenant_db] = lambda: db
    application.dependency_overrides[get_admin_db] = lambda: db
    application.dependency_overrides[get_current_user] = _test_user
    try:
        yield TestClient(application)
    finally:
        application.dependency_overrides.clear()
