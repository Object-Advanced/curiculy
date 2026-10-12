"""Demo households: one throwaway family per demo token, cleared when it expires.

``POST /api/auth/demo`` gives each visitor their own ``demo-…`` family, so
demos never share data. A demo token lasts ``DEMO_TOKEN_EXPIRE_MINUTES``; a
demo family with no activity for that long is deleted, at startup and every
few minutes while new demos start.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import settings
from app.db import DEMO_TENANT_PREFIX, owner_engine
from app.services.family_data import delete_family, family_tables

PURGE_EVERY = timedelta(minutes=10)
_lock = Lock()
_last_purge: datetime | None = None


def demo_last_activity(owner: Engine) -> dict[str, datetime | None]:
    """Every demo family and its latest activity (owner role: sees all families)."""
    latest: dict[str, datetime | None] = {}
    with owner.connect() as conn:
        for table in family_tables():
            stamp = "updated_at" if "updated_at" in table.c else "created_at" if "created_at" in table.c else None
            column = f"max({stamp})" if stamp else "NULL"
            rows = conn.execute(
                text(
                    f"SELECT tenant_id, {column} AS last FROM {table.name} "
                    "WHERE tenant_id LIKE :prefix GROUP BY tenant_id"
                ),
                {"prefix": f"{DEMO_TENANT_PREFIX}%"},
            ).all()
            for row in rows:
                known = latest.get(row.tenant_id)
                if row.last is not None and (known is None or row.last > known):
                    latest[row.tenant_id] = row.last
                else:
                    latest.setdefault(row.tenant_id, known)
    return latest


def purge_stale_demo_households(now: datetime | None = None, owner: Engine | None = None) -> int:
    """Delete demo families idle longer than a demo token lives; return how many."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=settings.demo_token_expire_minutes)
    purged = 0
    for tenant_id, last in demo_last_activity(owner or owner_engine()).items():
        if last is None or last < cutoff:
            delete_family(tenant_id)
            purged += 1
    return purged


def purge_stale_demo_households_now_and_then() -> None:
    """Purge at most every PURGE_EVERY; called when a new demo starts."""
    global _last_purge
    now = datetime.now(timezone.utc)
    with _lock:
        if _last_purge is not None and now - _last_purge < PURGE_EVERY:
            return
        _last_purge = now
    purge_stale_demo_households(now)
