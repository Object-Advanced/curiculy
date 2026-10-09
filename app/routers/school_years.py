from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.models import SchoolYear
from app.schemas import SchoolYearCreate, SchoolYearRead, SchoolYearUpdate
from app.services.school_year import create_named_school_year, update_named_school_year

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
