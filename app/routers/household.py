from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.schemas import HouseholdRead
from app.services.households import get_default_household

router = APIRouter(
    prefix="/household",
    tags=["household"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=HouseholdRead)
def read_household(db: Session = Depends(get_tenant_db)):
    return get_default_household(db)
