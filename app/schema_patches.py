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

Column retirement (settings date mirror only)
---------------------------------------------
``household_settings.start_date`` / ``end_date`` duplicated ``SchoolYear``.
``retire_household_settings_date_columns`` backfills a named year when a
household has leftover dates and no ``school_years`` row, then drops those
two columns. It does not overwrite an existing ``SchoolYear``. Do not treat
this as a general DROP-COLUMN runner. Do not DROP leftover
``scheduled_work`` / ``evidence_captures`` tables from here.
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
        table="assignments",
        column="curriculum_id",
        ddl="ALTER TABLE assignments ADD COLUMN curriculum_id INTEGER",
        extra_sql=(
            "CREATE INDEX IF NOT EXISTS ix_assignments_curriculum_id "
            "ON assignments (curriculum_id)",
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
    ColumnPatch(
        table="households",
        column="icon",
        ddl="ALTER TABLE households ADD COLUMN icon VARCHAR(32)",
    ),
    ColumnPatch(
        table="households",
        column="timezone",
        ddl="ALTER TABLE households ADD COLUMN timezone VARCHAR(64)",
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


def _school_year_name_sql() -> str:
    """SQL expression matching ``school_year_name`` in ``app.services.school_year``."""
    return (
        "CASE WHEN strftime('%Y', hs.start_date) = strftime('%Y', hs.end_date) "
        "THEN strftime('%Y', hs.start_date) "
        "ELSE strftime('%Y', hs.start_date) || '-' || strftime('%Y', hs.end_date) "
        "END"
    )


def _backfill_school_years_from_settings_dates(conn: Connection) -> None:
    """Copy leftover settings dates onto SchoolYear when no year exists.

    Does not update households that already have a ``school_years`` row.
    Named years already win when both stores exist.
    """
    tables = sqlite_user_tables(conn)
    if "household_settings" not in tables or "school_years" not in tables:
        return
    columns = sqlite_table_columns(conn, "household_settings")
    if "start_date" not in columns or "end_date" not in columns:
        return
    year_columns = sqlite_table_columns(conn, "school_years")
    required = {"household_id", "name", "start_date", "end_date"}
    if not required.issubset(year_columns):
        return
    name_sql = _school_year_name_sql()
    timestamp_cols = "created_at" in year_columns and "updated_at" in year_columns
    if timestamp_cols:
        conn.execute(
            text(
                "INSERT INTO school_years "
                "(household_id, name, start_date, end_date, created_at, updated_at) "
                f"SELECT hs.household_id, {name_sql}, hs.start_date, hs.end_date, "
                "datetime('now'), datetime('now') "
                "FROM household_settings hs "
                "WHERE hs.start_date IS NOT NULL AND hs.end_date IS NOT NULL "
                "AND NOT EXISTS ("
                "SELECT 1 FROM school_years sy "
                "WHERE sy.household_id = hs.household_id"
                ")"
            )
        )
        return
    conn.execute(
        text(
            "INSERT INTO school_years "
            "(household_id, name, start_date, end_date) "
            f"SELECT hs.household_id, {name_sql}, hs.start_date, hs.end_date "
            "FROM household_settings hs "
            "WHERE hs.start_date IS NOT NULL AND hs.end_date IS NOT NULL "
            "AND NOT EXISTS ("
            "SELECT 1 FROM school_years sy "
            "WHERE sy.household_id = hs.household_id"
            ")"
        )
    )


def _rebuild_household_settings_without_dates(conn: Connection) -> None:
    """SQLite fallback when ALTER TABLE DROP COLUMN is unavailable."""
    columns = sqlite_table_columns(conn, "household_settings")
    has_colors = "exception_colors" in columns
    has_created = "created_at" in columns
    has_updated = "updated_at" in columns
    color_ddl = "exception_colors TEXT," if has_colors else ""
    created_ddl = "created_at DATETIME NOT NULL," if has_created else ""
    updated_ddl = "updated_at DATETIME NOT NULL," if has_updated else ""
    conn.execute(text("DROP TABLE IF EXISTS household_settings_new"))
    conn.execute(
        text(
            "CREATE TABLE household_settings_new ("
            "id INTEGER PRIMARY KEY, "
            "household_id INTEGER NOT NULL, "
            "weekdays VARCHAR(32) NOT NULL, "
            f"{color_ddl}"
            f"{created_ddl}"
            f"{updated_ddl}"
            "CONSTRAINT uq_household_settings_household UNIQUE (household_id), "
            "FOREIGN KEY(household_id) REFERENCES households (id)"
            ")"
        )
    )
    select_cols = ["id", "household_id", "weekdays"]
    if has_colors:
        select_cols.append("exception_colors")
    if has_created:
        select_cols.append("created_at")
    if has_updated:
        select_cols.append("updated_at")
    col_sql = ", ".join(select_cols)
    conn.execute(
        text(
            f"INSERT INTO household_settings_new ({col_sql}) "
            f"SELECT {col_sql} FROM household_settings"
        )
    )
    conn.execute(text("DROP TABLE household_settings"))
    conn.execute(text("ALTER TABLE household_settings_new RENAME TO household_settings"))


def _sqlite_version_tuple(conn: Connection) -> tuple[int, int, int]:
    raw = str(conn.execute(text("SELECT sqlite_version()")).scalar() or "0.0.0")
    parts = []
    for piece in raw.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def retire_household_settings_date_columns(conn: Connection) -> None:
    """Promote leftover settings dates to SchoolYear, then drop the mirror.

    Idempotent. Existing ``SchoolYear`` rows are left unchanged when both
    stores were present. Does not DROP leftover assignment tables.
    """
    tables = sqlite_user_tables(conn)
    if "household_settings" not in tables:
        return
    columns = sqlite_table_columns(conn, "household_settings")
    has_start = "start_date" in columns
    has_end = "end_date" in columns
    if not has_start and not has_end:
        return
    _backfill_school_years_from_settings_dates(conn)
    if _sqlite_version_tuple(conn) >= (3, 35, 0):
        if has_start:
            conn.execute(text("ALTER TABLE household_settings DROP COLUMN start_date"))
        remaining = sqlite_table_columns(conn, "household_settings")
        if "end_date" in remaining:
            conn.execute(text("ALTER TABLE household_settings DROP COLUMN end_date"))
        return
    _rebuild_household_settings_without_dates(conn)


def apply_tenant_patches(conn: Connection) -> None:
    """ALTER existing tenant tables, then retire the settings date mirror."""
    apply_column_patches(conn, TENANT_COLUMN_PATCHES)
    retire_household_settings_date_columns(conn)


def apply_admin_patches(conn: Connection) -> None:
    apply_column_patches(conn, ADMIN_COLUMN_PATCHES)


def apply_catalog_patches(conn: Connection) -> None:
    apply_column_patches(conn, CATALOG_COLUMN_PATCHES)


def apply_tenant_schema(engine: Engine) -> None:
    """create_all plus tenant patches, including settings date-column retirement."""
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
