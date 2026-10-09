"""Core educational data model: subject taxonomy and dated assignment events.

The catalog in :mod:`app.models.curriculum` is static reference data describing
what a program *contains*. This module holds the two things it deliberately
leaves out:

* Taxonomy. ``SubjectTaxonomy`` is the hierarchical subject tree (Language Arts
  > Reading); ``ReportingCategory`` is the flat bucket a state or district wants
  numbers reported under. ``CurriculumClassification`` attaches both to a
  ``CurriculumResource`` so the same catalog row can be filed differently
  without editing the catalog.
* Events. ``Assignment`` is one dated piece of work for one student, with
  ``AssignmentGrade`` and ``AssignmentEvidence`` hanging off it. Catalog
  references are integer ids with no foreign key, because the catalog lives in
  a separate database; retiring a resource never rewrites a student's history.
  Everything owned by an assignment still cascades away with it.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import CatalogBase, TenantBase
from app.enums import AssignmentStatus, AttendanceStatus, ScoreType, enum_values
from app.models.curriculum import CurriculumResource, CurriculumUnit
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models import Student


class SubjectTaxonomy(TimestampMixin, CatalogBase):
    """Hierarchical subject tree: Language Arts > Reading > Phonics, any depth."""

    __tablename__ = "subject_taxonomies"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_subject_taxonomy_parent_name"),
        Index("ix_subject_taxonomies_parent_order", "parent_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_taxonomies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    parent: Mapped["SubjectTaxonomy | None"] = relationship(
        back_populates="children",
        foreign_keys=[parent_id],
        remote_side="SubjectTaxonomy.id",
    )
    children: Mapped[list["SubjectTaxonomy"]] = relationship(
        back_populates="parent",
        foreign_keys=[parent_id],
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str:
        """Path from the root, which is how a transcript line needs to read."""
        if self.parent is None:
            return self.name
        return f"{self.parent.full_name} > {self.name}"


class ReportingCategory(TimestampMixin, CatalogBase):
    """A reporting bucket, e.g. "Reading" or "Literature" on a state form.

    Kept separate from :class:`SubjectTaxonomy` because reporting buckets are
    flat, externally defined, and rarely line up with how a subject is taught.
    """

    __tablename__ = "reporting_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CurriculumClassification(TimestampMixin, TenantBase):
    """Files a household resource under a subject and, optionally, a report bucket.

    Subject and reporting-category ids point at catalog.db without a foreign key,
    matching how assignments store catalog references.
    """

    __tablename__ = "curriculum_classifications"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_resource_id",
            "subject_taxonomy_id",
            "reporting_category_id",
            name="uq_classification_resource_subject_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_resource_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_taxonomy_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    reporting_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum_resource: Mapped[CurriculumResource] = relationship(
        back_populates="classifications",
        foreign_keys=[curriculum_resource_id],
    )


class Assignment(TimestampMixin, TenantBase):
    """A dated piece of work for one student; the central educational event."""

    __tablename__ = "assignments"
    __table_args__ = (
        Index("ix_assignments_student_scheduled_date", "student_id", "scheduled_date"),
        Index("ix_assignments_student_status", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Tenant library / resource / unit ids are integers without ForeignKey().
    # Resource and unit ids were stored that way when the comment assumed a
    # catalog split; they actually point at tenant rows. ``curriculum_id``
    # likewise points at tenant ``curricula`` (same pattern as Enrollment).
    curriculum_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    curriculum_resource_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    curriculum_unit_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    subject_taxonomy_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, native_enum=False, length=32, values_callable=enum_values),
        default=AssignmentStatus.ASSIGNED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    shared_group_uuid: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    student: Mapped["Student"] = relationship(
        back_populates="assignments",
        foreign_keys=[student_id],
    )
    grade: Mapped["AssignmentGrade | None"] = relationship(
        back_populates="assignment",
        foreign_keys="AssignmentGrade.assignment_id",
        cascade="all, delete-orphan",
        uselist=False,
    )
    evidence: Mapped[list["AssignmentEvidence"]] = relationship(
        back_populates="assignment",
        foreign_keys="AssignmentEvidence.assignment_id",
        cascade="all, delete-orphan",
        order_by="AssignmentEvidence.id",
    )

    @property
    def is_complete(self) -> bool:
        return self.status is AssignmentStatus.COMPLETED

    @property
    def color_hex(self) -> str:
        """The owning student's calendar color, for tiles on a shared calendar."""
        from app.models import DEFAULT_STUDENT_COLOR

        student = self.student
        if student is not None and student.color_hex:
            return student.color_hex
        return DEFAULT_STUDENT_COLOR

    @property
    def curriculum_resource(self) -> CurriculumResource | None:
        return getattr(self, "_catalog_resource", None)

    @curriculum_resource.setter
    def curriculum_resource(self, value: CurriculumResource | None) -> None:
        self._catalog_resource = value
        if value is not None:
            self.curriculum_resource_id = value.id

    @property
    def curriculum_unit(self) -> CurriculumUnit | None:
        return getattr(self, "_catalog_unit", None)

    @curriculum_unit.setter
    def curriculum_unit(self, value: CurriculumUnit | None) -> None:
        self._catalog_unit = value
        if value is not None:
            self.curriculum_unit_id = value.id

    @property
    def subject_taxonomy(self) -> SubjectTaxonomy | None:
        return getattr(self, "_catalog_subject", None)

    @subject_taxonomy.setter
    def subject_taxonomy(self, value: SubjectTaxonomy | None) -> None:
        self._catalog_subject = value
        if value is not None:
            self.subject_taxonomy_id = value.id

    @property
    def subject_name(self) -> str | None:
        return self.subject_taxonomy.name if self.subject_taxonomy else None

    @property
    def resource_title(self) -> str | None:
        return self.curriculum_resource.title if self.curriculum_resource else None

    @property
    def unit_title(self) -> str | None:
        return self.curriculum_unit.title if self.curriculum_unit else None

    def resolved_curriculum_id(self) -> int | None:
        """Stored library id, else one derived from an attached resource or unit.

        Historical plan-apply rows have neither. Do not infer from title.
        """
        if self.curriculum_id is not None:
            return self.curriculum_id
        if self.curriculum_resource is not None:
            edition = self.curriculum_resource.curriculum_edition
            if edition is not None:
                return edition.curriculum_id
        if self.curriculum_unit is not None:
            edition = self.curriculum_unit.curriculum_edition
            if edition is not None:
                return edition.curriculum_id
        return None

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)


class AssignmentGrade(TimestampMixin, TenantBase):
    """The single recorded result for an assignment.

    ``score_value`` is a string on purpose: homeschool records mix "A+",
    "18/20", "Pass", and "92" and normalizing them destroys what the parent
    actually wrote down. ``score_type`` says how to interpret it.
    """

    __tablename__ = "assignment_grades"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_assignment_grade_assignment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    score_type: Mapped[ScoreType] = mapped_column(
        Enum(ScoreType, native_enum=False, length=32, values_callable=enum_values),
        default=ScoreType.PERCENTAGE,
        nullable=False,
    )
    score_value: Mapped[str] = mapped_column(String(64), nullable=False)
    graded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignment: Mapped[Assignment] = relationship(
        back_populates="grade",
        foreign_keys=[assignment_id],
    )


class AssignmentEvidence(TimestampMixin, TenantBase):
    """A work sample backing an assignment: a stored file, a link, or a note."""

    __tablename__ = "assignment_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignment: Mapped[Assignment] = relationship(
        back_populates="evidence",
        foreign_keys=[assignment_id],
    )


class Attendance(TimestampMixin, TenantBase):
    """One day's attendance for one student: present, absent, sick, or vacation."""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
        Index("ix_attendance_student_date", "student_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False, length=32, values_callable=enum_values),
        nullable=False,
    )

    student: Mapped["Student"] = relationship(
        back_populates="attendance",
        foreign_keys=[student_id],
    )
