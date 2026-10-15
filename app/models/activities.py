"""Activities: what a subject without a curriculum looks like on the record.

PE, music, art, health and safety rarely have a curriculum. An activity is
"5K race, PE, 40 min" with a photo at the finish line, for one child or
several, counting toward one or more subjects. Its photos are work samples;
a link holds a video (an unlisted YouTube video, a Drive file).
See docs/6-planning/product-spine.md ("Activities").
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import TenantBase
from app.models.mixins import TimestampMixin


class Activity(TimestampMixin, TenantBase):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    on_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Codes from app.reference.subjects
    subject_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )

    students: Mapped[list[ActivityStudent]] = relationship(
        back_populates="activity", cascade="all, delete-orphan", order_by="ActivityStudent.id"
    )
    evidence: Mapped[list[ActivityEvidence]] = relationship(
        back_populates="activity", cascade="all, delete-orphan", order_by="ActivityEvidence.id"
    )


class ActivityStudent(TenantBase):
    __tablename__ = "activity_students"
    __table_args__ = (UniqueConstraint("activity_id", "student_id", name="uq_activity_students_child"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)

    activity: Mapped[Activity] = relationship(back_populates="students")
    student = relationship("Student")


class ActivityEvidence(TenantBase):
    """A photo or PDF from an activity: a work sample."""

    __tablename__ = "activity_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    activity: Mapped[Activity] = relationship(back_populates="evidence")
