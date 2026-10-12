from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_admin_db
from app.schemas import HealthResponse
from app.services.db_health import ping_database

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_admin_db)) -> HealthResponse:
    ping_database(db)
    return HealthResponse(status="ok", database="ok", dev_mode=settings.dev_mode)
