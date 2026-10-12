"""Refuse to run unless families are walled off from each other.

Checked at startup (``app.db_startup``) and in the tests, against the live
database, so a missed policy or a wrongly configured role is caught by a
machine rather than remembered by a person:

1. The app's role is not a superuser, cannot bypass row-level security, and
   owns none of the tables.
2. Every table is either a family table (it has ``tenant_id``, row-level
   security is enabled **and forced**, and it has a policy) or on the explicit
   list of shared tables. Nothing else is allowed.
3. Every reference from one family table to another also matches on
   ``tenant_id``, so a row can never point at another family's row.
4. No views (a view runs with its owner's rights and would skip the policies
   unless created with ``security_invoker``) and no ``SECURITY DEFINER``
   functions in the schema.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db import AdminBase, CatalogBase, TenantBase

SCHEMA = "public"
TENANT_COLUMN = "tenant_id"
# Alembic's bookkeeping table is the only shared table outside the models.
EXTRA_SHARED_TABLES = frozenset({"alembic_version"})


class DatabaseSafetyError(RuntimeError):
    """The database is not set up to keep families apart; the app must not start."""


def shared_table_names() -> frozenset[str]:
    names = set(CatalogBase.metadata.tables) | set(AdminBase.metadata.tables)
    return frozenset(names | EXTRA_SHARED_TABLES)


def tenant_table_names() -> frozenset[str]:
    return frozenset(TenantBase.metadata.tables)


def _role_problems(conn: Connection) -> list[str]:
    row = conn.execute(
        text(
            "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname = current_user"
        )
    ).one()
    problems = []
    if row.rolsuper:
        problems.append(f"the app's role {row.rolname} is a superuser")
    if row.rolbypassrls:
        problems.append(f"the app's role {row.rolname} can bypass row-level security")
    owned = conn.execute(
        text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :schema AND c.relkind IN ('r', 'p') "
            "AND pg_get_userbyid(c.relowner) = current_user ORDER BY 1"
        ),
        {"schema": SCHEMA},
    ).scalars().all()
    if owned:
        problems.append(f"the app's role owns tables: {', '.join(owned)}")
    return problems


def _table_problems(conn: Connection) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
            "EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid "
            "        AND a.attname = :column AND NOT a.attisdropped) AS has_tenant, "
            "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :schema AND c.relkind IN ('r', 'p') ORDER BY c.relname"
        ),
        {"schema": SCHEMA, "column": TENANT_COLUMN},
    ).all()
    shared = shared_table_names()
    expected_tenant = tenant_table_names()
    problems = []
    seen = set()
    for row in rows:
        seen.add(row.relname)
        if row.has_tenant:
            missing = []
            if not row.relrowsecurity:
                missing.append("row-level security is off")
            if not row.relforcerowsecurity:
                missing.append("row-level security is not forced")
            if not row.policies:
                missing.append("it has no policy")
            if missing:
                problems.append(f"family table {row.relname}: {', '.join(missing)}")
        elif row.relname not in shared:
            problems.append(
                f"table {row.relname} has no {TENANT_COLUMN} and is not a known shared table"
            )
    for name in sorted(expected_tenant - seen):
        problems.append(f"family table {name} is missing (run the migrations)")
    return problems


def _reference_problems(conn: Connection) -> list[str]:
    """Each family-to-family foreign key needs a twin that includes tenant_id."""
    rows = conn.execute(
        text(
            "SELECT con.conrelid::regclass::text AS child, con.confrelid::regclass::text AS parent, "
            "ARRAY(SELECT a.attname FROM unnest(con.conkey) k "
            "      JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k) AS cols "
            "FROM pg_constraint con JOIN pg_namespace n ON n.oid = con.connamespace "
            "WHERE con.contype = 'f' AND n.nspname = :schema"
        ),
        {"schema": SCHEMA},
    ).all()
    tenant_tables = tenant_table_names()
    composite = {
        (row.child, row.parent, frozenset(row.cols))
        for row in rows
        if TENANT_COLUMN in row.cols
    }
    problems = []
    for row in rows:
        if TENANT_COLUMN in row.cols:
            continue
        if row.child in tenant_tables and row.parent in tenant_tables:
            wanted = frozenset([*row.cols, TENANT_COLUMN])
            if (row.child, row.parent, wanted) not in composite:
                problems.append(
                    f"{row.child}({', '.join(row.cols)}) -> {row.parent} "
                    f"does not also match on {TENANT_COLUMN}"
                )
    return problems


def _object_problems(conn: Connection) -> list[str]:
    problems = []
    views = conn.execute(
        text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :schema AND c.relkind IN ('v', 'm') ORDER BY 1"
        ),
        {"schema": SCHEMA},
    ).scalars().all()
    if views:
        problems.append(f"views are not allowed (they can skip row-level security): {', '.join(views)}")
    definers = conn.execute(
        text(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = :schema AND p.prosecdef ORDER BY 1"
        ),
        {"schema": SCHEMA},
    ).scalars().all()
    if definers:
        problems.append(f"SECURITY DEFINER functions are not allowed: {', '.join(definers)}")
    return problems


def database_safety_problems(engine: Engine) -> list[str]:
    """Every reason families might not be kept apart; empty when all is well."""
    with engine.connect() as conn:
        return [
            *_role_problems(conn),
            *_table_problems(conn),
            *_reference_problems(conn),
            *_object_problems(conn),
        ]


def verify_database_safety(engine: Engine) -> None:
    problems = database_safety_problems(engine)
    if problems:
        listed = "\n  - ".join(problems)
        raise DatabaseSafetyError(
            "The database does not keep families apart, so Curiculy will not start:\n  - "
            + listed
        )
