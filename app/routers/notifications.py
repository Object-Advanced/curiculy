"""In-app notifications for the parent household account."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.schemas.homework import ParentNotificationListRead, ParentNotificationRead
from app.services.notifications import list_notifications, mark_all_read, mark_read, unread_count

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=ParentNotificationListRead)
def get_notifications(db: Session = Depends(get_tenant_db)) -> ParentNotificationListRead:
    rows = list_notifications(db)
    return ParentNotificationListRead(
        unread_count=unread_count(db),
        notifications=[ParentNotificationRead.model_validate(row) for row in rows],
    )


@router.post("/read-all", response_model=ParentNotificationListRead)
def read_all_notifications(db: Session = Depends(get_tenant_db)) -> ParentNotificationListRead:
    mark_all_read(db)
    db.commit()
    rows = list_notifications(db)
    return ParentNotificationListRead(
        unread_count=0,
        notifications=[ParentNotificationRead.model_validate(row) for row in rows],
    )


@router.post("/{notification_id}/read", response_model=ParentNotificationRead)
def read_notification(
    notification_id: int, db: Session = Depends(get_tenant_db)
) -> ParentNotificationRead:
    row = mark_read(db, notification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    db.refresh(row)
    return ParentNotificationRead.model_validate(row)
