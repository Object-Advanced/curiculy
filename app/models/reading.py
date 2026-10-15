"""Reading lists: each child's books, with when they started and finished.

A book is on a child's list because the parent tracks it ("just track it"),
or because it was scheduled (from the Curriculum planner or the Library's
"Schedule it"), in which case it moves to reading and finished as its lessons
are checked off. Each entry belongs to a school year, so the lifetime record
has a reading list per year. See docs/6-planning/product-spine.md.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import TenantBase
from app.models.mixins import TimestampMixin


class ReadingListEntry(TimestampMixin, TenantBase):
    __tablename__ = "reading_list_entries"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "library_item_id", "school_year_id",
            name="uq_reading_list_entries_book", postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_year_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_years.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # up_next, reading, finished
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="up_next")
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    finished_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The subject it counts toward (Reading by default; a biography can count
    # toward History). A code from app.reference.subjects.
    counts_toward: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # tracked (added by the parent) or scheduled (its lessons are on the calendar)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="tracked")

    item = relationship("LibraryItem")
    student = relationship("Student")
