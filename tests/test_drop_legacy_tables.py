"""Operator DROP of empty leftover scheduled_work / evidence_captures tables."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.schema_patches import apply_tenant_schema
from app.services.legacy_table_drop import (
    drop_empty_legacy_tables,
    drop_empty_legacy_tables_in_dir,
    inspect_tenant_legacy_tables,
    legacy_tenant_db_paths,
    main,
)
from sqlalchemy import create_engine, text


def _create_tenant(
    directory: Path,
    name: str,
    *,
    scheduled: int | None = None,
    evidence: int | None = None,
    unrelated: bool = True,
) -> Path:
    path = directory / name
    conn = sqlite3.connect(path)
    try:
        if unrelated:
            conn.execute(
                "CREATE TABLE assignments (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
            )
            conn.execute("INSERT INTO assignments (id, title) VALUES (1, 'keep')")
        if scheduled is not None:
            conn.execute(
                """
                CREATE TABLE scheduled_work (
                    id INTEGER PRIMARY KEY,
                    enrollment_id INTEGER,
                    student_id INTEGER,
                    unit_id INTEGER,
                    title TEXT NOT NULL
                )
                """
            )
            for index in range(scheduled):
                conn.execute(
                    "INSERT INTO scheduled_work "
                    "(id, enrollment_id, student_id, title) VALUES (?, 1, 1, ?)",
                    (index + 1, f"legacy-{index + 1}"),
                )
        if evidence is not None:
            conn.execute(
                """
                CREATE TABLE evidence_captures (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER,
                    scheduled_work_id INTEGER,
                    path TEXT
                )
                """
            )
            for index in range(evidence):
                conn.execute(
                    "INSERT INTO evidence_captures "
                    "(id, student_id, scheduled_work_id, path) VALUES (?, 1, 1, ?)",
                    (index + 1, f"old-{index + 1}.webp"),
                )
        conn.commit()
    finally:
        conn.close()
    return path


def _table_names(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        conn.close()


def _rows(path: Path, table: str, columns: str) -> list[tuple]:
    conn = sqlite3.connect(path)
    try:
        return list(conn.execute(f"SELECT {columns} FROM {table} ORDER BY id"))
    finally:
        conn.close()


class TestLegacyTableDrop:
    def test_both_legacy_tables_absent_is_not_an_error(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_absent.db")
        report = drop_empty_legacy_tables(path, dry_run=False)

        assert report.error is None
        assert report.absent == ["scheduled_work", "evidence_captures"]
        assert report.dropped == []
        assert report.refused == []
        assert "assignments" in _table_names(path)
        assert _rows(path, "assignments", "id, title") == [(1, "keep")]

    def test_both_empty_tables_are_dropped_on_apply(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_empty.db", scheduled=0, evidence=0)
        report = drop_empty_legacy_tables(path, dry_run=False)

        assert report.error is None
        assert report.dropped == ["scheduled_work", "evidence_captures"]
        lines = "\n".join(report.format_lines())
        assert "scheduled_work: 0 rows, DROPPED" in lines
        assert "evidence_captures: 0 rows, DROPPED" in lines
        names = _table_names(path)
        assert "scheduled_work" not in names
        assert "evidence_captures" not in names
        assert "assignments" in names

    def test_only_empty_table_is_dropped_when_the_other_has_rows(
        self, tmp_path: Path
    ) -> None:
        path = _create_tenant(tmp_path, "tenant_mixed.db", scheduled=0, evidence=2)
        report = drop_empty_legacy_tables(path, dry_run=False)

        assert report.dropped == ["scheduled_work"]
        assert report.refused == ["evidence_captures"]
        assert report.tables["evidence_captures"].row_count == 2
        names = _table_names(path)
        assert "scheduled_work" not in names
        assert "evidence_captures" in names
        assert _rows(path, "evidence_captures", "id, path") == [
            (1, "old-1.webp"),
            (2, "old-2.webp"),
        ]

    def test_both_nonempty_tables_are_refused(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_full.db", scheduled=2, evidence=1)
        report = drop_empty_legacy_tables(path, dry_run=False)

        assert report.dropped == []
        assert report.refused == ["scheduled_work", "evidence_captures"]
        assert report.tables["scheduled_work"].row_count == 2
        assert report.tables["evidence_captures"].row_count == 1
        assert "scheduled_work" in _table_names(path)
        assert "evidence_captures" in _table_names(path)
        assert _rows(path, "scheduled_work", "id, title") == [
            (1, "legacy-1"),
            (2, "legacy-2"),
        ]
        assert _rows(path, "evidence_captures", "id, path") == [(1, "old-1.webp")]

    def test_rerun_after_cleanup_is_idempotent(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_again.db", scheduled=0, evidence=0)
        first = drop_empty_legacy_tables(path, dry_run=False)
        second = drop_empty_legacy_tables(path, dry_run=False)

        assert first.dropped == ["scheduled_work", "evidence_captures"]
        assert second.error is None
        assert second.absent == ["scheduled_work", "evidence_captures"]
        assert second.dropped == []
        assert "assignments" in _table_names(path)

    def test_unrelated_tables_survive(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_keep.db", scheduled=0, evidence=0)
        drop_empty_legacy_tables(path, dry_run=False)

        assert _table_names(path) == {"assignments"}
        assert _rows(path, "assignments", "id, title") == [(1, "keep")]

    def test_nonempty_legacy_rows_are_unchanged(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_rows.db", scheduled=1, evidence=0)
        before = _rows(path, "scheduled_work", "id, enrollment_id, student_id, title")
        drop_empty_legacy_tables(path, dry_run=False)
        after = _rows(path, "scheduled_work", "id, enrollment_id, student_id, title")

        assert before == [(1, 1, 1, "legacy-1")]
        assert after == before

    def test_multiple_tenant_files_are_isolated(self, tmp_path: Path) -> None:
        empty = _create_tenant(tmp_path, "tenant_one.db", scheduled=0, evidence=0)
        kept = _create_tenant(tmp_path, "tenant_two.db", scheduled=3, evidence=1)
        reports = {
            report.path.name: report
            for report in drop_empty_legacy_tables_in_dir(tmp_path, dry_run=False)
        }

        assert reports["tenant_one.db"].dropped == [
            "scheduled_work",
            "evidence_captures",
        ]
        assert reports["tenant_two.db"].dropped == []
        assert reports["tenant_two.db"].refused == [
            "scheduled_work",
            "evidence_captures",
        ]
        assert "scheduled_work" not in _table_names(empty)
        assert _rows(kept, "scheduled_work", "id, title") == [
            (1, "legacy-1"),
            (2, "legacy-2"),
            (3, "legacy-3"),
        ]

    def test_dry_run_performs_no_drop(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_dry.db", scheduled=0, evidence=0)
        report = drop_empty_legacy_tables(path, dry_run=True)

        assert report.dry_run is True
        assert report.eligible == ["scheduled_work", "evidence_captures"]
        assert report.dropped == []
        assert "would DROP" in "\n".join(report.format_lines())
        assert "scheduled_work" in _table_names(path)
        assert "evidence_captures" in _table_names(path)

    def test_malformed_database_is_left_untouched(self, tmp_path: Path) -> None:
        path = tmp_path / "tenant_bad.db"
        path.write_text("this is not sqlite", encoding="utf-8")
        before = path.read_bytes()
        report = drop_empty_legacy_tables(path, dry_run=False)

        assert report.error
        assert report.dropped == []
        assert path.read_bytes() == before

    def test_dir_scan_continues_after_a_malformed_file(self, tmp_path: Path) -> None:
        bad = tmp_path / "tenant_bad.db"
        bad.write_text("not a database", encoding="utf-8")
        good = _create_tenant(tmp_path, "tenant_good.db", scheduled=0, evidence=0)
        reports = drop_empty_legacy_tables_in_dir(tmp_path, dry_run=False)
        by_name = {report.path.name: report for report in reports}

        assert by_name["tenant_bad.db"].error
        assert by_name["tenant_bad.db"].dropped == []
        assert by_name["tenant_good.db"].dropped == [
            "scheduled_work",
            "evidence_captures",
        ]
        assert "scheduled_work" not in _table_names(good)

    def test_missing_legacy_table_is_not_an_error(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_one_table.db", scheduled=0)
        report = drop_empty_legacy_tables(path, dry_run=False)

        assert report.error is None
        assert report.dropped == ["scheduled_work"]
        assert report.absent == ["evidence_captures"]
        assert "evidence_captures" not in _table_names(path)

    def test_report_counts_match_sqlite(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_counts.db", scheduled=4, evidence=0)
        inspected = inspect_tenant_legacy_tables(path)

        assert inspected.tables["scheduled_work"].row_count == 4
        assert inspected.tables["evidence_captures"].row_count == 0
        lines = "\n".join(inspected.format_lines())
        assert "scheduled_work: 4 rows, refused (not empty)" in lines
        assert "evidence_captures: 0 rows, would DROP" in lines

    def test_catalog_admin_and_shared_tenant_files_are_not_scanned(
        self, tmp_path: Path
    ) -> None:
        _create_tenant(tmp_path, "catalog.db", scheduled=0, evidence=0)
        _create_tenant(tmp_path, "admin.db", scheduled=0, evidence=0)
        _create_tenant(tmp_path, "tenant.db", scheduled=0, evidence=0)
        household = _create_tenant(tmp_path, "tenant_live.db", scheduled=0, evidence=0)

        paths = legacy_tenant_db_paths(tmp_path)
        assert paths == [household]
        drop_empty_legacy_tables_in_dir(tmp_path, dry_run=False)

        assert "scheduled_work" in _table_names(tmp_path / "catalog.db")
        assert "scheduled_work" in _table_names(tmp_path / "admin.db")
        assert "scheduled_work" in _table_names(tmp_path / "tenant.db")
        assert "scheduled_work" not in _table_names(household)

    def test_locked_database_is_not_dropped(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_lock.db", scheduled=0, evidence=0)
        holder = sqlite3.connect(path)
        try:
            holder.execute("BEGIN EXCLUSIVE")
            report = drop_empty_legacy_tables(path, dry_run=False, timeout=0.2)
        finally:
            holder.rollback()
            holder.close()

        assert report.error
        assert report.dropped == []
        assert "scheduled_work" in _table_names(path)
        assert "evidence_captures" in _table_names(path)

    def test_cli_dry_run_default_does_not_drop(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_cli.db", scheduled=0, evidence=0)
        code = main(["--data-dir", str(tmp_path)])

        assert code == 0
        assert "scheduled_work" in _table_names(path)
        assert "evidence_captures" in _table_names(path)

    def test_cli_apply_drops_empty_tables(self, tmp_path: Path) -> None:
        path = _create_tenant(tmp_path, "tenant_cli_apply.db", scheduled=0, evidence=0)
        code = main(["--data-dir", str(tmp_path), "--apply"])

        assert code == 0
        names = _table_names(path)
        assert "scheduled_work" not in names
        assert "evidence_captures" not in names

    def test_cli_reports_malformed_file_and_returns_error(self, tmp_path: Path) -> None:
        (tmp_path / "tenant_bad.db").write_text("nope", encoding="utf-8")
        code = main(["--data-dir", str(tmp_path), "--apply"])
        assert code == 1

    def test_cli_missing_data_dir_returns_error(self, tmp_path: Path) -> None:
        code = main(["--data-dir", str(tmp_path / "missing")])
        assert code == 1

    def test_boot_schema_still_does_not_drop_legacy_tables(self, tmp_path: Path) -> None:
        path = tmp_path / "tenant_boot.db"
        engine = create_engine(f"sqlite:///{path}")
        try:
            apply_tenant_schema(engine)
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE scheduled_work (id INTEGER PRIMARY KEY)"))
                conn.execute(
                    text("CREATE TABLE evidence_captures (id INTEGER PRIMARY KEY)")
                )
            apply_tenant_schema(engine)
        finally:
            engine.dispose()
        names = _table_names(path)
        assert "scheduled_work" in names
        assert "evidence_captures" in names
