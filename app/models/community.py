"""The community catalog: book structures every family's entries build.

Shared tables (``CatalogBase``, like the book cache): deliberately outside any
one family's walled-off data, and holding nothing about a family.

- ``CatalogEntry``: a published book, textbook, workbook or online site, with
  its structure (chapters, the lesson list) in versions
  (``CatalogEntryVersion``), so any change can be rolled back.
- ``CatalogContribution``: what a family entered by hand, waiting for review,
  with the automatic checks' ``CatalogFlag`` rows. ``contributor`` names the
  family for review only; it is never shown to other families.
- ``CommunityCurriculum``: a textbook plus the workbooks, sites and books
  families teach alongside it ("Other families built a similar curriculum").

See docs/6-planning/product-spine.md ("Community catalog").
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import CatalogBase
from app.models.mixins import TimestampMixin

# Contribution statuses. "pending" and "asked" are open: a family's later
# edits refresh the open contribution instead of adding another.
PENDING, ASKED, APPROVED, MERGED, REJECTED, WITHDRAWN = (
    "pending", "asked", "approved", "merged", "rejected", "withdrawn",
)
OPEN_STATUSES = (PENDING, ASKED)


class CatalogEntry(TimestampMixin, CatalogBase):
    __tablename__ = "catalog_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # reading_book, textbook, workbook, online_program (app.services.library_rules)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # The current version's details, copied here so search needs no JSON.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    title_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    edition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    subject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapters_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lessons_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # A cover from the book lookup (a URL), or an uploaded cover an admin
    # approved (a file under the evidence volume's community folder).
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Families who entered or added it ("4 families have entered this book").
    families_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # published, or retired (hidden from search; families keep their copies)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="published", index=True)

    versions: Mapped[list[CatalogEntryVersion]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="CatalogEntryVersion.version"
    )


class CatalogEntryVersion(CatalogBase):
    __tablename__ = "catalog_entry_versions"
    __table_args__ = (UniqueConstraint("entry_id", "version", name="uq_catalog_entry_versions_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # Details, chapters and lesson list (app.services.community.snapshot_item)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    contribution_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_contributions.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    entry: Mapped[CatalogEntry] = relationship(back_populates="versions")


class CatalogContribution(TimestampMixin, CatalogBase):
    __tablename__ = "catalog_contributions"
    __table_args__ = (
        # One open contribution per family item or curriculum; edits refresh it.
        Index(
            "uq_catalog_contributions_open",
            "contributor",
            "kind",
            "source_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'asked')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # "item" (a library item) or "curriculum" (a planned curriculum)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    item_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    # The contributing family's id, for review only. Not "tenant_id": this is a
    # shared table, and that name marks family tables.
    contributor: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # The library item or planned curriculum in the contributor's data.
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # The catalog entry it started from: a family's edits to an adopted entry
    # are proposed corrections to it.
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    based_on_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # An uploaded cover in the contributor's evidence folder (every one is reviewed).
    cover_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PENDING, index=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Why it was rejected, or the question asked of the family.
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_entries.id", ondelete="SET NULL"), nullable=True
    )
    result_curriculum_id: Mapped[int | None] = mapped_column(
        ForeignKey("community_curricula.id", ondelete="SET NULL"), nullable=True
    )

    flags: Mapped[list[CatalogFlag]] = relationship(
        back_populates="contribution", cascade="all, delete-orphan", order_by="CatalogFlag.id"
    )


class CatalogFlag(CatalogBase):
    __tablename__ = "catalog_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    contribution_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_contributions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    # structure, identity, privacy, spam, copying, cover, link, behavior, agreement
    group: Mapped[str] = mapped_column(String(16), nullable=False)
    # "review" (an admin decides) or "note" (context for the admin)
    level: Mapped[str] = mapped_column(String(8), nullable=False)
    where: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    contribution: Mapped[CatalogContribution] = relationship(back_populates="flags")


class CommunityCurriculum(TimestampMixin, CatalogBase):
    __tablename__ = "community_curricula"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    days_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The textbook that sets the pace; suggestions are found through it.
    textbook_entry_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Its exact make-up ("textbook:12,workbook:40,reading:77"), so the same
    # combination from another family counts up instead of repeating.
    signature: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    families_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="published")

    items: Mapped[list[CommunityCurriculumItem]] = relationship(
        back_populates="curriculum", cascade="all, delete-orphan", order_by="CommunityCurriculumItem.position"
    )


class CommunityCurriculumItem(CatalogBase):
    __tablename__ = "community_curriculum_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("community_curricula.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # textbook, workbook, online, reading, teacher (app.schemas.planner.ROLES)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    curriculum: Mapped[CommunityCurriculum] = relationship(back_populates="items")
    entry: Mapped[CatalogEntry] = relationship()
