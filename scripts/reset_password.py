"""Reset a parent's password from the command line.

    docker compose exec api python scripts/reset_password.py parent@example.com

Prints a new temporary password to give the parent; they sign in with it.
(Self-serve reset by email comes with public signup. Until then a parent who
forgets their password needs whoever runs the server.) Kids sign in with
PINs, which a parent changes in Settings → Students.

    --password-stdin   read the new password from standard input instead

Sessions already signed in stay signed in until their token expires (24
hours by default).
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.security import hash_password  # noqa: E402
from app.db import open_admin_session  # noqa: E402
from app.enums import UserRole  # noqa: E402
from app.models.admin import User  # noqa: E402

# Same bounds as registration (bcrypt reads at most 72 bytes).
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72


def reset_password(email: str, new_password: str | None = None) -> str:
    """Set a parent's password and return it (generated when not given)."""
    password = new_password if new_password is not None else secrets.token_urlsafe(9)
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Passwords must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters"
        )
    session = open_admin_session()
    try:
        user = session.query(User).filter(User.email == email.strip().lower()).one_or_none()
        if user is None or user.role != UserRole.PARENT.value:
            raise ValueError(f"No parent account for {email}")
        user.hashed_password = hash_password(password)
        session.commit()
        return password
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args(argv)
    chosen = sys.stdin.readline().rstrip("\n") if args.password_stdin else None
    try:
        password = reset_password(args.email, chosen)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if chosen is None:
        print(f"Temporary password for {args.email.strip().lower()}: {password}")
    else:
        print(f"Password updated for {args.email.strip().lower()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
