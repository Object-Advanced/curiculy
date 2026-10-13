"""The Curriculum planner: a subject's textbook plus what goes with it, and scheduling it."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.reference.grades import normalize_grade
from app.reference.subjects import SUBJECTS_BY_CODE
from app.schemas.library import LibraryItemSummary, MissingRead, ProblemRead

ROLES = {
    "textbook": "Textbook",
    "workbook": "Workbook",
    "online": "Online site",
    "reading": "Book to read",
    "teacher": "For the parent",
}
ROLE_HINTS = {
    "textbook": "Its lessons set the pace: one lesson each school day.",
    "workbook": "Its pages are spread across the same days, a chapter at a time.",
    "online": "Scheduled on its own days a week, with its link.",
    "reading": "Read alongside: its pages (or chapters) are spread across the same days.",
    "teacher": "A teacher's edition or answer key, for you. It isn't put on your child's calendar.",
}


class CurriculumItemWrite(BaseModel):
    library_item_id: int
    role: str

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        if value not in ROLES:
            raise ValueError("Pick textbook, workbook, online, reading or teacher.")
        return value


class CurriculumFields(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    subject_code: str | None = None
    grade: str | None = None
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    notes: str | None = None

    @field_validator("subject_code")
    @classmethod
    def _subject(cls, value: str | None) -> str | None:
        if value is not None and value not in SUBJECTS_BY_CODE:
            raise ValueError("Pick a subject from the list.")
        return value

    @field_validator("grade", mode="before")
    @classmethod
    def _grade(cls, value: object) -> object:
        return normalize_grade(value) if isinstance(value, str) and value.strip() else None


class PlannedCurriculumCreate(CurriculumFields):
    """Start a curriculum, usually from a textbook (its subject and grade carry over)."""

    textbook_id: int | None = None


class PlannedCurriculumUpdate(CurriculumFields):
    pass


class CurriculumItemRead(BaseModel):
    id: int
    library_item_id: int
    role: str
    role_label: str
    role_hint: str
    item: LibraryItemSummary


class CourseRead(BaseModel):
    id: int
    curriculum_id: int
    student_id: int
    student_name: str
    start_date: date
    end_date: date | None
    weekdays: list[int]
    lessons_scheduled: int


class CurriculumReadiness(BaseModel):
    ready: bool
    missing: list[MissingRead]
    problems: list[ProblemRead]


class PlannedCurriculumRead(BaseModel):
    id: int
    name: str
    subject_code: str | None
    subject_name: str | None
    grade: str | None
    days_per_week: int | None
    notes: str | None
    items: list[CurriculumItemRead]
    readiness: CurriculumReadiness
    courses: list[CourseRead]
    # Started from a curriculum other families built
    community_curriculum_id: int | None = None


class ScheduleRequest(BaseModel):
    """Which children, starting when, and (optionally) which weekdays (Monday = 0)."""

    student_ids: list[int] = Field(min_length=1)
    start_date: date
    weekdays: list[int] | None = None

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if not value or any(day < 0 or day > 6 for day in value):
            raise ValueError("Weekdays run from 0 (Monday) to 6 (Sunday).")
        return sorted(set(value))


class ScheduledItemPreview(BaseModel):
    library_item_id: int
    title: str
    role: str
    summary: str
    count: int
    first_date: date | None
    last_date: date | None


class StudentPreview(BaseModel):
    student_id: int
    student_name: str
    finish_date: date | None
    lessons: int
    items: list[ScheduledItemPreview]


class SchedulePreview(BaseModel):
    start_date: date
    weekdays: list[int]
    weekday_names: list[str]
    school_year_end: date | None
    students: list[StudentPreview]
    warnings: list[str]


class ScheduleResult(BaseModel):
    courses: list[CourseRead]
    lessons_created: int
    calendar_url: str


class UnscheduleResult(BaseModel):
    lessons_removed: int
    # Finished lessons stay on the day they were done.
    lessons_kept: int


class FromCommunityRequest(BaseModel):
    """Start from a curriculum other families built; leave out anything you'll swap."""

    community_curriculum_id: int
    # The catalog entries to include (the textbook always is); all when left out.
    entry_ids: list[int] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
