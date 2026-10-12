"""The Library: four kinds of book, their structure, readiness, and search."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.reference.grades import normalize_grade
from app.reference.subjects import SUBJECTS_BY_CODE
from app.services.library_rules import KINDS, LESSON_TYPES, MATERIAL_KINDS, MEASURES, READING_KINDS

_PASSWORD = re.compile(r"\bpass(word|wd|code)?\s*[:=]", re.IGNORECASE)


def _one_of(value: str | None, allowed, message: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned not in allowed:
        raise ValueError(message)
    return cleaned


class LibraryItemFields(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    author: str | None = Field(default=None, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    series: str | None = Field(default=None, max_length=255)
    edition: str | None = Field(default=None, max_length=64)
    isbn: str | None = Field(default=None, max_length=20)
    subject_code: str | None = None
    grade: str | None = None
    reading_kind: str | None = None
    total_pages: int | None = Field(default=None, ge=1, le=5000)
    answer_key_start_page: int | None = Field(default=None, ge=1, le=5000)
    lesson_count: int | None = Field(default=None, ge=1, le=1000)
    measure: str | None = None
    minutes_per_session: int | None = Field(default=None, ge=1, le=300)
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    usual_pages_per_day: int | None = Field(default=None, ge=1, le=200)
    consumable: bool | None = None
    website_url: str | None = Field(default=None, max_length=1024)
    login_note: str | None = Field(default=None, max_length=255)
    cover_url: str | None = Field(default=None, max_length=1024)
    notes: str | None = None

    @field_validator("title", "author", "publisher", "series", "edition", "isbn", "notes", mode="before")
    @classmethod
    def _tidy(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            return cleaned or None
        return value

    @field_validator("subject_code")
    @classmethod
    def _subject(cls, value: str | None) -> str | None:
        return _one_of(value, SUBJECTS_BY_CODE, "Pick a subject from the list.")

    @field_validator("grade", mode="before")
    @classmethod
    def _grade(cls, value: object) -> object:
        return normalize_grade(value) if isinstance(value, str) and value.strip() else None

    @field_validator("reading_kind")
    @classmethod
    def _reading_kind(cls, value: str | None) -> str | None:
        return _one_of(value, READING_KINDS, "Pick novel, biography, poetry, picture book, read-aloud or other.")

    @field_validator("measure")
    @classmethod
    def _measure(cls, value: str | None) -> str | None:
        return _one_of(value, MEASURES, "Online programs are measured in lessons or minutes.")

    @field_validator("website_url", "cover_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        if not cleaned.startswith(("https://", "http://")):
            raise ValueError("Links start with https://")
        return cleaned

    @field_validator("login_note")
    @classmethod
    def _no_passwords(cls, value: str | None) -> str | None:
        if value and _PASSWORD.search(value):
            raise ValueError("Don't put passwords here. Curiculy never stores sign-ins for other sites.")
        return value.strip() if value else None


class LibraryItemCreate(LibraryItemFields):
    """``kind`` is asked first, so every question after it makes sense."""

    kind: str
    title: str = Field(min_length=1, max_length=255)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        return _one_of(value, KINDS, "Pick reading book, workbook, curriculum or online program.")


class LibraryItemUpdate(LibraryItemFields):
    kind: str | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str | None) -> str | None:
        return _one_of(value, KINDS, "Pick reading book, workbook, curriculum or online program.")


class ChapterWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_page: int = Field(ge=1, le=5000)
    subject_code: str | None = None

    @field_validator("subject_code")
    @classmethod
    def _subject(cls, value: str | None) -> str | None:
        return _one_of(value, SUBJECTS_BY_CODE, "Pick a subject from the list.")


class ChapterRead(ChapterWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MaterialWrite(BaseModel):
    """Leave out ``id`` to add a material; include it to keep or edit one."""

    id: int | None = None
    kind: str
    title: str = Field(min_length=1, max_length=255)
    isbn: str | None = Field(default=None, max_length=20)
    pages: int | None = Field(default=None, ge=1, le=5000)
    audience: str = "student"

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        return _one_of(value, MATERIAL_KINDS, "Pick a kind of material from the list.")

    @field_validator("audience")
    @classmethod
    def _audience(cls, value: str) -> str:
        return _one_of(value, {"student", "parent"}, "A material is for the student or the parent.")


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    title: str
    isbn: str | None
    pages: int | None
    audience: str


class LessonPagesWrite(BaseModel):
    material_id: int
    start_page: int = Field(ge=1, le=5000)
    end_page: int = Field(ge=1, le=5000)


class LessonPagesRead(LessonPagesWrite):
    model_config = ConfigDict(from_attributes=True)


class LessonWrite(BaseModel):
    number: int | None = Field(default=None, ge=1, le=10000)
    name: str | None = Field(default=None, max_length=255)
    type: str = "lesson"
    unit: str | None = Field(default=None, max_length=255)
    minutes: int | None = Field(default=None, ge=1, le=300)
    pages: list[LessonPagesWrite] = Field(default_factory=list)

    @field_validator("type")
    @classmethod
    def _type(cls, value: str) -> str:
        return _one_of(value, LESSON_TYPES, "A lesson is a lesson, test, quiz, review or project.")

    @field_validator("name", "unit", mode="before")
    @classmethod
    def _tidy(cls, value: object) -> object:
        if isinstance(value, str):
            return " ".join(value.split()) or None
        return value


class LessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: int | None
    name: str | None
    type: str
    unit: str | None
    minutes: int | None
    pages: list[LessonPagesRead]


class LessonGenerate(BaseModel):
    """'Make lessons 1-170': numbered lessons to fill in."""

    count: int = Field(ge=1, le=1000)
    first_number: int | None = Field(default=None, ge=1, le=10000)
    type: str = "lesson"

    @field_validator("type")
    @classmethod
    def _type(cls, value: str) -> str:
        return _one_of(value, LESSON_TYPES, "A lesson is a lesson, test, quiz, review or project.")


class MissingRead(BaseModel):
    field: str
    label: str
    reason: str


class ProblemRead(BaseModel):
    level: str
    where: str
    message: str


class ReadinessRead(BaseModel):
    """``ready`` means it can be scheduled; otherwise what's missing, and why."""

    ready: bool
    missing: list[MissingRead]
    problems: list[ProblemRead]
    lessons_total: int = 0
    lessons_with_pages: int = 0
    lessons_with_names: int = 0


class CoverRead(BaseModel):
    url: str | None
    source: str | None  # "upload", "lookup" or None (a generated cover)
    review: str | None = None  # uploaded covers: pending, approved, rejected


class LibraryItemSummary(BaseModel):
    id: int
    kind: str
    kind_label: str
    title: str
    author: str | None
    subject_code: str | None
    subject_name: str | None
    grade: str | None
    cover: CoverRead
    ready: bool
    missing_count: int
    problems_count: int


class LibraryItemRead(LibraryItemSummary):
    publisher: str | None
    series: str | None
    edition: str | None
    isbn: str | None
    reading_kind: str | None
    total_pages: int | None
    answer_key_start_page: int | None
    lesson_count: int | None
    measure: str | None
    minutes_per_session: int | None
    days_per_week: int | None
    usual_pages_per_day: int | None
    consumable: bool
    website_url: str | None
    login_note: str | None
    notes: str | None
    chapters: list[ChapterRead]
    materials: list[MaterialRead]
    lessons: list[LessonRead]
    readiness: ReadinessRead


class SearchResult(BaseModel):
    source: str  # library (already yours), catalog, open_library, google_books
    title: str
    subtitle: str | None = None
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None
    year: int | None = None
    isbn: str | None = None
    total_pages: int | None = None
    cover_url: str | None = None
    guessed_kind: str
    guessed_kind_label: str
    library_item_id: int | None = None


class SearchResults(BaseModel):
    query: str
    results: list[SearchResult]
    notice: str | None = None
