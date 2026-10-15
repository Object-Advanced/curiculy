"""School-year terms: quarters by default, or the parent's own.

Progress, work samples and reports are counted per term ("Q2 science still
needs 1 sample"). A new year gets four even quarters, and they follow the
year when its dates change. Once the parent sets their own terms (a
co-op's semesters, uneven quarters), Curiculy leaves them alone until the
parent resets them.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException

from app.models import SchoolYear, SchoolYearTerm
from app.schemas import TermWrite

MAX_TERMS = 12


def even_quarters(start: date, end: date) -> list[tuple[str, date, date]]:
    """Four quarters of (nearly) equal length, back to back."""
    days = (end - start).days + 1
    if days < 4:
        return [("Quarter 1", start, end)]
    cuts = [start + timedelta(days=round(days * k / 4)) for k in range(5)]
    return [(f"Quarter {k + 1}", cuts[k], cuts[k + 1] - timedelta(days=1)) for k in range(4)]


def _set(year: SchoolYear, terms: list[tuple[str, date, date]]) -> None:
    year.terms.clear()
    for position, (name, first, last) in enumerate(terms):
        year.terms.append(SchoolYearTerm(position=position, name=name, start_date=first, end_date=last))


def sync_terms(year: SchoolYear) -> None:
    """Keep Curiculy's quarters in step with the year's dates.

    The parent's own terms are left alone while they fit inside the year; if
    the year's dates move so one no longer does, it's back to even quarters.
    """
    if year.terms_by_parent and year.terms and all(
        year.start_date <= term.start_date and term.end_date <= year.end_date for term in year.terms
    ):
        return
    year.terms_by_parent = False
    wanted = even_quarters(year.start_date, year.end_date)
    if [(term.name, term.start_date, term.end_date) for term in year.terms] != wanted:
        _set(year, wanted)


def replace_terms(year: SchoolYear, terms: list[TermWrite]) -> None:
    """The parent's own terms: in order, inside the year, not overlapping."""
    if not terms:
        raise HTTPException(status_code=422, detail="Keep at least one term.")
    if len(terms) > MAX_TERMS:
        raise HTTPException(status_code=422, detail=f"A year can have up to {MAX_TERMS} terms.")
    ordered = sorted(terms, key=lambda term: term.start_date)
    for term in ordered:
        if term.start_date < year.start_date or term.end_date > year.end_date:
            raise HTTPException(
                status_code=422,
                detail=f"{term.name} runs outside the school year ({year.start_date:%b %-d, %Y} to {year.end_date:%b %-d, %Y}).",
            )
    for before, after in zip(ordered, ordered[1:]):
        if after.start_date <= before.end_date:
            raise HTTPException(status_code=422, detail=f"{before.name} and {after.name} overlap.")
    _set(year, [(term.name, term.start_date, term.end_date) for term in ordered])
    year.terms_by_parent = True


def reset_terms(year: SchoolYear) -> None:
    year.terms_by_parent = False
    sync_terms(year)


def term_for(year: SchoolYear, day: date) -> SchoolYearTerm | None:
    return next((term for term in year.terms if term.start_date <= day <= term.end_date), None)
