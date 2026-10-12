"""The fixed subject list. State requirements and families' own subjects map onto it.

``core`` subjects are the ones states commonly require; ``common`` are presets
families often add. A family's own subject ("Latin roots") says which of these
it counts toward, or none.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Subject:
    code: str
    name: str
    group: str  # "core" or "common"
    covers: str = ""  # what it includes, in plain words


SUBJECTS: tuple[Subject, ...] = (
    Subject("english", "English and language arts", "core", "Reading, writing, spelling, grammar, literature, speech"),
    Subject("math", "Mathematics", "core", "Arithmetic, algebra, geometry"),
    Subject("science", "Science", "core"),
    Subject("geography", "Geography", "core"),
    Subject("civics", "Civics", "core"),
    Subject("us_history", "U.S. and state history", "core"),
    Subject("world_history", "World history", "core"),
    Subject("health", "Health", "core"),
    Subject("pe", "Physical education", "core"),
    Subject("music", "Music", "core"),
    Subject("art", "Art", "core"),
    Subject("safety", "Safety education", "core", "Including fire prevention"),
    Subject("bible", "Bible and religion", "common"),
    Subject("foreign_language", "Foreign language", "common"),
    Subject("computer", "Typing and computers", "common"),
    Subject("logic", "Logic", "common"),
    Subject("life_skills", "Life skills", "common", "Cooking, money, home and car care"),
)
SUBJECTS_BY_CODE = {subject.code: subject for subject in SUBJECTS}


def subject_name(code: str | None) -> str | None:
    subject = SUBJECTS_BY_CODE.get(code or "")
    return subject.name if subject else None
