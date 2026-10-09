"""Family codes: how a child's device finds the household at sign-in.

A code is 8 characters from an alphabet without look-alikes (no 0/O, 1/I/L),
shown as ``ABCD-2345`` and stored without the dash. That is about 40 bits, and
the lookup endpoint is rate limited, so guessing one is impractical. The kid
sign-in screen remembers the code on the device, so after the first time a
child only taps their name and enters a PIN.
"""

from __future__ import annotations

import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.admin import FamilyCode

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
_ATTEMPTS = 8


def normalize_code(text: str | None) -> str | None:
    """``abcd-2345`` → ``ABCD2345``; None when it cannot be a family code."""
    if not text:
        return None
    cleaned = "".join(ch for ch in text.upper() if ch not in " -")
    if len(cleaned) != CODE_LENGTH or any(ch not in ALPHABET for ch in cleaned):
        return None
    return cleaned


def display_code(code: str) -> str:
    half = CODE_LENGTH // 2
    return f"{code[:half]}-{code[half:]}"


def _new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def _find(admin_db: Session, tenant_uuid: str) -> FamilyCode | None:
    return admin_db.query(FamilyCode).filter(FamilyCode.tenant_uuid == tenant_uuid).one_or_none()


def family_code_for(admin_db: Session, tenant_uuid: str) -> FamilyCode:
    """The household's code, made on first use."""
    row = _find(admin_db, tenant_uuid)
    if row is not None:
        return row
    for _ in range(_ATTEMPTS):
        row = FamilyCode(tenant_uuid=tenant_uuid, code=_new_code())
        admin_db.add(row)
        try:
            admin_db.commit()
        except IntegrityError:
            admin_db.rollback()
            existing = _find(admin_db, tenant_uuid)
            if existing is not None:  # another request made it first
                return existing
            continue  # the random code collided; try another
        admin_db.refresh(row)
        return row
    raise RuntimeError("Could not generate a unique family code")


def rotate_family_code(admin_db: Session, tenant_uuid: str) -> FamilyCode:
    """Replace the household's code; the old one stops working at once."""
    row = family_code_for(admin_db, tenant_uuid)
    for _ in range(_ATTEMPTS):
        row.code = _new_code()
        try:
            admin_db.commit()
        except IntegrityError:
            admin_db.rollback()
            continue
        admin_db.refresh(row)
        return row
    raise RuntimeError("Could not generate a unique family code")


def tenant_for_code(admin_db: Session, text: str | None) -> str | None:
    code = normalize_code(text)
    if code is None:
        return None
    row = admin_db.query(FamilyCode).filter(FamilyCode.code == code).one_or_none()
    return row.tenant_uuid if row is not None else None


def sign_in_names(names: dict[int, str]) -> dict[int, str]:
    """First names for the sign-in buttons, with a last initial only when two match.

    The sign-in screen is reachable without logging in, so it shows no more
    of a child's name than a sibling needs to find their own button.
    """
    def first(name: str) -> str:
        return name.split()[0] if name.split() else name

    counts: dict[str, int] = {}
    for name in names.values():
        counts[first(name).lower()] = counts.get(first(name).lower(), 0) + 1
    shown: dict[int, str] = {}
    for student_id, name in names.items():
        parts = name.split()
        label = first(name)
        if counts[label.lower()] > 1 and len(parts) > 1:
            label = f"{label} {parts[-1][0]}."
        shown[student_id] = label
    return shown
