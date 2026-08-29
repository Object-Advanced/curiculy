"""Password hashing and JWT helpers.

``get_current_user`` is imported by routers. It depends on ``get_admin_db``, so
the SQLAlchemy utilities in this module are defined first and the admin session
is imported only after those names exist. ``app.db`` then imports
``user_from_token`` once ``get_admin_db`` is already defined, which breaks the
circular import.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import reveal_secret, settings
from app.enums import UserRole

DEMO_TENANT_UUID = "DEMO"
DEV_TENANT_UUID = "dev"
CAPTURE_TOKEN_SCOPE = "evidence:write"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class CurrentUser:
    email: str
    tenant_uuid: str
    jti: str | None = None
    user_id: int | None = None
    is_demo: bool = False
    is_admin: bool = False
    role: str = "parent"
    student_id: int | None = None
    scope: str | None = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    *,
    subject: str,
    tenant_uuid: str,
    expires_delta: timedelta | None = None,
    is_admin: bool = False,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_uuid": tenant_uuid,
        "is_admin": bool(is_admin),
        "role": "parent",
        "jti": str(uuid4()),
        "iat": now,
        "exp": expire,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(
        payload,
        reveal_secret(settings.jwt_secret),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            reveal_secret(settings.jwt_secret),
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def user_from_token(token: str | None) -> CurrentUser:
    """Resolve a JWT (or the DEV_MODE bypass) into tenant routing claims."""
    if token:
        payload = decode_access_token(token)
        tenant_uuid = payload.get("tenant_uuid")
        subject = payload.get("sub")
        if not tenant_uuid or not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        tenant_uuid = str(tenant_uuid)
        student_id = payload.get("student_id")
        if student_id is not None:
            try:
                student_id = int(student_id)
            except (TypeError, ValueError):
                student_id = None
        role = str(payload.get("role") or "parent")
        raw_scope = payload.get("scope")
        scope = str(raw_scope) if raw_scope else None
        if role == UserRole.EVIDENCE.value or scope == CAPTURE_TOKEN_SCOPE:
            return CurrentUser(
                email=str(subject),
                tenant_uuid=tenant_uuid,
                jti=str(payload["jti"]) if payload.get("jti") else None,
                is_demo=False,
                is_admin=False,
                role=UserRole.EVIDENCE.value,
                student_id=None,
                scope=CAPTURE_TOKEN_SCOPE,
            )
        return CurrentUser(
            email=str(subject),
            tenant_uuid=tenant_uuid,
            jti=str(payload["jti"]) if payload.get("jti") else None,
            is_demo=tenant_uuid == DEMO_TENANT_UUID or bool(payload.get("demo")),
            is_admin=bool(payload.get("is_admin")),
            role=role,
            student_id=student_id,
            scope=scope,
        )
    if settings.dev_mode:
        return CurrentUser(
            email="dev@local",
            tenant_uuid=DEV_TENANT_UUID,
            is_admin=True,
            role="parent",
        )
    raise _UNAUTHENTICATED


# Imported after the JWT helpers exist so ``app.db`` can finish loading.
from app.db import get_admin_db  # noqa: E402


def is_capture_credential(user: CurrentUser) -> bool:
    return user.role == UserRole.EVIDENCE.value or user.scope == CAPTURE_TOKEN_SCOPE


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    admin_db: Session = Depends(get_admin_db),
) -> CurrentUser:
    """Authenticated user for protected routes. DEV_MODE skips the JWT."""
    from app.models.admin import User

    user = user_from_token(token)
    if is_capture_credential(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This credential can only upload evidence",
        )
    if user.is_demo or user.tenant_uuid == DEV_TENANT_UUID:
        return user
    row = admin_db.query(User).filter(User.email == user.email).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = row.role or UserRole.PARENT.value
    return CurrentUser(
        email=row.email,
        tenant_uuid=row.tenant_uuid,
        jti=user.jti,
        user_id=row.id,
        is_demo=False,
        is_admin=bool(row.is_admin) and role != UserRole.CHILD.value,
        role=role,
        student_id=row.student_id,
        scope=user.scope,
    )


def require_parent(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.PARENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent access required",
        )
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.PARENT.value or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_staging_upload(
    token: str | None = Depends(oauth2_scheme),
    admin_db: Session = Depends(get_admin_db),
) -> CurrentUser:
    """Parent session or a live capture credential. Nothing else."""
    from app.services.capture_tokens import assert_capture_token_active

    user = user_from_token(token)
    if is_capture_credential(user):
        assert_capture_token_active(admin_db, user)
        return user
    resolved = get_current_user(token, admin_db)
    if resolved.role != UserRole.PARENT.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parent access required",
        )
    return resolved
