"""The move engine: requests, previews and the catch-up sheet."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

CatchUpOption = Literal["push_back", "push_week", "use_day_off", "double_up", "skip"]


class LessonMoveRequest(BaseModel):
    """Move one lesson. ``ripple`` pushes the rest of its course along with it;
    ``just_this`` moves only it, sliding the lessons of the same book between
    the two days by one so their order holds."""

    kind: Literal["lesson"] = "lesson"
    assignment_id: int
    to_date: date
    mode: Literal["ripple", "just_this"] = "ripple"


class DayMoveRequest(BaseModel):
    """A day off or a sick day: each course's lessons from that day move forward
    by one of its days; other lessons that day move to the next school day."""

    kind: Literal["day"] = "day"
    date: date
    # Empty: every child.
    student_ids: list[int] = Field(default_factory=list, max_length=20)
    # A day ahead can go on the calendar too: "sick" (for each child) or "off".
    add_to_calendar: Literal["sick", "off"] | None = None
    title: str = Field(default="Day off", min_length=1, max_length=255)


class CatchUpRequest(BaseModel):
    kind: Literal["catch_up"] = "catch_up"
    course_id: int
    option: CatchUpOption
    allow_weekends: bool = False


class CourseMoveRequest(BaseModel):
    """Re-pace a course from today: new days of the week, and/or a pause."""

    kind: Literal["course"] = "course"
    course_id: int
    weekdays: list[int] | None = Field(default=None, min_length=1, max_length=7)
    pause_from: date | None = None
    pause_to: date | None = None

    @field_validator("weekdays")
    @classmethod
    def _days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("Days are 0 (Monday) through 6 (Sunday).")
        return sorted(set(value))


MoveRequest = Annotated[
    LessonMoveRequest | DayMoveRequest | CatchUpRequest | CourseMoveRequest, Field(discriminator="kind")
]


class MoveApply(BaseModel):
    """Apply a previewed move. The plan is worked out again; if the calendar
    changed since the preview, nothing is saved."""

    request: MoveRequest
    plan_hash: str = Field(min_length=8, max_length=128)


class LessonChange(BaseModel):
    assignment_id: int
    title: str
    student_id: int
    student_name: str
    course_name: str | None = None
    from_date: date
    # None when the lesson is skipped instead of moved.
    to_date: date | None = None
    skipped: bool = False


class CourseEffect(BaseModel):
    course_id: int
    course_name: str
    student_name: str
    finish_before: date | None
    finish_after: date | None
    lessons_moved: int


class MovePreview(BaseModel):
    summary: str
    changes: list[LessonChange]
    courses: list[CourseEffect]
    # The plan checker: what the move does to the family's guidelines. Warnings, never blocks.
    warnings: list[str] = Field(default_factory=list)
    # Other things the move does (a day off added to the calendar, a course's new days).
    notes: list[str] = Field(default_factory=list)
    plan_hash: str


class MoveResult(BaseModel):
    moved: int
    skipped: int
    summary: str


class CatchUpChoice(BaseModel):
    option: CatchUpOption
    label: str
    description: str
    workable: bool
    why_not: str | None = None
    # "Finishes Thu, Jun 4, on time"
    result: str | None = None
    recommended: bool = False
    preview: MovePreview | None = None


class CatchUpSheet(BaseModel):
    course_id: int
    course_name: str
    student_id: int
    student_name: str
    behind: int
    behind_since: date | None
    school_year_end: date | None
    daily_lesson_limit: int | None
    allow_weekends: bool
    choices: list[CatchUpChoice]


class BehindCourse(BaseModel):
    course_id: int
    course_name: str
    student_id: int
    student_name: str
    behind: int
    behind_since: date
