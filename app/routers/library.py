"""The Library: books, textbooks, workbooks and online sites.

Every change also updates the item's contribution to the community catalog
(automatic, once the item is ready to schedule; see ``app.services.community``).
See docs/6-planning/product-spine.md ("Library: one shelf, four kinds of book").
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_catalog_db
from app.evidence import resolve_evidence_file, store_cover
from app.models import LibraryItem
from app.schemas.community import AdoptEntry
from app.schemas.library import (
    ChapterWrite,
    LessonGenerate,
    LessonWrite,
    LibraryItemCreate,
    LibraryItemRead,
    LibraryItemSummary,
    LibraryItemUpdate,
    SearchResults,
)
from app.services.library import (
    COVER_PENDING,
    generate_lessons,
    get_item,
    item_read,
    item_summary,
    list_items,
    replace_chapters,
    replace_lessons,
    search,
)
from app.services import community, planner
from app.services.library_rules import KINDS
from app.services.providers.base import BibliographicProvider
from app.services.providers.google_books import GoogleBooksProvider
from app.services.providers.open_library import OpenLibraryProvider

router = APIRouter(prefix="/library", tags=["library"], dependencies=[Depends(require_parent)])


async def get_book_providers() -> AsyncIterator[list[BibliographicProvider]]:
    """Open Library first (no key needed), then Google Books. Tests replace this."""
    providers: list[BibliographicProvider] = [OpenLibraryProvider(), GoogleBooksProvider()]
    try:
        yield providers
    finally:
        for provider in providers:
            await provider.aclose()


@router.get("", response_model=list[LibraryItemSummary])
def list_library(
    kind: str | None = Query(default=None, description="reading_book, textbook, workbook or online_program"),
    db: Session = Depends(get_tenant_db),
) -> list[LibraryItemSummary]:
    if kind is not None and kind not in KINDS:
        raise HTTPException(status_code=422, detail="Filter by reading_book, textbook, workbook or online_program.")
    return [item_summary(item) for item in list_items(db, kind)]


@router.get("/search", response_model=SearchResults)
async def search_library(
    q: str = Query(min_length=1, max_length=200, description="An ISBN, title, author or series"),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
    providers: list[BibliographicProvider] = Depends(get_book_providers),
) -> SearchResults:
    """Your library, the community catalog (ready to add), the shared book cache, then Open Library
    and Google Books; each with its kind (catalog entries) or a guessed kind."""
    return await search(db, catalog_db, q, providers)


def _changed(db: Session, catalog_db: Session, item_id: int, user: CurrentUser) -> LibraryItemRead:
    """After any change: refresh the item's catalog contribution (and those of
    the curricula it's in), then read it back."""
    family = community.family_of(user)
    community.safely(catalog_db, community.item_changed, db, catalog_db, get_item(db, item_id), family)
    planner.refresh_contributions_for_item(db, catalog_db, item_id, family)
    return item_read(get_item(db, item_id))


@router.post("", response_model=LibraryItemRead, status_code=201)
def create_item(
    payload: LibraryItemCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    data = payload.model_dump(exclude_none=True)
    item = LibraryItem(**data)
    db.add(item)
    db.commit()
    return _changed(db, catalog_db, item.id, user)


@router.post("/from-community", response_model=LibraryItemRead, status_code=201)
def add_from_community(
    payload: AdoptEntry,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    """Add a community catalog entry to your library: its details, chapters and
    lesson list are copied in, ready to schedule. Returns your copy (200) if you
    already added it."""
    entry = community.get_published_entry(catalog_db, payload.entry_id)
    item, created = community.adopt_entry(db, catalog_db, entry, counted=community.family_of(user) is not None)
    if not created:
        response.status_code = 200
    return item_read(get_item(db, item.id))


@router.get("/{item_id}", response_model=LibraryItemRead)
def read_item(item_id: int, db: Session = Depends(get_tenant_db)) -> LibraryItemRead:
    return item_read(get_item(db, item_id))


@router.patch("/{item_id}", response_model=LibraryItemRead)
def update_item(
    item_id: int,
    payload: LibraryItemUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    item = get_item(db, item_id)
    for name, value in payload.model_dump(exclude_unset=True).items():
        if name in {"kind", "title", "consumable", "for_parent"} and value is None:
            continue
        setattr(item, name, value)
    db.commit()
    return _changed(db, catalog_db, item_id, user)


@router.delete("/{item_id}", status_code=204, response_class=Response)
def delete_item(
    item_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Response:
    curricula = planner.curricula_using(db, item_id)
    db.delete(get_item(db, item_id))
    db.commit()
    family = community.family_of(user)
    community.safely(catalog_db, community.item_removed, catalog_db, item_id, family)
    for curriculum_id in curricula:
        planner.refresh_contribution(db, catalog_db, curriculum_id, family)
    return Response(status_code=204)


@router.put("/{item_id}/chapters", response_model=LibraryItemRead)
def put_chapters(
    item_id: int,
    payload: list[ChapterWrite],
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    """Replace the chapters (reading books and workbooks), in order."""
    replace_chapters(db, get_item(db, item_id), payload)
    return _changed(db, catalog_db, item_id, user)


@router.put("/{item_id}/lessons", response_model=LibraryItemRead)
def put_lessons(
    item_id: int,
    payload: list[LessonWrite],
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    """Replace a textbook's whole lesson list, in order."""
    replace_lessons(db, get_item(db, item_id), payload)
    return _changed(db, catalog_db, item_id, user)


@router.post("/{item_id}/lessons/generate", response_model=LibraryItemRead)
def post_generate_lessons(
    item_id: int,
    payload: LessonGenerate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    """Add numbered lessons to fill in ("make lessons 1-170")."""
    generate_lessons(db, get_item(db, item_id), payload.count, payload.first_number, payload.type)
    return _changed(db, catalog_db, item_id, user)


@router.post("/{item_id}/cover", response_model=LibraryItemRead)
def upload_cover(
    item_id: int,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    """A real cover image (not a photo of the book). Shown to this family now; reviewed before others see it."""
    item = get_item(db, item_id)
    item.cover_path = store_cover(file.file, tenant_uuid=user.tenant_uuid)
    item.cover_review = COVER_PENDING
    db.commit()
    return _changed(db, catalog_db, item_id, user)


@router.get("/{item_id}/cover")
def read_cover(
    item_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> FileResponse:
    item = get_item(db, item_id)
    stored = resolve_evidence_file(item.cover_path, tenant_uuid=user.tenant_uuid) if item.cover_path else None
    if stored is None:
        raise HTTPException(status_code=404, detail="This item has no uploaded cover")
    return FileResponse(
        stored,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{item_id}/cover", response_model=LibraryItemRead)
def delete_cover(
    item_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> LibraryItemRead:
    item = get_item(db, item_id)
    item.cover_path = None
    item.cover_review = None
    db.commit()
    return _changed(db, catalog_db, item_id, user)
