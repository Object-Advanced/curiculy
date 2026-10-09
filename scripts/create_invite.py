"""Create an invite key so a new parent can register.

Registration is invite-gated, so the first parent account on a fresh install
needs a key that someone made by hand. This prints one:

    docker compose exec api python scripts/create_invite.py

Options:
    --key KEY          Use this exact key instead of a random one (the e2e
                       suite uses it to seed a known key on a throwaway app).
    --expires-days N   Expire the key after N days (default: never).

Running it twice with the same --key is safe: the existing unused key is kept.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import open_admin_session  # noqa: E402
from app.models.admin import InviteKey  # noqa: E402
from app.models.mixins import utcnow  # noqa: E402

MIN_KEY_LENGTH = 8
MAX_KEY_LENGTH = 64


def create_invite(key: str | None = None, expires_days: int | None = None) -> str:
    """Store an unused invite key and return it."""
    key = key or secrets.token_hex(MIN_KEY_LENGTH // 2)
    if not MIN_KEY_LENGTH <= len(key) <= MAX_KEY_LENGTH:
        raise ValueError(f"Invite keys must be {MIN_KEY_LENGTH}-{MAX_KEY_LENGTH} characters")
    expires_at = utcnow() + timedelta(days=expires_days) if expires_days else None
    session = open_admin_session()
    try:
        existing = session.query(InviteKey).filter(InviteKey.key == key).one_or_none()
        if existing is not None:
            if existing.redeemed_at is not None:
                raise ValueError("That invite key was already redeemed")
            return key
        session.add(InviteKey(key=key, tenant_uuid="", expires_at=expires_at))
        session.commit()
        return key
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--key", help="Use this key instead of a random one")
    parser.add_argument("--expires-days", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        print(create_invite(args.key, args.expires_days))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
