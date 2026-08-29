"""Household school-year bounds, class days, and calendar exceptions.

The settings calendar is household-wide: student-specific sick days stay on
the existing exceptions list and do not appear as global no-school days.
"""

from datetime import date, timedelta
from json import dumps, loads
from json.decoder import JSONDecodeError
from re import fullmatch

import holidays
from sqlalchemy.orm import Session

from app.enums import ExceptionKind
from app.models import CalendarException, Household, HouseholdSettings, SchoolYear
from app.schemas.core import DEFAULT_EXCEPTION_COLOR_VALUES
from app.services.households import get_default_household

DEFAULT_CLASS_WEEKDAYS = (0, 1, 2, 3, 4)
DEFAULT_WEEKDAYS_STORED = "0,1,2,3,4"
_HEX_COLOR = r"^#[0-9A-Fa-f]{6}$"


def default_school_year_bounds(today: date | None = None) -> tuple[date, date]:
    """August–June year, rolling over in July — same rule as the setup wizard."""
    today = today or date.today()
    start_year = today.year if today.month >= 7 else today.year - 1
    return date(start_year, 8, 1), date(start_year + 1, 6, 30)


def encode_weekdays(weekdays: list[int]) -> str:
    return ",".join(str(day) for day in sorted(set(weekdays)))


def parse_weekdays(stored: str | None) -> list[int]:
    if not stored:
        return list(DEFAULT_CLASS_WEEKDAYS)
    days: list[int] = []
    for part in stored.split(","):
        piece = part.strip()
        if not piece:
            continue
        try:
            day = int(piece)
        except ValueError:
            return list(DEFAULT_CLASS_WEEKDAYS)
        if not 0 <= day <= 6:
            return list(DEFAULT_CLASS_WEEKDAYS)
        days.append(day)
    return sorted(set(days)) or list(DEFAULT_CLASS_WEEKDAYS)


def school_year_name(start: date, end: date) -> str:
    if start.year == end.year:
        return str(start.year)
    return f"{start.year}-{end.year}"


def _latest_school_year(db: Session, household_id: int) -> SchoolYear | None:
    return (
        db.query(SchoolYear)
        .filter(SchoolYear.household_id == household_id)
        .order_by(SchoolYear.start_date.desc(), SchoolYear.id.desc())
        .first()
    )


def load_school_year_settings(db: Session) -> tuple[date, date, list[int], int | None]:
    household = get_default_household(db)
    row = (
        db.query(HouseholdSettings)
        .filter(HouseholdSettings.household_id == household.id)
        .first()
    )
    year = _latest_school_year(db, household.id)
    if row is not None:
        return row.start_date, row.end_date, parse_weekdays(row.weekdays), (
            year.id if year is not None else None
        )
    if year is not None:
        return year.start_date, year.end_date, list(DEFAULT_CLASS_WEEKDAYS), year.id
    start, end = default_school_year_bounds()
    return start, end, list(DEFAULT_CLASS_WEEKDAYS), None


def save_school_year_settings(
    db: Session, start_date: date, end_date: date, weekdays: list[int]
) -> tuple[date, date, list[int], int | None]:
    household = get_default_household(db)
    stored = encode_weekdays(weekdays)
    row = (
        db.query(HouseholdSettings)
        .filter(HouseholdSettings.household_id == household.id)
        .first()
    )
    if row is None:
        row = HouseholdSettings(
            household_id=household.id,
            start_date=start_date,
            end_date=end_date,
            weekdays=stored,
        )
        db.add(row)
    else:
        row.start_date = start_date
        row.end_date = end_date
        row.weekdays = stored

    year = _latest_school_year(db, household.id)
    if year is None:
        year = SchoolYear(
            household_id=household.id,
            name=school_year_name(start_date, end_date),
            start_date=start_date,
            end_date=end_date,
        )
        db.add(year)
    else:
        year.start_date = start_date
        year.end_date = end_date

    db.commit()
    db.refresh(year)
    return start_date, end_date, parse_weekdays(stored), year.id


def parse_exception_colors(stored: str | None) -> dict[str, str]:
    colors = dict(DEFAULT_EXCEPTION_COLOR_VALUES)
    if not stored:
        return colors
    try:
        data = loads(stored)
    except JSONDecodeError:
        return colors
    if not isinstance(data, dict):
        return colors
    for kind, value in data.items():
        if kind not in DEFAULT_EXCEPTION_COLOR_VALUES:
            continue
        if isinstance(value, str) and fullmatch(_HEX_COLOR, value.strip()):
            colors[kind] = value.strip().lower()
    return colors


def encode_exception_colors(colors: dict[str, str]) -> str:
    merged = parse_exception_colors(dumps(colors))
    return dumps(merged, sort_keys=True)


def _settings_row(db: Session) -> HouseholdSettings | None:
    household = get_default_household(db)
    return (
        db.query(HouseholdSettings)
        .filter(HouseholdSettings.household_id == household.id)
        .first()
    )


def load_exception_colors(db: Session) -> dict[str, str]:
    row = _settings_row(db)
    return parse_exception_colors(row.exception_colors if row is not None else None)


def save_exception_colors(db: Session, updates: dict[str, str | None]) -> dict[str, str]:
    household = get_default_household(db)
    row = (
        db.query(HouseholdSettings)
        .filter(HouseholdSettings.household_id == household.id)
        .first()
    )
    current = parse_exception_colors(row.exception_colors if row is not None else None)
    for kind, value in updates.items():
        if value is None or kind not in DEFAULT_EXCEPTION_COLOR_VALUES:
            continue
        current[kind] = value
    encoded = encode_exception_colors(current)
    if row is None:
        start, end, weekdays, _year_id = load_school_year_settings(db)
        row = HouseholdSettings(
            household_id=household.id,
            start_date=start,
            end_date=end,
            weekdays=encode_weekdays(weekdays),
            exception_colors=encoded,
        )
        db.add(row)
    else:
        row.exception_colors = encoded
    db.commit()
    return parse_exception_colors(encoded)


def household_exceptions(db: Session, household: Household) -> list[CalendarException]:
    return (
        db.query(CalendarException)
        .filter(
            CalendarException.household_id == household.id,
            CalendarException.student_id.is_(None),
        )
        .order_by(CalendarException.start_date, CalendarException.id)
        .all()
    )


def expand_exception_dates(exceptions: list[CalendarException]) -> list[date]:
    dates: set[date] = set()
    for item in exceptions:
        day = item.start_date
        while day <= item.end_date:
            dates.add(day)
            day += timedelta(days=1)
    return sorted(dates)


def exception_dates_for_household(db: Session) -> list[date]:
    household = get_default_household(db)
    return expand_exception_dates(household_exceptions(db, household))


def _covering_household_exceptions(
    db: Session, household_id: int, day: date
) -> list[CalendarException]:
    return (
        db.query(CalendarException)
        .filter(
            CalendarException.household_id == household_id,
            CalendarException.student_id.is_(None),
            CalendarException.start_date <= day,
            CalendarException.end_date >= day,
        )
        .order_by(CalendarException.id)
        .all()
    )


def _remove_day_from_exception(
    db: Session, item: CalendarException, day: date
) -> None:
    """Drop ``day`` from a range, shrinking or splitting as needed."""
    if item.start_date == item.end_date:
        db.delete(item)
        return
    if item.start_date == day:
        item.start_date = day + timedelta(days=1)
        return
    if item.end_date == day:
        item.end_date = day - timedelta(days=1)
        return
    later = CalendarException(
        household_id=item.household_id,
        student_id=item.student_id,
        kind=item.kind,
        title=item.title,
        start_date=day + timedelta(days=1),
        end_date=item.end_date,
        notes=item.notes,
    )
    item.end_date = day - timedelta(days=1)
    db.add(later)


def toggle_exception_date(db: Session, day: date) -> bool:
    """Create or remove a household exception for ``day``. True if now excepted."""
    household = get_default_household(db)
    covering = _covering_household_exceptions(db, household.id, day)
    if covering:
        for item in covering:
            _remove_day_from_exception(db, item, day)
        db.commit()
        return False
    db.add(
        CalendarException(
            household_id=household.id,
            student_id=None,
            kind=ExceptionKind.OTHER,
            title="No school",
            start_date=day,
            end_date=day,
        )
    )
    db.commit()
    return True


def public_holidays(country: str, year: int, subdiv: str | None = None) -> dict[date, str]:
    """Holiday map for one region and calendar year.

    Raises ``ValueError`` when the country or subdivision is unknown.
    """
    try:
        calendar = holidays.country_holidays(country, subdiv=subdiv, years=year)
    except (NotImplementedError, KeyError, ValueError) as error:
        region = f"{country}-{subdiv}" if subdiv else country
        raise ValueError(f"No public holidays for {region}") from error
    return {day: str(name) for day, name in calendar.items()}


def import_public_holidays(
    db: Session, country: str, year: int, subdiv: str | None = None
) -> tuple[int, int]:
    """Insert household holiday exceptions, skipping dates already blocked."""
    holiday_map = public_holidays(country, year, subdiv)
    household = get_default_household(db)
    existing = set(expand_exception_dates(household_exceptions(db, household)))
    imported = 0
    skipped = 0
    for day, name in sorted(holiday_map.items()):
        if day in existing:
            skipped += 1
            continue
        title = (name or "Holiday")[:255]
        db.add(
            CalendarException(
                household_id=household.id,
                student_id=None,
                kind=ExceptionKind.HOLIDAY,
                title=title,
                start_date=day,
                end_date=day,
            )
        )
        existing.add(day)
        imported += 1
    db.commit()
    return imported, skipped
