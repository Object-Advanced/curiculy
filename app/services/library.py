"""The family's Library: read, change and search books and programs.

Every read carries ``readiness`` (``app.services.library_rules``): what's
missing before the item can be scheduled, and why. Search looks in the
family's own Library, the shared book cache, then Open Library and Google
Books, and guesses each result's kind for the "What is this?" step.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    BookEdition,
    LibraryChapter,
    LibraryItem,
    LibraryLesson,
    LibraryLessonPages,
    LibraryMaterial,
    Work,
)
from app.reference.subjects import subject_name
from app.schemas.library import (
    ChapterWrite,
    CoverRead,
    LessonWrite,
    LibraryItemRead,
    LibraryItemSummary,
    MaterialWrite,
    MissingRead,
    ProblemRead,
    ReadinessRead,
    SearchResult,
    SearchResults,
)
from app.services.library_rules import (
    CURRICULUM,
    KINDS,
    READING_BOOK,
    WORKBOOK,
    Readiness,
    readiness,
)
from app.services.providers.base import BibliographicProvider, ProviderError
from app.services.resolver import (
    BookNotFoundError,
    BookResolver,
    InvalidISBNError,
    ProvidersUnavailableError,
)
from app.utils.isbn import is_valid_isbn, normalize_isbn

COVER_PENDING = "pending"


def _options():
    return (
        selectinload(LibraryItem.chapters),
        selectinload(LibraryItem.materials),
        selectinload(LibraryItem.lessons).selectinload(LibraryLesson.pages),
    )


def get_item(db: Session, item_id: int) -> LibraryItem:
    item = db.scalars(select(LibraryItem).where(LibraryItem.id == item_id).options(*_options())).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Not found in your library")
    return item


def list_items(db: Session, kind: str | None = None) -> list[LibraryItem]:
    query = select(LibraryItem).options(*_options()).order_by(func.lower(LibraryItem.title), LibraryItem.id)
    if kind:
        query = query.where(LibraryItem.kind == kind)
    return list(db.scalars(query).all())


def cover_of(item: LibraryItem) -> CoverRead:
    if item.cover_path:
        return CoverRead(url=f"/api/library/{item.id}/cover", source="upload", review=item.cover_review)
    if item.cover_url:
        return CoverRead(url=item.cover_url, source="lookup")
    return CoverRead(url=None, source=None)


def _readiness_read(result: Readiness) -> ReadinessRead:
    return ReadinessRead(
        ready=result.ready,
        missing=[MissingRead(field=m.field, label=m.label, reason=m.reason) for m in result.missing],
        problems=[ProblemRead(level=p.level, where=p.where, message=p.message) for p in result.problems],
        lessons_total=result.lessons_total,
        lessons_with_pages=result.lessons_with_pages,
        lessons_with_names=result.lessons_with_names,
    )


def _summary_fields(item: LibraryItem, result: Readiness) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "kind_label": KINDS[item.kind],
        "title": item.title,
        "author": item.author,
        "subject_code": item.subject_code,
        "subject_name": subject_name(item.subject_code),
        "grade": item.grade,
        "cover": cover_of(item),
        "ready": result.ready,
        "missing_count": len(result.missing),
        "problems_count": len(result.problems),
    }


def item_summary(item: LibraryItem) -> LibraryItemSummary:
    return LibraryItemSummary(**_summary_fields(item, readiness(item)))


def item_read(item: LibraryItem) -> LibraryItemRead:
    result = readiness(item)
    fields = (
        "publisher series edition isbn reading_kind total_pages answer_key_start_page lesson_count "
        "measure minutes_per_session days_per_week usual_pages_per_day consumable website_url "
        "login_note notes"
    ).split()
    return LibraryItemRead(
        **_summary_fields(item, result),
        **{name: getattr(item, name) for name in fields},
        chapters=item.chapters,
        materials=item.materials,
        lessons=item.lessons,
        readiness=_readiness_read(result),
    )


def _require_kind(item: LibraryItem, kinds: set[str], what: str) -> None:
    if item.kind not in kinds:
        allowed = " and ".join(sorted(KINDS[kind].lower() + "s" for kind in kinds))
        raise HTTPException(status_code=409, detail=f"Only {allowed} have {what}.")


def replace_chapters(db: Session, item: LibraryItem, chapters: list[ChapterWrite]) -> None:
    _require_kind(item, {READING_BOOK, WORKBOOK}, "chapters")
    item.chapters.clear()
    db.flush()
    for position, chapter in enumerate(chapters):
        item.chapters.append(
            LibraryChapter(
                position=position,
                name=" ".join(chapter.name.split()),
                start_page=chapter.start_page,
                subject_code=chapter.subject_code,
            )
        )
    db.commit()


def replace_materials(db: Session, item: LibraryItem, materials: list[MaterialWrite]) -> None:
    _require_kind(item, {CURRICULUM}, "materials")
    existing = {material.id: material for material in item.materials}
    unknown = [m.id for m in materials if m.id is not None and m.id not in existing]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Material {unknown[0]} isn't part of this curriculum.")
    keep = {m.id for m in materials if m.id is not None}
    for material_id, material in existing.items():
        if material_id not in keep:
            item.materials.remove(material)
    for position, payload in enumerate(materials):
        row = existing.get(payload.id) if payload.id is not None else None
        if row is None:
            row = LibraryMaterial()
            item.materials.append(row)
        row.position = position
        row.kind = payload.kind
        row.title = " ".join(payload.title.split())
        row.isbn = payload.isbn
        row.pages = payload.pages
        row.audience = payload.audience
    db.commit()


def replace_lessons(db: Session, item: LibraryItem, lessons: list[LessonWrite]) -> None:
    _require_kind(item, {CURRICULUM}, "a lesson list")
    material_ids = {material.id for material in item.materials}
    for lesson in lessons:
        for pages in lesson.pages:
            if pages.material_id not in material_ids:
                raise HTTPException(
                    status_code=422, detail=f"Material {pages.material_id} isn't part of this curriculum."
                )
    item.lessons.clear()
    db.flush()
    for position, payload in enumerate(lessons):
        item.lessons.append(
            LibraryLesson(
                position=position,
                number=payload.number,
                name=payload.name,
                type=payload.type,
                unit=payload.unit,
                minutes=payload.minutes,
                pages=[
                    LibraryLessonPages(material_id=p.material_id, start_page=p.start_page, end_page=p.end_page)
                    for p in payload.pages
                ],
            )
        )
    db.commit()


def generate_lessons(db: Session, item: LibraryItem, count: int, first_number: int | None, lesson_type: str) -> None:
    """Append numbered lessons to fill in later ("make lessons 1-170")."""
    _require_kind(item, {CURRICULUM}, "a lesson list")
    numbers = [lesson.number for lesson in item.lessons if lesson.number is not None]
    start = first_number or (max(numbers) + 1 if numbers else 1)
    position = len(item.lessons)
    for offset in range(count):
        item.lessons.append(LibraryLesson(position=position + offset, number=start + offset, type=lesson_type))
    db.commit()


# --- What is this? -----------------------------------------------------------

_CURRICULUM_PUBLISHERS = (
    "bju", "bob jones", "abeka", "a beka", "saxon", "apologia", "sonlight", "christian light",
    "good and the beautiful", "math-u-see", "singapore", "horizons", "alpha omega", "rod and staff",
    "memoria press", "notgrass", "master books", "masterbooks", "teaching textbooks",
    "all about learning", "institute for excellence in writing", "veritas press", "rightstart",
    "beast academy", "art of problem solving", "hake", "positive action",
)
_WORKBOOK_PUBLISHERS = ("spectrum", "evan-moor", "evan moor", "carson dellosa", "brain quest", "kumon", "school zone")
_CURRICULUM_WORDS = (
    "teacher's", "teachers edition", "teacher edition", "student text", "worktext", "answer key",
    "test pack", "tests and answer", "homeschool kit", "home school kit", "curriculum", "lesson plans",
)
_WORKBOOK_WORDS = ("workbook", "worksheets", "practice book", "activity book", "skill builder")


def guess_kind(title: str, subtitle: str | None = None, publisher: str | None = None) -> str:
    """A first guess for "What is this?"; the parent always confirms it."""
    text = f"{title} {subtitle or ''}".lower()
    owner = (publisher or "").lower()
    if any(word in text for word in _CURRICULUM_WORDS) or any(name in owner for name in _CURRICULUM_PUBLISHERS):
        return CURRICULUM
    if any(word in text for word in _WORKBOOK_WORDS) or any(name in owner for name in _WORKBOOK_PUBLISHERS):
        return WORKBOOK
    return READING_BOOK


def _result(source: str, **fields) -> SearchResult:
    kind = guess_kind(fields["title"], fields.get("subtitle"), fields.get("publisher"))
    return SearchResult(source=source, guessed_kind=kind, guessed_kind_label=KINDS[kind], **fields)


def _from_edition(edition: BookEdition, source: str = "catalog") -> SearchResult:
    publisher = edition.publisher or edition.work.publisher
    return _result(
        source,
        title=edition.work.title,
        subtitle=edition.work.subtitle,
        authors=[link.author_name for link in edition.work.authors],
        publisher=publisher.name if publisher else None,
        year=edition.publication_year,
        isbn=edition.isbn13 or edition.barcode,
        total_pages=edition.page_count,
        cover_url=edition.cover_image_path,
    )


async def search(
    db: Session,
    catalog_db: Session,
    query: str,
    providers: list[BibliographicProvider],
    limit: int = 12,
) -> SearchResults:
    text = " ".join(query.split())
    if len(text) < 2:
        return SearchResults(query=text, results=[])
    results: list[SearchResult] = []
    notice = None
    isbn = normalize_isbn(text) if is_valid_isbn(text) else None

    own = db.scalars(
        select(LibraryItem)
        .where(or_(LibraryItem.title.ilike(f"%{text}%"), LibraryItem.isbn == (isbn or text)))
        .order_by(LibraryItem.title)
        .limit(5)
    ).all()
    for item in own:
        results.append(
            SearchResult(
                source="library", title=item.title, authors=[item.author] if item.author else [],
                publisher=item.publisher, isbn=item.isbn, total_pages=item.total_pages,
                cover_url=cover_of(item).url, guessed_kind=item.kind, guessed_kind_label=KINDS[item.kind],
                library_item_id=item.id,
            )
        )

    if isbn:
        resolver = BookResolver(catalog_db, providers=providers)
        try:
            results.append(_from_edition(await resolver.resolve(isbn)))
        except (BookNotFoundError, InvalidISBNError):
            notice = "No book with that ISBN was found. You can add it yourself."
        except ProvidersUnavailableError:
            notice = "The book lookup services aren't answering right now. You can add it yourself, or try again later."
        return SearchResults(query=text, results=results, notice=notice)

    editions = catalog_db.scalars(
        select(BookEdition).join(Work).where(Work.title.ilike(f"%{text}%")).limit(5)
    ).all()
    results.extend(_from_edition(edition) for edition in editions)

    for provider in providers:
        try:
            found = await provider.search_by_title(text)
        except ProviderError:
            continue
        for hit in found:
            results.append(
                _result(
                    hit.source.value if hasattr(hit.source, "value") else str(hit.source),
                    title=hit.title,
                    subtitle=hit.subtitle,
                    authors=[credit.name for credit in hit.authors],
                    publisher=hit.publisher,
                    year=int(hit.publication_date[:4]) if hit.publication_date and hit.publication_date[:4].isdigit() else None,
                    isbn=hit.isbn13 or hit.isbn10,
                    total_pages=hit.page_count,
                    cover_url=hit.cover_url,
                )
            )
        if found:
            break
    else:
        if not results:
            notice = "Nothing matched. You can add it yourself."

    seen: set[tuple] = set()
    unique: list[SearchResult] = []
    for result in results:
        key = (result.isbn,) if result.isbn else (result.title.lower(), tuple(a.lower() for a in result.authors))
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return SearchResults(query=text, results=unique[:limit], notice=notice)
