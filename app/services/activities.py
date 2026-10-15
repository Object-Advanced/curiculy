"""Activities: "5K race, PE, 40 minutes", with a photo at the finish line.

For subjects without a curriculum (PE, music, art, health, safety), and for
anything else worth keeping on the record: a field trip, a co-op class, a
recital. An activity is for one child or several and counts toward one or more
subjects; its photos are work samples. See docs/6-planning/product-spine.md.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Activity, ActivityEvidence, ActivityStudent, Student
from app.reference.subjects import subject_name
from app.schemas.activities import (
    ActivityChild,
    ActivityCreate,
    ActivityEvidenceRead,
    ActivityRead,
    ActivitySubject,
    ActivityUpdate,
)


def _options():
    return (
        selectinload(Activity.students).selectinload(ActivityStudent.student),
        selectinload(Activity.evidence),
    )


def get_activity(db: Session, activity_id: int) -> Activity:
    activity = db.scalars(select(Activity).where(Activity.id == activity_id).options(*_options())).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


def list_activities(
    db: Session, *, student_id: int | None = None, start: date | None = None, end: date | None = None
) -> list[Activity]:
    """Newest first."""
    query = select(Activity).options(*_options()).order_by(Activity.on_date.desc(), Activity.id.desc())
    if student_id is not None:
        query = query.where(Activity.students.any(ActivityStudent.student_id == student_id))
    if start is not None:
        query = query.where(Activity.on_date >= start)
    if end is not None:
        query = query.where(Activity.on_date <= end)
    return list(db.scalars(query).all())


def activity_read(activity: Activity) -> ActivityRead:
    return ActivityRead(
        id=activity.id,
        title=activity.title,
        on_date=activity.on_date,
        minutes=activity.minutes,
        notes=activity.notes,
        link_url=activity.link_url,
        subjects=[ActivitySubject(code=code, name=subject_name(code) or code) for code in activity.subject_codes],
        students=[ActivityChild(student_id=link.student_id, name=link.student.name) for link in activity.students],
        evidence=[
            ActivityEvidenceRead(id=row.id, file_path=row.file_path, captured_at=row.captured_at)
            for row in activity.evidence
        ],
    )


def _set_students(db: Session, activity: Activity, student_ids: list[int]) -> None:
    found = set(db.scalars(select(Student.id).where(Student.id.in_(student_ids))).all())
    if len(found) != len(student_ids):
        raise HTTPException(status_code=404, detail="Student not found")
    keep = [link for link in activity.students if link.student_id in found]
    have = {link.student_id for link in keep}
    activity.students = keep + [ActivityStudent(student_id=sid) for sid in student_ids if sid not in have]


def create_activity(db: Session, payload: ActivityCreate) -> Activity:
    activity = Activity(
        title=payload.title.strip(),
        on_date=payload.on_date,
        minutes=payload.minutes,
        notes=(payload.notes or "").strip() or None,
        link_url=payload.link_url,
        subject_codes=payload.subject_codes,
    )
    _set_students(db, activity, payload.student_ids)
    db.add(activity)
    db.commit()
    return get_activity(db, activity.id)


def update_activity(db: Session, activity: Activity, payload: ActivityUpdate) -> Activity:
    changes = payload.model_dump(exclude_unset=True)
    for required in ("title", "on_date", "student_ids", "subject_codes"):
        if required in changes and changes[required] is None:
            changes.pop(required)
    if "student_ids" in changes:
        _set_students(db, activity, changes.pop("student_ids"))
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    if "notes" in changes:
        changes["notes"] = (changes["notes"] or "").strip() or None
    for field, value in changes.items():
        setattr(activity, field, value)
    db.commit()
    return get_activity(db, activity.id)


def delete_activity(db: Session, activity: Activity) -> None:
    """Its photos' rows go too; the files stay in the backup like any work sample."""
    db.delete(activity)
    db.commit()


def add_evidence(db: Session, activity: Activity, file_path: str, captured_at) -> ActivityEvidence:
    row = ActivityEvidence(file_path=file_path, captured_at=captured_at)
    activity.evidence.append(row)
    db.commit()
    db.refresh(row)
    return row


def remove_evidence(db: Session, activity: Activity, evidence_id: int) -> None:
    row = next((row for row in activity.evidence if row.id == evidence_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Work sample not found")
    activity.evidence.remove(row)
    db.commit()
