"""Leftover scheduled_work / evidence_captures rows on older tenant files."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.legacy_tables import (
    delete_legacy_rows_for_enrollments,
    delete_legacy_rows_for_student,
    delete_legacy_rows_for_units,
)


def _create_orphan_tables(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE scheduled_work (
                id INTEGER PRIMARY KEY,
                enrollment_id INTEGER,
                student_id INTEGER,
                unit_id INTEGER,
                title VARCHAR(255) NOT NULL
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE evidence_captures (
                id INTEGER PRIMARY KEY,
                student_id INTEGER,
                scheduled_work_id INTEGER,
                path VARCHAR(255)
            )
            """
        )
    )
    db.commit()


class TestDeleteLegacyRows:
    def test_student_helper_is_a_noop_when_tables_are_absent(self, db: Session) -> None:
        delete_legacy_rows_for_student(db, 1)

    def test_student_helper_clears_rows_created_after_create_all(
        self, db: Session
    ) -> None:
        _create_orphan_tables(db)
        db.execute(
            text(
                "INSERT INTO scheduled_work (id, enrollment_id, student_id, title) "
                "VALUES (1, 9, 7, 'legacy')"
            )
        )
        db.execute(
            text(
                "INSERT INTO evidence_captures "
                "(id, student_id, scheduled_work_id, path) "
                "VALUES (1, 7, 1, 'old.webp')"
            )
        )
        db.commit()

        delete_legacy_rows_for_student(db, 7)
        db.commit()

        assert db.execute(text("SELECT COUNT(*) FROM scheduled_work")).scalar() == 0
        assert db.execute(text("SELECT COUNT(*) FROM evidence_captures")).scalar() == 0

    def test_unit_helper_is_a_noop_for_an_empty_id_list(self, db: Session) -> None:
        _create_orphan_tables(db)
        db.execute(
            text(
                "INSERT INTO scheduled_work (id, enrollment_id, student_id, unit_id, title) "
                "VALUES (1, 1, 1, 4, 'legacy')"
            )
        )
        db.commit()

        delete_legacy_rows_for_units(db, [])
        db.commit()

        assert db.execute(text("SELECT COUNT(*) FROM scheduled_work")).scalar() == 1

    def test_unit_helper_clears_work_and_linked_captures(self, db: Session) -> None:
        _create_orphan_tables(db)
        db.execute(
            text(
                "INSERT INTO scheduled_work (id, enrollment_id, student_id, unit_id, title) "
                "VALUES (1, 1, 1, 4, 'keep'), (2, 1, 1, 8, 'drop')"
            )
        )
        db.execute(
            text(
                "INSERT INTO evidence_captures "
                "(id, student_id, scheduled_work_id, path) "
                "VALUES (1, 1, 1, 'keep.webp'), (2, 1, 2, 'drop.webp')"
            )
        )
        db.commit()

        delete_legacy_rows_for_units(db, [8])
        db.commit()

        leftover_work = db.execute(text("SELECT id FROM scheduled_work")).scalars().all()
        leftover_evidence = db.execute(
            text("SELECT id FROM evidence_captures")
        ).scalars().all()
        assert leftover_work == [1]
        assert leftover_evidence == [1]

    def test_enrollment_helper_clears_work_for_those_enrollments(
        self, db: Session
    ) -> None:
        _create_orphan_tables(db)
        db.execute(
            text(
                "INSERT INTO scheduled_work (id, enrollment_id, student_id, title) "
                "VALUES (1, 3, 1, 'drop'), (2, 4, 1, 'keep')"
            )
        )
        db.commit()

        delete_legacy_rows_for_enrollments(db, [3])
        db.commit()

        leftover = db.execute(text("SELECT id FROM scheduled_work")).scalars().all()
        assert leftover == [2]
