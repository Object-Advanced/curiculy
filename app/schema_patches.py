"""Runtime schema upgrades. This module is the schema runner, not Alembic.

Boot and tenant provisioning call ``create_all`` (new tables) then the ordered
ALTER/index patches below (new columns on files that already exist). Each patch
checks ``PRAGMA table_info`` first, so running it twice is a no-op.

Alembic revisions ``0001``–``0012`` are a historical archive. They assume one
database, an older ``curricula`` shape, and they never create ``admin.db`` or
the pacing-guide tables. Do not replay them. Do not add new revision files as
the way to ship a column; add a patch here and a test.

How to add a column
-------------------
1. Add it on the SQLAlchemy model.
2. Append an idempotent ALTER (and index if needed) to the matching list below.
3. ``create_all`` covers brand-new tables; it will not add columns to old files.
4. Test: fresh file, old file missing the column, second apply, existing rows
   still present.
5. Do not ``DROP COLUMN`` on household files.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

ALEMBIC_NOT_AUTHORITATIVE = (
    "Alembic revisions 0001-0012 are historical and must not be replayed. "
    "Curiculy schema changes run through create_all plus "
    "app.schema_patches (see entrypoint.sh → init_databases). "
    "Do not run alembic upgrade against catalog.db, admin.db, or tenant_*.db."
)


def refuse_alembic_replay() -> None:
    """Block the Alembic CLI from executing archived revision scripts."""
    raise RuntimeError(ALEMBIC_NOT_AUTHORITATIVE)


def sqlite_table_columns(conn: Connection, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def sqlite_user_tables(conn: Connection) -> set[str]:
    rows = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()
    return {row[0] for row in rows} - {"sqlite_sequence"}


@dataclass(frozen=True)
class ColumnPatch:
    """One additive column (and optional extra SQL) on an existing table."""

    table: str
    column: str
    ddl: str
    extra_sql: tuple[str, ...] = ()


# Tenant files: columns that create_all will not add to an older tenant_*.db.
TENANT_COLUMN_PATCHES: tuple[ColumnPatch, ...] = (
    ColumnPatch(
        table="students",
        column="color_hex",
        ddl=(
            "ALTER TABLE students ADD COLUMN color_hex VARCHAR(7) "
            "NOT NULL DEFAULT '#356b46'"
        ),
    ),
    ColumnPatch(
        table="assignments",
        column="shared_group_uuid",
        ddl="ALTER TABLE assignments ADD COLUMN shared_group_uuid VARCHAR(36)",
        extra_sql=(
            "CREATE INDEX IF NOT EXISTS ix_assignments_shared_group_uuid "
            "ON assignments (shared_group_uuid)",
        ),
    ),
    ColumnPatch(
        table="curriculum_plans",
        column="frequency_days",
        ddl=(
            "ALTER TABLE curriculum_plans ADD COLUMN frequency_days "
            "INTEGER NOT NULL DEFAULT 5"
        ),
    ),
    ColumnPatch(
        table="curriculum_plans",
        column="total_weeks",
        ddl=(
            "ALTER TABLE curriculum_plans ADD COLUMN total_weeks "
            "INTEGER NOT NULL DEFAULT 36"
        ),
    ),
    ColumnPatch(
        table="curriculum_plans",
        column="grading_weights",
        ddl="ALTER TABLE curriculum_plans ADD COLUMN grading_weights TEXT",
    ),
    ColumnPatch(
        table="curriculum_plans",
        column="is_archived",
        ddl=(
            "ALTER TABLE curriculum_plans ADD COLUMN is_archived "
            "BOOLEAN NOT NULL DEFAULT 0"
        ),
    ),
    ColumnPatch(
        table="curriculum_plans",
        column="status",
        ddl=(
            "ALTER TABLE curriculum_plans ADD COLUMN status "
            "VARCHAR(32) NOT NULL DEFAULT 'ready'"
        ),
    ),
    ColumnPatch(
        table="curriculum_lessons",
        column="notes",
        ddl="ALTER TABLE curriculum_lessons ADD COLUMN notes TEXT",
    ),
    ColumnPatch(
        table="curriculum_lessons",
        column="category",
        ddl="ALTER TABLE curriculum_lessons ADD COLUMN category VARCHAR(64)",
    ),
    ColumnPatch(
        table="curriculum_lessons",
        column="time_slot",
        ddl="ALTER TABLE curriculum_lessons ADD COLUMN time_slot VARCHAR(64)",
    ),
    ColumnPatch(
        table="curriculum_lessons",
        column="resources",
        ddl="ALTER TABLE curriculum_lessons ADD COLUMN resources TEXT",
    ),
    ColumnPatch(
        table="household_settings",
        column="exception_colors",
        ddl="ALTER TABLE household_settings ADD COLUMN exception_colors TEXT",
    ),
)

# admin.db: columns that create_all will not add to an older users table.
ADMIN_COLUMN_PATCHES: tuple[ColumnPatch, ...] = (
    ColumnPatch(
        table="users",
        column="is_admin",
        ddl="ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0",
    ),
    ColumnPatch(
        table="users",
        column="role",
        ddl="ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'parent'",
    ),
    ColumnPatch(
        table="users",
        column="student_id",
        ddl="ALTER TABLE users ADD COLUMN student_id INTEGER",
        extra_sql=(
            "CREATE INDEX IF NOT EXISTS ix_users_student_id ON users (student_id)",
        ),
    ),
    ColumnPatch(
        table="users",
        column="pin_failed_attempts",
        ddl=(
            "ALTER TABLE users ADD COLUMN pin_failed_attempts "
            "INTEGER NOT NULL DEFAULT 0"
        ),
    ),
    ColumnPatch(
        table="users",
        column="pin_locked_until",
        ddl="ALTER TABLE users ADD COLUMN pin_locked_until DATETIME",
    ),
)

# catalog.db has no column patches today. New ISBN-dictionary columns go here.
CATALOG_COLUMN_PATCHES: tuple[ColumnPatch, ...] = ()


def apply_column_patches(
    conn: Connection, patches: tuple[ColumnPatch, ...]
) -> None:
    tables = sqlite_user_tables(conn)
    for patch in patches:
        if patch.table not in tables:
            continue
        columns = sqlite_table_columns(conn, patch.table)
        if patch.column in columns:
            continue
        conn.execute(text(patch.ddl))
        for statement in patch.extra_sql:
            conn.execute(text(statement))


def apply_tenant_patches(conn: Connection) -> None:
    """ALTER existing tenant tables. Does not drop school-year date mirrors."""
    apply_column_patches(conn, TENANT_COLUMN_PATCHES)


def apply_admin_patches(conn: Connection) -> None:
    apply_column_patches(conn, ADMIN_COLUMN_PATCHES)


def apply_catalog_patches(conn: Connection) -> None:
    apply_column_patches(conn, CATALOG_COLUMN_PATCHES)


def apply_tenant_schema(engine: Engine) -> None:
    """create_all plus tenant column patches. Safe to run on every boot."""
    import app.models  # noqa: F401

    from app.db import TenantBase

    TenantBase.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        apply_tenant_patches(conn)


def apply_admin_schema(engine: Engine) -> None:
    """create_all plus admin column patches. Safe to run on every boot."""
    import app.models.admin  # noqa: F401

    from app.db import AdminBase

    AdminBase.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        apply_admin_patches(conn)


def apply_catalog_schema(engine: Engine) -> None:
    """create_all plus catalog column patches. Safe to run on every boot."""
    import app.models  # noqa: F401

    from app.db import CatalogBase

    CatalogBase.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        apply_catalog_patches(conn)
