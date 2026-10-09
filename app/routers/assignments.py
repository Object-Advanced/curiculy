"""Assignment endpoints: the student calendar, the detail view, and their writes.

The routes sit under different path roots but answer the same question, so they
share a module rather than a prefix. Both bounds of a window are inclusive, and
``period`` is the shorthand a calendar uses: ``?period=month`` with no dates
means the month containing today.

Every write answers with the full detail payload, because the caller is a
calendar that has to repaint a tile and a modal from the response alone.
"""

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_catalog_db, get_tenant_db
from app.enums import CalendarPeriod, UserRole
from app.evidence import store_capture
from app.models import (
    Assignment,
    AssignmentEvidence,
    AssignmentGrade,
    CurriculumResource,
    CurriculumUnit,
    Student,
    SubjectTaxonomy,
)
from app.models.mixins import utcnow
from app.schemas import (
    AssignmentCalendarRead,
    AssignmentCreate,
    AssignmentDetailRead,
    AssignmentEvidenceRead,
    AssignmentGradeUpsert,
    AssignmentRead,
    AssignmentStatusUpdate,
    AssignmentUpdate,
    StudentCourseRead,
)
from app.services.assignments import AssignmentQuery, InvalidDateRangeError, resolve_window
from app.services.child_accounts import is_child
from app.services.clock import household_today

router = APIRouter(tags=["assignments"], dependencies=[Depends(get_current_user)])


def _require_student_access(user: CurrentUser, student_id: int) -> None:
    if user.role == UserRole.CHILD.value and user.student_id != student_id:
        raise HTTPException(status_code=404, detail="Student not found")


def _require_assignment_access(user: CurrentUser, assignment: Assignment) -> None:
    if user.role == UserRole.CHILD.value and assignment.student_id != user.student_id:
        raise HTTPException(status_code=404, detail="Assignment not found")


def _sync_shared_group(
    tenant_db: Session,
    assignment: Assignment,
    *,
    sync_status: bool = False,
    sync_completion_date: bool = False,
) -> None:
    """Copy completion fields onto every sibling that shares this lesson."""
    if not assignment.shared_group_uuid:
        return
    for member in AssignmentQuery(tenant_db).for_shared_group(assignment.shared_group_uuid):
        if member.id == assignment.id:
            continue
        if sync_status:
            member.status = assignment.status
        if sync_completion_date:
            member.completion_date = assignment.completion_date


def _load_assignment(tenant_db: Session, catalog_db: Session, assignment_id: int) -> Assignment:
    assignment = AssignmentQuery(tenant_db, catalog_db).get(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


def _require_references(
    tenant_db: Session, catalog_db: Session, payload: AssignmentCreate
) -> None:
    """Resolve the optional catalog links up front.

    Left to the database these would surface as an opaque integrity error, or as
    nothing at all on a SQLite file with foreign keys switched off.
    """
    if tenant_db.get(Student, payload.student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if payload.curriculum_resource_id is not None and tenant_db.get(
        CurriculumResource, payload.curriculum_resource_id
    ) is None:
        raise HTTPException(status_code=404, detail="Curriculum resource not found")
    if payload.curriculum_unit_id is not None and tenant_db.get(
        CurriculumUnit, payload.curriculum_unit_id
    ) is None:
        raise HTTPException(status_code=404, detail="Curriculum unit not found")
    if payload.subject_taxonomy_id is not None and catalog_db.get(
        SubjectTaxonomy, payload.subject_taxonomy_id
    ) is None:
        raise HTTPException(status_code=404, detail="Subject not found")


def _require_completion_after_schedule(
    scheduled_date: date,
    completion_date: date | None,
) -> None:
    if completion_date is not None and completion_date < scheduled_date:
        raise HTTPException(
            status_code=400,
            detail="completion_date must be on or after scheduled_date",
        )


@router.get("/students/{student_id}/assignments", response_model=AssignmentCalendarRead)
def list_student_assignments(
    student_id: int,
    start_date: date | None = Query(
        default=None,
        description="Inclusive lower bound, or the date a 'period' is anchored on.",
    ),
    end_date: date | None = Query(
        default=None,
        description="Inclusive upper bound. Cannot be combined with 'period'.",
    ),
    period: CalendarPeriod | None = Query(
        default=None,
        description="Resolves to explicit bounds around 'start_date', or around "
        "today when no date is given. Weeks run Monday to Sunday.",
    ),
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> AssignmentCalendarRead:
    _require_student_access(user, student_id)
    student = tenant_db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    try:
        window = resolve_window(
            start_date=start_date,
            end_date=end_date,
            period=period,
            today=household_today(tenant_db),
        )
    except InvalidDateRangeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    assignments = AssignmentQuery(tenant_db, catalog_db).for_student(student_id, window)
    return AssignmentCalendarRead(
        student_id=student_id,
        period=period,
        start_date=window.start_date,
        end_date=window.end_date,
        count=len(assignments),
        assignments=[AssignmentRead.model_validate(item) for item in assignments],
    )


@router.get("/students/{student_id}/courses", response_model=list[StudentCourseRead])
def list_student_courses(
    student_id: int,
    _user: CurrentUser = Depends(require_parent),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> list[StudentCourseRead]:
    """Active courses for a student dashboard, with completed / total lesson counts."""
    student = tenant_db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return [
        StudentCourseRead.model_validate(course)
        for course in AssignmentQuery(tenant_db, catalog_db).courses_for_student(student_id)
    ]


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetailRead)
def get_assignment(
    assignment_id: int,
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Assignment:
    assignment = _load_assignment(tenant_db, catalog_db, assignment_id)
    _require_assignment_access(user, assignment)
    return assignment


@router.post("/assignments", response_model=AssignmentDetailRead, status_code=201)
def create_assignment(
    payload: AssignmentCreate,
    _user: CurrentUser = Depends(require_parent),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Assignment:
    _require_references(tenant_db, catalog_db, payload)
    _require_completion_after_schedule(payload.scheduled_date, payload.completion_date)

    assignment = Assignment(**payload.model_dump())
    tenant_db.add(assignment)
    tenant_db.commit()
    # Re-read so the response carries the eagerly loaded display text the
    # calendar renders a tile from, rather than lazy-loading it per field.
    return _load_assignment(tenant_db, catalog_db, assignment.id)


@router.patch("/assignments/{assignment_id}/status", response_model=AssignmentDetailRead)
def update_assignment_status(
    assignment_id: int,
    payload: AssignmentStatusUpdate,
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Assignment:
    """Mark an assignment complete (or move it to any other status).

    Parents may do this for any household assignment and still sync a shared
    group. A child may change status only on their own row, and never on a
    sibling's copy.
    """
    assignment = _load_assignment(tenant_db, catalog_db, assignment_id)
    _require_assignment_access(user, assignment)
    assignment.status = payload.status
    if not is_child(user):
        _sync_shared_group(tenant_db, assignment, sync_status=True)
    tenant_db.commit()
    return _load_assignment(tenant_db, catalog_db, assignment_id)


@router.put("/assignments/{assignment_id}", response_model=AssignmentDetailRead)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    _user: CurrentUser = Depends(require_parent),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Assignment:
    """Reschedule an assignment, mark it complete, or move its status."""
    assignment = _load_assignment(tenant_db, catalog_db, assignment_id)
    changes = payload.model_dump(exclude_unset=True)
    # The two dates are checked against each other after the merge, since a
    # request that moves only one of them still has to end up consistent.
    _require_completion_after_schedule(
        changes.get("scheduled_date", assignment.scheduled_date),
        changes.get("completion_date", assignment.completion_date),
    )

    for field, value in changes.items():
        setattr(assignment, field, value)
    if "status" in changes or "completion_date" in changes:
        _sync_shared_group(
            tenant_db,
            assignment,
            sync_status="status" in changes,
            sync_completion_date="completion_date" in changes,
        )
    tenant_db.commit()
    return _load_assignment(tenant_db, catalog_db, assignment_id)


@router.put("/assignments/{assignment_id}/grade", response_model=AssignmentDetailRead)
def upsert_assignment_grade(
    assignment_id: int,
    payload: AssignmentGradeUpsert,
    _parent: CurrentUser = Depends(require_parent),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Assignment:
    """Record the grade for an assignment, replacing any grade already there.

    An existing row is mutated in place instead of being swapped for a new
    ``AssignmentGrade``. The relationship is ``delete-orphan`` and a flush emits
    inserts before deletes, so assigning a replacement object would send the new
    row while the old one still holds the same ``assignment_id`` and break the
    unique constraint on it.
    """
    assignment = _load_assignment(tenant_db, catalog_db, assignment_id)
    values = payload.model_dump()

    if assignment.grade is None:
        assignment.grade = AssignmentGrade(**values)
    else:
        for field, value in values.items():
            setattr(assignment.grade, field, value)
    tenant_db.commit()
    return _load_assignment(tenant_db, catalog_db, assignment_id)


@router.post(
    "/assignments/{assignment_id}/evidence",
    response_model=AssignmentEvidenceRead,
    status_code=201,
)
def upload_assignment_evidence(
    assignment_id: int,
    file: UploadFile = File(...),
    apply_to_group: bool = Query(
        False,
        description="Ignored when the assignment has a shared_group_uuid: evidence "
        "is always attached to every sibling in that group. Kept so older clients "
        "that still send the flag continue to work.",
    ),
    user: CurrentUser = Depends(require_parent),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> AssignmentEvidence:
    """Attach a photo of completed work to an assignment.

    When the assignment belongs to a shared group, the same stored file is
    linked from every sibling so the household does not keep duplicate copies.
    """
    _ = apply_to_group
    assignment = _load_assignment(tenant_db, catalog_db, assignment_id)
    file_path = store_capture(file.file, tenant_uuid=user.tenant_uuid)
    captured_at = utcnow()

    by_id = {assignment.id: assignment}
    if assignment.shared_group_uuid:
        for member in AssignmentQuery(tenant_db, catalog_db).for_shared_group(
            assignment.shared_group_uuid
        ):
            by_id.setdefault(member.id, member)

    uploaded = None
    for target in by_id.values():
        evidence = AssignmentEvidence(
            file_path=file_path,
            captured_at=captured_at,
        )
        target.evidence.append(evidence)
        if target.id == assignment.id:
            uploaded = evidence

    tenant_db.commit()
    tenant_db.refresh(uploaded)
    return uploaded


@router.delete("/assignments/{assignment_id}", status_code=204, response_class=Response)
def delete_assignment(
    assignment_id: int,
    _user: CurrentUser = Depends(require_parent),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Response:
    """Remove an assignment; its grade and evidence cascade away with it."""
    assignment = _load_assignment(tenant_db, catalog_db, assignment_id)
    tenant_db.delete(assignment)
    tenant_db.commit()
    return Response(status_code=204)
