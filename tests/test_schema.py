"""Runtime schema process: create_all + patches, not Alembic replay.

These tests use temporary SQLite files only. They never open /data databases.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
import app.models.admin  # noqa: F401
from app.config import settings
from app.db import (
    AdminBase,
    CatalogBase,
    TenantBase,
    _ensure_admin_schema,
    _ensure_catalog_schema,
    _ensure_tenant_schema,
    _existing_tenant_file_urls,
)
from app.models import Curriculum, Household, Student
from app.schema_patches import (
    ADMIN_COLUMN_PATCHES,
    ALEMBIC_NOT_AUTHORITATIVE,
    CATALOG_COLUMN_PATCHES,
    TENANT_COLUMN_PATCHES,
    apply_admin_schema,
    apply_catalog_schema,
    apply_tenant_schema,
    refuse_alembic_replay,
    sqlite_table_columns,
    sqlite_user_tables,
)

ROOT = Path(__file__).resolve().parents[1]


def _file_engine(path: Path) -> Engine:
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def _assert_metadata_present(engine: Engine, metadata) -> None:
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names()) - {"sqlite_sequence"}
    missing_tables = set(metadata.tables) - db_tables
    assert missing_tables == set(), missing_tables
    for table in metadata.tables.values():
        db_cols = {column["name"] for column in inspector.get_columns(table.name)}
        missing_cols = {column.name for column in table.columns} - db_cols
        assert missing_cols == set(), (table.name, missing_cols)


class TestFreshDatabases:
    def test_fresh_catalog_matches_models(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path / "catalog.db")
        try:
            apply_catalog_schema(engine)
            _assert_metadata_present(engine, CatalogBase.metadata)
        finally:
            engine.dispose()

    def test_fresh_admin_matches_models(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path / "admin.db")
        try:
            apply_admin_schema(engine)
            _assert_metadata_present(engine, AdminBase.metadata)
        finally:
            engine.dispose()

    def test_fresh_tenant_matches_models(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path / "tenant.db")
        try:
            apply_tenant_schema(engine)
            _assert_metadata_present(engine, TenantBase.metadata)
            names = set(inspect(engine).get_table_names())
            assert "scheduled_work" not in names
            assert "evidence_captures" not in names
        finally:
            engine.dispose()


class TestUpgradeExistingFiles:
    def test_old_tenant_gains_missing_columns_and_keeps_rows(
        self, tmp_path: Path
    ) -> None:
        engine = _file_engine(tmp_path / "tenant_legacy.db")
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE households (
                            id INTEGER PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            created_at DATETIME,
                            updated_at DATETIME
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE students (
                            id INTEGER PRIMARY KEY,
                            household_id INTEGER NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            grade VARCHAR(64),
                            notes TEXT,
                            created_at DATETIME,
                            updated_at DATETIME
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO households (id, name, created_at, updated_at) "
                        "VALUES (1, 'KeepMe', '2026-01-01', '2026-01-01')"
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO students "
                        "(id, household_id, name, grade, notes, created_at, updated_at) "
                        "VALUES (1, 1, 'Ada', '3', 'keep', '2026-01-01', '2026-01-01')"
                    )
                )

            apply_tenant_schema(engine)
            apply_tenant_schema(engine)

            with engine.connect() as conn:
                columns = sqlite_table_columns(conn, "students")
                assert "color_hex" in columns
                tables = sqlite_user_tables(conn)
                assert "assignments" in tables
                assert "homework_help_sessions" in tables
                assert "curriculum_plans" in tables
                row = conn.execute(
                    text("SELECT name, notes FROM students WHERE id = 1")
                ).one()
                assert row[0] == "Ada"
                assert row[1] == "keep"
                household = conn.execute(
                    text("SELECT name FROM households WHERE id = 1")
                ).one()
                assert household[0] == "KeepMe"
            # create_all does not ALTER columns on tables that already exist.
            # This file's households row predates jurisdiction_id; patches do
            # not add that leftover. Fresh files are checked against models.
        finally:
            engine.dispose()

    def test_old_admin_gains_user_columns_and_keeps_email(
        self, tmp_path: Path
    ) -> None:
        engine = _file_engine(tmp_path / "admin_legacy.db")
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE users (
                            id INTEGER PRIMARY KEY,
                            email VARCHAR(255) NOT NULL,
                            hashed_password VARCHAR(255) NOT NULL,
                            tenant_uuid VARCHAR(64) NOT NULL,
                            created_at DATETIME,
                            updated_at DATETIME
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email, hashed_password, tenant_uuid, created_at, updated_at) "
                        "VALUES (1, 'keep@example.com', 'hash', 'family-1', "
                        "'2026-01-01', '2026-01-01')"
                    )
                )

            apply_admin_schema(engine)
            apply_admin_schema(engine)

            with engine.connect() as conn:
                columns = sqlite_table_columns(conn, "users")
                assert "role" in columns
                assert "is_admin" in columns
                assert "student_id" in columns
                assert "pin_failed_attempts" in columns
                assert "pin_locked_until" in columns
                tables = sqlite_user_tables(conn)
                assert "invite_keys" in tables
                assert "capture_tokens" in tables
                row = conn.execute(
                    text("SELECT email, tenant_uuid FROM users WHERE id = 1")
                ).one()
                assert row[0] == "keep@example.com"
                assert row[1] == "family-1"
            _assert_metadata_present(engine, AdminBase.metadata)
        finally:
            engine.dispose()

    def test_catalog_reapply_does_not_delete_rows(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path / "catalog.db")
        try:
            apply_catalog_schema(engine)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO publishers (name, created_at, updated_at) "
                        "VALUES ('Saxon', '2026-01-01', '2026-01-01')"
                    )
                )
            apply_catalog_schema(engine)
            with engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM publishers")).scalar()
                name = conn.execute(text("SELECT name FROM publishers")).scalar()
                assert count == 1
                assert name == "Saxon"
            _assert_metadata_present(engine, CatalogBase.metadata)
        finally:
            engine.dispose()

    def test_discovered_tenant_files_are_upgraded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            settings,
            "tenant_database_url",
            f"sqlite:///{tmp_path / 'tenant.db'}",
        )
        legacy = tmp_path / "tenant_family-1.db"
        engine = _file_engine(legacy)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE students (
                            id INTEGER PRIMARY KEY,
                            household_id INTEGER NOT NULL,
                            name VARCHAR(255) NOT NULL
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO students (id, household_id, name) "
                        "VALUES (7, 1, 'Bea')"
                    )
                )
            urls = _existing_tenant_file_urls()
            assert any(str(legacy) in url for url in urls)
            for url in urls:
                patch_engine = create_engine(
                    url, connect_args={"check_same_thread": False}
                )
                try:
                    apply_tenant_schema(patch_engine)
                finally:
                    patch_engine.dispose()
            with engine.connect() as conn:
                assert "color_hex" in sqlite_table_columns(conn, "students")
                assert (
                    conn.execute(text("SELECT name FROM students WHERE id = 7")).scalar()
                    == "Bea"
                )
        finally:
            engine.dispose()


class TestIdempotencyAndSafety:
    def test_wrappers_match_public_apply_functions(self) -> None:
        assert _ensure_tenant_schema is apply_tenant_schema
        assert _ensure_admin_schema is apply_admin_schema
        assert _ensure_catalog_schema is apply_catalog_schema

    def test_tenant_patches_name_live_model_columns(self) -> None:
        for patch in TENANT_COLUMN_PATCHES:
            assert patch.table in TenantBase.metadata.tables
            assert patch.column in TenantBase.metadata.tables[patch.table].c

    def test_admin_patches_name_live_model_columns(self) -> None:
        for patch in ADMIN_COLUMN_PATCHES:
            assert patch.table in AdminBase.metadata.tables
            assert patch.column in AdminBase.metadata.tables[patch.table].c

    def test_catalog_has_no_column_patches_yet(self) -> None:
        assert CATALOG_COLUMN_PATCHES == ()

    def test_legacy_work_tables_are_not_mapped(self) -> None:
        assert "scheduled_work" not in TenantBase.metadata.tables
        assert "evidence_captures" not in TenantBase.metadata.tables

    def test_existing_empty_legacy_tables_are_not_dropped(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path / "tenant.db")
        try:
            apply_tenant_schema(engine)
            with engine.begin() as conn:
                conn.execute(
                    text("CREATE TABLE scheduled_work (id INTEGER PRIMARY KEY)")
                )
                conn.execute(
                    text("CREATE TABLE evidence_captures (id INTEGER PRIMARY KEY)")
                )
            apply_tenant_schema(engine)
            with engine.connect() as conn:
                names = {
                    row[0]
                    for row in conn.execute(
                        text("SELECT name FROM sqlite_master WHERE type = 'table'")
                    )
                }
            assert "scheduled_work" in names
            assert "evidence_captures" in names
        finally:
            engine.dispose()

    def test_household_settings_date_columns_are_not_dropped(
        self, tmp_path: Path
    ) -> None:
        engine = _file_engine(tmp_path / "tenant.db")
        try:
            apply_tenant_schema(engine)
            apply_tenant_schema(engine)
            with engine.connect() as conn:
                columns = sqlite_table_columns(conn, "household_settings")
            assert "start_date" in columns
            assert "end_date" in columns
            assert "weekdays" in columns
            assert "exception_colors" in columns
        finally:
            engine.dispose()

    def test_orm_rows_survive_second_schema_apply(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path / "tenant.db")
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        try:
            apply_tenant_schema(engine)
            session = factory()
            try:
                household = Household(name="Keep")
                session.add(household)
                session.flush()
                session.add(Student(household_id=household.id, name="Cora"))
                session.add(Curriculum(title="Saxon Math 3"))
                session.commit()
            finally:
                session.close()

            apply_tenant_schema(engine)

            session = factory()
            try:
                assert session.query(Household).count() == 1
                assert session.query(Student).filter_by(name="Cora").count() == 1
                assert session.query(Curriculum).filter_by(title="Saxon Math 3").count() == 1
            finally:
                session.close()
        finally:
            engine.dispose()


class TestAlembicIsNotAuthoritative:
    def test_refuse_helper_explains_the_rule(self) -> None:
        with pytest.raises(RuntimeError, match="must not be replayed"):
            refuse_alembic_replay()
        assert "init_databases" in ALEMBIC_NOT_AUTHORITATIVE
        assert "schema_patches" in ALEMBIC_NOT_AUTHORITATIVE

    def test_env_py_refuses_instead_of_calling_init_databases(self) -> None:
        source = (ROOT / "alembic" / "env.py").read_text()
        assert "refuse_alembic_replay" in source
        assert "init_databases()" not in source

    def test_alembic_upgrade_does_not_replay_revisions(self) -> None:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "must not be replayed" in combined

    def test_revision_0001_is_not_live_curricula_shape(self) -> None:
        source = (ROOT / "alembic" / "versions" / "0001_initial.py").read_text()
        assert 'sa.Column("isbn"' in source
        assert 'sa.Column("publisher"' in source
        assert "publisher_name" not in source
        assert "isbn" not in Curriculum.__table__.c
        assert "publisher" not in Curriculum.__table__.c
        assert "publisher_name" in Curriculum.__table__.c

    def test_revision_0007_alters_plans_it_never_created(self) -> None:
        source = (ROOT / "alembic" / "versions" / "0007_lesson_plan_builder.py").read_text()
        assert "op.create_table" not in source
        assert "curriculum_plans" in source
        assert "curriculum_plans" in TenantBase.metadata.tables

    def test_admin_tables_are_absent_from_alembic_history(self) -> None:
        blob = "".join(
            path.read_text()
            for path in sorted((ROOT / "alembic" / "versions").glob("*.py"))
        )
        assert 'op.create_table(\n        "users"' not in blob
        assert "capture_tokens" not in blob
        assert "users" in AdminBase.metadata.tables
        assert "capture_tokens" in AdminBase.metadata.tables
