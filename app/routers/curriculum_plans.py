"""Structured pacing-guide catalog: CSV/PDF import, manual builder, and apply.

These routes live under ``/curriculum`` (singular) so they never collide with the
household book catalog at ``/curricula``. A pacing guide is a flat sequence of
daily lessons, not an Auto-schedule program tree. CSV imports finish inline;
PDF imports create the plan immediately and parse lessons in a background task.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.enums import CurriculumPlanStatus
from app.models import CurriculumLesson, CurriculumPlan, Student
from app.schemas.curriculum_plans import (
    CurriculumLessonRead,
    CurriculumLessonWrite,
    CurriculumPlanApplyRead,
    CurriculumPlanApplyRequest,
    CurriculumPlanArchiveRequest,
    CurriculumPlanDetailRead,
    CurriculumPlanImportRead,
    CurriculumPlanListRead,
    CurriculumPlanPdfImportRead,
    CurriculumPlanWrite,
    dump_json_value,
)
from app.services.ai_curriculum_worker import process_pdf_curriculum_background
from app.services.curriculum_plan_apply import (
    CurriculumPlanApplyError,
    apply_curriculum_plan,
)
from app.services.curriculum_plan_import import (
    CurriculumPlanImportError,
    import_pacing_csv,
    plan_title_from_filename,
)

router = APIRouter(
    prefix="/curriculum",
    tags=["curriculum-plans"],
    dependencies=[Depends(require_parent)],
)


def _plan_list_item(plan: CurriculumPlan, lesson_count: int) -> CurriculumPlanListRead:
    return CurriculumPlanListRead(
        id=plan.id,
        title=plan.title,
        publisher=plan.publisher,
        author=plan.author,
        grade_level=plan.grade_level,
        subject=plan.subject,
        frequency_days=plan.frequency_days,
        total_weeks=plan.total_weeks,
        grading_weights=plan.grading_weights,
        is_archived=plan.is_archived,
        status=plan.status,
        created_at=plan.created_at,
        lesson_count=lesson_count,
    )


def _ordered_lessons(db: Session, plan_id: int) -> list[CurriculumLesson]:
    return (
        db.query(CurriculumLesson)
        .filter(CurriculumLesson.plan_id == plan_id)
        .order_by(
            CurriculumLesson.week_number.asc(),
            CurriculumLesson.day_number.asc(),
            CurriculumLesson.id.asc(),
        )
        .all()
    )


def _plan_detail(db: Session, plan: CurriculumPlan) -> CurriculumPlanDetailRead:
    lessons = _ordered_lessons(db, plan.id)
    return CurriculumPlanDetailRead(
        id=plan.id,
        title=plan.title,
        publisher=plan.publisher,
        author=plan.author,
        grade_level=plan.grade_level,
        subject=plan.subject,
        frequency_days=plan.frequency_days,
        total_weeks=plan.total_weeks,
        grading_weights=plan.grading_weights,
        is_archived=plan.is_archived,
        status=plan.status,
        created_at=plan.created_at,
        lessons=[CurriculumLessonRead.model_validate(lesson) for lesson in lessons],
    )


def _require_plan(db: Session, plan_id: int) -> CurriculumPlan:
    plan = db.get(CurriculumPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Curriculum plan not found")
    return plan


def _lesson_columns(item: CurriculumLessonWrite) -> dict[str, object]:
    return {
        "unit_title": item.unit_title,
        "week_number": item.week_number,
        "day_number": item.day_number,
        "title": (item.title or "").strip()[:255],
        "description": item.description,
        "pages": item.pages,
        "notes": item.notes,
        "category": item.category,
        "time_slot": item.time_slot,
        "resources": dump_json_value(item.resources),
    }


def _apply_plan_metadata(plan: CurriculumPlan, payload: CurriculumPlanWrite) -> None:
    plan.title = payload.title[:255]
    plan.publisher = payload.publisher
    plan.author = payload.author
    plan.grade_level = payload.grade_level
    plan.subject = payload.subject
    plan.frequency_days = payload.frequency_days
    plan.total_weeks = payload.total_weeks
    plan.grading_weights = dump_json_value(payload.grading_weights)


def _content_lessons(payload: CurriculumPlanWrite) -> list[CurriculumLessonWrite]:
    return [item for item in payload.lessons if item.has_content]


def _sync_lessons(
    db: Session, plan: CurriculumPlan, payload: CurriculumPlanWrite
) -> None:
    incoming = _content_lessons(payload)
    existing = {lesson.id: lesson for lesson in plan.lessons}
    keep_ids: set[int] = set()
    to_add: list[CurriculumLesson] = []
    for item in incoming:
        if item.id is None:
            to_add.append(CurriculumLesson(plan_id=plan.id, **_lesson_columns(item)))
            continue
        row = existing.get(item.id)
        if row is None:
            raise HTTPException(
                status_code=400,
                detail=f"lesson {item.id} does not belong to this plan",
            )
        for key, value in _lesson_columns(item).items():
            setattr(row, key, value)
        keep_ids.add(item.id)
    for lesson in list(plan.lessons):
        if lesson.id in existing and lesson.id not in keep_ids:
            db.delete(lesson)
    db.add_all(to_add)


@router.post(
    "/import-csv",
    response_model=CurriculumPlanImportRead,
    status_code=201,
)
async def import_curriculum_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_tenant_db),
) -> CurriculumPlanImportRead:
    """Accept a pacing-guide CSV and bulk-insert a new plan plus its lessons."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="the CSV payload is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400, detail="the CSV file must be UTF-8 text"
        ) from error
    try:
        plan = import_pacing_csv(db, text, file.filename)
    except CurriculumPlanImportError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    return CurriculumPlanImportRead(id=plan.id)


@router.post(
    "/import-pdf",
    response_model=CurriculumPlanPdfImportRead,
    status_code=202,
)
async def import_curriculum_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_tenant_db),
) -> CurriculumPlanPdfImportRead:
    """Accept a pacing-guide PDF and queue AI parsing in the background."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="the PDF payload is empty")
    plan = CurriculumPlan(
        title=plan_title_from_filename(file.filename)[:255],
        status=CurriculumPlanStatus.PROCESSING,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    background_tasks.add_task(
        process_pdf_curriculum_background,
        plan.id,
        raw,
        db,
    )
    return CurriculumPlanPdfImportRead(
        plan_id=plan.id,
        message="PDF accepted for background AI processing.",
    )


@router.get("/plans", response_model=list[CurriculumPlanListRead])
def list_curriculum_plans(
    archived: bool = Query(False),
    db: Session = Depends(get_tenant_db),
) -> list[CurriculumPlanListRead]:
    """List saved pacing guides and how many lessons each one contains."""
    lesson_count = func.count(CurriculumLesson.id)
    query = db.query(CurriculumPlan, lesson_count).outerjoin(
        CurriculumLesson, CurriculumLesson.plan_id == CurriculumPlan.id
    )
    if not archived:
        query = query.filter(CurriculumPlan.is_archived.is_(False))
    rows = (
        query.group_by(CurriculumPlan.id)
        .order_by(CurriculumPlan.created_at.desc(), CurriculumPlan.id.desc())
        .all()
    )
    return [_plan_list_item(plan, count) for plan, count in rows]


@router.post("/plans", response_model=CurriculumPlanDetailRead, status_code=201)
def create_curriculum_plan(
    payload: CurriculumPlanWrite,
    db: Session = Depends(get_tenant_db),
) -> CurriculumPlanDetailRead:
    """Create a custom pacing guide and its nested lesson rows."""
    plan = CurriculumPlan()
    _apply_plan_metadata(plan, payload)
    db.add(plan)
    db.flush()
    db.add_all(
        [
            CurriculumLesson(plan_id=plan.id, **_lesson_columns(item))
            for item in _content_lessons(payload)
        ]
    )
    db.commit()
    db.refresh(plan)
    return _plan_detail(db, plan)


@router.get("/plans/{plan_id}", response_model=CurriculumPlanDetailRead)
def get_curriculum_plan(
    plan_id: int,
    db: Session = Depends(get_tenant_db),
) -> CurriculumPlanDetailRead:
    """Return one pacing guide and its lessons in week/day order."""
    return _plan_detail(db, _require_plan(db, plan_id))


@router.put("/plans/{plan_id}", response_model=CurriculumPlanDetailRead)
def update_curriculum_plan(
    plan_id: int,
    payload: CurriculumPlanWrite,
    db: Session = Depends(get_tenant_db),
) -> CurriculumPlanDetailRead:
    """Update plan metadata and replace the lesson list with the payload."""
    plan = _require_plan(db, plan_id)
    _apply_plan_metadata(plan, payload)
    _sync_lessons(db, plan, payload)
    db.commit()
    db.refresh(plan)
    return _plan_detail(db, plan)


@router.post("/plans/{plan_id}/archive", response_model=CurriculumPlanListRead)
def archive_curriculum_plan(
    plan_id: int,
    payload: CurriculumPlanArchiveRequest | None = None,
    db: Session = Depends(get_tenant_db),
) -> CurriculumPlanListRead:
    """Soft-archive or restore a pacing guide."""
    plan = _require_plan(db, plan_id)
    plan.is_archived = True if payload is None else payload.is_archived
    db.commit()
    db.refresh(plan)
    count = (
        db.query(func.count(CurriculumLesson.id))
        .filter(CurriculumLesson.plan_id == plan.id)
        .scalar()
        or 0
    )
    return _plan_list_item(plan, count)


@router.delete("/plans/{plan_id}", status_code=204, response_class=Response)
def delete_curriculum_plan(
    plan_id: int,
    db: Session = Depends(get_tenant_db),
) -> Response:
    """Permanently delete a pacing guide and its lessons."""
    plan = _require_plan(db, plan_id)
    db.delete(plan)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/plans/{plan_id}/apply",
    response_model=CurriculumPlanApplyRead,
    status_code=201,
)
def apply_plan_to_calendar(
    plan_id: int,
    payload: CurriculumPlanApplyRequest,
    db: Session = Depends(get_tenant_db),
) -> CurriculumPlanApplyRead:
    """Generate dated assignments from the plan's week/day sequence."""
    plan = _require_plan(db, plan_id)
    student = db.get(Student, payload.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    try:
        return apply_curriculum_plan(
            db,
            plan,
            student,
            payload.start_date,
            payload.target_days,
        )
    except CurriculumPlanApplyError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
