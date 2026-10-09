"""Unlinked evidence: captures from the Chrome extension before they are filed.

Staging is a holding area, not a second evidence store. ``POST /staging`` writes
the file next to assignment attachments and records the path; ``POST /link``
copies that path onto an assignment and drops the staging row.

``POST /staging`` accepts a parent JWT or a capture credential
(``scope=evidence:write``). Listing and linking stay parent-only.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import (
    CurrentUser,
    get_current_user,
    is_capture_credential,
    require_parent,
    require_staging_upload,
)
from app.db import get_staging_tenant_db, get_tenant_db
from app.enums import UserRole
from app.evidence import (
    evidence_media_type,
    resolve_evidence_file,
    store_capture,
    stored_relative_path,
)
from app.models import Assignment, AssignmentEvidence, EvidenceStaging
from app.models.mixins import utcnow
from app.schemas import AssignmentEvidenceRead, EvidenceLinkRequest, EvidenceStagingRead

router = APIRouter(
    prefix="/evidence",
    tags=["evidence"],
)

files_router = APIRouter(
    prefix="/evidence",
    tags=["evidence"],
    dependencies=[Depends(get_current_user)],
)

_DEFAULT_SOURCE = "chrome_extension"


@router.post("/staging", response_model=EvidenceStagingRead, status_code=201)
def stage_evidence(
    file: UploadFile = File(...),
    source: str = Form(_DEFAULT_SOURCE),
    user: CurrentUser = Depends(require_staging_upload),
    tenant_db: Session = Depends(get_staging_tenant_db),
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
    user: CurrentUser = Depends(require_parent),
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
    user: CurrentUser = Depends(require_parent),
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


def _child_may_read_file(tenant_db: Session, user: CurrentUser, relative: str) -> bool:
    if user.student_id is None:
        return False
    matches = (
        relative,
        f"/{relative}",
        f"data/evidence/{relative}",
        f"/data/evidence/{relative}",
    )
    row = (
        tenant_db.query(AssignmentEvidence)
        .join(Assignment, Assignment.id == AssignmentEvidence.assignment_id)
        .filter(
            AssignmentEvidence.file_path.in_(matches),
            Assignment.student_id == user.student_id,
        )
        .first()
    )
    return row is not None


@files_router.get("/files/{file_path:path}")
def get_evidence_file(
    file_path: str,
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
) -> FileResponse:
    """Serve one stored work sample to the household that owns it."""
    relative = stored_relative_path(file_path)
    if relative is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    stored = resolve_evidence_file(relative, tenant_uuid=user.tenant_uuid)
    if stored is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if is_capture_credential(user):
        raise HTTPException(
            status_code=403,
            detail="This credential can only upload evidence",
        )
    if user.role == UserRole.CHILD.value and not _child_may_read_file(
        tenant_db, user, relative
    ):
        raise HTTPException(status_code=403, detail="Parent access required")
    return FileResponse(
        stored,
        media_type=evidence_media_type(stored),
        filename=stored.name,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )
