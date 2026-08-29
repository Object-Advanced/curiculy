"""Portfolio report aggregation: completed work for one student and school year.

Assignments are not keyed to a school year, so the year bound is the inclusive
``scheduled_date`` window. Status is the completion signal; ``completion_date``
is often null because the dashboard only patches status.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_catalog_db, get_tenant_db
from app.enums import PortfolioReportType
from app.schemas import (
    PortfolioEmailRead,
    PortfolioEmailRequest,
    PortfolioGenerateRequest,
    PortfolioPreviewRead,
    PortfolioReportRead,
)
from app.services.portfolio import (
    PortfolioLookupError,
    build_portfolio_message,
    build_portfolio_report,
    load_portfolio_report,
    pdf_filename,
    render_portfolio_fragment,
    render_portfolio_pdf,
    send_portfolio_email,
)

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(require_parent)],
)


def _report_or_404(
    tenant_db: Session,
    catalog_db: Session,
    filters: PortfolioGenerateRequest,
) -> PortfolioReportRead:
    try:
        return build_portfolio_report(tenant_db, catalog_db, filters)
    except PortfolioLookupError as error:
        raise HTTPException(status_code=404, detail=error.detail) from error


@router.get("/report", response_model=PortfolioReportRead)
def get_portfolio_report(
    student_id: int,
    school_year_id: int,
    report_type: PortfolioReportType,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> PortfolioReportRead:
    if report_type is PortfolioReportType.CUSTOM:
        raise HTTPException(
            status_code=400,
            detail="POST /api/portfolios/generate for custom reports",
        )
    try:
        return load_portfolio_report(
            tenant_db, catalog_db, student_id, school_year_id, report_type
        )
    except PortfolioLookupError as error:
        raise HTTPException(status_code=404, detail=error.detail) from error


@router.post("/generate", response_model=PortfolioReportRead)
def generate_portfolio_report(
    payload: PortfolioGenerateRequest,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> PortfolioReportRead:
    return _report_or_404(tenant_db, catalog_db, payload)


@router.post("/preview", response_model=PortfolioPreviewRead)
def preview_portfolio_report(
    payload: PortfolioGenerateRequest,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> PortfolioPreviewRead:
    report = _report_or_404(tenant_db, catalog_db, payload)
    return PortfolioPreviewRead(html=render_portfolio_fragment(report, for_pdf=False))


@router.post("/email", response_model=PortfolioEmailRead)
def email_portfolio(
    payload: PortfolioEmailRequest,
    background_tasks: BackgroundTasks,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> PortfolioEmailRead:
    report = _report_or_404(tenant_db, catalog_db, payload)
    pdf_bytes = render_portfolio_pdf(report)
    message = build_portfolio_message(
        evaluator_email=str(payload.evaluator_email),
        subject=payload.subject,
        body=payload.message,
        pdf_bytes=pdf_bytes,
        filename=pdf_filename(report),
    )
    background_tasks.add_task(send_portfolio_email, message)
    return PortfolioEmailRead(status="success")
