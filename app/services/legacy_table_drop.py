"""Operator retirement of leftover ``scheduled_work`` / ``evidence_captures`` tables.

ORM models for those tables are gone. New tenant files never create them.
Older ``tenant_*.db`` files may still have the physical tables. This module
DROPs a leftover table only when ``COUNT(*) = 0``. It never DELETEs rows to
make a table empty. It is not called from application boot.

Operators run ``scripts/drop_legacy_tables.py``. Default is dry-run.
"""

from __future__ import annotations

import sqlite3
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path

LEGACY_TABLES: tuple[str, ...] = ("scheduled_work", "evidence_captures")
# Child table first so a leftover FK cannot block DROP of scheduled_work.
_DROP_ORDER: tuple[str, ...] = ("evidence_captures", "scheduled_work")
_CONNECT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class LegacyTableStatus:
    name: str
    exists: bool
    row_count: int | None = None
    dropped: bool = False

    @property
    def eligible(self) -> bool:
        return self.exists and self.row_count == 0

    @property
    def refused(self) -> bool:
        return self.exists and self.row_count is not None and self.row_count > 0


@dataclass
class TenantLegacyDropReport:
    """Inspection (and optional DROP) result for one tenant file."""

    path: Path
    dry_run: bool = True
    error: str | None = None
    tables: dict[str, LegacyTableStatus] = field(default_factory=dict)

    @property
    def absent(self) -> list[str]:
        return [
            name
            for name in LEGACY_TABLES
            if name in self.tables
            and not self.tables[name].exists
            and not self.tables[name].dropped
        ]

    @property
    def eligible(self) -> list[str]:
        return [name for name in LEGACY_TABLES if self.tables.get(name) is not None and self.tables[name].eligible]

    @property
    def dropped(self) -> list[str]:
        return [name for name in LEGACY_TABLES if self.tables.get(name) is not None and self.tables[name].dropped]

    @property
    def refused(self) -> list[str]:
        return [name for name in LEGACY_TABLES if self.tables.get(name) is not None and self.tables[name].refused]

    def format_lines(self) -> list[str]:
        lines = [self.path.name]
        if self.error:
            lines.append(f"  ERROR: {self.error}")
            lines.append("  no tables dropped")
            return lines
        for name in LEGACY_TABLES:
            status = self.tables[name]
            if status.dropped:
                lines.append(f"  {name}: 0 rows, DROPPED")
            elif not status.exists:
                lines.append(f"  {name}: absent")
            elif status.row_count == 0:
                verb = "would DROP" if self.dry_run else "left in place"
                lines.append(f"  {name}: 0 rows, {verb}")
            else:
                lines.append(
                    f"  {name}: {status.row_count} rows, refused (not empty)"
                )
        if self.dry_run:
            lines.append("  dry-run: no tables dropped")
        return lines


def _quote_table(name: str) -> str:
    if name not in LEGACY_TABLES:
        raise ValueError(f"refusing to touch table {name!r}")
    return f'"{name}"'


def _connect(path: Path, *, readonly: bool, timeout: float) -> sqlite3.Connection:
    if readonly:
        uri = path.resolve().as_uri() + "?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=timeout)
    return sqlite3.connect(str(path.resolve()), timeout=timeout)


def _inspect_connection(conn: sqlite3.Connection) -> dict[str, LegacyTableStatus]:
    tables: dict[str, LegacyTableStatus] = {}
    for name in LEGACY_TABLES:
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        if not present:
            tables[name] = LegacyTableStatus(name=name, exists=False)
            continue
        count = conn.execute(f"SELECT COUNT(*) FROM {_quote_table(name)}").fetchone()[0]
        tables[name] = LegacyTableStatus(name=name, exists=True, row_count=int(count))
    return tables


def inspect_tenant_legacy_tables(
    path: Path, *, timeout: float = _CONNECT_TIMEOUT_SECONDS
) -> TenantLegacyDropReport:
    """Read-only inspection. Never DROP."""
    path = Path(path)
    if not path.is_file():
        return TenantLegacyDropReport(
            path=path,
            dry_run=True,
            error="not a file",
        )
    try:
        conn = _connect(path, readonly=True, timeout=timeout)
    except (OSError, sqlite3.Error) as exc:
        return TenantLegacyDropReport(path=path, dry_run=True, error=str(exc))
    try:
        tables = _inspect_connection(conn)
    except sqlite3.Error as exc:
        return TenantLegacyDropReport(path=path, dry_run=True, error=str(exc))
    finally:
        conn.close()
    return TenantLegacyDropReport(path=path, dry_run=True, tables=tables)


def drop_empty_legacy_tables(
    path: Path,
    *,
    dry_run: bool = True,
    timeout: float = _CONNECT_TIMEOUT_SECONDS,
) -> TenantLegacyDropReport:
    """DROP leftover tables only when they exist and ``COUNT(*) = 0``.

    Never DELETEs rows. A file that cannot be opened is left unchanged.
    """
    report = inspect_tenant_legacy_tables(path, timeout=timeout)
    report.dry_run = dry_run
    if report.error or dry_run:
        return report

    eligible = [
        name
        for name in _DROP_ORDER
        if name in report.tables and report.tables[name].eligible
    ]
    if not eligible:
        return report

    try:
        conn = _connect(path, readonly=False, timeout=timeout)
    except (OSError, sqlite3.Error) as exc:
        report.error = str(exc)
        report.tables = {
            name: LegacyTableStatus(
                name=name,
                exists=status.exists,
                row_count=status.row_count,
                dropped=False,
            )
            for name, status in report.tables.items()
        }
        return report

    dropped: set[str] = set()
    try:
        conn.execute("BEGIN IMMEDIATE")
        live = _inspect_connection(conn)
        for name in eligible:
            status = live[name]
            if not status.eligible:
                continue
            conn.execute(f"DROP TABLE {_quote_table(name)}")
            dropped.add(name)
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        report.error = str(exc)
        report.tables = {
            name: LegacyTableStatus(
                name=name,
                exists=status.exists,
                row_count=status.row_count,
                dropped=False,
            )
            for name, status in report.tables.items()
        }
        return report
    finally:
        conn.close()

    updated = inspect_tenant_legacy_tables(path, timeout=timeout)
    tables: dict[str, LegacyTableStatus] = {}
    for name in LEGACY_TABLES:
        before = report.tables[name]
        if name in dropped:
            tables[name] = LegacyTableStatus(
                name=name,
                exists=False,
                row_count=0,
                dropped=True,
            )
            continue
        if not updated.error and name in updated.tables:
            after = updated.tables[name]
            tables[name] = LegacyTableStatus(
                name=name,
                exists=after.exists,
                row_count=after.row_count,
            )
        else:
            tables[name] = LegacyTableStatus(
                name=name,
                exists=before.exists,
                row_count=before.row_count,
            )
    return TenantLegacyDropReport(path=path, dry_run=False, tables=tables)


def legacy_tenant_db_paths(data_dir: Path) -> list[Path]:
    """Household files only: ``tenant_*.db``. Not catalog, admin, or ``tenant.db``."""
    if not data_dir.is_dir():
        return []
    return sorted(
        path
        for path in data_dir.glob("tenant_*.db")
        if path.is_file()
    )


def drop_empty_legacy_tables_in_dir(
    data_dir: Path,
    *,
    dry_run: bool = True,
    timeout: float = _CONNECT_TIMEOUT_SECONDS,
) -> list[TenantLegacyDropReport]:
    results: list[TenantLegacyDropReport] = []
    for path in legacy_tenant_db_paths(data_dir):
        results.append(drop_empty_legacy_tables(path, dry_run=dry_run, timeout=timeout))
    return results


def _parse_args(argv: list[str] | None = None) -> Namespace:
    parser = ArgumentParser(
        description=(
            "DROP leftover scheduled_work / evidence_captures tables only when "
            "they are empty. Never deletes rows. Does not run at application "
            "startup. Backup tenant_*.db files before --apply."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
        help="Directory of tenant_*.db files (container data is /data).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="DROP empty leftover tables. Without this flag the run is a dry-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    data_dir = args.data_dir
    dry_run = not args.apply
    if not data_dir.is_dir():
        print(f"No data directory at {data_dir}")
        return 1
    paths = legacy_tenant_db_paths(data_dir)
    if not paths:
        print(f"No tenant_*.db files in {data_dir}")
        return 0
    exit_code = 0
    for report in drop_empty_legacy_tables_in_dir(data_dir, dry_run=dry_run):
        print("\n".join(report.format_lines()))
        if report.error:
            exit_code = 1
    return exit_code
