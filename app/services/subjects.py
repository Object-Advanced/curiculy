"""Each child's subjects for a school year, kept in step with the family's state.

Required subjects come from the state's reviewed rules for the child's grade
band (``app.reference.state_subjects``). They're added automatically, and
re-labelled if the family moves or the child changes band; a subject that is
no longer required becomes a common one rather than disappearing, so its
objective isn't lost.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SchoolYear, Student, StudentSubject
from app.reference.state_subjects import STATE_SUBJECTS, Band, band_for
from app.reference.states import STATES
from app.reference.subjects import SUBJECTS, SUBJECTS_BY_CODE, subject_name
from app.schemas.subjects import (
    RequiredSubject,
    StateSubjectsRead,
    StudentSubjectRead,
    StudentSubjectsRead,
)
from app.services.clock import household_today
from app.services.households import get_default_household, state_on
from app.services.school_year import require_operational_school_year

REQUIRED, COMMON, OWN = "required", "common", "own"
_ORDER = {subject.code: index for index, subject in enumerate(SUBJECTS)}


def state_subjects(state_code: str, grade: str | None) -> StateSubjectsRead:
    rules = STATE_SUBJECTS.get(state_code)
    band = band_for(state_code, grade)
    return StateSubjectsRead(
        state_code=state_code,
        state_name=STATES[state_code],
        grade=grade,
        supported=rules is not None,
        band=band.name if band else None,
        rule=rules.rule if rules else None,
        subjects=[
            RequiredSubject(
                code=code,
                name=subject_name(code) or code,
                state_label=label,
                every_year=code in rules.every_year,
            )
            for code, label in (band.subjects if band else ())
        ]
        if rules
        else [],
        sources=list(rules.sources) if rules else [],
    )


def school_year_or_current(db: Session, school_year_id: int | None) -> SchoolYear:
    if school_year_id is None:
        year = require_operational_school_year(db)
        db.commit()
        return year
    year = db.get(SchoolYear, school_year_id)
    if year is None:
        raise HTTPException(status_code=404, detail="School year not found")
    return year


def state_for_year(db: Session, year: SchoolYear) -> str | None:
    """The state on the year's first day, or today if the year has started."""
    return state_on(get_default_household(db), max(household_today(db), year.start_date))


def _sync(db: Session, student: Student, year: SchoolYear, band: Band | None) -> list[StudentSubject]:
    rows = db.scalars(
        select(StudentSubject).where(
            StudentSubject.student_id == student.id, StudentSubject.school_year_id == year.id
        )
    ).all()
    required = {code for code, _ in band.subjects} if band else set()
    by_code = {row.subject_code: row for row in rows if row.subject_code}
    for code in required - by_code.keys():
        row = StudentSubject(
            student_id=student.id,
            school_year_id=year.id,
            subject_code=code,
            name=subject_name(code) or code,
            kind=REQUIRED,
            counts_toward=code,
            active=True,
        )
        db.add(row)
        rows.append(row)
    for row in rows:
        if row.subject_code in required:
            row.kind = REQUIRED
        elif row.kind == REQUIRED:
            row.kind = COMMON
    db.commit()
    return rows


def _covered_before(db: Session, student: Student, year: SchoolYear) -> set[str]:
    earlier = db.execute(
        select(StudentSubject.subject_code, StudentSubject.counts_toward)
        .join(SchoolYear, SchoolYear.id == StudentSubject.school_year_id)
        .where(
            StudentSubject.student_id == student.id,
            StudentSubject.active.is_(True),
            SchoolYear.start_date < year.start_date,
        )
    ).all()
    return {code for row in earlier for code in row if code}


def _read(
    row: StudentSubject,
    *,
    band: Band | None,
    every_year: frozenset[str],
    covered: set[str],
    state_name: str | None,
) -> StudentSubjectRead:
    labels = dict(band.subjects) if band else {}
    code = row.subject_code or row.counts_toward
    yearly = row.kind == REQUIRED and row.subject_code in every_year
    return StudentSubjectRead(
        id=row.id,
        subject_code=row.subject_code,
        name=row.name,
        kind=row.kind,
        counts_toward=row.counts_toward,
        counts_toward_name=subject_name(row.counts_toward),
        active=row.active,
        objective=row.objective,
        covered_before=bool(code and code in covered),
        every_year=yearly,
        state_label=labels.get(row.subject_code or ""),
        warning=f"{state_name} expects this every year." if yearly and not row.active else None,
    )


def _sort_key(row: StudentSubject) -> tuple:
    kind_order = {REQUIRED: 0, COMMON: 1, OWN: 2}[row.kind]
    return (kind_order, _ORDER.get(row.subject_code or "", 99), row.position, row.id or 0)


def student_subjects(db: Session, student: Student, year: SchoolYear) -> StudentSubjectsRead:
    state_code = state_for_year(db, year)
    rules = STATE_SUBJECTS.get(state_code or "")
    band = band_for(state_code, student.grade)
    rows = _sync(db, student, year, band)
    covered = _covered_before(db, student, year)
    every_year = rules.every_year if rules else frozenset()
    state_name = STATES.get(state_code or "")
    return StudentSubjectsRead(
        student_id=student.id,
        school_year_id=year.id,
        state_code=state_code,
        supported=rules is not None,
        band=band.name if band else None,
        rule=rules.rule if rules else None,
        subjects=[
            _read(row, band=band, every_year=every_year, covered=covered, state_name=state_name)
            for row in sorted(rows, key=_sort_key)
        ],
    )


def add_subject(
    db: Session,
    student: Student,
    year: SchoolYear,
    *,
    subject_code: str | None,
    name: str | None,
    counts_toward: str | None,
) -> StudentSubject:
    if subject_code is not None:
        existing = db.scalars(
            select(StudentSubject).where(
                StudentSubject.student_id == student.id,
                StudentSubject.school_year_id == year.id,
                StudentSubject.subject_code == subject_code,
            )
        ).first()
        if existing is not None:
            existing.active = True
            db.commit()
            return existing
        row = StudentSubject(
            student_id=student.id,
            school_year_id=year.id,
            subject_code=subject_code,
            name=SUBJECTS_BY_CODE[subject_code].name,
            kind=COMMON,
            counts_toward=subject_code,
        )
    else:
        row = StudentSubject(
            student_id=student.id,
            school_year_id=year.id,
            subject_code=None,
            name=name or "",
            kind=OWN,
            counts_toward=counts_toward,
        )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
