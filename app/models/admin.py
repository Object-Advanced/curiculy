"""Admin-database models: login accounts and invite keys.

These live on ``admin.db``, not on a tenant file. ``AdminBase`` is declared
next to the catalog and tenant bases in ``app.db``.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db import AdminBase
from app.enums import UserRole
from app.models.mixins import TimestampMixin


class User(TimestampMixin, AdminBase):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_uuid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(16),
        default=UserRole.PARENT.value,
        server_default=UserRole.PARENT.value,
        nullable=False,
    )
    student_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    pin_failed_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    pin_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InviteKey(TimestampMixin, AdminBase):
    __tablename__ = "invite_keys"
    __table_args__ = (UniqueConstraint("key", name="uq_invite_keys_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_uuid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
