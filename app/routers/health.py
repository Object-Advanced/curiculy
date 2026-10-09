from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_admin_db, get_catalog_db
from app.schemas import HealthResponse
from app.services.db_health import ping_shared_databases

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    catalog_db: Session = Depends(get_catalog_db),
    admin_db: Session = Depends(get_admin_db),
) -> HealthResponse:
    ping_shared_databases(catalog_db, admin_db)
    return HealthResponse(status="ok", database="ok", dev_mode=settings.dev_mode)
