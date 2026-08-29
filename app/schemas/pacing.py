"""Preview and commit payloads for the syllabus generator.

A preview writes nothing, so its response doubles as the commit request's
payload: the caller edits the lessons it disagrees with and posts them back.
The two lesson models therefore differ only in what is required — a preview
computes the scheduled dates, a commit is told them.

Lessons deliberately do not forbid extra keys. ``page_count`` is computed on the
way out, and a caller that round-trips the preview response unchanged would
otherwise be rejected for echoing a field it was just handed.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.enums import ResourceKind, UnitKind

# 0 is Monday and 6 is Sunday, matching ``date.weekday()``.
WEEKDAYS_MONDAY_TO_FRIDAY = (0, 1, 2, 3, 4)

ACTIVE_WEEKDAYS_DESCRIPTION = "Days school is in session, where 0 is Monday and 6 is Sunday."


def _normalize_weekdays(value: list[int]) -> list[int]:
    if not value:
        raise ValueError("at least one active weekday is required")
    for weekday in value:
        if not 0 <= weekday <= 6:
            raise ValueError(f"{weekday} is not a weekday; use 0 for Monday through 6 for Sunday")
    return sorted(set(value))


class SyllabusLesson(BaseModel):
    """One generated lesson: a slice of the page range on one school day."""

    sequence: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    scheduled_date: date | None = None

    @computed_field
    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1

    @model_validator(mode="after")
    def _check_page_range(self) -> "SyllabusLesson":
        if self.end_page < self.start_page:
            raise ValueError(f"end_page {self.end_page} precedes start_page {self.start_page}")
        return self


class ApprovedLesson(SyllabusLesson):
    """A lesson the parent accepted, which means its date is settled."""

    scheduled_date: date


class PacingPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_id: int
    target_completion_date: date | None = Field(
        default=None,
        description="Last day work may land on. Required unless pages_per_day is set, "
        "in which case the finish date is computed from the pace.",
    )
    pages_per_day: int | None = Field(
        default=None,
        ge=1,
        description="Schedule forward at this many pages on each school day. "
        "The last lesson takes the remainder. Cannot be combined with a deadline.",
    )
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    start_date: date | None = Field(
        default=None,
        description="First candidate school day. Defaults to today.",
    )
    active_weekdays: list[int] = Field(
        default_factory=lambda: list(WEEKDAYS_MONDAY_TO_FRIDAY),
        description=ACTIVE_WEEKDAYS_DESCRIPTION,
    )
    target_lessons: int | None = Field(
        default=None,
        ge=1,
        description="Defaults to one lesson per available school day, never more "
        "lessons than there are pages to cover. Ignored when pages_per_day is set.",
    )
    excluded_dates: list[date] = Field(
        default_factory=list,
        description="Individual days to skip, such as a holiday or a trip.",
    )

    @field_validator("active_weekdays")
    @classmethod
    def _check_weekdays(cls, value: list[int]) -> list[int]:
        return _normalize_weekdays(value)

    @model_validator(mode="after")
    def _check_page_range(self) -> "PacingPreviewRequest":
        if self.end_page < self.start_page:
            raise ValueError(f"end_page {self.end_page} precedes start_page {self.start_page}")
        return self

    @model_validator(mode="after")
    def _check_pacing_mode(self) -> "PacingPreviewRequest":
        if self.pages_per_day is None and self.target_completion_date is None:
            raise ValueError("either target_completion_date or pages_per_day is required")
        return self


class PacingCalculation(BaseModel):
    """The arithmetic behind a preview, so the caller can show its reasoning.

    ``day_interval`` and ``lessons_per_day`` are two views of the same ratio: a
    stretched course lands on every Nth school day, a compressed one stacks N
    lessons onto each of them.
    """

    start_date: date
    target_completion_date: date
    active_weekdays: list[int]
    available_days: int
    total_lessons: int
    total_pages: int
    pages_per_lesson: float
    lessons_per_day: int
    day_interval: int
    is_rigorous: bool
    warning: str | None


class PacingPreviewRead(BaseModel):
    book_id: int
    book_title: str
    pacing: PacingCalculation
    lessons: list[SyllabusLesson]


class PacingCommitRequest(BaseModel):
    """An approved syllabus, ready to become catalog structure and assignments."""

    model_config = ConfigDict(extra="forbid")

    student_id: int | None = Field(
        default=None,
        description="A single student to schedule. Prefer student_ids when assigning "
        "the same syllabus to more than one child.",
    )
    student_ids: list[int] = Field(
        default_factory=list,
        description="Students who each receive an identical copy of every lesson. "
        "Combined with student_id when both are sent.",
    )
    curriculum_edition_id: int
    course_title: str = Field(min_length=1, max_length=255)
    lessons: list[ApprovedLesson] = Field(min_length=1)
    book_id: int | None = Field(
        default=None,
        description="Links the created resource to a scanned book edition.",
    )
    start_page: int | None = Field(
        default=None,
        ge=1,
        description="First page of the scheduled range. Optional; the lessons already carry it.",
    )
    end_page: int | None = Field(
        default=None,
        ge=1,
        description="Last page of the scheduled range. Stored on the book as page_count "
        "when it is missing or has changed.",
    )
    resource_kind: ResourceKind = ResourceKind.STUDENT_TEXT
    resource_title: str | None = Field(
        default=None,
        max_length=255,
        description="Defaults to the book's title, or to the course title.",
    )
    course_kind: UnitKind = UnitKind.COURSE
    subject_taxonomy_id: int | None = None

    @field_validator("lessons")
    @classmethod
    def _check_sequences(cls, value: list[ApprovedLesson]) -> list[ApprovedLesson]:
        sequences = [lesson.sequence for lesson in value]
        if len(set(sequences)) != len(sequences):
            raise ValueError("every lesson needs a distinct sequence number")
        return value

    @model_validator(mode="after")
    def _require_students(self) -> "PacingCommitRequest":
        if not self.students_to_schedule():
            raise ValueError("at least one student is required")
        return self

    def students_to_schedule(self) -> list[int]:
        """Student ids to write assignments for, in request order without duplicates."""
        ids: list[int] = []
        if self.student_id is not None:
            ids.append(self.student_id)
        for student_id in self.student_ids:
            if student_id not in ids:
                ids.append(student_id)
        return ids


class PacingCommitRead(BaseModel):
    """What the commit created, addressed well enough to undo or inspect."""

    student_id: int
    student_ids: list[int]
    curriculum_edition_id: int
    curriculum_resource_id: int
    resource_created: bool
    course_unit_id: int
    lesson_unit_ids: list[int]
    assignment_ids: list[int]
    units_created: int
    page_mappings_created: int
    assignments_created: int
    first_scheduled_date: date
    last_scheduled_date: date
