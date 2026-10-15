"""Reading lists: each child's books, with when they started and finished.

A tracked book moves along when the parent says so. A scheduled book (its
daily reading is on the calendar) also moves along by itself as its lessons are
checked off: started when the first is done, finished when the last is. The
lessons only ever move it forward, so a parent who marks a book finished early
(the child raced ahead) keeps that. See docs/6-planning/product-spine.md.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import AssignmentStatus
from app.models import Assignment, Course, LibraryItem, ReadingListEntry, Student
from app.reference.subjects import subject_name
from app.schemas.reading import ReadingEntryCreate, ReadingEntryRead, ReadingEntryUpdate
from app.services.clock import household_today
from app.services.library import item_summary
from app.services.library_rules import READING_BOOK
from app.services.school_year import ensure_operational_school_year

DEFAULT_SUBJECT = "english"
STATUS_LABELS = {"up_next": "Up next", "reading": "Reading", "finished": "Finished"}
_ORDER = {"up_next": 0, "reading": 1, "finished": 2}
_CLOSED = {AssignmentStatus.COMPLETED, AssignmentStatus.SKIPPED, AssignmentStatus.EXCUSED}


def _options():
    return (
        selectinload(ReadingListEntry.item).selectinload(LibraryItem.chapters),
        selectinload(ReadingListEntry.item).selectinload(LibraryItem.lessons),
        selectinload(ReadingListEntry.student),
    )


def get_entry(db: Session, entry_id: int) -> ReadingListEntry:
    entry = db.scalars(select(ReadingListEntry).where(ReadingListEntry.id == entry_id).options(*_options())).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Not on a reading list")
    return entry


def list_entries(
    db: Session,
    *,
    student_id: int | None = None,
    library_item_id: int | None = None,
    school_year_id: int | None = None,
) -> list[ReadingListEntry]:
    query = select(ReadingListEntry).options(*_options()).order_by(ReadingListEntry.id)
    if student_id is not None:
        query = query.where(ReadingListEntry.student_id == student_id)
    if library_item_id is not None:
        query = query.where(ReadingListEntry.library_item_id == library_item_id)
    if school_year_id is not None:
        query = query.where(ReadingListEntry.school_year_id == school_year_id)
    return list(db.scalars(query).all())


def _lessons(db: Session, entries: list[ReadingListEntry]) -> dict[tuple[int, int], list[Assignment]]:
    """The calendar lessons of each (child, book), from courses still on the calendar."""
    if not entries:
        return {}
    rows = db.scalars(
        select(Assignment)
        .join(Course, Course.id == Assignment.course_id)
        .where(
            Assignment.student_id.in_({entry.student_id for entry in entries}),
            Assignment.library_item_id.in_({entry.library_item_id for entry in entries}),
        )
    ).all()
    found: dict[tuple[int, int], list[Assignment]] = {}
    for row in rows:
        found.setdefault((row.student_id, row.library_item_id), []).append(row)
    return found


def _progress(entry: ReadingListEntry, lessons: list[Assignment]) -> tuple[str, date | None, date | None]:
    """The status and dates to show: the parent's, moved forward by checked-off lessons.

    Started when a lesson is done (or under way); finished when every lesson is
    done, skipped or excused.
    """
    status, started, finished = entry.status, entry.started_on, entry.finished_on
    done = sorted(lesson.completion_date or lesson.scheduled_date for lesson in lessons
                  if lesson.status == AssignmentStatus.COMPLETED)
    begun = done or sorted(lesson.scheduled_date for lesson in lessons
                           if lesson.status == AssignmentStatus.IN_PROGRESS)
    if begun:
        started = started or begun[0]
        if _ORDER[status] < _ORDER["reading"]:
            status = "reading"
    if done and all(lesson.status in _CLOSED for lesson in lessons) and _ORDER[status] < _ORDER["finished"]:
        status, finished = "finished", finished or done[-1]
    return status, started, finished


def entry_reads(db: Session, entries: list[ReadingListEntry]) -> list[ReadingEntryRead]:
    lessons = _lessons(db, entries)
    reads = []
    for entry in entries:
        rows = lessons.get((entry.student_id, entry.library_item_id), [])
        status, started, finished = _progress(entry, rows)
        counts = entry.counts_toward or entry.item.subject_code or DEFAULT_SUBJECT
        reads.append(ReadingEntryRead(
            id=entry.id,
            student_id=entry.student_id,
            student_name=entry.student.name,
            school_year_id=entry.school_year_id,
            book=item_summary(entry.item),
            status=status,
            status_label=STATUS_LABELS[status],
            started_on=started,
            finished_on=finished,
            counts_toward=counts,
            counts_toward_name=subject_name(counts) or counts,
            source=entry.source,
            scheduled=bool(rows),
            lessons_total=len(rows),
            lessons_done=sum(1 for row in rows if row.status == AssignmentStatus.COMPLETED),
            pages=entry.item.total_pages,
        ))
    # Reading first, then up next, then finished (most recent first).
    rank = {"reading": 0, "up_next": 1, "finished": 2}
    reads.sort(key=lambda read: (
        rank[read.status],
        -(read.finished_on.toordinal() if read.finished_on else 0),
        read.book.title.lower(),
    ))
    return reads


def entry_read(db: Session, entry: ReadingListEntry) -> ReadingEntryRead:
    return entry_reads(db, [entry])[0]


def _current_year_id(db: Session) -> int | None:
    year = ensure_operational_school_year(db)
    return year.id if year else None


def _settle_dates(entry: ReadingListEntry, today: date) -> None:
    """A book being read has a start date; a finished one has both."""
    if entry.status == "up_next":
        entry.started_on = entry.finished_on = None
        return
    if entry.status == "reading":
        entry.finished_on = None
    if entry.status == "finished" and entry.finished_on is None:
        entry.finished_on = today
    if entry.started_on is None:
        entry.started_on = min(today, entry.finished_on) if entry.finished_on else today
    if entry.finished_on and entry.finished_on < entry.started_on:
        raise HTTPException(status_code=422, detail="The day they finished can't be before the day they started.")


def add_entry(db: Session, payload: ReadingEntryCreate) -> ReadingListEntry:
    if db.get(Student, payload.student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")
    item = db.get(LibraryItem, payload.library_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found in your library")
    if item.kind != READING_BOOK:
        raise HTTPException(status_code=422, detail="Only books to read go on a reading list.")
    year_id = _current_year_id(db)
    exists = db.scalars(select(ReadingListEntry.id).where(
        ReadingListEntry.student_id == payload.student_id,
        ReadingListEntry.library_item_id == item.id,
        ReadingListEntry.school_year_id.is_not_distinct_from(year_id),
    )).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Already on their reading list.")
    entry = ReadingListEntry(
        student_id=payload.student_id,
        library_item_id=item.id,
        school_year_id=year_id,
        status=payload.status,
        started_on=payload.started_on,
        finished_on=payload.finished_on,
        counts_toward=payload.counts_toward,
        source="tracked",
    )
    _settle_dates(entry, household_today(db))
    db.add(entry)
    db.commit()
    return get_entry(db, entry.id)


def update_entry(db: Session, entry: ReadingListEntry, payload: ReadingEntryUpdate) -> ReadingListEntry:
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") is None:
        changes.pop("status", None)
    for field, value in changes.items():
        setattr(entry, field, value)
    _settle_dates(entry, household_today(db))
    db.commit()
    return get_entry(db, entry.id)


def delete_entry(db: Session, entry: ReadingListEntry) -> None:
    db.delete(entry)
    db.commit()


# --- Hooks from the planner -------------------------------------------------------

def on_scheduled(db: Session, student_id: int, item: LibraryItem, school_year_id: int | None,
                 counts_toward: str | None) -> None:
    """A book's reading went on the calendar: it goes on the child's list too. Doesn't commit."""
    if item.kind != READING_BOOK:
        return
    entry = db.scalars(select(ReadingListEntry).where(
        ReadingListEntry.student_id == student_id,
        ReadingListEntry.library_item_id == item.id,
        ReadingListEntry.school_year_id.is_not_distinct_from(school_year_id),
    )).first()
    if entry is None:
        db.add(ReadingListEntry(
            student_id=student_id,
            library_item_id=item.id,
            school_year_id=school_year_id,
            status="up_next",
            counts_toward=counts_toward,
            source="scheduled",
        ))
    else:
        entry.source = "scheduled"


def on_unscheduled(db: Session, course: Course, lessons: list[Assignment]) -> None:
    """A course is coming off the calendar (call before its lessons are removed).

    Its books that were never started come off the list; started ones stay, as
    tracked books, with how far they got. Doesn't commit.
    """
    by_item: dict[int, list[Assignment]] = {}
    for lesson in lessons:
        if lesson.library_item_id is not None:
            by_item.setdefault(lesson.library_item_id, []).append(lesson)
    if not by_item:
        return
    entries = db.scalars(select(ReadingListEntry).where(
        ReadingListEntry.student_id == course.student_id,
        ReadingListEntry.library_item_id.in_(by_item),
        ReadingListEntry.school_year_id.is_not_distinct_from(course.school_year_id),
        ReadingListEntry.source == "scheduled",
    )).all()
    for entry in entries:
        status, started, finished = _progress(entry, by_item[entry.library_item_id])
        if status == "up_next":
            db.delete(entry)
            continue
        entry.source = "tracked"
        entry.status, entry.started_on, entry.finished_on = status, started, finished
