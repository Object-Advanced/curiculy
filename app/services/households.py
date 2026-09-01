from sqlalchemy.orm import Session

from app.models import Household
from app.schemas.core import HOUSEHOLD_ICON_LETTER

DEFAULT_HOUSEHOLD_NAME = "Default household"


def get_default_household(db: Session) -> Household:
    """Return the one household for this tenant file, creating it if needed.

    New family databases start as ``DEFAULT_HOUSEHOLD_NAME``. The setup wizard
    (and PATCH /household) rename that row; there is still one household per file.
    """
    household = db.query(Household).order_by(Household.id).first()
    if household is None:
        household = Household(name=DEFAULT_HOUSEHOLD_NAME)
        db.add(household)
        db.commit()
        db.refresh(household)
    return household


def update_household(db: Session, *, name: str | None = None, icon: str | None = None) -> Household:
    household = get_default_household(db)
    if name is not None:
        household.name = name
    if icon is not None:
        household.icon = None if icon == HOUSEHOLD_ICON_LETTER else icon
    db.commit()
    db.refresh(household)
    return household


def rename_household(db: Session, name: str) -> Household:
    return update_household(db, name=name)
