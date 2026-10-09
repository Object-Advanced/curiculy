"""Process health is catalog.db + admin.db, not household tenant files."""

from collections.abc import Iterator
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db import _existing_tenant_file_urls, get_catalog_db
from app.main import create_app
from app.services.legacy_table_drop import legacy_tenant_db_paths


@pytest.fixture
def health_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "admin_database_url", f"sqlite:///{tmp_path / 'admin.db'}")
    monkeypatch.setattr(settings, "tenant_database_url", f"sqlite:///{tmp_path / 'tenant.db'}")
    monkeypatch.setattr(
        settings, "catalog_database_url", f"sqlite:///{tmp_path / 'catalog.db'}"
    )
    return tmp_path


@pytest.fixture
def health_client(health_dir: Path, db: Session) -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_catalog_db] = lambda: db
    try:
        yield TestClient(application)
    finally:
        application.dependency_overrides.clear()


def _ok(body: dict) -> None:
    assert body == {"status": "ok", "database": "ok", "dev_mode": False}


def _write_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("SELECT 1")
        connection.commit()
    finally:
        connection.close()


def test_shared_catalog_and_admin_are_healthy(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    _ok(response.json())


def test_healthy_household_file_does_not_fail_health(
    health_client: TestClient, health_dir: Path
) -> None:
    household = health_dir / "tenant_family-1.db"
    _write_sqlite(household)
    before = household.read_bytes()

    response = health_client.get("/api/health")

    assert response.status_code == 200
    _ok(response.json())
    assert household.read_bytes() == before


def test_malformed_household_file_does_not_fail_health(
    health_client: TestClient, health_dir: Path
) -> None:
    household = health_dir / "tenant_broken.db"
    household.write_bytes(b"this is not sqlite")
    before = household.read_bytes()

    response = health_client.get("/api/health")

    assert response.status_code == 200
    _ok(response.json())
    assert household.read_bytes() == before


def test_locked_household_file_does_not_fail_health(
    health_client: TestClient, health_dir: Path
) -> None:
    household = health_dir / "tenant_lock.db"
    _write_sqlite(household)
    holder = sqlite3.connect(household)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        response = health_client.get("/api/health")
    finally:
        holder.rollback()
        holder.close()

    assert response.status_code == 200
    _ok(response.json())


def test_catalog_admin_and_shared_tenant_files_are_not_treated_as_household(
    health_client: TestClient, health_dir: Path
) -> None:
    catalog = health_dir / "catalog.db"
    shared = health_dir / "tenant.db"
    household = health_dir / "tenant_live.db"
    catalog.write_bytes(b"not-sqlite-catalog")
    shared.write_bytes(b"not-sqlite-shared-tenant")
    household.write_bytes(b"not-sqlite-household")
    before = {path: path.read_bytes() for path in (catalog, shared, household)}

    assert legacy_tenant_db_paths(health_dir) == [household]

    response = health_client.get("/api/health")

    assert response.status_code == 200
    _ok(response.json())
    for path, payload in before.items():
        assert path.read_bytes() == payload


def test_health_does_not_create_or_mutate_household_files(
    health_client: TestClient, health_dir: Path
) -> None:
    household = health_dir / "tenant_family-1.db"
    _write_sqlite(household)
    before_household = household.read_bytes()
    before_names = {path.name for path in health_dir.iterdir()}

    response = health_client.get("/api/health")

    assert response.status_code == 200
    _ok(response.json())
    after_names = {path.name for path in health_dir.iterdir()}
    created = after_names - before_names
    assert "tenant.db" not in created
    assert not any(
        name.startswith("tenant_") and name.endswith(".db") for name in created
    )
    assert household.read_bytes() == before_household


def test_health_response_contract_is_unchanged(
    health_client: TestClient, health_dir: Path
) -> None:
    (health_dir / "tenant_secret-uuid.db").write_bytes(b"not sqlite")
    response = health_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    _ok(body)
    dumped = response.text
    assert "tenant_secret-uuid" not in dumped
    assert "tenant_secret-uuid.db" not in dumped
    assert str(health_dir) not in dumped


def test_health_does_not_discover_household_files(
    health_client: TestClient, health_dir: Path
) -> None:
    _write_sqlite(health_dir / "tenant_family-1.db")
    with patch(
        "app.db._existing_tenant_file_urls",
        wraps=_existing_tenant_file_urls,
    ) as discover:
        response = health_client.get("/api/health")

    assert response.status_code == 200
    _ok(response.json())
    discover.assert_not_called()


def test_shared_database_failure_fails_health(client: TestClient, db: Session) -> None:
    with patch.object(db, "execute", side_effect=RuntimeError("catalog down")):
        with pytest.raises(RuntimeError, match="catalog down"):
            client.get("/api/health")
