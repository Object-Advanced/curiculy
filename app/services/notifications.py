"""In-app notifications for homework help and curriculum-plan processing."""

from sqlalchemy.orm import Session

from app.enums import ParentNotificationType
from app.models import ParentNotification, Student
from app.models.mixins import utcnow


def create_notification(
    db: Session,
    *,
    type: ParentNotificationType,
    student_id: int | None,
    assignment_id: int | None,
    title: str,
    body: str,
) -> ParentNotification:
    row = ParentNotification(
        type=type,
        student_id=student_id,
        assignment_id=assignment_id,
        title=title,
        body=body,
    )
    db.add(row)
    db.flush()
    return row


def list_notifications(db: Session, *, limit: int = 50) -> list[ParentNotification]:
    return (
        db.query(ParentNotification)
        .order_by(ParentNotification.id.desc())
        .limit(limit)
        .all()
    )


def unread_count(db: Session) -> int:
    return (
        db.query(ParentNotification)
        .filter(ParentNotification.read_at.is_(None))
        .count()
    )


def mark_read(db: Session, notification_id: int) -> ParentNotification | None:
    row = db.get(ParentNotification, notification_id)
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = utcnow()
    return row


def mark_all_read(db: Session) -> int:
    now = utcnow()
    rows = db.query(ParentNotification).filter(ParentNotification.read_at.is_(None)).all()
    for row in rows:
        row.read_at = now
    return len(rows)


def student_name(db: Session, student_id: int | None) -> str:
    if student_id is None:
        return "A student"
    student = db.get(Student, student_id)
    return student.name if student is not None else "A student"


def notify_curriculum_plan_processed(
    db: Session, *, title: str | None, ready: bool
) -> ParentNotification:
    """Record that a PDF or paper plan left ``processing``. Caller commits."""
    label = (title or "").strip() or "Curriculum plan"
    if ready:
        return create_notification(
            db,
            type=ParentNotificationType.CURRICULUM_PLAN_READY,
            student_id=None,
            assignment_id=None,
            title="Curriculum plan is ready",
            body=f"“{label}” finished processing and is ready to apply.",
        )
    return create_notification(
        db,
        type=ParentNotificationType.CURRICULUM_PLAN_FAILED,
        student_id=None,
        assignment_id=None,
        title="Curriculum plan processing failed",
        body=f"“{label}” could not be processed. You can try the upload again.",
    )
