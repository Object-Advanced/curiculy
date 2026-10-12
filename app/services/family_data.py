"""Export, delete and restore one family's rows.

One tool for several jobs: the nightly family copies (backups layer 3), the
lifetime archive a family can download, a parent's request to delete their
data, restoring one family without touching anyone else, and clearing out
expired demo households.

Everything here runs in a ``TenantSession``: row-level security limits every
read and delete to that one family, and each statement also names the family
explicitly, so a mistake would need both safeguards to fail.
"""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, Table, delete, insert, select, text
from sqlalchemy.engine import Engine

from app.db import TenantBase, TenantSession, open_family_session

EXPORT_FORMAT = "curiculy-family-export"
EXPORT_VERSION = 1


def family_tables() -> list[Table]:
    """Family tables, parents before children (the order rows can be inserted)."""
    return list(TenantBase.metadata.sorted_tables)


def _to_json(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _from_json(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name, value in row.items():
        column = table.columns.get(name)
        if column is None:
            continue
        if value is not None and isinstance(column.type, DateTime):
            value = datetime.fromisoformat(value)
        elif value is not None and isinstance(column.type, Date):
            value = date.fromisoformat(value)
        out[name] = value
    return out


def export_family(session: TenantSession) -> dict[str, Any]:
    """Every row this family owns, table by table, as JSON-ready data."""
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in family_tables():
        rows = session.execute(
            select(table).where(table.c.tenant_id == session.tenant_id).order_by(*table.primary_key)
        ).mappings()
        tables[table.name] = [{key: _to_json(value) for key, value in row.items()} for row in rows]
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "tenant_id": session.tenant_id,
        "tables": tables,
    }


def delete_family_rows(session: TenantSession) -> int:
    """Delete every row this family owns (children before parents); return the count.

    Doesn't commit. Sign-ins and work-sample files are handled separately.
    """
    deleted = 0
    for table in reversed(family_tables()):
        result = session.execute(delete(table).where(table.c.tenant_id == session.tenant_id))
        deleted += result.rowcount or 0
    return deleted


def restore_family(session: TenantSession, export: dict[str, Any]) -> int:
    """Replace this family's rows with an export of the same family; return rows restored.

    Doesn't commit. Run ``advance_sequences`` afterwards (as the owner) when
    restoring into a database the rows didn't come from.
    """
    if export.get("format") != EXPORT_FORMAT or export.get("version") != EXPORT_VERSION:
        raise ValueError("Not a Curiculy family export this version can read.")
    if export.get("tenant_id") != session.tenant_id:
        raise ValueError("This export belongs to a different family.")
    delete_family_rows(session)
    restored = 0
    tables = export.get("tables", {})
    for table in family_tables():
        rows = [_from_json(table, row) for row in tables.get(table.name, [])]
        for row in rows:
            row["tenant_id"] = session.tenant_id
        if rows:
            session.execute(insert(table), rows)
            restored += len(rows)
    return restored


def advance_sequences(owner: Engine) -> None:
    """Move every id sequence past the highest id in use (owner role)."""
    with owner.begin() as conn:
        for table in family_tables():
            for column in table.primary_key.columns:
                sequence = conn.execute(
                    text("SELECT pg_get_serial_sequence(:table, :column)"),
                    {"table": table.name, "column": column.name},
                ).scalar()
                if sequence:
                    conn.execute(
                        text(
                            f"SELECT setval(:seq, GREATEST((SELECT COALESCE(max({column.name}), 0) "
                            f"FROM {table.name}), 1))"
                        ),
                        {"seq": sequence},
                    )


def write_export(path: Path, export: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(export, handle, separators=(",", ":"))


def read_export(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def delete_family(tenant_id: str) -> int:
    """Delete one family's rows in its own transaction; return the count."""
    session = open_family_session(tenant_id)
    try:
        deleted = delete_family_rows(session)
        session.commit()
        return deleted
    finally:
        session.close()
