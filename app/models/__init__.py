from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import TenantBase
from app.enums import ExceptionKind, enum_values
from app.models.curriculum import (
    Author,
    BookEdition,
    Curriculum,
    CurriculumEdition,
    CurriculumLesson,
    CurriculumPageMapping,
    CurriculumPlan,
    CurriculumResource,
    CurriculumUnit,
    Publisher,
    Work,
    WorkAuthor,
)
from app.models.education import (
    Assignment,
    AssignmentEvidence,
    AssignmentGrade,
    Attendance,
    CurriculumClassification,
    ReportingCategory,
    SubjectTaxonomy,
)
from app.models.evidence_staging import EvidenceStaging
from app.models.homework import HomeworkHelpMessage, HomeworkHelpSession, ParentNotification
from app.models.library import (
    LibraryChapter,
    LibraryItem,
    LibraryLesson,
    LibraryLessonPages,
    LibraryMaterial,
)
from app.models.mixins import TimestampMixin

DEFAULT_STUDENT_COLOR = "#356b46"
# Distinct greens used when a child has not picked a custom color yet.
STUDENT_COLOR_PALETTE = (
    "#356b46",  # forest
    "#5a9a6a",  # sage
    "#1f7a5c",  # teal pine
    "#8fbc6a",  # moss
    "#164a32",  # deep pine
    "#6bbf8a",  # mint
)


def next_unused_student_color(taken: set[str] | list[str]) -> str:
    taken_lower = {color.lower() for color in taken if color}
    for color in STUDENT_COLOR_PALETTE:
        if color.lower() not in taken_lower:
            return color
    return STUDENT_COLOR_PALETTE[len(taken_lower) % len(STUDENT_COLOR_PALETTE)]


class Household(TimestampMixin, TenantBase):
    """The family itself: exactly one row per family (``tenant_id``)."""

    __tablename__ = "households"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_households_tenant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # IANA zone ("America/Chicago"). "Today" for this family follows it; the
    # SPA fills it from the parent's browser when it is missing.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    students: Mapped[list["Student"]] = relationship(back_populates="household")
    school_years: Mapped[list["SchoolYear"]] = relationship(back_populates="household")
    settings: Mapped["HouseholdSettings | None"] = relationship(
        back_populates="household",
        uselist=False,
        cascade="all, delete-orphan",
    )
    calendar_exceptions: Mapped[list["CalendarException"]] = relationship(
        back_populates="household"
    )
    states: Mapped[list["HouseholdState"]] = relationship(
        back_populates="household",
        cascade="all, delete-orphan",
        order_by="HouseholdState.starts_on",
    )


class HouseholdState(TimestampMixin, TenantBase):
    """Which state the family homeschools in, from a date (a move adds a row).

    The state on a given day is the row with the latest ``starts_on`` on or
    before it, so each part of a school year is checked against the right law.
    """

    __tablename__ = "household_states"
    __table_args__ = (
        UniqueConstraint("household_id", "starts_on", name="uq_household_states_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)

    household: Mapped[Household] = relationship(back_populates="states")


class Student(TimestampMixin, TenantBase):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # A code from app.reference.grades ("PreK", "K", "1" … "12").
    grade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # When a parent last set or confirmed the grade; it's asked again after
    # each July 1 (a new school year).
    grade_confirmed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Only so a state's special-education rules apply. The IEP itself and any
    # diagnosis are never stored (docs: Privacy, keep the minimum).
    has_iep: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_hex: Mapped[str] = mapped_column(
        String(7),
        default=DEFAULT_STUDENT_COLOR,
        server_default=DEFAULT_STUDENT_COLOR,
        nullable=False,
    )

    household: Mapped[Household] = relationship(back_populates="students")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student")
    calendar_exceptions: Mapped[list["CalendarException"]] = relationship(
        back_populates="student"
    )
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="student",
        foreign_keys="Assignment.student_id",
        cascade="all, delete-orphan",
    )
    attendance: Mapped[list[Attendance]] = relationship(
        back_populates="student",
        foreign_keys="Attendance.student_id",
        cascade="all, delete-orphan",
    )


class StudentSubject(TimestampMixin, TenantBase):
    """One subject slot for one child in one school year.

    ``kind``: ``required`` (the family's state requires it for the child's
    grade), ``common`` (a preset from the subject list) or ``own`` (named by
    the family, counting toward a listed subject or nothing). ``active`` is
    whether it's taught this year; ``objective`` is the one line that prints
    in the state's "objectives by subject" outline.
    """

    __tablename__ = "student_subjects"
    __table_args__ = (
        Index(
            "uq_student_subjects_listed",
            "student_id",
            "school_year_id",
            "subject_code",
            unique=True,
            postgresql_where=text("subject_code IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey("school_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # A code from app.reference.subjects; NULL for the family's own subjects.
    subject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    counts_toward: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class SchoolYear(TimestampMixin, TenantBase):
    __tablename__ = "school_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    household: Mapped[Household] = relationship(back_populates="school_years")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="school_year")


class HouseholdSettings(TimestampMixin, TenantBase):
    """One row per household: class days and exception colors.

    Operational school-year dates live only on ``SchoolYear``. This table does
    not store a year window.

    ``weekdays`` is a comma-separated list of Python weekday numbers
    (0 is Monday, 6 is Sunday), matching auto-schedule.
    """

    __tablename__ = "household_settings"
    __table_args__ = (
        UniqueConstraint("household_id", name="uq_household_settings_household"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    weekdays: Mapped[str] = mapped_column(String(32), nullable=False, default="0,1,2,3,4")
    exception_colors: Mapped[str | None] = mapped_column(Text, nullable=True)

    household: Mapped[Household] = relationship(back_populates="settings")


class Enrollment(TimestampMixin, TenantBase):
    """This student is using this curriculum in this school year.

    Created from Settings or as a side effect of pacing commit / plan apply.
    Unique on student + curriculum + school year.
    """
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "curriculum_id",
            "school_year_id",
            name="uq_enrollment_student_curriculum_year",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    curriculum_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    school_year_id: Mapped[int] = mapped_column(ForeignKey("school_years.id"), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    student: Mapped[Student] = relationship(back_populates="enrollments")
    school_year: Mapped[SchoolYear] = relationship(back_populates="enrollments")


class CalendarException(TimestampMixin, TenantBase):
    __tablename__ = "calendar_exceptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    kind: Mapped[ExceptionKind] = mapped_column(
        Enum(ExceptionKind, native_enum=False, length=32, values_callable=enum_values),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    household: Mapped[Household] = relationship(back_populates="calendar_exceptions")
    student: Mapped[Student | None] = relationship(back_populates="calendar_exceptions")


__all__ = [
    "DEFAULT_STUDENT_COLOR",
    "STUDENT_COLOR_PALETTE",
    "next_unused_student_color",
    "Assignment",
    "AssignmentEvidence",
    "AssignmentGrade",
    "Attendance",
    "Author",
    "BookEdition",
    "CalendarException",
    "Curriculum",
    "CurriculumClassification",
    "CurriculumEdition",
    "CurriculumLesson",
    "CurriculumPageMapping",
    "CurriculumPlan",
    "CurriculumResource",
    "CurriculumUnit",
    "Enrollment",
    "EvidenceStaging",
    "HomeworkHelpMessage",
    "HomeworkHelpSession",
    "Household",
    "HouseholdSettings",
    "HouseholdState",
    "LibraryChapter",
    "LibraryItem",
    "LibraryLesson",
    "LibraryLessonPages",
    "LibraryMaterial",
    "ParentNotification",
    "Publisher",
    "ReportingCategory",
    "SchoolYear",
    "Student",
    "StudentSubject",
    "SubjectTaxonomy",
    "Work",
    "WorkAuthor",
]
