from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Household
from app.schemas.core import HOUSEHOLD_ICON_LETTER

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
) -> Household:
    household = get_default_household(db)
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
