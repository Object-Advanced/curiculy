"""Syllabus generation endpoints: preview the pacing, then commit it.

The two routes are deliberately a read and a write of the same payload. A preview
is pure calculation and touches nothing, so a parent can drag the target date
around and watch the schedule change; the commit takes the lessons that came back
and writes them once, as a unit.

Both directions of a bad fit are answered rather than refused. Too few lessons
for the window spreads them out, too many stacks them up and returns a warning
alongside the schedule, because only the parent can decide whether the deadline
or the workload should move.
"""

from math import ceil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_catalog_db, get_tenant_db
from app.models import BookEdition, CurriculumEdition, Student, SubjectTaxonomy
from app.schemas import (
    PacingCalculation,
    PacingCommitRead,
    PacingCommitRequest,
    PacingPreviewRead,
    PacingPreviewRequest,
)
from app.services.ai_generator import SyllabusGenerationError, SyllabusGenerator
from app.services.clock import household_today
from app.services.pacing import PacingEngine, PacingError, SyllabusCommitError, SyllabusCommitter

router = APIRouter(
    prefix="/pacing",
    tags=["pacing"],
    dependencies=[Depends(require_parent)],
)


def _load_book(db: Session, book_id: int) -> BookEdition:
    book = db.get(BookEdition, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book edition not found")
    return book


def _sync_page_count(book: BookEdition, end_page: int) -> None:
    """Keep the catalog's page count in step with the range the parent just used.

    A missing or zero count is filled in. A different count is overwritten, so a
    custom end page typed in Auto-schedule becomes the default for the next run.
    """
    if book.page_count in (None, 0) or book.page_count != end_page:
        book.page_count = end_page


def _require_references(
    tenant_db: Session, catalog_db: Session, payload: PacingCommitRequest
) -> None:
    """Resolve every reference up front.

    Left to the database these would surface as an opaque integrity error, or as
    nothing at all on a SQLite file with foreign keys switched off.
    """
    for student_id in payload.students_to_schedule():
        if tenant_db.get(Student, student_id) is None:
            raise HTTPException(status_code=404, detail="Student not found")
        for model, entity_id, missing, db in (
            (CurriculumEdition, payload.curriculum_edition_id, "Curriculum edition not found", tenant_db),
            (BookEdition, payload.book_id, "Book edition not found", catalog_db),
            (SubjectTaxonomy, payload.subject_taxonomy_id, "Subject not found", catalog_db),
        ):
            if entity_id is not None and db.get(model, entity_id) is None:
                raise HTTPException(status_code=404, detail=missing)


@router.post("/generate-preview", response_model=PacingPreviewRead)
def generate_preview(
    payload: PacingPreviewRequest,
    catalog_db: Session = Depends(get_catalog_db),
    tenant_db: Session = Depends(get_tenant_db),
) -> PacingPreviewRead:
    """Draft a syllabus for a page range, paced by a deadline or a daily page count."""
    book = _load_book(catalog_db, payload.book_id)
    start_date = payload.start_date or household_today(tenant_db)
    total_pages = payload.end_page - payload.start_page + 1

    engine = PacingEngine()
    try:
        if payload.pages_per_day is not None:
            target_lessons = ceil(total_pages / payload.pages_per_day)
            school_days = engine.school_days_ahead(
                start_date,
                target_lessons,
                payload.active_weekdays,
                payload.excluded_dates,
            )
            distribution = engine.distribute_lessons(target_lessons, len(school_days))
            scheduled_dates = engine.assign_dates(school_days, target_lessons)
            lessons = SyllabusGenerator().generate_syllabus(
                book_title=book.work.title,
                start_page=payload.start_page,
                end_page=payload.end_page,
                target_lessons=target_lessons,
                pages_per_day=payload.pages_per_day,
            )
            finish_date = scheduled_dates[-1]
            pages_per_lesson = float(payload.pages_per_day)
        else:
            school_days = engine.school_days(
                start_date,
                payload.target_completion_date,
                payload.active_weekdays,
                payload.excluded_dates,
            )
            # One lesson per school day is the natural default, but a short range
            # cannot be cut into more lessons than it has pages.
            target_lessons = payload.target_lessons or min(len(school_days), total_pages)
            distribution = engine.distribute_lessons(target_lessons, len(school_days))
            scheduled_dates = engine.assign_dates(school_days, target_lessons)
            lessons = SyllabusGenerator().generate_syllabus(
                book_title=book.work.title,
                start_page=payload.start_page,
                end_page=payload.end_page,
                target_lessons=target_lessons,
            )
            finish_date = payload.target_completion_date
            pages_per_lesson = round(total_pages / target_lessons, 2)
    except (PacingError, SyllabusGenerationError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    _sync_page_count(book, payload.end_page)
    catalog_db.commit()

    return PacingPreviewRead(
        book_id=book.id,
        book_title=book.work.title,
        pacing=PacingCalculation(
            start_date=start_date,
            target_completion_date=finish_date,
            active_weekdays=payload.active_weekdays,
            available_days=distribution.available_days,
            total_lessons=distribution.total_lessons,
            total_pages=total_pages,
            pages_per_lesson=pages_per_lesson,
            lessons_per_day=distribution.lessons_per_day,
            day_interval=distribution.day_interval,
            is_rigorous=distribution.is_rigorous,
            warning=distribution.warning,
        ),
        lessons=[
            lesson.model_copy(update={"scheduled_date": day})
            for lesson, day in zip(lessons, scheduled_dates, strict=True)
        ],
    )


@router.post("/commit", response_model=PacingCommitRead, status_code=201)
def commit_syllabus(
    payload: PacingCommitRequest,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> PacingCommitRead:
    """Write an approved syllabus as catalog structure and dated assignments."""
    _require_references(tenant_db, catalog_db, payload)
    if payload.book_id is not None and payload.end_page is not None:
        _sync_page_count(_load_book(catalog_db, payload.book_id), payload.end_page)
    try:
        return SyllabusCommitter(catalog_db, tenant_db).commit(payload)
    except SyllabusCommitError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
