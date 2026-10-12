"""Read-only ping for the database.

``GET /api/health`` proves the API process can reach Postgres. It reads no
family's data: the session has no family set, so row-level security would
show it none anyway.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def ping_database(session: Session) -> None:
    """Minimal read. Writes nothing."""
    session.execute(text("SELECT 1"))
