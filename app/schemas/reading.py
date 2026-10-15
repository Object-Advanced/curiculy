"""Reading lists: each child's books, with when they started and finished."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.reference.subjects import SUBJECTS_BY_CODE
from app.schemas.library import LibraryItemSummary

ReadingStatus = Literal["up_next", "reading", "finished"]


def _subject(value: str | None) -> str | None:
    if value is not None and value not in SUBJECTS_BY_CODE:
        raise ValueError("Pick a subject from the list.")
    return value


class ReadingEntryCreate(BaseModel):
    student_id: int
    library_item_id: int
    status: ReadingStatus = "up_next"
    started_on: date | None = None
    finished_on: date | None = None
    counts_toward: str | None = None

    _counts = field_validator("counts_toward")(_subject)

    @model_validator(mode="after")
    def _dates(self) -> ReadingEntryCreate:
        if self.started_on and self.finished_on and self.finished_on < self.started_on:
            raise ValueError("The day they finished can't be before the day they started.")
        return self


class ReadingEntryUpdate(BaseModel):
    """Only the fields sent are changed; null clears a date."""

    status: ReadingStatus | None = None
    started_on: date | None = None
    finished_on: date | None = None
    counts_toward: str | None = None

    _counts = field_validator("counts_toward")(_subject)


class ReadingEntryRead(BaseModel):
    id: int
    student_id: int
    student_name: str
    school_year_id: int | None
    book: LibraryItemSummary
    status: ReadingStatus
    status_label: str
    started_on: date | None
    finished_on: date | None
    counts_toward: str
    counts_toward_name: str
    # tracked: added by the parent. scheduled: its daily reading is on the calendar.
    source: str
    scheduled: bool
    lessons_total: int = 0
    lessons_done: int = 0
    pages: int | None = Field(default=None, description="The book's total pages, when known")
