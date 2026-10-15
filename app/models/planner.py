"""The Curriculum planner, and scheduling a curriculum for a child.

A ``PlannedCurriculum`` is a plan for one subject: usually its textbook (whose
lesson list sets the pace) plus any workbooks, online sites and books that go
with it, each a ``PlannedCurriculumItem`` pointing at a Library item. Without
a textbook, the parent picks the pace when scheduling. A single book
scheduled from the Library is a ``solo`` curriculum of one item. It isn't tied
to a child, so one plan can serve two children or be reused next year.

Scheduling makes a ``Course``: one child, one curriculum, one school year, a
start date and the weekdays it runs on. The dated lessons it puts on the
calendar remember their course.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import TenantBase
from app.models.community import CommunityCurriculum
from app.models.mixins import TimestampMixin


class PlannedCurriculum(TimestampMixin, TenantBase):
    __tablename__ = "planned_curricula"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # How many days a week the lessons happen (a 4-day program leaves a flex day).
    days_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # One library item scheduled on its own (the Library's "Schedule"): kept
    # out of the planner's list and never contributed to the catalog.
    solo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    # Started from a community curriculum ("Other families built a similar
    # curriculum"); unchanged copies aren't contributed back as new.
    # (A shared table, so it's referenced by its column, not by name.)
    community_curriculum_id: Mapped[int | None] = mapped_column(
        ForeignKey(CommunityCurriculum.id, ondelete="SET NULL"), nullable=True
    )

    items: Mapped[list[PlannedCurriculumItem]] = relationship(
        back_populates="curriculum", cascade="all, delete-orphan", order_by="PlannedCurriculumItem.position"
    )
    courses: Mapped[list[Course]] = relationship(back_populates="curriculum")


class PlannedCurriculumItem(TimestampMixin, TenantBase):
    __tablename__ = "planned_curriculum_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("planned_curricula.id", ondelete="CASCADE"), nullable=False, index=True
    )
    library_item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # textbook (sets the pace), workbook, online, reading, teacher (for the parent; not scheduled)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    curriculum: Mapped[PlannedCurriculum] = relationship(back_populates="items")
    library_item = relationship("LibraryItem")


class Course(TimestampMixin, TenantBase):
    """A curriculum scheduled for one child: the lessons on the calendar belong to it."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("planned_curricula.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_year_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_years.id", ondelete="SET NULL"), nullable=True, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # "0,1,2,3": the weekdays lessons land on (Monday = 0).
    weekdays: Mapped[str] = mapped_column(String(32), nullable=False)
    # "About how long is a lesson?": the estimate for lessons without their own.
    default_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    curriculum: Mapped[PlannedCurriculum] = relationship(back_populates="courses")
    student = relationship("Student")
