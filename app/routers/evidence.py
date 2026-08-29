"""Unlinked evidence: captures from the Chrome extension before they are filed.

Staging is a holding area, not a second evidence store. ``POST /staging`` writes
the file next to assignment attachments and records the path; ``POST /link``
copies that path onto an assignment and drops the staging row.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_tenant_db
from app.evidence import store_capture
from app.models import Assignment, AssignmentEvidence, EvidenceStaging
from app.models.mixins import utcnow
from app.schemas import AssignmentEvidenceRead, EvidenceLinkRequest, EvidenceStagingRead

router = APIRouter(
    prefix="/evidence",
    tags=["evidence"],
    dependencies=[Depends(require_parent)],
)

_DEFAULT_SOURCE = "chrome_extension"


@router.post("/staging", response_model=EvidenceStagingRead, status_code=201)
def stage_evidence(
    file: UploadFile = File(...),
    source: str = Form(_DEFAULT_SOURCE),
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
) -> EvidenceStaging:
    """Store a screenshot and hold it until a parent links it to an assignment."""
    file_path = store_capture(
        file.file,
        file.filename,
        tenant_uuid=user.tenant_uuid,
        content_type=file.content_type,
    )
    row = EvidenceStaging(
        tenant_id=user.tenant_uuid,
        file_path=file_path,
        captured_at=utcnow(),
        source=(source or "").strip() or _DEFAULT_SOURCE,
    )
    tenant_db.add(row)
    tenant_db.commit()
    tenant_db.refresh(row)
    return row


@router.get("/staging", response_model=list[EvidenceStagingRead])
def list_staged_evidence(
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
) -> list[EvidenceStaging]:
    """Every capture that has not yet been linked, newest first."""
    return (
        tenant_db.query(EvidenceStaging)
        .filter(EvidenceStaging.tenant_id == user.tenant_uuid)
        .order_by(EvidenceStaging.captured_at.desc(), EvidenceStaging.id.desc())
        .all()
    )


@router.post("/link", response_model=AssignmentEvidenceRead)
def link_staged_evidence(
    payload: EvidenceLinkRequest,
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
) -> AssignmentEvidence:
    """Attach a staged file to an assignment and remove it from the holding area."""
    staging = tenant_db.get(EvidenceStaging, payload.evidence_id)
    if staging is None or staging.tenant_id != user.tenant_uuid:
        raise HTTPException(status_code=404, detail="Staging evidence not found")

    assignment = tenant_db.get(Assignment, payload.assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    evidence = AssignmentEvidence(
        file_path=staging.file_path,
        captured_at=staging.captured_at,
    )
    assignment.evidence.append(evidence)
    tenant_db.delete(staging)
    tenant_db.commit()
    tenant_db.refresh(evidence)
    return evidence
