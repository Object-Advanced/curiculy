"""Child PIN accounts, JWT roles, and household user switching."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from re import fullmatch

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, create_access_token, hash_password, verify_password
from app.enums import UserRole
from app.models.admin import User
from app.models.mixins import utcnow
from app.schemas.auth import Token

PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 8
PIN_MAX_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15

CHILD_EMAIL_DOMAIN = "kid.local"


def child_account_email(tenant_uuid: str, student_id: int) -> str:
    return f"child.{tenant_uuid}.{student_id}@{CHILD_EMAIL_DOMAIN}"


def is_child(user: CurrentUser) -> bool:
    return user.role == UserRole.CHILD.value


def is_parent(user: CurrentUser) -> bool:
    return user.role == UserRole.PARENT.value


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_pin(pin: str) -> str:
    cleaned = (pin or "").strip()
    if not fullmatch(rf"\d{{{PIN_MIN_LENGTH},{PIN_MAX_LENGTH}}}", cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PIN must be {PIN_MIN_LENGTH} to {PIN_MAX_LENGTH} digits",
        )
    return cleaned


def parent_users_for_tenant(admin_db: Session, tenant_uuid: str) -> list[User]:
    return (
        admin_db.query(User)
        .filter(User.tenant_uuid == tenant_uuid, User.role == UserRole.PARENT.value)
        .order_by(User.id)
        .all()
    )


def parent_user_for_tenant(admin_db: Session, tenant_uuid: str) -> User | None:
    parents = parent_users_for_tenant(admin_db, tenant_uuid)
    return parents[0] if parents else None


def child_user_for_student(admin_db: Session, tenant_uuid: str, student_id: int) -> User | None:
    return (
        admin_db.query(User)
        .filter(
            User.tenant_uuid == tenant_uuid,
            User.role == UserRole.CHILD.value,
            User.student_id == student_id,
        )
        .one_or_none()
    )


def child_users_for_tenant(admin_db: Session, tenant_uuid: str) -> list[User]:
    return (
        admin_db.query(User)
        .filter(User.tenant_uuid == tenant_uuid, User.role == UserRole.CHILD.value)
        .order_by(User.student_id)
        .all()
    )


def child_login_student_ids(admin_db: Session, tenant_uuid: str) -> set[int]:
    return {
        user.student_id
        for user in child_users_for_tenant(admin_db, tenant_uuid)
        if user.student_id is not None
    }


def token_for_account(user: User, *, extra: dict | None = None) -> str:
    claims: dict = {"role": user.role or UserRole.PARENT.value}
    if user.role == UserRole.CHILD.value and user.student_id is not None:
        claims["student_id"] = user.student_id
    if extra:
        claims.update(extra)
    return create_access_token(
        subject=user.email,
        tenant_uuid=user.tenant_uuid,
        is_admin=bool(user.is_admin) and user.role != UserRole.CHILD.value,
        extra=claims,
    )


def token_payload(user: User) -> Token:
    return Token(access_token=token_for_account(user))


def demo_token(
    *,
    role: str = UserRole.PARENT.value,
    student_id: int | None = None,
    jti: str | None = None,
) -> Token:
    from app.config import settings
    from app.core.security import DEMO_TENANT_UUID

    extra: dict = {"demo": True, "role": role}
    if student_id is not None:
        extra["student_id"] = student_id
    if jti:
        extra["jti"] = jti
    return Token(
        access_token=create_access_token(
            subject="demo",
            tenant_uuid=DEMO_TENANT_UUID,
            expires_delta=timedelta(minutes=settings.demo_token_expire_minutes),
            extra=extra,
        )
    )


def pin_is_locked(user: User) -> bool:
    if user.pin_locked_until is None:
        return False
    return _as_utc(user.pin_locked_until) > utcnow()


def register_pin_failure(admin_db: Session, user: User) -> None:
    user.pin_failed_attempts = int(user.pin_failed_attempts or 0) + 1
    if user.pin_failed_attempts >= PIN_MAX_ATTEMPTS:
        user.pin_locked_until = utcnow() + timedelta(minutes=PIN_LOCK_MINUTES)
        user.pin_failed_attempts = 0
    admin_db.add(user)
    admin_db.commit()


def register_pin_success(admin_db: Session, user: User) -> None:
    user.pin_failed_attempts = 0
    user.pin_locked_until = None
    admin_db.add(user)
    admin_db.commit()


def upsert_child_pin(
    admin_db: Session,
    *,
    tenant_uuid: str,
    student_id: int,
    pin: str,
) -> User:
    pin = validate_pin(pin)
    existing = child_user_for_student(admin_db, tenant_uuid, student_id)
    if existing is not None:
        existing.hashed_password = hash_password(pin)
        existing.pin_failed_attempts = 0
        existing.pin_locked_until = None
        admin_db.add(existing)
        admin_db.commit()
        admin_db.refresh(existing)
        return existing
    child = User(
        email=child_account_email(tenant_uuid, student_id),
        hashed_password=hash_password(pin),
        tenant_uuid=tenant_uuid,
        is_admin=False,
        role=UserRole.CHILD.value,
        student_id=student_id,
        pin_failed_attempts=0,
    )
    admin_db.add(child)
    admin_db.commit()
    admin_db.refresh(child)
    return child


def delete_child_pin(admin_db: Session, tenant_uuid: str, student_id: int) -> bool:
    existing = child_user_for_student(admin_db, tenant_uuid, student_id)
    if existing is None:
        return False
    admin_db.delete(existing)
    admin_db.commit()
    return True


def delete_child_account(admin_db: Session, tenant_uuid: str, student_id: int) -> None:
    delete_child_pin(admin_db, tenant_uuid, student_id)


def authenticate_child_pin(admin_db: Session, child: User, pin: str) -> None:
    if pin_is_locked(child):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Too many attempts. Try again later.",
        )
    if not verify_password(pin, child.hashed_password):
        register_pin_failure(admin_db, child)
        if pin_is_locked(child):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Too many attempts. Try again later.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect name or PIN",
        )
    register_pin_success(admin_db, child)


def verify_parent_password(admin_db: Session, tenant_uuid: str, password: str) -> User:
    parent = parent_user_for_tenant(admin_db, tenant_uuid)
    if parent is None or not verify_password(password, parent.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect parent password",
        )
    return parent
