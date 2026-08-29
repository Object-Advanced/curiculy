"""Orphan ``scheduled_work`` / ``evidence_captures`` tables on older tenant files.

The live calendar is ``Assignment``. Those two tables are not mapped anymore and
were empty on every family file we could inspect. Existing SQLite files may still
contain the tables (``create_all`` does not drop them). Do not DROP them here.

Student and curriculum deletes still clear leftover rows so a forgotten FK
cannot block removal.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.orm import Session

ORPHAN_TABLES = ("evidence_captures", "scheduled_work")


def _table_names(session: Session) -> set[str]:
    bind = session.get_bind()
    if bind is None:
        return set()
    # sqlite_master is live on this connection. Inspector.get_table_names() can
    # return a cache from create_all, which would miss leftover tables created
    # later on the same engine.
    if bind.dialect.name == "sqlite":
        rows = session.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'table'")
        ).all()
        return {str(row[0]) for row in rows}
    inspector = inspect(bind)
    inspector.clear_cache()
    return set(inspector.get_table_names())


def _present_orphans(session: Session) -> set[str]:
    names = _table_names(session)
    return {name for name in ORPHAN_TABLES if name in names}


def _delete_in(session: Session, sql: str, key: str, ids: Sequence[int]) -> None:
    stmt = text(sql).bindparams(bindparam(key, expanding=True))
    session.execute(stmt, {key: list(ids)})


def delete_legacy_rows_for_student(session: Session, student_id: int) -> None:
    tables = _present_orphans(session)
    if "evidence_captures" in tables:
        session.execute(
            text("DELETE FROM evidence_captures WHERE student_id = :id"),
            {"id": student_id},
        )
    if "scheduled_work" in tables:
        session.execute(
            text("DELETE FROM scheduled_work WHERE student_id = :id"),
            {"id": student_id},
        )


def delete_legacy_rows_for_units(session: Session, unit_ids: Sequence[int]) -> None:
    ids = [int(item) for item in unit_ids]
    if not ids:
        return
    tables = _present_orphans(session)
    if "scheduled_work" not in tables:
        return
    if "evidence_captures" in tables:
        _delete_in(
            session,
            "DELETE FROM evidence_captures WHERE scheduled_work_id IN "
            "(SELECT id FROM scheduled_work WHERE unit_id IN :ids)",
            "ids",
            ids,
        )
    _delete_in(
        session,
        "DELETE FROM scheduled_work WHERE unit_id IN :ids",
        "ids",
        ids,
    )


def delete_legacy_rows_for_enrollments(
    session: Session, enrollment_ids: Sequence[int]
) -> None:
    ids = [int(item) for item in enrollment_ids]
    if not ids:
        return
    tables = _present_orphans(session)
    if "scheduled_work" not in tables:
        return
    if "evidence_captures" in tables:
        _delete_in(
            session,
            "DELETE FROM evidence_captures WHERE scheduled_work_id IN "
            "(SELECT id FROM scheduled_work WHERE enrollment_id IN :ids)",
            "ids",
            ids,
        )
    _delete_in(
        session,
        "DELETE FROM scheduled_work WHERE enrollment_id IN :ids",
        "ids",
        ids,
    )


def delete_legacy_rows_for_student(session: Session, student_id: int) -> None:
    tables = _table_names(session)
    if "evidence_captures" in tables:
        session.execute(
            text("DELETE FROM evidence_captures WHERE student_id = :id"),
            {"id": student_id},
        )
    if "scheduled_work" in tables:
        session.execute(
            text("DELETE FROM scheduled_work WHERE student_id = :id"),
            {"id": student_id},
        )


def delete_legacy_rows_for_units(session: Session, unit_ids: Sequence[int]) -> None:
    ids = [int(item) for item in unit_ids]
    if not ids:
        return
    tables = _table_names(session)
    if "scheduled_work" not in tables:
        return
    if "evidence_captures" in tables:
        _delete_in(
            session,
            "DELETE FROM evidence_captures WHERE scheduled_work_id IN "
            "(SELECT id FROM scheduled_work WHERE unit_id IN :ids)",
            "ids",
            ids,
        )
    _delete_in(
        session,
        "DELETE FROM scheduled_work WHERE unit_id IN :ids",
        "ids",
        ids,
    )


def delete_legacy_rows_for_enrollments(
    session: Session, enrollment_ids: Sequence[int]
) -> None:
    ids = [int(item) for item in enrollment_ids]
    if not ids:
        return
    tables = _table_names(session)
    if "scheduled_work" not in tables:
        return
    if "evidence_captures" in tables:
        _delete_in(
            session,
            "DELETE FROM evidence_captures WHERE scheduled_work_id IN "
            "(SELECT id FROM scheduled_work WHERE enrollment_id IN :ids)",
            "ids",
            ids,
        )
    _delete_in(
        session,
        "DELETE FROM scheduled_work WHERE enrollment_id IN :ids",
        "ids",
        ids,
    )
