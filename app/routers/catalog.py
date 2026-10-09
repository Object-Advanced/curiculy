"""Curriculum catalog ISBN lookup.

``POST /catalog/lookup-isbn`` fills the Add curriculum form from a barcode.
``POST /catalog/from-isbn`` is a one-shot API that stores library + edition +
book together. The SPA does not call it; tests do. Keep it until callers move.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_catalog_db
from app.core.deps import get_tenant_db
from app.schemas.catalog import (
    BookEditionRead,
    CurriculumFromISBNRead,
    CurriculumFromISBNRequest,
    ISBNLookupRead,
    ISBNLookupRequest,
)
from app.services.catalog import create_curriculum_from_edition, lookup_from_edition
from app.services.resolver import (
    BookNotFoundError,
    BookResolver,
    InvalidISBNError,
    ProvidersUnavailableError,
)

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
    dependencies=[Depends(require_parent)],
)


async def get_resolver(db: Session = Depends(get_catalog_db)) -> AsyncIterator[BookResolver]:
    async with BookResolver(db) as resolver:
        yield resolver


def _http_for_resolution(error: Exception) -> HTTPException:
    if isinstance(error, InvalidISBNError):
        return HTTPException(status_code=400, detail=str(error))
    if isinstance(error, BookNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ProvidersUnavailableError):
        return HTTPException(status_code=503, detail=str(error))
    raise error


@router.post("/lookup-isbn", response_model=ISBNLookupRead)
async def lookup_isbn(
    payload: ISBNLookupRequest,
    resolver: BookResolver = Depends(get_resolver),
) -> ISBNLookupRead:
    try:
        edition = await resolver.resolve(payload.isbn)
    except (InvalidISBNError, BookNotFoundError, ProvidersUnavailableError) as error:
        raise _http_for_resolution(error) from error
    return lookup_from_edition(edition)


@router.post("/from-isbn", response_model=CurriculumFromISBNRead, status_code=201)
async def create_curriculum_from_isbn(
    payload: CurriculumFromISBNRequest,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
    resolver: BookResolver = Depends(get_resolver),
) -> CurriculumFromISBNRead:
    try:
        edition = await resolver.resolve(payload.isbn, commit=False)
        curriculum, curriculum_edition = create_curriculum_from_edition(
            tenant_db, edition, payload
        )
        result = CurriculumFromISBNRead(
            id=curriculum.id,
            title=curriculum.title,
            publisher_id=curriculum.publisher_id,
            publisher_name=curriculum.publisher_name,
            subject=curriculum.subject,
            description=curriculum.description,
            source_type=curriculum.source_type,
            curriculum_edition_id=curriculum_edition.id,
            edition_label=curriculum_edition.edition_label,
            book_edition=BookEditionRead.model_validate(edition),
        )
        catalog_db.commit()
        tenant_db.commit()
    except (InvalidISBNError, BookNotFoundError, ProvidersUnavailableError) as error:
        catalog_db.rollback()
        tenant_db.rollback()
        raise _http_for_resolution(error) from error
    except Exception:
        catalog_db.rollback()
        tenant_db.rollback()
        raise

    return result
