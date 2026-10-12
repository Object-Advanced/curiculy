"""The community catalog: what families see, and the admin review queue."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.reference.grades import normalize_grade
from app.reference.subjects import SUBJECTS_BY_CODE
from app.schemas.library import ChapterWrite, LessonWrite
from app.services.library_rules import MEASURES, READING_KINDS


# --- Families -----------------------------------------------------------------

class CommunityEntrySummary(BaseModel):
    id: int
    kind: str
    kind_label: str
    title: str
    author: str | None
    publisher: str | None
    edition: str | None
    isbn: str | None
    subject_code: str | None
    subject_name: str | None
    grade: str | None
    total_pages: int | None
    chapters_count: int
    lessons_count: int
    cover_url: str | None
    families_count: int
    # "170 lessons, 640 pages, entered by 4 families"
    detail: str


class CommunityChapter(BaseModel):
    name: str
    start_page: int
    subject_code: str | None = None


class CommunityLesson(BaseModel):
    number: int | None = None
    name: str | None = None
    type: str = "lesson"
    unit: str | None = None
    minutes: int | None = None
    start_page: int | None = None
    end_page: int | None = None


class CommunityEntryRead(CommunityEntrySummary):
    """Everything a family sees before adding it: the details, chapters and lesson list."""

    version: int
    series: str | None
    reading_kind: str | None
    answer_key_start_page: int | None
    lesson_count: int | None
    measure: str | None
    minutes_per_session: int | None
    days_per_week: int | None
    for_parent: bool
    website_url: str | None
    chapters: list[CommunityChapter]
    lessons: list[CommunityLesson]
    # How many community curricula use it ("Used in 3 curricula")
    in_curricula: int
    # The family's copy, when they already added it
    library_item_id: int | None


class AdoptEntry(BaseModel):
    entry_id: int


class SuggestedItem(BaseModel):
    role: str
    role_label: str
    entry: CommunityEntrySummary
    # The family's copy, when it's already in their library
    library_item_id: int | None
    # Families who used it (in this curriculum, or alongside the textbook)
    families_count: int


class CommunityCurriculumRead(BaseModel):
    id: int
    name: str
    subject_code: str | None
    subject_name: str | None
    grade: str | None
    days_per_week: int | None
    families_count: int
    items: list[SuggestedItem]


class SuggestionsRead(BaseModel):
    """'Other families built a similar curriculum using these…'"""

    textbook: CommunityEntrySummary | None
    families_count: int
    curricula: list[CommunityCurriculumRead]
    # Everything used alongside the textbook, most-used first, for "change anything"
    often_used_with: list[SuggestedItem]
    message: str


# --- Admins -------------------------------------------------------------------

class FlagRead(BaseModel):
    code: str
    group: str
    level: str
    where: str
    message: str


class ContributionSummary(BaseModel):
    id: int
    kind: str  # item or curriculum
    item_kind: str | None
    kind_label: str
    title: str
    isbn: str | None
    status: str
    needs_review: bool
    is_correction: bool
    has_cover: bool
    # A stable label, not the family's id: "Family 3f9a2c"
    contributor_label: str
    review_flags: int
    notes: int
    created_at: datetime
    updated_at: datetime


class FieldChange(BaseModel):
    field: str
    catalog: Any = None
    contributed: Any = None


class ContributionChanges(BaseModel):
    """What a correction (or a duplicate) changes compared with the catalog's version."""

    summary: str
    fields: list[FieldChange]
    chapters_before: int
    chapters_after: int
    lessons_before: int
    lessons_after: int
    lessons_changed: list[str]


class LookupBook(BaseModel):
    title: str
    authors: list[str]
    page_count: int | None


class ContributorRead(BaseModel):
    label: str
    accepted: int
    rejected: int
    total: int


class ContributionDetail(ContributionSummary):
    data: dict[str, Any]
    flags: list[FlagRead]
    # The catalog entry it changes, or the one it seems to repeat
    compare_entry: CommunityEntrySummary | None
    changes: ContributionChanges | None
    lookup: LookupBook | None
    cover_url: str | None
    contributor: ContributorRead
    review_note: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    result_entry_id: int | None
    result_curriculum_id: int | None


class CatalogEdits(BaseModel):
    """Approve with edits: any field to change, and whole chapter or lesson lists."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
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
    for_parent: bool | None = None
    website_url: str | None = Field(default=None, max_length=1024)
    chapters: list[ChapterWrite] | None = None
    lessons: list[LessonWrite] | None = None

    @field_validator("subject_code")
    @classmethod
    def _subject(cls, value: str | None) -> str | None:
        if value is not None and value not in SUBJECTS_BY_CODE:
            raise ValueError("Pick a subject from the list.")
        return value

    @field_validator("grade", mode="before")
    @classmethod
    def _grade(cls, value: object) -> object:
        return normalize_grade(value) if isinstance(value, str) and value.strip() else value

    @field_validator("reading_kind")
    @classmethod
    def _reading_kind(cls, value: str | None) -> str | None:
        if value is not None and value not in READING_KINDS:
            raise ValueError("Pick novel, biography, poetry, picture book, read-aloud or other.")
        return value

    @field_validator("measure")
    @classmethod
    def _measure(cls, value: str | None) -> str | None:
        if value is not None and value not in MEASURES:
            raise ValueError("Online programs are measured in lessons or minutes.")
        return value


class ApproveRequest(BaseModel):
    edits: CatalogEdits | None = None
    # False approves the details but not the uploaded cover.
    include_cover: bool = True
    note: str | None = Field(default=None, max_length=2000)


class MergeRequest(BaseModel):
    """Another family entered a book that's already in the catalog."""

    entry_id: int
    # True makes this contribution the entry's new version (it's better).
    replace_details: bool = False
    include_cover: bool = True
    note: str | None = Field(default=None, max_length=2000)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class EntryVersionRead(BaseModel):
    version: int
    approved_by: str
    note: str | None
    contribution_id: int | None
    created_at: datetime


class EntryAdminRead(CommunityEntryRead):
    status: str
    versions: list[EntryVersionRead]


class RollbackRequest(BaseModel):
    version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=2000)


class ReviewResult(BaseModel):
    contribution: ContributionDetail
    entry_id: int | None = None
    curriculum_id: int | None = None
    # Curricula: items left out because they aren't in the catalog
    left_out: list[str] = Field(default_factory=list)
