"""Issue, look up, and revoke Chrome-extension upload credentials.

The credential is a JWT with ``scope=evidence:write``. Authority is limited to
``POST /api/evidence/staging``. Revocation lives on ``admin.db`` so a stolen
token can be cut off without rotating ``JWT_SECRET``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    CAPTURE_TOKEN_SCOPE,
    CurrentUser,
    create_access_token,
)
from app.enums import UserRole
from app.models.admin import CaptureToken
from app.models.mixins import utcnow

CAPTURE_TOKEN_SUBJECT_PREFIX = "capture."

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def capture_token_subject(tenant_uuid: str) -> str:
    return f"{CAPTURE_TOKEN_SUBJECT_PREFIX}{tenant_uuid}"


def active_capture_token(admin_db: Session, tenant_uuid: str) -> CaptureToken | None:
    now = utcnow()
    rows = (
        admin_db.query(CaptureToken)
        .filter(
            CaptureToken.tenant_uuid == tenant_uuid,
            CaptureToken.revoked_at.is_(None),
        )
        .order_by(CaptureToken.id.desc())
        .all()
    )
    for row in rows:
        if _as_utc(row.expires_at) > now:
            return row
    return None


def revoke_active_capture_tokens(admin_db: Session, tenant_uuid: str) -> int:
    now = utcnow()
    rows = (
        admin_db.query(CaptureToken)
        .filter(
            CaptureToken.tenant_uuid == tenant_uuid,
            CaptureToken.revoked_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.revoked_at = now
    if rows:
        admin_db.commit()
    return len(rows)


def assert_capture_token_active(admin_db: Session, user: CurrentUser) -> CaptureToken:
    if not user.jti:
        raise _UNAUTHENTICATED
    row = (
        admin_db.query(CaptureToken)
        .filter(CaptureToken.jti == user.jti)
        .one_or_none()
    )
    if row is None or row.revoked_at is not None:
        raise _UNAUTHENTICATED
    if row.tenant_uuid != user.tenant_uuid:
        raise _UNAUTHENTICATED
    if _as_utc(row.expires_at) <= utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return row


def issue_capture_token(
    admin_db: Session,
    *,
    tenant_uuid: str,
    created_by_user_id: int | None,
) -> tuple[str, CaptureToken]:
    revoke_active_capture_tokens(admin_db, tenant_uuid)
    jti = str(uuid4())
    lifetime = timedelta(days=settings.capture_token_expire_days)
    expires_at = utcnow() + lifetime
    row = CaptureToken(
        tenant_uuid=tenant_uuid,
        jti=jti,
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
    )
    admin_db.add(row)
    admin_db.commit()
    admin_db.refresh(row)
    token = create_access_token(
        subject=capture_token_subject(tenant_uuid),
        tenant_uuid=tenant_uuid,
        is_admin=False,
        expires_delta=lifetime,
        extra={
            "role": UserRole.EVIDENCE.value,
            "scope": CAPTURE_TOKEN_SCOPE,
            "jti": jti,
        },
    )
    return token, row
