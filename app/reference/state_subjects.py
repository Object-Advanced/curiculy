"""Each state's required subjects, by grade band, mapped onto the subject list.

Only states whose requirements have been reviewed are here (the "no square
pegs" process, docs/6-planning/state-requirements/). Anywhere else, families
pick their subjects freely and Curiculy says the state's list isn't ready yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.reference.grades import grade_number


@dataclass(frozen=True)
class Band:
    name: str  # "elementary", "secondary"
    first_grade: int  # K = 0
    last_grade: int
    # (subject code, the state's own wording)
    subjects: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class StateSubjects:
    bands: tuple[Band, ...]
    every_year: frozenset[str]
    rule: str
    sources: tuple[str, ...]


STATE_SUBJECTS: dict[str, StateSubjects] = {
    # Reviewed 2026-10-11: docs/6-planning/state-requirements/pennsylvania.md, rows 11-12 and Q12.
    "PA": StateSubjects(
        bands=(
            Band(
                "elementary", 0, 6,
                (
                    ("english", "English (spelling, reading and writing)"),
                    ("math", "Arithmetic"),
                    ("science", "Science"),
                    ("geography", "Geography"),
                    ("civics", "Civics"),
                    ("us_history", "History of the United States and Pennsylvania"),
                    ("health", "Health and physiology"),
                    ("pe", "Physical education"),
                    ("music", "Music"),
                    ("art", "Art"),
                    ("safety", "Safety education, including the dangers and prevention of fires"),
                ),
            ),
            Band(
                "secondary", 7, 12,
                (
                    ("english", "English (language, literature, speech and composition)"),
                    ("math", "Mathematics (general mathematics, algebra and geometry)"),
                    ("science", "Science"),
                    ("geography", "Geography"),
                    ("civics", "Civics"),
                    ("us_history", "History of the United States and Pennsylvania"),
                    ("world_history", "World history"),
                    ("health", "Health"),
                    ("pe", "Physical education"),
                    ("music", "Music"),
                    ("art", "Art"),
                    ("safety", "Safety education, including fire prevention"),
                ),
            ),
        ),
        every_year=frozenset({"safety"}),
        rule=(
            "Pennsylvania lists the subjects to cover in elementary (K–6) and secondary (7–12) grades. "
            "They don't all have to be taught every year, except fire-safety instruction, which must be "
            "regular and continuous. Pick this year's subjects; earlier years' show as covered."
        ),
        sources=(
            "https://hslda.org/post/how-to-comply-with-pennsylvanias-homeschool-law",
            "https://www.pa.gov/agencies/education/resources/policies-acts-and-laws/basic-education-circulars-becs/purdons-statutes/home-education-program",
        ),
    ),
}


def band_for(state_code: str | None, grade: str | None) -> Band | None:
    rules = STATE_SUBJECTS.get(state_code or "")
    number = grade_number(grade)
    if rules is None or number is None:
        return None
    return next((band for band in rules.bands if band.first_grade <= number <= band.last_grade), None)
