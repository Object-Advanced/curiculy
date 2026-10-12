"""Postgres: one database, each family's rows walled off by row-level security.

Every family table (``TenantBase``) carries ``tenant_id``. Postgres policies
(created by the migrations) let a connection see and write only the rows whose
``tenant_id`` matches the ``app.tenant_id`` setting of its current transaction.
A ``TenantSession`` sets that at the start of every transaction with
``set_config(..., true)``, the same as ``SET LOCAL``, so it ends with the
transaction and can never leak to the next request on a pooled connection. A
session that never sets it sees no family rows at all, and cannot insert any.

Shared tables have no policy: ``CatalogBase`` (the book cache) and
``AdminBase`` (sign-ins, invite keys, family codes, capture tokens).

The app connects as a role that owns nothing and cannot bypass row-level
security (``DATABASE_URL``); ``app.db_safety`` refuses to start otherwise. The
owner role (``DATABASE_OWNER_URL``) owns the tables and runs migrations,
startup upkeep and backups. See docs/6-planning/decision-records/data-tier.md.
"""

from collections.abc import Generator
from functools import lru_cache
from hashlib import sha256
from re import compile as regexp

from fastapi import HTTPException, status
from sqlalchemy import String, create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, SessionTransaction, mapped_column

from app.config import reveal_secret, settings

_SAFE_TENANT = regexp(r"^[A-Za-z0-9_-]{1,64}$")

# The SQL function every family table's default and policy use. It returns
# NULL when no family is set, so a session without one sees nothing and its
# inserts fail the NOT NULL on tenant_id.
CURRENT_TENANT_SQL = "curiculy_current_tenant()"
TENANT_SETTING = "app.tenant_id"
DEMO_TENANT_PREFIX = "demo-"


class CatalogBase(DeclarativeBase):
    """Shared book cache (ISBN lookups), read and written by every family."""


class AdminBase(DeclarativeBase):
    """Shared sign-in tables. Never queried with a family scope."""


class TenantBase(DeclarativeBase):
    """One family's data. Every table gets ``tenant_id`` and a row-level policy."""

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        server_default=text(CURRENT_TENANT_SQL),
    )


@lru_cache(maxsize=1)
def app_engine() -> Engine:
    """The request path's engine: the role that row-level security applies to."""
    return create_engine(
        reveal_secret(settings.database_url),
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_pool_size,
    )


@lru_cache(maxsize=1)
def owner_engine() -> Engine:
    """Migrations, startup upkeep and backups only. Never used by a request."""
    return create_engine(reveal_secret(settings.database_owner_url), pool_pre_ping=True)


def dispose_engines() -> None:
    """Close pooled connections and forget the engines (tests, shutdown)."""
    for factory in (app_engine, owner_engine):
        if factory.cache_info().currsize:
            factory().dispose()
        factory.cache_clear()


class TenantSession(Session):
    """A session that can only see and change one family's rows."""

    def __init__(self, *args: object, tenant_id: str, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.tenant_id = tenant_id


def set_tenant(connection: Connection, tenant_id: str) -> None:
    """Scope the connection's current transaction to one family."""
    connection.execute(
        text("SELECT set_config(:name, :tenant, true)"),
        {"name": TENANT_SETTING, "tenant": tenant_id},
    )


@event.listens_for(TenantSession, "after_begin")
def _scope_transaction(
    session: TenantSession,
    _transaction: SessionTransaction,
    connection: Connection,
) -> None:
    set_tenant(connection, session.tenant_id)


def tenant_id_for(tenant_uuid: str, demo_key: str | None = None) -> str:
    """The ``tenant_id`` a request works in.

    A demo gets its own throwaway family per demo token (``demo-…``), so
    visitors never share data. DEV_MODE uses one fixed development family.
    """
    from app.core.security import DEMO_TENANT_UUID, DEV_TENANT_UUID

    if tenant_uuid == DEMO_TENANT_UUID:
        digest = sha256((demo_key or "demo").encode()).hexdigest()[:32]
        return f"{DEMO_TENANT_PREFIX}{digest}"
    if tenant_uuid == DEV_TENANT_UUID:
        return DEV_TENANT_UUID
    if not _SAFE_TENANT.fullmatch(tenant_uuid) or tenant_uuid.startswith(DEMO_TENANT_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant",
        )
    return tenant_uuid


def open_tenant_session(tenant_uuid: str, demo_key: str | None = None) -> TenantSession:
    """A session scoped to one family; close it when done."""
    return TenantSession(
        bind=app_engine(),
        autoflush=False,
        tenant_id=tenant_id_for(tenant_uuid, demo_key),
    )


def open_family_session(tenant_id: str) -> TenantSession:
    """A session for a family by its stored ``tenant_id`` (upkeep and backups)."""
    if not _SAFE_TENANT.fullmatch(tenant_id):
        raise ValueError("Invalid tenant id")
    return TenantSession(bind=app_engine(), autoflush=False, tenant_id=tenant_id)


def open_shared_session() -> Session:
    """A session for the shared tables (sign-ins, the book cache). Sees no family rows."""
    return Session(bind=app_engine(), autoflush=False)


def open_admin_session() -> Session:
    return open_shared_session()


def get_catalog_db() -> Generator[Session, None, None]:
    db = open_shared_session()
    try:
        yield db
    finally:
        db.close()


def get_admin_db() -> Generator[Session, None, None]:
    db = open_shared_session()
    try:
        yield db
    finally:
        db.close()


def provision_tenant(tenant_uuid: str) -> None:
    """Create a new family's household row (one per family)."""
    from app.services.households import get_default_household

    session = open_tenant_session(tenant_uuid)
    try:
        get_default_household(session)
    finally:
        session.close()
