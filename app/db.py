import tempfile
import time
from collections import OrderedDict
from collections.abc import Generator
from hashlib import sha256
from pathlib import Path
from re import compile as regexp
from threading import Lock

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_SAFE_TENANT = regexp(r"^[A-Za-z0-9_-]{1,64}$")
_lock = Lock()
_file_makers: dict[str, sessionmaker] = {}

# Demo households are throwaway SQLite files, not one shared in-memory
# connection: the SPA sends requests in parallel, and a single connection used
# from several threads corrupts reads. Only the most recently used demos are
# kept; older files are deleted.
DEMO_HOUSEHOLD_LIMIT = 64
_demo_households: OrderedDict[str, tuple[sessionmaker, Engine, Path]] = OrderedDict()


def _connect_args(url: str) -> dict[str, bool]:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_path(url: str) -> None:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return
    database = parsed.database
    if not database or database == ":memory:":
        return
    Path(database).parent.mkdir(parents=True, exist_ok=True)


def _engine(url: str) -> Engine:
    return create_engine(url, connect_args=_connect_args(url))


def _sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


catalog_engine = _engine(settings.catalog_database_url)
tenant_engine = _engine(settings.tenant_database_url)

CatalogSessionLocal = _sessionmaker(catalog_engine)
TenantSessionLocal = _sessionmaker(tenant_engine)


class CatalogBase(DeclarativeBase):
    pass


class TenantBase(DeclarativeBase):
    pass


class AdminBase(DeclarativeBase):
    pass


from app.schema_patches import (  # noqa: E402
    apply_admin_schema as _ensure_admin_schema,
    apply_catalog_schema as _ensure_catalog_schema,
    apply_tenant_schema as _ensure_tenant_schema,
)


def _admin_maker() -> sessionmaker:
    import app.models.admin  # noqa: F401

    url = settings.admin_database_url
    with _lock:
        maker = _file_makers.get(url)
        if maker is None:
            _ensure_sqlite_path(url)
            engine = _engine(url)
            _ensure_admin_schema(engine)
            maker = _sessionmaker(engine)
            _file_makers[url] = maker
        return maker


def open_admin_session() -> Session:
    return _admin_maker()()


def get_catalog_db() -> Generator[Session, None, None]:
    db = CatalogSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_admin_db() -> Generator[Session, None, None]:
    db = open_admin_session()
    try:
        yield db
    finally:
        db.close()


def tenant_file_url(tenant_uuid: str) -> str:
    """``sqlite:////data/tenant_{uuid}.db`` derived from TENANT_DATABASE_URL."""
    if not _SAFE_TENANT.fullmatch(tenant_uuid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant",
        )
    parsed = make_url(settings.tenant_database_url)
    database = parsed.database
    if not database or database == ":memory:":
        return "sqlite:///:memory:"
    tenant_path = Path(database).with_name(f"tenant_{tenant_uuid}.db")
    return f"sqlite:///{tenant_path}"


def _file_tenant_maker(url: str) -> sessionmaker:
    import app.models  # noqa: F401

    with _lock:
        maker = _file_makers.get(url)
        if maker is None:
            _ensure_sqlite_path(url)
            engine = _engine(url)
            _ensure_tenant_schema(engine)
            maker = _sessionmaker(engine)
            _file_makers[url] = maker
        return maker


def provision_tenant(tenant_uuid: str) -> None:
    """Create ``tenant_{uuid}.db`` and initialize the household schema."""
    _file_tenant_maker(tenant_file_url(tenant_uuid))


def demo_data_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "curiculy-demo"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _delete_sqlite_file(path: Path) -> None:
    for suffix in ("", "-journal", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _demo_maker(demo_key: str) -> sessionmaker:
    """One throwaway household file per demo JWT, evicted least recently used."""
    import app.models  # noqa: F401

    with _lock:
        entry = _demo_households.get(demo_key)
        if entry is not None:
            _demo_households.move_to_end(demo_key)
            return entry[0]
        digest = sha256(demo_key.encode()).hexdigest()[:32]
        path = demo_data_dir() / f"demo_{digest}.db"
        engine = _engine(f"sqlite:///{path}")
        _ensure_tenant_schema(engine)
        maker = _sessionmaker(engine)
        _demo_households[demo_key] = (maker, engine, path)
        while len(_demo_households) > DEMO_HOUSEHOLD_LIMIT:
            _, (_, old_engine, old_path) = _demo_households.popitem(last=False)
            old_engine.dispose()
            _delete_sqlite_file(old_path)
        return maker


def purge_stale_demo_households() -> None:
    """Delete demo files older than a demo token can live (left by a restart)."""
    cutoff = time.time() - settings.demo_token_expire_minutes * 60
    for path in demo_data_dir().glob("demo_*.db"):
        if path.stat().st_mtime < cutoff:
            _delete_sqlite_file(path)


def open_tenant_session(tenant_uuid: str, demo_key: str | None = None) -> Session:
    from app.core.security import DEMO_TENANT_UUID, DEV_TENANT_UUID

    if tenant_uuid == DEMO_TENANT_UUID:
        return _demo_maker(demo_key or "demo")()
    if tenant_uuid == DEV_TENANT_UUID:
        return TenantSessionLocal()
    return _file_tenant_maker(tenant_file_url(tenant_uuid))()


def _existing_tenant_file_urls() -> list[str]:
    """Every ``tenant_{uuid}.db`` next to TENANT_DATABASE_URL, for schema patches."""
    parsed = make_url(settings.tenant_database_url)
    database = parsed.database
    if not database or database == ":memory:":
        return []
    data_dir = Path(database).parent
    if not data_dir.is_dir():
        return []
    return [f"sqlite:///{path}" for path in sorted(data_dir.glob("tenant_*.db"))]


def init_databases() -> None:
    """Apply the runtime schema to catalog, shared tenant, admin, and every tenant_*.db.

    Uses ``create_all`` plus ``app.schema_patches``. Does not replay Alembic.
    Existing planner rows are not deleted. The settings date-mirror columns
    are retired after a SchoolYear backfill (see schema_patches).
    """
    import app.models  # noqa: F401  (registers every mapper before create_all)
    import app.models.admin  # noqa: F401

    _ensure_sqlite_path(settings.catalog_database_url)
    _ensure_sqlite_path(settings.tenant_database_url)
    _ensure_sqlite_path(settings.admin_database_url)
    _ensure_catalog_schema(catalog_engine)
    _ensure_tenant_schema(tenant_engine)
    for url in _existing_tenant_file_urls():
        engine = _engine(url)
        try:
            _ensure_tenant_schema(engine)
        finally:
            engine.dispose()
    _admin_maker()
    purge_stale_demo_households()


# JWT helpers live in ``app.core.security``; imported here after ``get_admin_db``
# exists so that module can depend on this one without a circular import.
from app.core.security import oauth2_scheme  # noqa: E402


def get_tenant_db(
    token: str | None = Depends(oauth2_scheme),
    admin_db: Session = Depends(get_admin_db),
) -> Generator[Session, None, None]:
    """Session for an application user (parent, child, or demo).

    Identity comes from ``get_current_user``, which rejects capture credentials
    and uses the admin ``users`` row for tenant_uuid. Opening a tenant file is
    not capture authorization. Staging must use ``get_staging_tenant_db``.
    """
    from app.core.security import get_current_user

    user = get_current_user(token, admin_db)
    db = open_tenant_session(user.tenant_uuid, user.jti)
    try:
        yield db
    finally:
        db.close()


def get_staging_tenant_db(
    token: str | None = Depends(oauth2_scheme),
    admin_db: Session = Depends(get_admin_db),
) -> Generator[Session, None, None]:
    """Session for a parent JWT or a live capture credential.

    Only evidence staging should depend on this. Capture tokens cannot open a
    tenant file through ``get_tenant_db``.
    """
    from app.core.security import require_staging_upload

    user = require_staging_upload(token, admin_db)
    db = open_tenant_session(user.tenant_uuid, user.jti)
    try:
        yield db
    finally:
        db.close()
