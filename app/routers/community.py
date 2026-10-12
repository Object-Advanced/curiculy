"""The community catalog, for families: look at an entry, its cover, and the
curricula other families built around a textbook.

Adding an entry to the family's library is ``POST /api/library/from-community``.
See docs/6-planning/product-spine.md ("Community catalog").
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import require_parent
from app.db import get_catalog_db
from app.evidence import COMMUNITY_COVERS, resolve_evidence_file
from app.schemas.community import CommunityEntryRead, SuggestionsRead
from app.services.community import entry_read, get_published_entry, suggestions_for
from app.services.library import get_item

router = APIRouter(prefix="/community", tags=["community"], dependencies=[Depends(require_parent)])


@router.get("/entries/{entry_id}", response_model=CommunityEntryRead)
def read_entry(
    entry_id: int,
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> CommunityEntryRead:
    """A catalog entry's details, chapters and lesson list, to look at before adding it."""
    return entry_read(db, catalog_db, get_published_entry(catalog_db, entry_id))


@router.get("/entries/{entry_id}/cover")
def read_entry_cover(entry_id: int, catalog_db: Session = Depends(get_catalog_db)) -> FileResponse:
    entry = get_published_entry(catalog_db, entry_id)
    stored = resolve_evidence_file(entry.cover_path, tenant_uuid=COMMUNITY_COVERS) if entry.cover_path else None
    if stored is None:
        raise HTTPException(status_code=404, detail="This entry has no uploaded cover")
    return FileResponse(
        stored,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/suggestions", response_model=SuggestionsRead)
def read_suggestions(
    library_item_id: int = Query(description="A textbook in your library"),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> SuggestionsRead:
    """'Other families built a similar curriculum using these…': every curriculum
    built around this textbook, and what's most often used with it."""
    return suggestions_for(db, catalog_db, get_item(db, library_item_id))
