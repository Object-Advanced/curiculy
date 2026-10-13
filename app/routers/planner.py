"""The Curriculum planner: build a subject's curriculum around a textbook, then
schedule it for one or more children.

Every change also updates the curriculum's contribution to the community
catalog (once it's fully built), so the next family with the same textbook can
start from it. See docs/6-planning/product-spine.md.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_catalog_db
from app.schemas.planner import (
    CurriculumCreate,
    CurriculumItemWrite,
    CurriculumRead,
    CurriculumUpdate,
    FromCommunityRequest,
    SchedulePreview,
    ScheduleRequest,
    ScheduleResult,
    UnscheduleResult,
)
from app.services import community
from app.services import planner as service
from app.services.library import get_item

router = APIRouter(prefix="/planner", tags=["planner"], dependencies=[Depends(require_parent)])


def _changed(db: Session, catalog_db: Session, curriculum_id: int, user: CurrentUser) -> CurriculumRead:
    service.refresh_contribution(db, catalog_db, curriculum_id, community.family_of(user))
    return service.curriculum_read(db, service.get_curriculum(db, curriculum_id))


@router.get("/curricula", response_model=list[CurriculumRead])
def list_curricula(db: Session = Depends(get_tenant_db)) -> list[CurriculumRead]:
    return [service.curriculum_read(db, curriculum) for curriculum in service.list_curricula(db)]


@router.post("/curricula", response_model=CurriculumRead, status_code=201)
def create_curriculum(
    payload: CurriculumCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> CurriculumRead:
    """Start a curriculum, usually from a textbook (its subject and grade carry over)."""
    curriculum = service.create_curriculum(db, payload)
    return _changed(db, catalog_db, curriculum.id, user)


@router.post("/curricula/from-community", response_model=CurriculumRead, status_code=201)
def create_from_community(
    payload: FromCommunityRequest,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> CurriculumRead:
    """Start from a curriculum other families built. Its books are added to your
    library (or your copies are used), and you can change anything after."""
    curriculum = service.from_community(
        db, catalog_db, payload.community_curriculum_id, payload.entry_ids, payload.name,
        counted=community.family_of(user) is not None,
    )
    return _changed(db, catalog_db, curriculum.id, user)


@router.get("/curricula/{planned_curriculum_id}", response_model=CurriculumRead)
def read_curriculum(planned_curriculum_id: int, db: Session = Depends(get_tenant_db)) -> CurriculumRead:
    return service.curriculum_read(db, service.get_curriculum(db, planned_curriculum_id))


@router.patch("/curricula/{planned_curriculum_id}", response_model=CurriculumRead)
def update_curriculum(
    planned_curriculum_id: int,
    payload: CurriculumUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> CurriculumRead:
    service.update_curriculum(db, service.get_curriculum(db, planned_curriculum_id), payload)
    return _changed(db, catalog_db, planned_curriculum_id, user)


@router.delete("/curricula/{planned_curriculum_id}", status_code=204, response_class=Response)
def delete_curriculum(
    planned_curriculum_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Response:
    """Delete a curriculum that isn't on anyone's calendar (unschedule it first)."""
    service.delete_curriculum(db, service.get_curriculum(db, planned_curriculum_id))
    service.refresh_contribution(db, catalog_db, planned_curriculum_id, community.family_of(user))
    return Response(status_code=204)


@router.post("/curricula/{planned_curriculum_id}/items", response_model=CurriculumRead)
def add_item(
    planned_curriculum_id: int,
    payload: CurriculumItemWrite,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> CurriculumRead:
    """Add a library item as the textbook, a workbook, an online site, a book to
    read, or something for the parent."""
    curriculum = service.get_curriculum(db, planned_curriculum_id)
    service.add_item(db, curriculum, get_item(db, payload.library_item_id), payload.role)
    db.commit()
    return _changed(db, catalog_db, planned_curriculum_id, user)


@router.delete("/curricula/{planned_curriculum_id}/items/{item_id}", response_model=CurriculumRead)
def remove_item(
    planned_curriculum_id: int,
    item_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> CurriculumRead:
    """Take a library item out of the curriculum (it stays in your library)."""
    curriculum = service.get_curriculum(db, planned_curriculum_id)
    service.remove_item(curriculum, item_id)
    db.commit()
    return _changed(db, catalog_db, planned_curriculum_id, user)


@router.post("/curricula/{planned_curriculum_id}/schedule/preview", response_model=SchedulePreview)
def preview_schedule(
    planned_curriculum_id: int, payload: ScheduleRequest, db: Session = Depends(get_tenant_db)
) -> SchedulePreview:
    """What scheduling would put on the calendar, for each child. Nothing is saved."""
    return service.preview(db, service.get_curriculum(db, planned_curriculum_id), payload)


@router.post("/curricula/{planned_curriculum_id}/schedule", response_model=ScheduleResult, status_code=201)
def schedule(
    planned_curriculum_id: int, payload: ScheduleRequest, db: Session = Depends(get_tenant_db)
) -> ScheduleResult:
    """Put it on the calendar: a course and dated lessons for each child."""
    return service.schedule(db, service.get_curriculum(db, planned_curriculum_id), payload)


@router.delete("/courses/{course_id}", response_model=UnscheduleResult)
def unschedule(course_id: int, db: Session = Depends(get_tenant_db)) -> UnscheduleResult:
    """Take a course off the calendar. Finished lessons stay on the day they were done."""
    removed, kept = service.unschedule(db, service.get_course(db, course_id))
    return UnscheduleResult(lessons_removed=removed, lessons_kept=kept)
