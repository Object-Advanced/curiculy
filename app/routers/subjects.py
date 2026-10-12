"""Reference lists, what a state requires, and each child's subjects for a year."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import require_parent
from app.models import Student, StudentSubject
from app.reference.grades import GRADES, normalize_grade
from app.reference.states import STATES, normalize_state
from app.reference.subjects import SUBJECTS
from app.schemas.subjects import (
    GradeOption,
    ReferenceRead,
    StateOption,
    StateSubjectsRead,
    StudentSubjectCreate,
    StudentSubjectRead,
    StudentSubjectsRead,
    StudentSubjectUpdate,
    SubjectOption,
)
from app.services.subjects import (
    OWN,
    REQUIRED,
    add_subject,
    school_year_or_current,
    state_subjects,
    student_subjects,
)

reference_router = APIRouter(tags=["reference"])
router = APIRouter(tags=["subjects"], dependencies=[Depends(require_parent)])


@reference_router.get("/reference", response_model=ReferenceRead)
def reference() -> ReferenceRead:
    """The fixed lists: states, grades and subjects. Public: nothing private in it."""
    return ReferenceRead(
        states=[StateOption(code=code, name=name) for code, name in STATES.items()],
        grades=[GradeOption(code=code, label=label) for code, label in GRADES],
        subjects=[
            SubjectOption(code=s.code, name=s.name, group=s.group, covers=s.covers) for s in SUBJECTS
        ],
    )


@reference_router.get("/state-requirements/{state_code}/subjects", response_model=StateSubjectsRead)
def required_subjects(state_code: str, grade: str | None = Query(default=None)) -> StateSubjectsRead:
    """What a state requires for a grade (public, like the state pages on the website)."""
    try:
        code = normalize_state(state_code)
        grade_code = normalize_grade(grade) if grade else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return state_subjects(code, grade_code)


def _student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def _row(db: Session, subject_id: int) -> StudentSubject:
    row = db.get(StudentSubject, subject_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return row


@router.get("/students/{student_id}/subjects", response_model=StudentSubjectsRead)
def list_subjects(
    student_id: int,
    school_year_id: int | None = Query(default=None),
    db: Session = Depends(get_tenant_db),
) -> StudentSubjectsRead:
    """The child's subjects this school year; the state's required ones are added automatically."""
    student = _student(db, student_id)
    return student_subjects(db, student, school_year_or_current(db, school_year_id))


@router.post("/students/{student_id}/subjects", response_model=StudentSubjectsRead, status_code=201)
def create_subject(
    student_id: int,
    payload: StudentSubjectCreate,
    db: Session = Depends(get_tenant_db),
) -> StudentSubjectsRead:
    student = _student(db, student_id)
    year = school_year_or_current(db, payload.school_year_id)
    add_subject(
        db,
        student,
        year,
        subject_code=payload.subject_code,
        name=payload.name,
        counts_toward=payload.counts_toward,
    )
    return student_subjects(db, student, year)


@router.patch("/student-subjects/{subject_id}", response_model=StudentSubjectRead)
def update_subject(
    subject_id: int,
    payload: StudentSubjectUpdate,
    db: Session = Depends(get_tenant_db),
) -> StudentSubjectRead:
    """Turn a subject on or off for this year, write its objective, or rename your own."""
    row = _row(db, subject_id)
    if (payload.name is not None or payload.counts_toward is not None or payload.clear_counts_toward) and row.kind != OWN:
        raise HTTPException(status_code=409, detail="Only your own subjects can be renamed or re-mapped.")
    if payload.active is not None:
        row.active = payload.active
    if payload.objective is not None:
        row.objective = payload.objective.strip() or None
    if payload.name is not None:
        row.name = " ".join(payload.name.split())
    if payload.clear_counts_toward:
        row.counts_toward = None
    elif payload.counts_toward is not None:
        row.counts_toward = payload.counts_toward
    db.commit()
    year_view = student_subjects(db, _student(db, row.student_id), school_year_or_current(db, row.school_year_id))
    return next(item for item in year_view.subjects if item.id == row.id)


@router.delete("/student-subjects/{subject_id}", status_code=204, response_class=Response)
def delete_subject(subject_id: int, db: Session = Depends(get_tenant_db)) -> Response:
    row = _row(db, subject_id)
    if row.kind == REQUIRED:
        raise HTTPException(
            status_code=409,
            detail="Your state requires this subject. Turn it off for this year instead.",
        )
    db.delete(row)
    db.commit()
    return Response(status_code=204)
