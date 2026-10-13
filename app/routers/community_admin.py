"""The community catalog's review queue, for admins (Settings → Admin).

See ``app.services.community_review`` and docs/6-planning/product-spine.md
("The admin review queue").
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_admin
from app.db import get_catalog_db
from app.evidence import resolve_evidence_file
from app.schemas.community import (
    ApproveRequest,
    AskRequest,
    CommunityEntrySummary,
    ContributionDetail,
    ContributionSummary,
    EntryAdminRead,
    MergeRequest,
    RejectRequest,
    ReviewResult,
    RollbackRequest,
)
from app.services import community_review as review

router = APIRouter(prefix="/admin/community", tags=["admin"], dependencies=[Depends(require_admin)])


def get_family_opener() -> review.FamilyOpener:
    """How a review reaches the contributing family's own data. Tests replace this."""
    return review.open_family


@router.get("/contributions", response_model=list[ContributionSummary])
def list_contributions(
    status: str | None = Query(default=None, description="open (default), all, pending, asked, approved, merged, rejected, withdrawn"),
    kind: str | None = Query(default=None, description="item or curriculum"),
    catalog_db: Session = Depends(get_catalog_db),
) -> list[ContributionSummary]:
    return review.list_contributions(catalog_db, status, kind)


@router.get("/contributions/{contribution_id}", response_model=ContributionDetail)
def read_contribution(contribution_id: int, catalog_db: Session = Depends(get_catalog_db)) -> ContributionDetail:
    return review.contribution_detail(catalog_db, review.get_contribution(catalog_db, contribution_id))


@router.get("/contributions/{contribution_id}/cover")
def read_contribution_cover(contribution_id: int, catalog_db: Session = Depends(get_catalog_db)) -> FileResponse:
    contribution = review.get_contribution(catalog_db, contribution_id)
    stored = None
    if contribution.cover_path:
        stored = resolve_evidence_file(contribution.cover_path, tenant_uuid=contribution.contributor)
    if stored is None:
        raise HTTPException(status_code=404, detail="This contribution has no cover")
    return FileResponse(
        stored,
        media_type="image/webp",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/contributions/{contribution_id}/approve", response_model=ReviewResult)
def approve(
    contribution_id: int,
    payload: ApproveRequest,
    admin: CurrentUser = Depends(require_admin),
    catalog_db: Session = Depends(get_catalog_db),
    open_family: review.FamilyOpener = Depends(get_family_opener),
) -> ReviewResult:
    """Approve, or approve with edits. Books become (or update) a catalog entry;
    curricula become a suggestion for families with the same textbook."""
    contribution = review.get_contribution(catalog_db, contribution_id)
    return review.approve(catalog_db, contribution, payload, admin=admin.email, open_family=open_family)


@router.post("/contributions/{contribution_id}/merge", response_model=ReviewResult)
def merge(
    contribution_id: int,
    payload: MergeRequest,
    admin: CurrentUser = Depends(require_admin),
    catalog_db: Session = Depends(get_catalog_db),
    open_family: review.FamilyOpener = Depends(get_family_opener),
) -> ReviewResult:
    contribution = review.get_contribution(catalog_db, contribution_id)
    return review.merge(catalog_db, contribution, payload, admin=admin.email, open_family=open_family)


@router.post("/contributions/{contribution_id}/reject", response_model=ReviewResult)
def reject(
    contribution_id: int,
    payload: RejectRequest,
    admin: CurrentUser = Depends(require_admin),
    catalog_db: Session = Depends(get_catalog_db),
    open_family: review.FamilyOpener = Depends(get_family_opener),
) -> ReviewResult:
    """Reject with a reason; the family is told, and their own copy is untouched."""
    contribution = review.get_contribution(catalog_db, contribution_id)
    return review.reject(catalog_db, contribution, payload.reason, admin=admin.email, open_family=open_family)


@router.post("/contributions/{contribution_id}/ask", response_model=ReviewResult)
def ask(
    contribution_id: int,
    payload: AskRequest,
    admin: CurrentUser = Depends(require_admin),
    catalog_db: Session = Depends(get_catalog_db),
    open_family: review.FamilyOpener = Depends(get_family_opener),
) -> ReviewResult:
    """Ask the contributor; their next change brings it back to the queue."""
    contribution = review.get_contribution(catalog_db, contribution_id)
    return review.ask(catalog_db, contribution, payload.question, admin=admin.email, open_family=open_family)


@router.get("/entries", response_model=list[CommunityEntrySummary])
def list_entries(
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, description="published or retired"),
    catalog_db: Session = Depends(get_catalog_db),
) -> list[CommunityEntrySummary]:
    return review.list_entries(catalog_db, q, status)


@router.get("/entries/{entry_id}", response_model=EntryAdminRead)
def read_entry(entry_id: int, catalog_db: Session = Depends(get_catalog_db)) -> EntryAdminRead:
    return review.entry_admin_read(catalog_db, review.get_entry(catalog_db, entry_id))


@router.post("/entries/{entry_id}/rollback", response_model=EntryAdminRead)
def rollback(
    entry_id: int,
    payload: RollbackRequest,
    admin: CurrentUser = Depends(require_admin),
    catalog_db: Session = Depends(get_catalog_db),
) -> EntryAdminRead:
    """Go back to an older version (added as a new version, so history is kept)."""
    entry = review.get_entry(catalog_db, entry_id)
    return review.rollback(catalog_db, entry, payload.version, admin=admin.email, note=payload.note)


@router.post("/entries/{entry_id}/retire", response_model=EntryAdminRead)
def retire(entry_id: int, catalog_db: Session = Depends(get_catalog_db)) -> EntryAdminRead:
    """Hide it from search. Families who added it keep their copies."""
    return review.set_status(catalog_db, review.get_entry(catalog_db, entry_id), "retired")


@router.post("/entries/{entry_id}/publish", response_model=EntryAdminRead)
def publish(entry_id: int, catalog_db: Session = Depends(get_catalog_db)) -> EntryAdminRead:
    return review.set_status(catalog_db, review.get_entry(catalog_db, entry_id), "published")
