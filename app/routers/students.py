from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_admin_db, get_tenant_db
from app.models import (
    Assignment,
    CalendarException,
    DEFAULT_STUDENT_COLOR,
    Enrollment,
    EvidenceCapture,
    ScheduledWork,
    Student,
    next_unused_student_color,
)
from app.schemas import StudentCreate, StudentRead, StudentSparkRead
from app.schemas.auth import StudentPinUpsert
from app.services.child_accounts import (
    child_login_student_ids,
    delete_child_account,
    upsert_child_pin,
)
from app.services.households import get_default_household
from app.services.spark import lesson_question

router = APIRouter(
    prefix="/students",
    tags=["students"],
    dependencies=[Depends(require_parent)],
)


def _get_student(student_id: int, db: Session) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def _student_read(
    student: Student,
    *,
    login_ids: set[int] | None = None,
    admin_db: Session | None = None,
    tenant_uuid: str | None = None,
) -> StudentRead:
    if login_ids is None:
        login_ids = (
            child_login_student_ids(admin_db, tenant_uuid)
            if admin_db is not None and tenant_uuid
            else set()
        )
    return StudentRead.model_validate(student).model_copy(
        update={"has_login": student.id in login_ids}
    )


def _clear_student_dependents(db: Session, student_id: int) -> None:
    """Remove rows that point at the student but are not cascaded from assignments.

    Assignments, grades, and evidence follow ``Student.assignments``. Enrollments,
    exceptions, and the older scheduled-work tables do not, so they are deleted
    here before the student row itself.
    """
    for model in (EvidenceCapture, ScheduledWork, Enrollment, CalendarException):
        for row in db.query(model).filter(model.student_id == student_id).all():
            db.delete(row)


@router.get("", response_model=list[StudentRead])
def list_students(
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[StudentRead]:
    students = db.query(Student).order_by(Student.id).all()
    login_ids = child_login_student_ids(admin_db, user.tenant_uuid)
    return [_student_read(student, login_ids=login_ids) for student in students]


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> StudentRead:
    return _student_read(
        _get_student(student_id, db),
        admin_db=admin_db,
        tenant_uuid=user.tenant_uuid,
    )


@router.get("/{student_id}/spark", response_model=StudentSparkRead)
def get_student_spark(student_id: int, db: Session = Depends(get_tenant_db)) -> StudentSparkRead:
    """Ask a kind question about today's lessons when the local model is up."""
    student = _get_student(student_id, db)
    titles = [
        title
        for (title,) in db.query(Assignment.title)
        .filter(Assignment.student_id == student.id, Assignment.scheduled_date == date.today())
        .order_by(Assignment.id)
        if title
    ]
    asked = lesson_question(student.name, student.grade, titles)
    if asked is None:
        return StudentSparkRead(student_id=student.id, source="none")
    question, about = asked
    return StudentSparkRead(
        student_id=student.id,
        source="ai",
        question=question,
        about=about,
    )


@router.post("", response_model=StudentRead, status_code=201)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> StudentRead:
    household = get_default_household(db)
    data = payload.model_dump()
    if not data.get("color_hex"):
        taken = {
            (color or DEFAULT_STUDENT_COLOR).lower()
            for (color,) in db.query(Student.color_hex).filter(
                Student.household_id == household.id
            )
        }
        data["color_hex"] = next_unused_student_color(taken)
    student = Student(household_id=household.id, **data)
    db.add(student)
    db.commit()
    db.refresh(student)
    return _student_read(student, admin_db=admin_db, tenant_uuid=user.tenant_uuid)


@router.put("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    payload: StudentCreate,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> StudentRead:
    student = _get_student(student_id, db)
    data = payload.model_dump()
    if not data.get("color_hex"):
        data["color_hex"] = student.color_hex or DEFAULT_STUDENT_COLOR
    for field, value in data.items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return _student_read(student, admin_db=admin_db, tenant_uuid=user.tenant_uuid)


@router.post("/{student_id}/pin", response_model=StudentRead)
def set_student_pin(
    student_id: int,
    payload: StudentPinUpsert,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> StudentRead:
    student = _get_student(student_id, db)
    upsert_child_pin(
        admin_db,
        tenant_uuid=user.tenant_uuid,
        student_id=student.id,
        pin=payload.pin,
    )
    return _student_read(student, admin_db=admin_db, tenant_uuid=user.tenant_uuid)


@router.delete("/{student_id}/pin", response_model=StudentRead)
def clear_student_pin(
    student_id: int,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> StudentRead:
    student = _get_student(student_id, db)
    delete_child_account(admin_db, user.tenant_uuid, student.id)
    return _student_read(student, admin_db=admin_db, tenant_uuid=user.tenant_uuid)


@router.delete("/{student_id}", status_code=204, response_class=Response)
def delete_student(
    student_id: int,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Remove a student; assignments, grades, and evidence cascade away with them."""
    student = _get_student(student_id, db)
    _clear_student_dependents(db, student_id)
    db.delete(student)
    db.commit()
    delete_child_account(admin_db, user.tenant_uuid, student_id)
    return Response(status_code=204)
