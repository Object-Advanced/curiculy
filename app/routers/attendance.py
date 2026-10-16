"""Daily attendance: one row per child per date, always the parent's tap.

``POST /attendance`` upserts on that pair (the calendar's radios). The
"School today?" card and the weekly sweep read ``/attendance/days``, which
suggests each day from the work done, and save with ``/attendance/confirm``.
See ``app/services/attendance.py``.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.models import Attendance, Student
from app.schemas import AttendanceRead, AttendanceUpsert
from app.schemas.attendance import AttendanceConfirm, AttendanceDays, AttendanceSummary
from app.services import attendance as service
from app.services.assignments import InvalidDateRangeError, resolve_window

router = APIRouter(
    prefix="/attendance",
    tags=["attendance"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=list[AttendanceRead])
def list_attendance(
    start_date: date = Query(..., description="Inclusive lower bound."),
    end_date: date = Query(..., description="Inclusive upper bound."),
    db: Session = Depends(get_tenant_db),
) -> list[Attendance]:
    try:
        window = resolve_window(start_date=start_date, end_date=end_date)
    except InvalidDateRangeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    query = db.query(Attendance)
    if window.start_date is not None:
        query = query.filter(Attendance.date >= window.start_date)
    if window.end_date is not None:
        query = query.filter(Attendance.date <= window.end_date)
    return query.order_by(Attendance.date, Attendance.student_id, Attendance.id).all()


@router.post("", response_model=AttendanceRead)
def upsert_attendance(
    payload: AttendanceUpsert, db: Session = Depends(get_tenant_db)
) -> Attendance:
    if db.get(Student, payload.student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")

    row = (
        db.query(Attendance)
        .filter(
            Attendance.student_id == payload.student_id,
            Attendance.date == payload.date,
        )
        .one_or_none()
    )
    if row is None:
        row = Attendance(
            student_id=payload.student_id,
            date=payload.date,
            status=payload.status,
        )
        db.add(row)
    else:
        row.status = payload.status
    row.source = "parent"
    db.commit()
    db.refresh(row)
    return row


@router.get("/days", response_model=AttendanceDays)
def attendance_days(
    start_date: date | None = Query(None, description="Inclusive; the family's today when left out."),
    end_date: date | None = Query(None, description="Inclusive; the start date when left out. Up to 62 days."),
    student_id: int | None = Query(None),
    db: Session = Depends(get_tenant_db),
) -> AttendanceDays:
    """Each day and child: what's marked, and what the day's work suggests. Saves nothing."""
    return service.day_cards(db, start_date, end_date, student_id)


@router.post("/confirm", response_model=list[AttendanceRead])
def confirm_attendance(payload: AttendanceConfirm, db: Session = Depends(get_tenant_db)) -> list[Attendance]:
    """Save the parent's marks ("Looks right"). Days that haven't happened can't be marked."""
    return service.confirm(db, payload.marks)


@router.get("/summary", response_model=AttendanceSummary)
def attendance_summary(
    school_year_id: int | None = Query(None, description="The current school year when left out."),
    db: Session = Depends(get_tenant_db),
) -> AttendanceSummary:
    """Each child's school year so far: present, sick, absent, not marked, and the school days ahead."""
    return service.summary(db, school_year_id)
