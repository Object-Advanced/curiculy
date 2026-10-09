from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.models import CalendarException, Student
from app.schemas import (
    CalendarExceptionCreate,
    CalendarExceptionDatesRead,
    CalendarExceptionRead,
    CalendarExceptionToggleRead,
    CalendarExceptionToggleRequest,
    ImportHolidaysRead,
    ImportHolidaysRequest,
)
from app.services.households import get_default_household
from app.services.school_year import (
    exception_dates_for_household,
    import_public_holidays,
    toggle_exception_date,
)

router = APIRouter(
    prefix="/exceptions",
    tags=["exceptions"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=list[CalendarExceptionRead])
def list_exceptions(db: Session = Depends(get_tenant_db)) -> list[CalendarException]:
    return db.query(CalendarException).order_by(CalendarException.id).all()


@router.post("", response_model=CalendarExceptionRead, status_code=201)
def create_exception(
    payload: CalendarExceptionCreate, db: Session = Depends(get_tenant_db)
) -> CalendarException:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    if payload.student_id is not None and db.get(Student, payload.student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")
    household = get_default_household(db)
    exception = CalendarException(household_id=household.id, **payload.model_dump())
    db.add(exception)
    db.commit()
    db.refresh(exception)
    return exception


@router.get("/dates", response_model=CalendarExceptionDatesRead)
def list_exception_dates(db: Session = Depends(get_tenant_db)) -> CalendarExceptionDatesRead:
    return CalendarExceptionDatesRead(dates=exception_dates_for_household(db))


@router.post("/toggle", response_model=CalendarExceptionToggleRead)
def toggle_exception(
    payload: CalendarExceptionToggleRequest, db: Session = Depends(get_tenant_db)
) -> CalendarExceptionToggleRead:
    excepted = toggle_exception_date(db, payload.date)
    return CalendarExceptionToggleRead(
        date=payload.date,
        excepted=excepted,
        dates=exception_dates_for_household(db),
    )


@router.post("/import-holidays", response_model=ImportHolidaysRead)
def import_holidays(
    payload: ImportHolidaysRequest, db: Session = Depends(get_tenant_db)
) -> ImportHolidaysRead:
    try:
        imported, skipped = import_public_holidays(
            db, payload.country, payload.year, payload.subdiv
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ImportHolidaysRead(
        imported=imported,
        skipped=skipped,
        dates=exception_dates_for_household(db),
    )
