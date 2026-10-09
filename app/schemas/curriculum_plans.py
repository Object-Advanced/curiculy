"""Read and write models for structured pacing guides.

These are distinct from the household book catalog (``CurriculumRead``) and from
the Auto-schedule import payload (``CurriculumImportRequest``). A plan is a
flat sequence of daily lessons, optionally grouped by unit and week.

``AIParsedLesson`` / ``AIParsedCurriculum`` are the contract Ollama must satisfy
when a PDF pacing guide is turned into rows.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import CurriculumPlanStatus
from app.schemas.core import ORMModel
from app.schemas.pacing import _normalize_weekdays

ROUTINE_CATEGORY = "Routine/Break"
COURSEWORK_CATEGORY = "Daily Work"
DEFAULT_ROUTINE_DAYS = 5

_ROUTINE_TITLES = {
    "lunch",
    "recess",
    "snack",
    "break",
    "rest",
    "rest time",
    "nap",
    "restroom",
    "bathroom",
    "transition",
    "free play",
    "freeplay",
    "outdoor play",
    "play time",
    "cleanup",
    "pack up",
    "dismissal",
    "arrival",
    "brain break",
    "stretch",
    "water break",
    "quiet time",
}
_ROUTINE_CATEGORY_ALIASES = {
    "routine/break",
    "routine",
    "break",
    "breaks",
    "not coursework",
}
_TIME_PREFIX = re.compile(
    r"^(?P<slot>\d{1,2}:\d{2}\s*(?:[-–]|to)\s*\d{1,2}:\d{2}(?:\s*[ap]\.?m\.?)?)\s+"
    r"(?P<rest>.+)$",
    re.IGNORECASE,
)
_TIME_ONLY = re.compile(
    r"^\d{1,2}:\d{2}\s*(?:[-–]|to)\s*\d{1,2}:\d{2}(?:\s*[ap]\.?m\.?)?$",
    re.IGNORECASE,
)
_TIME_START = re.compile(
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>[ap]\.?m\.?)?",
    re.IGNORECASE,
)
_PACING_TITLE = re.compile(r"\b(lesson|chapter|worksheet|unit)\b", re.IGNORECASE)
_PLACEHOLDER_TITLE = re.compile(
    r"^(week\s*\d+|day\s*\d+|week\s*\d+\s*[,:\-–]?\s*day\s*\d+|"
    r"\d+\s*weeks?|untitled|n/?a|none|tbd|-|\.|-+|\*+)$",
    re.IGNORECASE,
)


def parse_json_object(value: Any) -> dict[str, float] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("must be a JSON object") from error
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("must be a JSON object")
    parsed: dict[str, float] = {}
    for key, weight in value.items():
        name = str(key).strip()
        if not name:
            continue
        parsed[name] = float(weight)
    return parsed or None


def parse_json_string_list(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("must be a JSON array of strings") from error
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("must be a JSON array of strings")
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or None


def dump_json_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)) and not value:
        return None
    return json.dumps(value)


def _normalize_label(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def canonical_lesson_category(category: str | None) -> str | None:
    label = (category or "").strip()
    if not label:
        return None
    if _normalize_label(label) in _ROUTINE_CATEGORY_ALIASES:
        return ROUTINE_CATEGORY
    return label[:64]


def is_routine_title(title: str | None) -> bool:
    name = _normalize_label(title)
    if not name:
        return False
    if name in _ROUTINE_TITLES:
        return True
    return any(name == item or name.startswith(f"{item} ") for item in _ROUTINE_TITLES)


def is_routine_item(title: str | None, category: str | None) -> bool:
    """Lunch, recess, and other timetable breaks are not graded coursework."""
    if canonical_lesson_category(category) == ROUTINE_CATEGORY:
        return True
    return is_routine_title(title)


def is_schedulable_lesson(title: str | None, category: str | None) -> bool:
    """Assignments that should land on a student's calendar."""
    return bool((title or "").strip()) and not is_routine_item(title, category)


def normalize_lesson_category(
    title: str | None,
    category: str | None,
    *,
    overwrite_explicit: bool = False,
) -> str | None:
    explicit = canonical_lesson_category(category)
    if is_routine_title(title) and (overwrite_explicit or explicit is None):
        return ROUTINE_CATEGORY
    if explicit:
        return explicit
    if overwrite_explicit:
        return COURSEWORK_CATEGORY
    return None


def extract_time_slot(*parts: str | None) -> str | None:
    for part in parts:
        text = (part or "").strip()
        if not text:
            continue
        if _TIME_ONLY.match(text):
            return text[:64]
        match = _TIME_PREFIX.match(text)
        if match:
            return match.group("slot").strip()[:64]
    return None


def split_title_time_slot(title: str | None) -> tuple[str, str | None]:
    text = (title or "").strip()
    match = _TIME_PREFIX.match(text)
    if not match:
        return text, None
    rest = match.group("rest").strip()
    slot = match.group("slot").strip()[:64]
    return (rest or text, slot)


def time_slot_sort_key(value: str | None) -> tuple[int, int]:
    """Order ``8:30`` before ``10:00``; unknown slots stay after timed ones."""
    text = (value or "").strip()
    if not text:
        return (99, 0)
    match = _TIME_START.search(text)
    if not match:
        return (50, 0)
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = (match.group("ampm") or "").lower().replace(".", "")
    if ampm.startswith("p") and hour < 12:
        hour += 12
    if ampm.startswith("a") and hour == 12:
        hour = 0
    return (hour, minute)


def _lesson_identity(lesson: AIParsedLesson) -> tuple[int, int, str, str]:
    week = lesson.week_number if lesson.week_number is not None else 1
    return (
        week,
        lesson.day_number,
        (lesson.title or "").strip().lower(),
        (lesson.time_slot or "").strip().lower(),
    )


def dedupe_parsed_lessons(lessons: list[AIParsedLesson]) -> list[AIParsedLesson]:
    """Keep the first row for each week/day/title/time-slot combination."""
    seen: set[tuple[int, int, str, str]] = set()
    unique: list[AIParsedLesson] = []
    for lesson in lessons:
        key = _lesson_identity(lesson)
        if key in seen:
            continue
        seen.add(key)
        unique.append(lesson)
    return unique


def is_placeholder_title(title: str | None) -> bool:
    """True for empty-grid labels like "Week 1" or "36 weeks" with no assignment."""
    return bool(_PLACEHOLDER_TITLE.match((title or "").strip()))


def drop_placeholder_lessons(lessons: list[AIParsedLesson]) -> list[AIParsedLesson]:
    """Remove cover-page week labels that are not real coursework."""
    kept: list[AIParsedLesson] = []
    for lesson in lessons:
        title = (lesson.title or "").strip()
        if not title:
            continue
        if is_placeholder_title(title) and not (
            (lesson.pages or "").strip()
            or (lesson.time_slot or "").strip()
            or (lesson.description or "").strip()
        ):
            continue
        kept.append(lesson)
    return kept


def looks_like_daily_routine(lessons: list[AIParsedLesson]) -> bool:
    """True when a single-day timetable was dumped without a multi-week grid."""
    titled = [lesson for lesson in lessons if (lesson.title or "").strip()]
    if len(titled) < 2:
        return False
    days = {lesson.day_number for lesson in titled}
    weeks = {lesson.week_number for lesson in titled if lesson.week_number is not None}
    if len(days) != 1:
        return False
    if any(week != 1 for week in weeks):
        return False
    timed = sum(1 for lesson in titled if (lesson.time_slot or "").strip())
    if timed >= 2:
        return True
    if any((lesson.pages or "").strip() for lesson in titled):
        return False
    if any(_PACING_TITLE.search(lesson.title or "") for lesson in titled):
        return False
    titles = {(lesson.title or "").strip().lower() for lesson in titled}
    return len(titles) >= 2


def expand_daily_routine(
    lessons: list[AIParsedLesson],
    frequency_days: int = DEFAULT_ROUTINE_DAYS,
) -> list[AIParsedLesson]:
    """Copy a one-day subject stack across Week 1's school days."""
    if not looks_like_daily_routine(lessons):
        return lessons
    frequency = max(1, min(7, frequency_days))
    template = [
        lesson.model_copy(update={"week_number": 1, "day_number": 1})
        for lesson in lessons
        if (lesson.title or "").strip()
    ]
    expanded: list[AIParsedLesson] = []
    for day in range(1, frequency + 1):
        for lesson in template:
            expanded.append(lesson.model_copy(update={"day_number": day}))
    return expanded


class CurriculumPlanListRead(ORMModel):
    id: int
    title: str
    publisher: str | None
    author: str | None
    grade_level: str | None
    subject: str | None
    frequency_days: int
    total_weeks: int
    grading_weights: dict[str, float] | None = None
    is_archived: bool = False
    status: CurriculumPlanStatus = CurriculumPlanStatus.READY
    created_at: datetime
    lesson_count: int

    @field_validator("grading_weights", mode="before")
    @classmethod
    def _parse_list_weights(cls, value: Any) -> dict[str, float] | None:
        return parse_json_object(value)


class CurriculumLessonRead(ORMModel):
    id: int
    unit_title: str | None
    week_number: int | None
    day_number: int
    title: str
    description: str | None
    pages: str | None
    notes: str | None = None
    category: str | None = None
    time_slot: str | None = None
    resources: list[str] | None = None

    @field_validator("resources", mode="before")
    @classmethod
    def _parse_resources(cls, value: Any) -> list[str] | None:
        return parse_json_string_list(value)


class CurriculumPlanDetailRead(ORMModel):
    id: int
    title: str
    publisher: str | None
    author: str | None
    grade_level: str | None
    subject: str | None
    frequency_days: int
    total_weeks: int
    grading_weights: dict[str, float] | None = None
    is_archived: bool = False
    status: CurriculumPlanStatus = CurriculumPlanStatus.READY
    created_at: datetime
    lessons: list[CurriculumLessonRead]

    @field_validator("grading_weights", mode="before")
    @classmethod
    def _parse_detail_weights(cls, value: Any) -> dict[str, float] | None:
        return parse_json_object(value)


class CurriculumPlanImportRead(ORMModel):
    id: int


class CurriculumPlanPdfImportRead(BaseModel):
    plan_id: int
    message: str


class CurriculumPlanPaperImportRead(BaseModel):
    id: int
    status: CurriculumPlanStatus


class CurriculumLessonWrite(BaseModel):
    id: int | None = None
    unit_title: str | None = Field(default=None, max_length=255)
    week_number: int | None = Field(default=None, ge=1)
    day_number: int = Field(ge=1)
    title: str = Field(default="", max_length=255)
    description: str | None = None
    pages: str | None = Field(default=None, max_length=64)
    notes: str | None = None
    category: str | None = Field(default=None, max_length=64)
    time_slot: str | None = Field(default=None, max_length=64)
    resources: list[str] | None = None

    @field_validator(
        "unit_title",
        "description",
        "pages",
        "notes",
        "category",
        "time_slot",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("resources", mode="before")
    @classmethod
    def _clean_resources(cls, value: Any) -> list[str] | None:
        return parse_json_string_list(value)

    @model_validator(mode="after")
    def _categorize_routine_blocks(self) -> "CurriculumLessonWrite":
        self.category = normalize_lesson_category(self.title, self.category)
        if not self.time_slot:
            title, slot = split_title_time_slot(self.title)
            extracted = slot or extract_time_slot(self.description, self.notes)
            if extracted:
                self.time_slot = extracted
                if slot and title:
                    self.title = title
        return self

    @property
    def has_content(self) -> bool:
        title = (self.title or "").strip()
        notes = (self.notes or "").strip()
        return bool(title or notes or self.resources)


class CurriculumPlanWrite(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    author: str | None = Field(default=None, max_length=255)
    grade_level: str | None = Field(default=None, max_length=64)
    subject: str | None = Field(default=None, max_length=128)
    frequency_days: int = Field(default=5, ge=1, le=7)
    total_weeks: int = Field(default=36, ge=1, le=52)
    grading_weights: dict[str, float] | None = None
    lessons: list[CurriculumLessonWrite] = Field(default_factory=list)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("publisher", "author", "grade_level", "subject", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("grading_weights", mode="before")
    @classmethod
    def _parse_write_weights(cls, value: Any) -> dict[str, float] | None:
        return parse_json_object(value)

    @model_validator(mode="after")
    def _require_title(self) -> "CurriculumPlanWrite":
        if not self.title:
            raise ValueError("title is required")
        return self

    @model_validator(mode="after")
    def _dedupe_identical_lessons(self) -> "CurriculumPlanWrite":
        seen: set[tuple[int | None, int, str, str]] = set()
        unique: list[CurriculumLessonWrite] = []
        for lesson in self.lessons:
            key = (
                lesson.week_number,
                lesson.day_number,
                (lesson.title or "").strip().lower(),
                (lesson.time_slot or "").strip().lower(),
            )
            if lesson.has_content and key in seen:
                continue
            if lesson.has_content:
                seen.add(key)
            unique.append(lesson)
        self.lessons = unique
        return self


class CurriculumPlanArchiveRequest(BaseModel):
    is_archived: bool = True


class CurriculumPlanApplyRequest(BaseModel):
    student_id: int
    start_date: date
    target_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])

    @field_validator("target_days")
    @classmethod
    def _check_target_days(cls, value: list[int]) -> list[int]:
        return _normalize_weekdays(value)


class CurriculumPlanApplyRead(BaseModel):
    plan_id: int
    student_id: int
    assignments_created: int
    assignment_ids: list[int]
    first_scheduled_date: date | None = None
    last_scheduled_date: date | None = None


class AIParsedLesson(BaseModel):
    """One lesson as the local Ollama model must emit it."""

    model_config = ConfigDict(extra="forbid")

    unit_title: str | None = None
    week_number: int | None = None
    day_number: int
    title: str
    description: str | None = None
    pages: str | None = None
    time_slot: str | None = None
    category: str | None = None
    subject: str | None = None

    @field_validator(
        "unit_title",
        "description",
        "pages",
        "time_slot",
        "category",
        "subject",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _normalize_subject_time_and_category(self) -> "AIParsedLesson":
        subject = (self.subject or "").strip() or None
        self.subject = subject
        title = (self.title or "").strip()
        if not title and subject:
            title = subject
        split_title, split_slot = split_title_time_slot(title)
        if split_slot:
            title = split_title or title
            if not self.time_slot:
                self.time_slot = split_slot
        if not self.time_slot:
            self.time_slot = extract_time_slot(self.description)
        self.title = title
        if not (self.unit_title or "").strip() and subject:
            self.unit_title = subject[:255]
        self.category = normalize_lesson_category(
            self.title,
            self.category,
            overwrite_explicit=True,
        )
        return self


class AIParsedCurriculum(BaseModel):
    """Structured Ollama output for a full pacing-guide PDF."""

    model_config = ConfigDict(extra="forbid")

    lessons: list[AIParsedLesson] = Field(default_factory=list)

    @model_validator(mode="after")
    def _dedupe_and_expand_daily_routines(self) -> "AIParsedCurriculum":
        self.lessons = expand_daily_routine(
            drop_placeholder_lessons(dedupe_parsed_lessons(self.lessons))
        )
        return self
