from sqlalchemy.orm import Session

from app.models import Household

DEFAULT_HOUSEHOLD_NAME = "Default household"


def get_default_household(db: Session) -> Household:
    household = db.query(Household).order_by(Household.id).first()
    if household is None:
        household = Household(name=DEFAULT_HOUSEHOLD_NAME)
        db.add(household)
        db.commit()
        db.refresh(household)
    return household
