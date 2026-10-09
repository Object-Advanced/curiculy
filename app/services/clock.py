"""What "today" means for a household.

School days follow the family's wall clock, not the server's. The container
runs in UTC, so ``date.today()`` turns into tomorrow at 5pm in California and
8pm in New York. Every "today" the API works out (the dashboard, spark,
recalibrate's overdue cutoff, the weekly checklist, default dates) comes from
``household_today`` instead.

The zone is the household's ``timezone`` (set from the parent's browser), then
``DEFAULT_TIMEZONE``, then the server's own clock, which was the old behavior.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Household


def _now() -> datetime:
    """The current instant. Tests freeze this."""
    return datetime.now(timezone.utc)


def parse_zone(name: str | None) -> ZoneInfo | None:
    """The zone for an IANA name, or None if it is blank or unknown."""
    if not name or not name.strip():
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return None


def household_zone(db: Session) -> ZoneInfo | None:
    """The household's zone, else DEFAULT_TIMEZONE, else None (server clock)."""
    stored = db.execute(
        select(Household.timezone).order_by(Household.id).limit(1)
    ).scalar_one_or_none()
    return parse_zone(stored) or parse_zone(settings.default_timezone)


def household_today(db: Session) -> date:
    """Today's date on the household's wall clock."""
    zone = household_zone(db)
    now = _now()
    return now.astimezone(zone).date() if zone else now.astimezone().date()
