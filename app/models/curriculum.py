"""Curriculum models: a shared ISBN dictionary, and a per-household library.

``catalog.db`` holds bibliographic reference data a barcode scan can reuse:
publishers, authors, works, and book editions. A family's saved programs live
in ``tenant.db`` as ``Curriculum`` (the household library) plus the editions,
resources, and units Auto-schedule writes for that lockbox alone.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import CatalogBase, TenantBase
from app.enums import (
    BookFormat,
    ContributorRole,
    CurriculumPlanStatus,
    CurriculumSource,
    MappingSource,
    ResourceKind,
    UnitKind,
    enum_values,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models import CurriculumClassification


class Publisher(TimestampMixin, CatalogBase):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    works: Mapped[list["Work"]] = relationship(
        back_populates="publisher",
        foreign_keys="Work.publisher_id",
    )
    book_editions: Mapped[list["BookEdition"]] = relationship(
        back_populates="publisher",
        foreign_keys="BookEdition.publisher_id",
    )


class Author(TimestampMixin, CatalogBase):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    work_links: Mapped[list["WorkAuthor"]] = relationship(
        back_populates="author",
        foreign_keys="WorkAuthor.author_id",
        cascade="all, delete-orphan",
    )


class Work(TimestampMixin, CatalogBase):
    """A book as an intellectual work, independent of any particular printing."""

    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publisher_id: Mapped[int | None] = mapped_column(
        ForeignKey("publishers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    publisher: Mapped[Publisher | None] = relationship(
        back_populates="works",
        foreign_keys=[publisher_id],
    )
    editions: Mapped[list["BookEdition"]] = relationship(
        back_populates="work",
        foreign_keys="BookEdition.work_id",
        cascade="all, delete-orphan",
    )
    author_links: Mapped[list["WorkAuthor"]] = relationship(
        back_populates="work",
        foreign_keys="WorkAuthor.work_id",
        cascade="all, delete-orphan",
    )

    @property
    def authors(self) -> list["WorkAuthor"]:
        """Contributors in billing order, which is how a title page reads."""
        return sorted(self.author_links, key=lambda link: (link.sort_order, link.id))


class WorkAuthor(TimestampMixin, CatalogBase):
    """Association object so a contributor's role and billing order are stored."""

    __tablename__ = "work_authors"
    __table_args__ = (
        UniqueConstraint("work_id", "author_id", "role", name="uq_work_author_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[ContributorRole] = mapped_column(
        Enum(ContributorRole, native_enum=False, length=32, values_callable=enum_values),
        default=ContributorRole.AUTHOR,
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    work: Mapped[Work] = relationship(
        back_populates="author_links",
        foreign_keys=[work_id],
    )
    author: Mapped[Author] = relationship(
        back_populates="work_links",
        foreign_keys=[author_id],
    )

    @property
    def author_name(self) -> str:
        return self.author.name


class BookEdition(TimestampMixin, CatalogBase):
    """A specific printing of a work; this is what a barcode identifies."""

    __tablename__ = "book_editions"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    publisher_id: Mapped[int | None] = mapped_column(
        ForeignKey("publishers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    edition_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    isbn10: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    isbn13: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    printing: Mapped[str | None] = mapped_column(String(64), nullable=True)
    book_format: Mapped[BookFormat] = mapped_column(
        Enum(BookFormat, native_enum=False, length=32, values_callable=enum_values),
        default=BookFormat.SOFTCOVER,
        nullable=False,
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    work: Mapped[Work] = relationship(
        back_populates="editions",
        foreign_keys=[work_id],
    )
    publisher: Mapped[Publisher | None] = relationship(
        back_populates="book_editions",
        foreign_keys=[publisher_id],
    )


class Curriculum(TimestampMixin, TenantBase):
    """A teaching program in one household's library, e.g. "Saxon Math 3".

    Distinct from the shared ISBN dictionary in ``catalog.db``. Listing this
    table is how the Curriculum Catalog page stays tenant-scoped.
    """

    __tablename__ = "curricula"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[CurriculumSource] = mapped_column(
        Enum(CurriculumSource, native_enum=False, length=32, values_callable=enum_values),
        default=CurriculumSource.MANUAL,
        nullable=False,
    )

    editions: Mapped[list["CurriculumEdition"]] = relationship(
        back_populates="curriculum",
        foreign_keys="CurriculumEdition.curriculum_id",
        cascade="all, delete-orphan",
    )

    @property
    def publisher_id(self) -> int | None:
        """Kept on the read model for compatibility; publishers live in catalog.db."""
        return None


class CurriculumEdition(TimestampMixin, TenantBase):
    """A revision of a program; pacing and page numbers are edition-specific."""

    __tablename__ = "curriculum_editions"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_id",
            "edition_label",
            name="uq_curriculum_edition_label",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edition_label: Mapped[str] = mapped_column(String(128), nullable=False)
    copyright_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum: Mapped[Curriculum] = relationship(
        back_populates="editions",
        foreign_keys=[curriculum_id],
    )
    resources: Mapped[list["CurriculumResource"]] = relationship(
        back_populates="curriculum_edition",
        foreign_keys="CurriculumResource.curriculum_edition_id",
        cascade="all, delete-orphan",
    )
    units: Mapped[list["CurriculumUnit"]] = relationship(
        back_populates="curriculum_edition",
        foreign_keys="CurriculumUnit.curriculum_edition_id",
        cascade="all, delete-orphan",
    )


class CurriculumResource(TimestampMixin, TenantBase):
    """A component a parent actually holds: student text, answer key, manipulative."""

    __tablename__ = "curriculum_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_edition_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_editions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    book_edition_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    kind: Mapped[ResourceKind] = mapped_column(
        Enum(ResourceKind, native_enum=False, length=32, values_callable=enum_values),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_consumable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum_edition: Mapped[CurriculumEdition] = relationship(
        back_populates="resources",
        foreign_keys=[curriculum_edition_id],
    )
    page_mappings: Mapped[list["CurriculumPageMapping"]] = relationship(
        back_populates="curriculum_resource",
        foreign_keys="CurriculumPageMapping.curriculum_resource_id",
        cascade="all, delete-orphan",
    )
    classifications: Mapped[list["CurriculumClassification"]] = relationship(
        back_populates="curriculum_resource",
        foreign_keys="CurriculumClassification.curriculum_resource_id",
        cascade="all, delete-orphan",
    )

    @property
    def book_edition(self) -> BookEdition | None:
        """The shared catalog printing, attached by the read path from catalog.db."""
        return getattr(self, "_catalog_book", None)

    @book_edition.setter
    def book_edition(self, value: BookEdition | None) -> None:
        self._catalog_book = value
        if value is not None:
            self.book_edition_id = value.id


class CurriculumUnit(TimestampMixin, TenantBase):
    """Teachable structure: course > unit > chapter > lesson, to any depth."""

    __tablename__ = "curriculum_units"
    __table_args__ = (
        Index(
            "ix_curriculum_units_edition_parent_order",
            "curriculum_edition_id",
            "parent_id",
            "sort_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_edition_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_editions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("curriculum_units.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kind: Mapped[UnitKind] = mapped_column(
        Enum(UnitKind, native_enum=False, length=32, values_callable=enum_values),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum_edition: Mapped[CurriculumEdition] = relationship(
        back_populates="units",
        foreign_keys=[curriculum_edition_id],
    )
    parent: Mapped["CurriculumUnit | None"] = relationship(
        back_populates="children",
        foreign_keys=[parent_id],
        remote_side="CurriculumUnit.id",
    )
    children: Mapped[list["CurriculumUnit"]] = relationship(
        back_populates="parent",
        foreign_keys=[parent_id],
        cascade="all, delete-orphan",
    )
    page_mappings: Mapped[list["CurriculumPageMapping"]] = relationship(
        back_populates="curriculum_unit",
        foreign_keys="CurriculumPageMapping.curriculum_unit_id",
        cascade="all, delete-orphan",
    )


class CurriculumPageMapping(TimestampMixin, TenantBase):
    """Where a unit physically lives in a resource, so pacing can count pages."""

    __tablename__ = "curriculum_page_mappings"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_unit_id",
            "curriculum_resource_id",
            "page_start",
            name="uq_page_mapping_unit_resource_start",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_unit_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    curriculum_resource_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    printed_page_start: Mapped[str | None] = mapped_column(String(32), nullable=True)
    printed_page_end: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[MappingSource] = mapped_column(
        Enum(MappingSource, native_enum=False, length=32, values_callable=enum_values),
        default=MappingSource.MANUAL,
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum_unit: Mapped[CurriculumUnit] = relationship(
        back_populates="page_mappings",
        foreign_keys=[curriculum_unit_id],
    )
    curriculum_resource: Mapped[CurriculumResource] = relationship(
        back_populates="page_mappings",
        foreign_keys=[curriculum_resource_id],
    )

    @property
    def page_count(self) -> int:
        return max(0, self.page_end - self.page_start + 1)

    @property
    def resource_title(self) -> str:
        return self.curriculum_resource.title


class CurriculumPlan(TimestampMixin, TenantBase):
    """A multi-week pacing guide, distinct from a standalone book in ``curricula``.

    Households import these from a CSV of units, weeks, and daily lessons, or
    author them in the lesson-plan builder. They do not participate in
    Auto-schedule; that path still uses CurriculumUnit.
    """

    __tablename__ = "curriculum_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    frequency_days: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", nullable=False
    )
    total_weeks: Mapped[int] = mapped_column(
        Integer, default=36, server_default="36", nullable=False
    )
    grading_weights: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    status: Mapped[CurriculumPlanStatus] = mapped_column(
        Enum(
            CurriculumPlanStatus,
            native_enum=False,
            length=32,
            values_callable=enum_values,
        ),
        default=CurriculumPlanStatus.READY,
        server_default=CurriculumPlanStatus.READY.value,
        nullable=False,
    )

    lessons: Mapped[list["CurriculumLesson"]] = relationship(
        back_populates="plan",
        foreign_keys="CurriculumLesson.plan_id",
        cascade="all, delete-orphan",
        order_by="CurriculumLesson.week_number, CurriculumLesson.day_number, CurriculumLesson.id",
    )


class CurriculumLesson(TimestampMixin, TenantBase):
    """One block in a pacing guide: unit, week, day, title, and optional time slot."""

    __tablename__ = "curriculum_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_slot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resources: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped["CurriculumPlan"] = relationship(
        back_populates="lessons",
        foreign_keys=[plan_id],
    )
