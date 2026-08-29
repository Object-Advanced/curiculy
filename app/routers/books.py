"""Book catalog endpoints.

``POST /books/resolve`` is the scanner's entry point; the two ``GET`` routes read
back what resolution stored. Resolution always returns 200, whether the edition
was already catalogued or was just fetched, because the caller asked "what book
is this?" and the answer does not depend on who won the race to cache it.
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_catalog_db
from app.models import BookEdition
from app.schemas import BookEditionRead, BookResolveRequest
from app.services.resolver import (
    BookNotFoundError,
    BookResolver,
    InvalidISBNError,
    ProvidersUnavailableError,
    canonical_isbn13,
    load_edition,
    load_edition_by_isbn13,
)

router = APIRouter(
    prefix="/books",
    tags=["books"],
    dependencies=[Depends(require_parent)],
)


async def get_resolver(db: Session = Depends(get_catalog_db)) -> AsyncIterator[BookResolver]:
    async with BookResolver(db) as resolver:
        yield resolver


@router.post("/resolve", response_model=BookEditionRead)
async def resolve_book(
    payload: BookResolveRequest,
    resolver: BookResolver = Depends(get_resolver),
) -> BookEdition:
    try:
        return await resolver.resolve(payload.isbn)
    except InvalidISBNError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except BookNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProvidersUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/isbn/{isbn}", response_model=BookEditionRead)
def get_book_by_isbn(isbn: str, db: Session = Depends(get_catalog_db)) -> BookEdition:
    try:
        canonical = canonical_isbn13(isbn)
    except InvalidISBNError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    edition = load_edition_by_isbn13(db, canonical)
    if edition is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return edition


@router.get("/{book_id}", response_model=BookEditionRead)
def get_book(book_id: int, db: Session = Depends(get_catalog_db)) -> BookEdition:
    edition = load_edition(db, book_id)
    if edition is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return edition
