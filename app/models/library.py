"""The family's Library: reading books, workbooks, curricula and online programs.

One ``LibraryItem`` per book or program, with its structure: ``LibraryChapter``
rows (reading books and workbooks), and for curricula ``LibraryMaterial`` rows
(student text, worktext, teacher's edition…) and the full lesson list
(``LibraryLesson`` with ``LibraryLessonPages`` per material).

What each kind must have before it can be scheduled, and why, lives in
``app.services.library_rules``. See docs/6-planning/product-spine.md
("Library: one shelf, four kinds of book").

These replace the older ``curricula`` / ``curriculum_plans`` structures as the
new screens are built; the older tables stay until then.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import TenantBase
from app.models.mixins import TimestampMixin


class LibraryItem(TimestampMixin, TenantBase):
    __tablename__ = "library_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # reading_book, workbook, curriculum, online_program
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
    website_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # A hint for the parent ("log in as Ada"). Never a password.
    login_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # A cover found by the lookup (a URL), or one the family uploaded (a file
    # under the evidence volume, reviewed before other families see it).
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_review: Mapped[str | None] = mapped_column(String(16), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    chapters: Mapped[list[LibraryChapter]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="LibraryChapter.position"
    )
    materials: Mapped[list[LibraryMaterial]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="LibraryMaterial.position"
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


class LibraryMaterial(TimestampMixin, TenantBase):
    __tablename__ = "library_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # student_text, worktext, teachers_edition, answer_key, tests, reader,
    # activity_book, video_online, other
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "student" materials are what kid screens point to; "parent" ones aren't shown to kids.
    audience: Mapped[str] = mapped_column(String(16), nullable=False, default="student")

    item: Mapped[LibraryItem] = relationship(back_populates="materials")


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

    item: Mapped[LibraryItem] = relationship(back_populates="lessons")
    pages: Mapped[list[LibraryLessonPages]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="LibraryLessonPages.id"
    )


class LibraryLessonPages(TimestampMixin, TenantBase):
    """A lesson's pages in one material ("Text pp. 212-215")."""

    __tablename__ = "library_lesson_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("library_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("library_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)

    lesson: Mapped[LibraryLesson] = relationship(back_populates="pages")
    material: Mapped[LibraryMaterial] = relationship()
