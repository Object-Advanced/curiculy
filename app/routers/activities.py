"""Activities: "5K race, PE, 40 minutes", with a photo at the finish line.

What a subject without a curriculum looks like on the record. See
docs/6-planning/product-spine.md ("Activities").
"""

from datetime import date

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import CurrentUser, get_current_user, require_parent
from app.evidence import store_capture
from app.schemas.activities import ActivityCreate, ActivityEvidenceRead, ActivityRead, ActivityUpdate
from app.services import activities as service
from app.models.mixins import utcnow

router = APIRouter(prefix="/activities", tags=["activities"], dependencies=[Depends(require_parent)])


@router.get("", response_model=list[ActivityRead])
def list_activities(
    student_id: int | None = Query(None),
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    db: Session = Depends(get_tenant_db),
) -> list[ActivityRead]:
    """Newest first. ``from`` and ``to`` include the days given."""
    return [service.activity_read(row) for row in service.list_activities(db, student_id=student_id, start=start, end=end)]


@router.post("", response_model=ActivityRead, status_code=201)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_tenant_db)) -> ActivityRead:
    return service.activity_read(service.create_activity(db, payload))


@router.get("/{activity_id}", response_model=ActivityRead)
def get_activity(activity_id: int, db: Session = Depends(get_tenant_db)) -> ActivityRead:
    return service.activity_read(service.get_activity(db, activity_id))


@router.patch("/{activity_id}", response_model=ActivityRead)
def update_activity(activity_id: int, payload: ActivityUpdate, db: Session = Depends(get_tenant_db)) -> ActivityRead:
    return service.activity_read(service.update_activity(db, service.get_activity(db, activity_id), payload))


@router.delete("/{activity_id}", status_code=204, response_class=Response)
def delete_activity(activity_id: int, db: Session = Depends(get_tenant_db)) -> Response:
    service.delete_activity(db, service.get_activity(db, activity_id))
    return Response(status_code=204)


@router.post("/{activity_id}/evidence", response_model=ActivityEvidenceRead, status_code=201)
def upload_activity_evidence(
    activity_id: int,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> ActivityEvidenceRead:
    """A photo or PDF from the activity: a work sample for each of its subjects."""
    activity = service.get_activity(db, activity_id)
    file_path = store_capture(file.file, tenant_uuid=user.tenant_uuid)
    row = service.add_evidence(db, activity, file_path, utcnow())
    return ActivityEvidenceRead(id=row.id, file_path=row.file_path, captured_at=row.captured_at)


@router.delete("/{activity_id}/evidence/{activity_evidence_id}", status_code=204, response_class=Response)
def delete_activity_evidence(
    activity_id: int, activity_evidence_id: int, db: Session = Depends(get_tenant_db)
) -> Response:
    service.remove_evidence(db, service.get_activity(db, activity_id), activity_evidence_id)
    return Response(status_code=204)
