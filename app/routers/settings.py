"""Household school-year settings and exception colors."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.schemas.core import (
    ExceptionColorsRead,
    ExceptionColorsUpdate,
    SchoolYearSettingsRead,
    SchoolYearSettingsUpdate,
)
from app.services.school_year import (
    load_exception_colors,
    load_school_year_settings,
    save_exception_colors,
    save_school_year_settings,
)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
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
