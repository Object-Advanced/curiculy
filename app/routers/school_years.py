from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.models import SchoolYear
from app.schemas import SchoolYearCreate, SchoolYearRead
from app.services.households import get_default_household

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
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    household = get_default_household(db)
    school_year = SchoolYear(household_id=household.id, **payload.model_dump())
    db.add(school_year)
    db.commit()
    db.refresh(school_year)
    return school_year
