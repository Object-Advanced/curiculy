from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, object_session

from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_admin_db
from app.core.deps import get_tenant_db
from app.models import (
    Activity,
    ActivityStudent,
    CalendarException,
    DEFAULT_STUDENT_COLOR,
    Enrollment,
    Student,
    next_unused_student_color,
)
from app.reference.grades import grade_needs_confirming
from app.schemas import GradeConfirm, StudentCreate, StudentRead
from app.schemas.auth import StudentPinUpsert
from app.services.clock import household_today
from app.services.child_accounts import (
    child_login_student_ids,
    delete_child_account,
    upsert_child_pin,
)
from app.services.households import get_default_household

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
    today: date | None = None,
) -> StudentRead:
    if login_ids is None:
        login_ids = (
            child_login_student_ids(admin_db, tenant_uuid)
            if admin_db is not None and tenant_uuid
            else set()
        )
    today = today or household_today(object_session(student))
    return StudentRead.model_validate(student).model_copy(
        update={
            "has_login": student.id in login_ids,
            "grade_needs_confirming": grade_needs_confirming(
                student.grade, student.grade_confirmed_on, today
            ),
        }
    )


def _clear_student_dependents(db: Session, student_id: int) -> None:
    """Remove rows that point at the student but are not cascaded from assignments.

    Assignments, grades, and evidence follow ``Student.assignments``. Enrollments
    and exceptions do not, so they are deleted here before the student row.
    """
    for model in (Enrollment, CalendarException):
        for row in db.query(model).filter(model.student_id == student_id).all():
            db.delete(row)
    # An activity that was only this child's goes with them; a shared one stays
    # for the siblings.
    for activity in db.query(Activity).filter(Activity.students.any(ActivityStudent.student_id == student_id)).all():
        if all(link.student_id == student_id for link in activity.students):
            db.delete(activity)


@router.get("", response_model=list[StudentRead])
def list_students(
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[StudentRead]:
    students = db.query(Student).order_by(Student.id).all()
    login_ids = child_login_student_ids(admin_db, user.tenant_uuid)
    today = household_today(db)
    return [_student_read(student, login_ids=login_ids, today=today) for student in students]


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


@router.post("", response_model=StudentRead, status_code=201)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> StudentRead:
    household = get_default_household(db)
    data = payload.model_dump()
    data["has_iep"] = bool(data.get("has_iep"))
    if data.get("grade"):
        data["grade_confirmed_on"] = household_today(db)
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
    if data.get("has_iep") is None:
        data.pop("has_iep")
    # Re-sending the same grade (older screens send every field) isn't a confirmation.
    if data.get("grade") and data["grade"] != student.grade:
        data["grade_confirmed_on"] = household_today(db)
    for field, value in data.items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return _student_read(student, admin_db=admin_db, tenant_uuid=user.tenant_uuid)


@router.post("/{student_id}/confirm-grade", response_model=StudentRead)
def confirm_grade(
    student_id: int,
    payload: GradeConfirm,
    db: Session = Depends(get_tenant_db),
    admin_db: Session = Depends(get_admin_db),
    user: CurrentUser = Depends(get_current_user),
) -> StudentRead:
    """The child's grade for the new school year (asked again after each July 1)."""
    student = _get_student(student_id, db)
    student.grade = payload.grade
    student.grade_confirmed_on = household_today(db)
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
