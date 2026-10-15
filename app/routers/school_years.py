from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.models import SchoolYear
from app.schemas import SchoolYearCreate, SchoolYearRead, SchoolYearUpdate, TermWrite
from app.services.school_year import create_named_school_year, update_named_school_year
from app.services.terms import replace_terms, reset_terms

router = APIRouter(
    prefix="/school-years",
    tags=["school-years"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=list[SchoolYearRead])
def list_school_years(db: Session = Depends(get_tenant_db)) -> list[SchoolYear]:
    return db.query(SchoolYear).order_by(SchoolYear.id).all()


@router.get("/{school_year_id}", response_model=SchoolYearRead)
def get_school_year(school_year_id: int, db: Session = Depends(get_tenant_db)) -> SchoolYear:
    school_year = db.get(SchoolYear, school_year_id)
    if school_year is None:
        raise HTTPException(status_code=404, detail="School year not found")
    return school_year


@router.post("", response_model=SchoolYearRead, status_code=201)
def create_school_year(payload: SchoolYearCreate, db: Session = Depends(get_tenant_db)) -> SchoolYear:
    try:
        return create_named_school_year(
            db, payload.name, payload.start_date, payload.end_date
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/{school_year_id}", response_model=SchoolYearRead)
def update_school_year(
    school_year_id: int,
    payload: SchoolYearUpdate,
    db: Session = Depends(get_tenant_db),
) -> SchoolYear:
    school_year = db.get(SchoolYear, school_year_id)
    if school_year is None:
        raise HTTPException(status_code=404, detail="School year not found")
    try:
        return update_named_school_year(
            db,
            school_year,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _year(db: Session, school_year_id: int) -> SchoolYear:
    school_year = db.get(SchoolYear, school_year_id)
    if school_year is None:
        raise HTTPException(status_code=404, detail="School year not found")
    return school_year


@router.put("/{school_year_id}/terms", response_model=SchoolYearRead)
def set_terms(school_year_id: int, payload: list[TermWrite], db: Session = Depends(get_tenant_db)) -> SchoolYear:
    """The parent's own terms (semesters, uneven quarters): in order, inside the year, not overlapping."""
    school_year = _year(db, school_year_id)
    replace_terms(school_year, payload)
    db.commit()
    db.refresh(school_year)
    return school_year


@router.post("/{school_year_id}/terms/reset", response_model=SchoolYearRead)
def reset_year_terms(school_year_id: int, db: Session = Depends(get_tenant_db)) -> SchoolYear:
    """Back to four even quarters that follow the year's dates."""
    school_year = _year(db, school_year_id)
    reset_terms(school_year)
    db.commit()
    db.refresh(school_year)
    return school_year
