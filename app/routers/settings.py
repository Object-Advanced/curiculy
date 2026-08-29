"""Household school-year settings and the year-at-a-glance exception calendar."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.schemas.core import (
    CalendarExceptionDatesRead,
    CalendarExceptionToggleRead,
    CalendarExceptionToggleRequest,
    ExceptionColorsRead,
    ExceptionColorsUpdate,
    ImportHolidaysRead,
    ImportHolidaysRequest,
    SchoolYearSettingsRead,
    SchoolYearSettingsUpdate,
)
from app.services.school_year import (
    exception_dates_for_household,
    import_public_holidays,
    load_exception_colors,
    load_school_year_settings,
    save_exception_colors,
    save_school_year_settings,
    toggle_exception_date,
)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_parent)],
)

calendar_exceptions_router = APIRouter(
    prefix="/calendar/exceptions",
    tags=["calendar"],
    dependencies=[Depends(require_parent)],
)


@router.get("/school-year", response_model=SchoolYearSettingsRead)
def get_school_year(db: Session = Depends(get_tenant_db)) -> SchoolYearSettingsRead:
    start_date, end_date, weekdays, school_year_id = load_school_year_settings(db)
    return SchoolYearSettingsRead(
        start_date=start_date,
        end_date=end_date,
        weekdays=weekdays,
        school_year_id=school_year_id,
    )


@router.put("/school-year", response_model=SchoolYearSettingsRead)
def put_school_year(
    payload: SchoolYearSettingsUpdate, db: Session = Depends(get_tenant_db)
) -> SchoolYearSettingsRead:
    start_date, end_date, weekdays, school_year_id = save_school_year_settings(
        db, payload.start_date, payload.end_date, payload.weekdays
    )
    return SchoolYearSettingsRead(
        start_date=start_date,
        end_date=end_date,
        weekdays=weekdays,
        school_year_id=school_year_id,
    )


@router.get("/exception-colors", response_model=ExceptionColorsRead)
def get_exception_colors(db: Session = Depends(get_tenant_db)) -> ExceptionColorsRead:
    return ExceptionColorsRead.model_validate(load_exception_colors(db))


@router.put("/exception-colors", response_model=ExceptionColorsRead)
def put_exception_colors(
    payload: ExceptionColorsUpdate, db: Session = Depends(get_tenant_db)
) -> ExceptionColorsRead:
    colors = save_exception_colors(db, payload.model_dump())
    return ExceptionColorsRead.model_validate(colors)


@calendar_exceptions_router.get("", response_model=CalendarExceptionDatesRead)
def list_exception_dates(db: Session = Depends(get_tenant_db)) -> CalendarExceptionDatesRead:
    return CalendarExceptionDatesRead(dates=exception_dates_for_household(db))


@calendar_exceptions_router.post("/toggle", response_model=CalendarExceptionToggleRead)
def toggle_exception(
    payload: CalendarExceptionToggleRequest, db: Session = Depends(get_tenant_db)
) -> CalendarExceptionToggleRead:
    excepted = toggle_exception_date(db, payload.date)
    return CalendarExceptionToggleRead(
        date=payload.date,
        excepted=excepted,
        dates=exception_dates_for_household(db),
    )


@calendar_exceptions_router.post("/import-holidays", response_model=ImportHolidaysRead)
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
