"""FastAPI dependencies that need both the signed-in user and a database.

They live here, not in ``app.db``, so imports run one way: ``app.core.security``
uses ``app.db`` and this module uses both. ``app.db`` imports neither.
"""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user, require_staging_upload
from app.db import open_tenant_session


def get_tenant_db(
    user: CurrentUser = Depends(get_current_user),
) -> Generator[Session, None, None]:
    """Session for an application user (parent, child, or demo).

    ``get_current_user`` rejects capture credentials and reads tenant_uuid
    from the admin ``users`` row; as a dependency it is resolved once per
    request and shared with the route. Opening a tenant file is not capture
    authorization. Staging must use ``get_staging_tenant_db``.
    """
    db = open_tenant_session(user.tenant_uuid, user.jti)
    try:
        yield db
    finally:
        db.close()


def get_staging_tenant_db(
    user: CurrentUser = Depends(require_staging_upload),
) -> Generator[Session, None, None]:
    """Session for a parent JWT or a live capture credential.

    Only evidence staging should depend on this. Capture tokens cannot open a
    tenant file through ``get_tenant_db``.
    """
    db = open_tenant_session(user.tenant_uuid, user.jti)
    try:
        yield db
    finally:
        db.close()
