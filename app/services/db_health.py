"""Read-only pings for shared infrastructure databases.

``GET /api/health`` proves the API process can reach ``catalog.db`` and
``admin.db``. It does not open household ``tenant_{uuid}.db`` files and it
does not open the shared ``tenant.db`` used in DEV_MODE.

One family's disk must not fail the process probe or the SPA health pill.
Opening household files on this unauthenticated GET would also contend with
live writers, scale with household count, and (if wired as a container probe)
restart every family because of one file.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def ping_database(session: Session) -> None:
    """Minimal read. Does not create files, patch schema, or write rows."""
    session.execute(text("SELECT 1"))


def ping_shared_databases(catalog_db: Session, admin_db: Session) -> None:
    """Ping catalog.db and admin.db only."""
    ping_database(catalog_db)
    ping_database(admin_db)
