from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_admin_db, get_catalog_db
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    catalog_db: Session = Depends(get_catalog_db),
    admin_db: Session = Depends(get_admin_db),
) -> HealthResponse:
    catalog_db.execute(text("SELECT 1"))
    admin_db.execute(text("SELECT 1"))
    return HealthResponse(status="ok", database="ok", dev_mode=settings.dev_mode)
