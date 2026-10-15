"""Reading lists: each child's books, with when they started and finished.

Scheduled books (from the Curriculum planner or the Library's "Schedule it")
join the list by themselves and move along as their lessons are checked off.
See docs/6-planning/product-spine.md ("Reading lists").
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import require_parent
from app.schemas.reading import ReadingEntryCreate, ReadingEntryRead, ReadingEntryUpdate
from app.services import reading as service

router = APIRouter(prefix="/reading-list", tags=["reading"], dependencies=[Depends(require_parent)])


@router.get("", response_model=list[ReadingEntryRead])
def list_reading(
    student_id: int | None = Query(None),
    library_item_id: int | None = Query(None),
    school_year_id: int | None = Query(None),
    db: Session = Depends(get_tenant_db),
) -> list[ReadingEntryRead]:
    """Reading first, then up next, then finished (most recent first)."""
    entries = service.list_entries(
        db, student_id=student_id, library_item_id=library_item_id, school_year_id=school_year_id
    )
    return service.entry_reads(db, entries)


@router.post("", response_model=ReadingEntryRead, status_code=201)
def add_reading(payload: ReadingEntryCreate, db: Session = Depends(get_tenant_db)) -> ReadingEntryRead:
    """Put a book on a child's list for this school year ("just track it")."""
    return service.entry_read(db, service.add_entry(db, payload))


@router.patch("/{reading_id}", response_model=ReadingEntryRead)
def update_reading(
    reading_id: int, payload: ReadingEntryUpdate, db: Session = Depends(get_tenant_db)
) -> ReadingEntryRead:
    """Started, finished, or what it counts toward. Dates fill in with today when left out."""
    entry = service.update_entry(db, service.get_entry(db, reading_id), payload)
    return service.entry_read(db, entry)


@router.delete("/{reading_id}", status_code=204, response_class=Response)
def delete_reading(reading_id: int, db: Session = Depends(get_tenant_db)) -> Response:
    """Take a book off a child's list. Lessons on the calendar stay."""
    service.delete_entry(db, service.get_entry(db, reading_id))
    return Response(status_code=204)
