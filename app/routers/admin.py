"""Invite-key management for administrators."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db import get_admin_db
from app.models.admin import InviteKey
from app.models.mixins import utcnow
from app.schemas.auth import InviteKeyRead

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

INVITE_KEY_LENGTH = 8
INVITE_KEY_ATTEMPTS = 8


def _generate_invite_key() -> str:
    return secrets.token_hex(INVITE_KEY_LENGTH // 2)


@router.post("/invite", response_model=InviteKeyRead, status_code=status.HTTP_201_CREATED)
def create_invite_key(admin_db: Session = Depends(get_admin_db)) -> InviteKey:
    for _ in range(INVITE_KEY_ATTEMPTS):
        invite = InviteKey(key=_generate_invite_key(), tenant_uuid="")
        admin_db.add(invite)
        try:
            admin_db.commit()
        except IntegrityError:
            admin_db.rollback()
            continue
        admin_db.refresh(invite)
        return invite
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not generate a unique invite key",
    )


@router.get("/invites", response_model=list[InviteKeyRead])
def list_unused_invite_keys(admin_db: Session = Depends(get_admin_db)) -> list[InviteKey]:
    now = utcnow()
    return (
        admin_db.query(InviteKey)
        .filter(
            InviteKey.redeemed_at.is_(None),
            or_(InviteKey.expires_at.is_(None), InviteKey.expires_at > now),
        )
        .order_by(InviteKey.created_at.desc(), InviteKey.id.desc())
        .all()
    )
