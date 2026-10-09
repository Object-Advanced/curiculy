"""Printable household reports: the ink-saver weekly checklist and later PDFs."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_catalog_db
from app.core.deps import get_tenant_db
from app.services.weekly_manifest import (
    WeeklyManifestLookupError,
    build_weekly_manifest,
    pdf_filename,
    render_weekly_manifest_pdf,
)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_parent)],
)


@router.get("/weekly-manifest")
def weekly_manifest(
    student_id: int = Query(..., description="Student whose weekday work to print."),
    start_date: date | None = Query(
        default=None,
        description="Any day in the week to print. Defaults to today; snapped to "
        "that week's Monday so the window is always Monday through Friday.",
    ),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Response:
    try:
        manifest = build_weekly_manifest(
            tenant_db, catalog_db, student_id, start_date
        )
    except WeeklyManifestLookupError as error:
        raise HTTPException(status_code=404, detail=error.detail) from error

    pdf_bytes = render_weekly_manifest_pdf(manifest)
    filename = pdf_filename(manifest)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
