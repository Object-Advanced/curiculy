"""SQLite connection settings, foreign-key enforcement, and engine caching."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import app.core.security as security
import app.db as db_module
from app.config import settings
from app.db import TenantBase
from scripts.check_foreign_keys import check_file
from tests.test_auth import bearer, seed_user

pytest_plugins = ["tests.test_auth"]


@pytest.fixture
def tenant_file(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tenant.db'}")
    TenantBase.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_every_connection_enforces_foreign_keys_and_uses_wal(tenant_file) -> None:
    with tenant_file.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_a_row_pointing_at_a_missing_parent_is_refused(tenant_file) -> None:
    with pytest.raises(IntegrityError):
        with tenant_file.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO assignments (student_id, title, scheduled_date, status, "
                    "created_at, updated_at) VALUES (999, 'Orphan', '2026-10-08', 'assigned', "
                    "datetime('now'), datetime('now'))"
                )
            )


def test_declared_cascades_now_run(tenant_file) -> None:
    with tenant_file.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO households (id, name, created_at, updated_at) "
                "VALUES (1, 'Home', datetime('now'), datetime('now'))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO students (id, household_id, name, color_hex, created_at, updated_at) "
                "VALUES (1, 1, 'Ada', '#356b46', datetime('now'), datetime('now'))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO attendance (student_id, date, status, created_at, updated_at) "
                "VALUES (1, :day, 'Present', datetime('now'), datetime('now'))"
            ),
            {"day": "2026-10-08"},
        )
    with tenant_file.begin() as conn:
        conn.execute(text("DELETE FROM students WHERE id = 1"))
    with tenant_file.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM attendance")).scalar() == 0


def test_household_engines_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "tenant_database_url", f"sqlite:///{tmp_path / 'tenant.db'}")
    monkeypatch.setattr(db_module, "TENANT_ENGINE_LIMIT", 2)
    monkeypatch.setattr(db_module, "_tenant_engines", type(db_module._tenant_engines)())
    for name in ("one", "two", "three"):
        db_module.open_tenant_session(name).close()

    assert len(db_module._tenant_engines) == 2
    assert not any("tenant_one" in url for url in db_module._tenant_engines)


class TestForeignKeyReport:
    def test_clean_file_is_ok(self, tmp_path: Path, tenant_file) -> None:
        assert check_file(tmp_path / "tenant.db") == []

    def test_orphans_and_stale_references_are_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "old.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE parents (id INTEGER PRIMARY KEY);
            CREATE TABLE children (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parents(id));
            CREATE TABLE stale (id INTEGER PRIMARY KEY, book_id INTEGER REFERENCES book_editions(id));
            INSERT INTO children (id, parent_id) VALUES (1, 42);
            """
        )
        conn.commit()
        conn.close()

        problems = check_file(path)

        assert "stale.book_id references missing table book_editions" in problems
        assert "children row 1 points at a missing parents row" in problems


def test_a_request_decodes_its_token_once(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_user()
    token = auth_client.post(
        "/api/auth/token", data={"username": "parent@example.com", "password": "secret"}
    ).json()["access_token"]
    calls = []
    original = security.decode_access_token
    monkeypatch.setattr(
        security, "decode_access_token", lambda value: calls.append(value) or original(value)
    )

    response = auth_client.get("/api/students", headers=bearer(token))

    assert response.status_code == 200
    assert len(calls) == 1
