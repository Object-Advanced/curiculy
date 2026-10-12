"""Backups: the verified whole-database dump, per-family copies, and restoring one family."""

from __future__ import annotations

import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.db import open_family_session, owner_engine
from app.models import Assignment, Household, Student
from app.services.family_data import (
    advance_sequences,
    delete_family_rows,
    export_family,
    read_export,
    restore_family,
    write_export,
)
from scripts import backup
from scripts.restore_family import restore_from_file

pytestmark = pytest.mark.usefixtures("committed_db")


def _family(tenant_id: str, child: str, lessons: int = 2) -> None:
    session = open_family_session(tenant_id)
    try:
        household = Household(name=f"{child} family")
        session.add(household)
        session.flush()
        student = Student(household_id=household.id, name=child)
        session.add(student)
        session.flush()
        for day in range(1, lessons + 1):
            session.add(
                Assignment(student_id=student.id, title=f"{child} lesson {day}", scheduled_date=date(2026, 10, day))
            )
        session.commit()
    finally:
        session.close()


def _export(tenant_id: str) -> dict:
    session = open_family_session(tenant_id)
    try:
        return export_family(session)
    finally:
        session.close()


def _names(tenant_id: str) -> list[str]:
    session = open_family_session(tenant_id)
    try:
        return [row.title for row in session.query(Assignment).order_by(Assignment.id)]
    finally:
        session.close()


class TestFamilyCopies:
    def test_export_holds_only_that_family(self) -> None:
        _family("family-a", "Ada")
        _family("family-b", "Ben")
        export = _export("family-a")
        assert export["tenant_id"] == "family-a"
        assert [row["name"] for row in export["tables"]["students"]] == ["Ada"]
        assert all(
            row["tenant_id"] == "family-a" for rows in export["tables"].values() for row in rows
        )

    def test_restore_brings_one_family_back_and_leaves_others_alone(self, tmp_path: Path) -> None:
        _family("family-a", "Ada")
        _family("family-b", "Ben")
        path = tmp_path / "family-a.json.gz"
        write_export(path, _export("family-a"))

        session = open_family_session("family-a")
        try:
            delete_family_rows(session)
            session.add(Household(name="Changed after the backup"))
            session.commit()
        finally:
            session.close()

        tenant_id, restored = restore_from_file(path)

        assert (tenant_id, restored) == ("family-a", 4)
        assert _names("family-a") == ["Ada lesson 1", "Ada lesson 2"]
        assert _names("family-b") == ["Ben lesson 1", "Ben lesson 2"]
        assert _export("family-a")["tables"] == read_export(path)["tables"]

    def test_a_copy_cannot_be_restored_into_another_family(self) -> None:
        _family("family-a", "Ada")
        export = _export("family-a")
        session = open_family_session("family-b")
        try:
            with pytest.raises(ValueError, match="different family"):
                restore_family(session, export)
        finally:
            session.close()

    def test_new_rows_after_a_restore_get_fresh_ids(self, tmp_path: Path) -> None:
        _family("family-a", "Ada")
        path = tmp_path / "a.json.gz"
        write_export(path, _export("family-a"))
        restore_from_file(path)
        advance_sequences(owner_engine())
        _family("family-b", "Ben", lessons=1)
        assert _names("family-b") == ["Ben lesson 1"]


def test_snapshots_keep_only_the_newest(tmp_path: Path) -> None:
    for name in ("2026-10-01T000000Z", "2026-10-02T000000Z", "2026-10-03T000000Z", "notes"):
        (tmp_path / name).mkdir()
    assert backup.prune_snapshots(tmp_path, keep=2) == ["2026-10-01T000000Z"]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "2026-10-02T000000Z",
        "2026-10-03T000000Z",
        "notes",
    ]


def test_evidence_mirror_copies_only_new_files(tmp_path: Path) -> None:
    source = tmp_path / "evidence" / "family-a"
    source.mkdir(parents=True)
    (source / "one.webp").write_bytes(b"one")
    mirror = tmp_path / "mirror"
    assert backup.mirror_evidence(tmp_path / "evidence", mirror) == 1
    (source / "two.webp").write_bytes(b"two")
    assert backup.mirror_evidence(tmp_path / "evidence", mirror) == 1
    assert (mirror / "family-a" / "two.webp").read_bytes() == b"two"


@pytest.mark.skipif(shutil.which("pg_dump") is None, reason="needs the Postgres client tools")
def test_nightly_backup_dumps_verifies_and_copies_each_family(tmp_path: Path) -> None:
    _family("family-a", "Ada")
    _family("family-b", "Ben")
    _family("demo-0123456789abcdef", "Visitor")
    evidence = tmp_path / "evidence"
    (evidence / "family-a").mkdir(parents=True)
    (evidence / "family-a" / "page.webp").write_bytes(b"photo")

    manifest = backup.run_backup(
        tmp_path / "backups",
        evidence_dir=evidence,
        now=datetime(2026, 10, 12, 2, 0, tzinfo=timezone.utc),
    )

    snapshot = tmp_path / "backups" / "2026-10-12T020000Z"
    assert (snapshot / "curiculy.dump").stat().st_size > 0
    assert manifest["database"]["restored_rows"]["students"] == 3
    assert [row["family"] for row in manifest["families"]] == ["family-a", "family-b"]
    assert read_export(snapshot / "families" / "family-a.json.gz")["tenant_id"] == "family-a"
    assert manifest["evidence_files_copied"] == 1
    assert (snapshot / "manifest.json").is_file()
