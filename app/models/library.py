"""The family's Library: books, textbooks, workbooks and online sites.

One ``LibraryItem`` per book or site, with its structure: ``LibraryChapter``
rows (books and workbooks) and, for textbooks, the lesson list
(``LibraryLesson``: number, name, type and pages). A curriculum, built in the
Curriculum planner, ties a textbook to workbooks, sites and books for a
subject (``app.models.planner``).

What each kind must have before it can be scheduled, and why, lives in
``app.services.library_rules``. See docs/6-planning/product-spine.md.

These replace the older ``curricula`` / ``curriculum_plans`` structures as the
new screens take over; the older tables stay until then.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import TenantBase
from app.models.community import CatalogEntry
from app.models.mixins import TimestampMixin


class LibraryItem(TimestampMixin, TenantBase):
    __tablename__ = "library_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # reading_book ("Book"), textbook, workbook, online_program ("Online site")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    series: Mapped[str | None] = mapped_column(String(255), nullable=True)
    edition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    # The subject (curricula, workbooks, online programs), or what a reading
    # book counts toward. A code from app.reference.subjects.
    subject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Reading books: novel, biography, poetry, picture_book, read_aloud, other
    reading_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Workbooks: pages from here to the end are the answer key or appendix,
    # never scheduled.
    answer_key_start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Workbooks with numbered lessons; online programs measured in lessons.
    lesson_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Online programs: "lessons" or "minutes".
    measure: Mapped[str | None] = mapped_column(String(16), nullable=True)
    minutes_per_session: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Curricula: days a week it's designed for; online programs: days a week.
    days_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usual_pages_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    # A teacher's edition or answer key: for the parent; kids never see it,
    # and it needs no lesson list of its own.
    for_parent: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    website_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # A hint for the parent ("log in as Ada"). Never a password.
    login_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # A cover found by the lookup (a URL), or one the family uploaded (a file
    # under the evidence volume, reviewed before other families see it).
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_review: Mapped[str | None] = mapped_column(String(16), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Added from the community catalog (or linked to it once the family's own
    # entry was approved): the entry and the version this copy matches. Edits
    # after that are offered to the catalog as corrections.
    # (A shared table, so it's referenced by its column, not by name.)
    catalog_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey(CatalogEntry.id, ondelete="SET NULL"), nullable=True, index=True
    )
    catalog_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chapters: Mapped[list[LibraryChapter]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="LibraryChapter.position"
    )
    lessons: Mapped[list[LibraryLesson]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="LibraryLesson.position"
    )


class LibraryChapter(TimestampMixin, TenantBase):
    __tablename__ = "library_chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    # Workbooks that mix subjects (Brain Quest): the chapter's subject.
    subject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)

    item: Mapped[LibraryItem] = relationship(back_populates="chapters")


class LibraryLesson(TimestampMixin, TenantBase):
    __tablename__ = "library_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # lesson, test, quiz, review, project
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="lesson")
    unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The lesson's pages in this textbook, quizzes and tests included.
    start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    item: Mapped[LibraryItem] = relationship(back_populates="lessons")
