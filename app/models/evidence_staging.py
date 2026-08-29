"""Holding area for captures that are not yet filed against an assignment.

Screenshots from the Chrome extension land here, on the tenant evidence volume,
until a parent links them to a specific assignment. Each household already has
its own SQLite file, so ``tenant_id`` is the JWT tenant UUID rather than a
foreign key: there is no tenants table on this database.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import TenantBase
from app.models.mixins import TimestampMixin, utcnow


class EvidenceStaging(TimestampMixin, TenantBase):
    """An unlinked capture waiting to be attached to an assignment."""

    __tablename__ = "evidence_staging"
    __table_args__ = (Index("ix_evidence_staging_captured_at", "captured_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        default="chrome_extension",
        server_default="chrome_extension",
        nullable=False,
    )
