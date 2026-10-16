from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.schemas import HouseholdRead, HouseholdStateAdd, HouseholdStatePeriod, HouseholdUpdate
from app.services.households import (
    add_state,
    household_read,
    replace_states,
    update_household,
)

router = APIRouter(
    prefix="/household",
    tags=["household"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=HouseholdRead)
def read_household(db: Session = Depends(get_tenant_db)):
    return household_read(db)


@router.patch("", response_model=HouseholdRead)
def update_household_route(payload: HouseholdUpdate, db: Session = Depends(get_tenant_db)):
    household = update_household(
        db, name=payload.name, icon=payload.icon, timezone=payload.timezone, count_by=payload.count_by,
        daily_lesson_limit=payload.daily_lesson_limit if "daily_lesson_limit" in payload.model_fields_set else ...,
    )
    return household_read(db, household)


@router.post("/state", response_model=HouseholdRead)
def set_state(payload: HouseholdStateAdd, db: Session = Depends(get_tenant_db)):
    """The family's state from a date (today if left out): picked at sign-up, or after a move."""
    return household_read(db, add_state(db, payload.state_code, payload.starts_on))


@router.put("/states", response_model=HouseholdRead)
def set_state_history(
    payload: list[HouseholdStatePeriod], db: Session = Depends(get_tenant_db)
):
    """Replace every state period (Settings edits the history as a list)."""
    try:
        household = replace_states(db, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return household_read(db, household)
