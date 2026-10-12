"""The fixed list of grades, and turning what a parent typed into one of them.

Codes are what's stored: "PreK", "K", "1" … "12". They read naturally after
"Grade" ("Grade K", "Grade 3"), and both apps' age-band logic already
understands them (``gradeBand`` in static/js/app.js and frontend/src/lib/spark.ts).
"""

from __future__ import annotations

import re
from datetime import date

GRADES: list[tuple[str, str]] = [
    ("PreK", "Pre-K"),
    ("K", "Kindergarten"),
    *[(str(n), f"{n}{'st' if n == 1 else 'nd' if n == 2 else 'rd' if n == 3 else 'th'} grade") for n in range(1, 13)],
]
GRADE_CODES = [code for code, _ in GRADES]
GRADE_LABELS = dict(GRADES)

_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
    "freshman": 9, "sophomore": 10, "junior": 11, "senior": 12,
}
_PREK = {"prek", "pre-k", "pre k", "pk", "preschool", "pre-kindergarten", "prekindergarten"}
_K = {"k", "kindergarten", "kinder", "tk", "transitional kindergarten"}


def normalize_grade(value: str) -> str:
    """'3rd', 'Grade 3', 'third', 'Kindergarten', 'pre-k' -> a grade code."""
    text = re.sub(r"\s+", " ", value.strip().lower())
    text = re.sub(r"\b(grade|gr\.?|year)\b", "", text).strip(" .")
    if text in _PREK:
        return "PreK"
    if text in _K:
        return "K"
    if text in _WORDS:
        return str(_WORDS[text])
    match = re.fullmatch(r"(\d{1,2})(st|nd|rd|th)?", text)
    if match and 1 <= int(match.group(1)) <= 12:
        return str(int(match.group(1)))
    raise ValueError("Pick a grade: Pre-K, Kindergarten, or 1 to 12.")


def grade_number(code: str | None) -> int | None:
    """PreK -> -1, K -> 0, "3" -> 3; None stays None."""
    if code is None:
        return None
    return {"PreK": -1, "K": 0}.get(code, int(code) if code.isdigit() else None)


def last_grade_check(today: date) -> date:
    """The most recent July 1: grades are re-confirmed each new school year."""
    july_first = date(today.year, 7, 1)
    return july_first if today >= july_first else date(today.year - 1, 7, 1)


def grade_needs_confirming(grade: str | None, confirmed_on: date | None, today: date) -> bool:
    if grade is None or confirmed_on is None:
        return True
    return confirmed_on < last_grade_check(today)
