"""Daily attendance for the family calendar.

One row per student per date. ``POST`` upserts on that pair so marking present
or absent from a calendar cell can be repeated without creating duplicates.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.models import Attendance, Student
from app.schemas import AttendanceRead, AttendanceUpsert
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
    db.commit()
    db.refresh(row)
    return row
