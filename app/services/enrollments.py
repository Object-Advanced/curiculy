"""Create or reuse Enrollment rows for a student + curriculum + school year.

Enrollment means “this child is using this program this year.” Settings can
still POST one by hand. Pacing commit and plan-apply call ``ensure_enrollment``
in the same transaction as the assignments they write.
"""

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums import CurriculumSource
from app.models import Curriculum, CurriculumPlan, Enrollment


def get_enrollment(
    db: Session, student_id: int, curriculum_id: int, school_year_id: int
) -> Enrollment | None:
    return (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == student_id,
            Enrollment.curriculum_id == curriculum_id,
            Enrollment.school_year_id == school_year_id,
        )
        .first()
    )


def ensure_enrollment(
    db: Session,
    *,
    student_id: int,
    curriculum_id: int,
    school_year_id: int,
) -> Enrollment:
    """Return the enrollment row, inserting one if this trio is new.

    Does not commit. Unique on student + curriculum + school year; a concurrent
    insert is recovered via savepoint so the outer assignment transaction stays
    intact.
    """
    existing = get_enrollment(db, student_id, curriculum_id, school_year_id)
    if existing is not None:
        return existing
    try:
        with db.begin_nested():
            row = Enrollment(
                student_id=student_id,
                curriculum_id=curriculum_id,
                school_year_id=school_year_id,
            )
            db.add(row)
            db.flush()
            return row
    except IntegrityError:
        found = get_enrollment(db, student_id, curriculum_id, school_year_id)
        if found is None:
            raise
        return found


def enroll_students(
    db: Session,
    student_ids: list[int],
    curriculum_id: int,
    school_year_id: int,
) -> list[Enrollment]:
    return [
        ensure_enrollment(
            db,
            student_id=student_id,
            curriculum_id=curriculum_id,
            school_year_id=school_year_id,
        )
        for student_id in student_ids
    ]


def curriculum_for_plan(db: Session, plan: CurriculumPlan) -> Curriculum:
    """Household library row that a pacing guide enrolls against.

    Plans have no curriculum_id. Reuse a library title that already matches;
    otherwise create one from the plan title so the reading list has a book.
    """
    title = (plan.title or "").strip() or "Untitled plan"
    existing = (
        db.query(Curriculum)
        .filter(func.lower(Curriculum.title) == title.lower())
        .order_by(Curriculum.id.asc())
        .first()
    )
    if existing is not None:
        return existing
    curriculum = Curriculum(
        title=title[:255],
        publisher_name=(plan.publisher or None),
        subject=(plan.subject or None),
        source_type=CurriculumSource.MANUAL,
    )
    db.add(curriculum)
    db.flush()
    return curriculum
