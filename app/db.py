from collections.abc import Generator
from pathlib import Path
from re import compile as regexp
from threading import Lock

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

_SAFE_TENANT = regexp(r"^[A-Za-z0-9_-]{1,64}$")
_lock = Lock()
_file_makers: dict[str, sessionmaker] = {}
_demo_makers: dict[str, sessionmaker] = {}


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


def _engine(url: str, *, memory: bool = False) -> Engine:
    if memory:
        return create_engine(
            url,
            connect_args=_connect_args(url),
            poolclass=StaticPool,
        )
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


def _sqlite_table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _ensure_tenant_schema(engine: Engine) -> None:
    """create_all will not add columns to an existing tenant.db from earlier phases."""
    TenantBase.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        if "students" in tables:
            columns = _sqlite_table_columns(conn, "students")
            if "color_hex" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE students ADD COLUMN color_hex VARCHAR(7) "
                        "NOT NULL DEFAULT '#356b46'"
                    )
                )
        if "assignments" in tables:
            columns = _sqlite_table_columns(conn, "assignments")
            if "shared_group_uuid" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE assignments ADD COLUMN shared_group_uuid VARCHAR(36)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_assignments_shared_group_uuid "
                        "ON assignments (shared_group_uuid)"
                    )
                )
        if "curriculum_plans" in tables:
            columns = _sqlite_table_columns(conn, "curriculum_plans")
            if "frequency_days" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE curriculum_plans ADD COLUMN frequency_days "
                        "INTEGER NOT NULL DEFAULT 5"
                    )
                )
            if "total_weeks" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE curriculum_plans ADD COLUMN total_weeks "
                        "INTEGER NOT NULL DEFAULT 36"
                    )
                )
            if "grading_weights" not in columns:
                conn.execute(
                    text("ALTER TABLE curriculum_plans ADD COLUMN grading_weights TEXT")
                )
            if "is_archived" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE curriculum_plans ADD COLUMN is_archived "
                        "BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if "status" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE curriculum_plans ADD COLUMN status "
                        "VARCHAR(32) NOT NULL DEFAULT 'ready'"
                    )
                )
        if "curriculum_lessons" in tables:
            columns = _sqlite_table_columns(conn, "curriculum_lessons")
            if "notes" not in columns:
                conn.execute(text("ALTER TABLE curriculum_lessons ADD COLUMN notes TEXT"))
            if "category" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE curriculum_lessons ADD COLUMN category VARCHAR(64)"
                    )
                )
            if "time_slot" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE curriculum_lessons ADD COLUMN time_slot VARCHAR(64)"
                    )
                )
            if "resources" not in columns:
                conn.execute(
                    text("ALTER TABLE curriculum_lessons ADD COLUMN resources TEXT")
                )
        if "household_settings" in tables:
            columns = _sqlite_table_columns(conn, "household_settings")
            if "exception_colors" not in columns:
                conn.execute(
                    text("ALTER TABLE household_settings ADD COLUMN exception_colors TEXT")
                )


def _ensure_admin_schema(engine: Engine) -> None:
    """create_all will not add columns to an existing admin.db from earlier phases."""
    AdminBase.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        if "users" not in tables:
            return
        columns = _sqlite_table_columns(conn, "users")
        if "is_admin" not in columns:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
            )
        if "role" not in columns:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'parent'")
            )
        if "student_id" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN student_id INTEGER"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_users_student_id ON users (student_id)")
            )
        if "pin_failed_attempts" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN pin_failed_attempts "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )
        if "pin_locked_until" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN pin_locked_until DATETIME"))


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


def _demo_maker(demo_key: str) -> sessionmaker:
    """One in-memory schema per demo JWT. Gone when the process restarts."""
    import app.models  # noqa: F401

    with _lock:
        maker = _demo_makers.get(demo_key)
        if maker is None:
            engine = _engine("sqlite:///:memory:", memory=True)
            TenantBase.metadata.create_all(engine)
            maker = _sessionmaker(engine)
            _demo_makers[demo_key] = maker
        return maker


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
    """Create catalog, tenant, and admin schemas if they do not already exist."""
    import app.models  # noqa: F401  (registers every mapper before create_all)
    import app.models.admin  # noqa: F401

    _ensure_sqlite_path(settings.catalog_database_url)
    _ensure_sqlite_path(settings.tenant_database_url)
    _ensure_sqlite_path(settings.admin_database_url)
    CatalogBase.metadata.create_all(catalog_engine)
    _ensure_tenant_schema(tenant_engine)
    for url in _existing_tenant_file_urls():
        engine = _engine(url)
        try:
            _ensure_tenant_schema(engine)
        finally:
            engine.dispose()
    _admin_maker()


# JWT helpers live in ``app.core.security``; imported here after ``get_admin_db``
# exists so that module can depend on this one without a circular import.
from app.core.security import oauth2_scheme, user_from_token  # noqa: E402


def get_tenant_db(
    token: str | None = Depends(oauth2_scheme),
) -> Generator[Session, None, None]:
    """Session for the tenant named in the caller's JWT (or DEV_MODE fallback)."""
    user = user_from_token(token)
    db = open_tenant_session(user.tenant_uuid, user.jti)
    try:
        yield db
    finally:
        db.close()
