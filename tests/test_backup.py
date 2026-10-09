"""Backups: consistent database snapshots, an evidence mirror, and a restore drill."""

import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.backup import main, prune_snapshots, run_backup

NOW = datetime(2026, 10, 9, 2, 30, tzinfo=timezone.utc)


def _wal_database(path: Path, rows: int = 3) -> sqlite3.Connection:
    """A WAL database whose newest rows are still only in the -wal file."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE lessons (id INTEGER PRIMARY KEY, title TEXT)")
    conn.executemany(
        "INSERT INTO lessons (title) VALUES (?)", [(f"Lesson {n}",) for n in range(rows)]
    )
    conn.commit()
    return conn  # left open so nothing checkpoints the WAL into the main file


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    return path


def test_snapshot_includes_writes_still_in_the_wal(data_dir: Path, tmp_path: Path) -> None:
    writer = _wal_database(data_dir / "tenant_family.db")
    try:
        manifest = run_backup(data_dir, tmp_path / "backups", now=NOW)
    finally:
        writer.close()

    snapshot = tmp_path / "backups" / "2026-10-09T023000Z"
    copy = sqlite3.connect(snapshot / "tenant_family.db")
    try:
        assert copy.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 3
    finally:
        copy.close()
    assert manifest["databases"] == [
        {"name": "tenant_family.db", "bytes": (snapshot / "tenant_family.db").stat().st_size, "check": "ok"}
    ]
    assert json.loads((snapshot / "manifest.json").read_text())["created_at"] == "2026-10-09T023000Z"


def test_evidence_is_mirrored_once(data_dir: Path, tmp_path: Path) -> None:
    evidence = data_dir / "evidence" / "family"
    evidence.mkdir(parents=True)
    (evidence / "a.webp").write_bytes(b"photo-a")
    dest = tmp_path / "backups"

    first = run_backup(data_dir, dest, evidence_dir=data_dir / "evidence", now=NOW)
    (evidence / "b.webp").write_bytes(b"photo-b")
    second = run_backup(data_dir, dest, evidence_dir=data_dir / "evidence", now=NOW + timedelta(days=1))

    assert first["evidence_files_copied"] == 1
    assert second["evidence_files_copied"] == 1
    assert (dest / "evidence" / "family" / "b.webp").read_bytes() == b"photo-b"


def test_only_the_newest_snapshots_are_kept(data_dir: Path, tmp_path: Path) -> None:
    dest = tmp_path / "backups"
    for day in range(4):
        run_backup(data_dir, dest, keep=10, now=NOW + timedelta(days=day))
    (dest / "evidence").mkdir()

    removed = prune_snapshots(dest, keep=2)

    assert removed == ["2026-10-09T023000Z", "2026-10-10T023000Z"]
    assert sorted(path.name for path in dest.iterdir()) == [
        "2026-10-11T023000Z",
        "2026-10-12T023000Z",
        "evidence",
    ]


def test_restore_drill_brings_the_data_back(data_dir: Path, tmp_path: Path) -> None:
    writer = _wal_database(data_dir / "tenant_family.db", rows=5)
    writer.close()
    run_backup(data_dir, tmp_path / "backups", now=NOW)

    # Disaster: the live file is lost. Restore = copy the snapshot back.
    (data_dir / "tenant_family.db").unlink()
    shutil.copy2(tmp_path / "backups" / "2026-10-09T023000Z" / "tenant_family.db", data_dir)

    restored = sqlite3.connect(data_dir / "tenant_family.db")
    try:
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 5
    finally:
        restored.close()


def test_a_damaged_database_fails_the_run(
    data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (data_dir / "tenant_family.db").write_bytes(b"this is not a database" * 100)

    exit_code = main(["--data-dir", str(data_dir), "--dest", str(tmp_path / "backups")])

    assert exit_code == 1
    assert "tenant_family.db" in capsys.readouterr().err
