"""Homework-help sessions and in-app parent notifications."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import TenantBase
from app.enums import HomeworkHelpMessageRole, HomeworkHelpStatus, ParentNotificationType, enum_values
from app.models.mixins import TimestampMixin


class HomeworkHelpSession(TimestampMixin, TenantBase):
    __tablename__ = "homework_help_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[HomeworkHelpStatus] = mapped_column(
        Enum(HomeworkHelpStatus, native_enum=False, length=32, values_callable=enum_values),
        default=HomeworkHelpStatus.ACTIVE,
        nullable=False,
    )
    push_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    messages: Mapped[list["HomeworkHelpMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="HomeworkHelpMessage.id",
    )


class HomeworkHelpMessage(TimestampMixin, TenantBase):
    __tablename__ = "homework_help_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("homework_help_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[HomeworkHelpMessageRole] = mapped_column(
        Enum(HomeworkHelpMessageRole, native_enum=False, length=32, values_callable=enum_values),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped[HomeworkHelpSession] = relationship(back_populates="messages")


class ParentNotification(TimestampMixin, TenantBase):
    __tablename__ = "parent_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ParentNotificationType] = mapped_column(
        Enum(ParentNotificationType, native_enum=False, length=64, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
