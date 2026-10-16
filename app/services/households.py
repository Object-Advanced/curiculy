from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Household, HouseholdState
from app.schemas.core import HOUSEHOLD_ICON_LETTER, HouseholdRead, HouseholdStatePeriod
from app.services.clock import household_today

DEFAULT_HOUSEHOLD_NAME = "Default household"


def get_default_household(db: Session) -> Household:
    """Return this family's one household, creating it if needed.

    New families start as ``DEFAULT_HOUSEHOLD_NAME``. The setup wizard (and
    PATCH /household) rename that row. The database allows one household per
    family; if two first requests race, the loser reads the winner's row.
    """
    household = db.query(Household).order_by(Household.id).first()
    if household is not None:
        return household
    try:
        with db.begin_nested():
            household = Household(name=DEFAULT_HOUSEHOLD_NAME)
            db.add(household)
    except IntegrityError:
        return db.query(Household).order_by(Household.id).one()
    db.commit()
    db.refresh(household)
    return household


def update_household(
    db: Session,
    *,
    name: str | None = None,
    icon: str | None = None,
    timezone: str | None = None,
    count_by: str | None = None,
    daily_lesson_limit: int | None | object = ...,
) -> Household:
    household = get_default_household(db)
    if count_by is not None:
        household.count_by = count_by
    if daily_lesson_limit is not ...:
        household.daily_lesson_limit = daily_lesson_limit
    if name is not None:
        household.name = name
    if icon is not None:
        household.icon = None if icon == HOUSEHOLD_ICON_LETTER else icon
    if timezone is not None:
        household.timezone = timezone
    db.commit()
    db.refresh(household)
    return household


def rename_household(db: Session, name: str) -> Household:
    return update_household(db, name=name)


def state_on(household: Household, day: date) -> str | None:
    """The family's state on ``day``: the latest period starting on or before it."""
    current = None
    for period in sorted(household.states, key=lambda row: row.starts_on):
        if period.starts_on <= day:
            current = period.state_code
    return current


def household_read(db: Session, household: Household | None = None) -> HouseholdRead:
    """The household with its state today and every state period."""
    household = household or get_default_household(db)
    today = household_today(db)
    return HouseholdRead.model_validate(household).model_copy(
        update={"state_code": state_on(household, today)}
    )


def add_state(db: Session, state_code: str, starts_on: date | None = None) -> Household:
    """The family homeschools in ``state_code`` from ``starts_on`` (today by default).

    A period on the same date is replaced, so fixing a mistake doesn't add one.
    """
    household = get_default_household(db)
    starts_on = starts_on or household_today(db)
    existing = next((row for row in household.states if row.starts_on == starts_on), None)
    if existing is not None:
        existing.state_code = state_code
    else:
        household.states.append(HouseholdState(state_code=state_code, starts_on=starts_on))
    db.commit()
    db.refresh(household)
    return household


def replace_states(db: Session, periods: list[HouseholdStatePeriod]) -> Household:
    """Replace the whole state history (Settings edits it as a list)."""
    starts = [period.starts_on for period in periods]
    if len(set(starts)) != len(starts):
        raise ValueError("Two state periods can't start on the same day.")
    household = get_default_household(db)
    household.states.clear()
    db.flush()
    for period in sorted(periods, key=lambda row: row.starts_on):
        household.states.append(
            HouseholdState(state_code=period.state_code, starts_on=period.starts_on)
        )
    db.commit()
    db.refresh(household)
    return household
