from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.schemas import HouseholdRead, HouseholdUpdate
from app.services.households import get_default_household, update_household

router = APIRouter(
    prefix="/household",
    tags=["household"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=HouseholdRead)
def read_household(db: Session = Depends(get_tenant_db)):
    return get_default_household(db)


@router.patch("", response_model=HouseholdRead)
def update_household_route(payload: HouseholdUpdate, db: Session = Depends(get_tenant_db)):
    return update_household(db, name=payload.name, icon=payload.icon)
