"""Migration steps that wall families off from each other.

Every family table (``TenantBase``) needs, in the migration that creates it:

1. ``protect_family_table(name)``: row-level security on **and forced**, a
   policy that admits only rows whose ``tenant_id`` is the current family, and
   a unique ``(tenant_id, id)`` so other family tables can reference it.
2. ``add_family_reference(child, [column], parent)`` for each foreign key to
   another family table: a second foreign key on ``(tenant_id, column)``, so a
   row can never point at another family's row.

``app.db_safety`` checks the live database for both and refuses to start if
any table is missed. The constraints these add start with
``TENANCY_CONSTRAINT_PREFIXES`` and are ignored by autogenerate.
"""

from __future__ import annotations

from alembic import op

TENANCY_CONSTRAINT_PREFIXES = ("fk_tenant_", "uq_tenant_row_")
POLICY = "family_isolation"

CREATE_CURRENT_TENANT = """
CREATE FUNCTION curiculy_current_tenant() RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT NULLIF(current_setting('app.tenant_id', true), '') $$
"""
DROP_CURRENT_TENANT = "DROP FUNCTION curiculy_current_tenant()"


def create_current_tenant_function() -> None:
    """The family a transaction works in, or NULL when none is set."""
    op.execute(CREATE_CURRENT_TENANT)


def protect_family_table(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY} ON {table} "
        "USING (tenant_id = curiculy_current_tenant()) "
        "WITH CHECK (tenant_id = curiculy_current_tenant())"
    )
    op.create_unique_constraint(f"uq_tenant_row_{table}", table, ["tenant_id", "id"])


def add_family_reference(
    child: str,
    columns: list[str],
    parent: str,
    *,
    ondelete: str | None = None,
) -> None:
    """A foreign key on (tenant_id, columns) -> parent (tenant_id, id).

    ``ondelete`` mirrors the plain foreign key. SET NULL clears only the
    listed columns, never tenant_id.
    """
    name = f"fk_tenant_{child}_{'_'.join(columns)}"
    action = ""
    if ondelete == "CASCADE":
        action = " ON DELETE CASCADE"
    elif ondelete == "SET NULL":
        action = f" ON DELETE SET NULL ({', '.join(columns)})"
    elif ondelete:
        raise ValueError(f"Unsupported ON DELETE {ondelete}")
    op.execute(
        f"ALTER TABLE {child} ADD CONSTRAINT {name} "
        f"FOREIGN KEY (tenant_id, {', '.join(columns)}) "
        f"REFERENCES {parent} (tenant_id, id){action}"
    )
