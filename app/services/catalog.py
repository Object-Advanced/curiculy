from sqlalchemy import func
from sqlalchemy.orm import Session

from app.enums import CurriculumSource, ResourceKind
from app.models import (
    BookEdition,
    Curriculum,
    CurriculumEdition,
    CurriculumResource,
    Publisher,
    Work,
)
from app.schemas.catalog import CurriculumFromISBNRequest, ISBNLookupRead
from app.schemas.core import CurriculumCreate
from app.schemas.curriculum import DEFAULT_EDITION_LABEL
from app.utils.isbn import barcode_to_isbn13, to_isbn13


def get_or_create_publisher(db: Session, name: str | None) -> Publisher | None:
    """Resolve a publisher by name, matching case-insensitively before inserting."""
    cleaned = (name or "").strip()
    if not cleaned:
        return None

    publisher = (
        db.query(Publisher).filter(func.lower(Publisher.name) == cleaned.lower()).first()
    )
    if publisher is None:
        publisher = Publisher(name=cleaned)
        db.add(publisher)
        db.flush()
    return publisher


def lookup_from_edition(edition: BookEdition) -> ISBNLookupRead:
    """Project a stored edition onto the fields the curriculum form fills."""
    publisher = edition.publisher or edition.work.publisher
    identifier = edition.isbn13 or edition.barcode or ""
    return ISBNLookupRead(
        isbn13=identifier,
        isbn10=edition.isbn10,
        barcode=edition.barcode,
        title=edition.work.title,
        subtitle=edition.work.subtitle,
        publisher=publisher.name if publisher is not None else None,
        description=edition.work.description,
        page_count=edition.page_count,
        publication_year=edition.publication_year,
        authors=[link.author_name for link in edition.work.authors],
    )


def get_or_create_manual_edition(
    db: Session,
    sku: str,
    title: str,
    publisher: Publisher | None,
    description: str | None,
) -> BookEdition:
    """Store a parent-typed ISBN or proprietary SKU as a local book edition.

    Imported here lazily so this module and :mod:`app.services.resolver` do not
    import each other at load time.
    """
    from app.services.resolver import load_edition, load_edition_by_identifier

    existing = load_edition_by_identifier(db, sku)
    if existing is not None:
        return existing

    raw = sku.strip()
    canonical = to_isbn13(raw) or barcode_to_isbn13(raw)
    work = Work(
        title=title,
        publisher_id=publisher.id if publisher is not None else None,
        description=description,
    )
    db.add(work)
    db.flush()
    edition = BookEdition(
        work_id=work.id,
        publisher_id=publisher.id if publisher is not None else None,
        isbn13=canonical,
        barcode=raw[:64],
    )
    db.add(edition)
    db.flush()
    stored = load_edition(db, edition.id)
    return stored if stored is not None else edition


def create_curriculum_from_edition(
    tenant_db: Session,
    edition: BookEdition,
    payload: CurriculumFromISBNRequest,
    *,
    source_type: CurriculumSource = CurriculumSource.BARCODE,
) -> tuple[Curriculum, CurriculumEdition]:
    """Attach a resolved book to a new household curriculum edition and student-text resource.

    The caller owns the transaction: this only flushes, so a failed curriculum
    insert can roll back the book ingestion that produced ``edition``.
    """
    title = (payload.title or edition.work.title).strip()
    publisher_name = payload.publisher
    if publisher_name is None and edition.publisher is not None:
        publisher_name = edition.publisher.name
    elif publisher_name is None and edition.work.publisher is not None:
        publisher_name = edition.work.publisher.name

    description = payload.description
    if description is None:
        description = edition.work.description

    curriculum = Curriculum(
        title=title,
        subject=payload.subject,
        description=description,
        source_type=source_type,
        publisher_name=(publisher_name or "").strip() or None,
    )
    tenant_db.add(curriculum)
    tenant_db.flush()

    edition_label = edition.edition_label or DEFAULT_EDITION_LABEL
    curriculum_edition = CurriculumEdition(
        curriculum_id=curriculum.id,
        edition_label=edition_label,
        copyright_year=edition.publication_year,
        is_current=True,
    )
    tenant_db.add(curriculum_edition)
    tenant_db.flush()

    tenant_db.add(
        CurriculumResource(
            curriculum_edition_id=curriculum_edition.id,
            book_edition_id=edition.id,
            kind=ResourceKind.STUDENT_TEXT,
            title=edition.work.title,
            is_required=True,
            sort_order=0,
        )
    )
    tenant_db.flush()
    return curriculum, curriculum_edition


def create_curriculum(
    tenant_db: Session,
    catalog_db: Session,
    payload: CurriculumCreate,
) -> Curriculum:
    """Save a program to the household library, upserting ISBN metadata when new."""
    if payload.sku:
        from app.services.resolver import load_edition_by_identifier

        edition = load_edition_by_identifier(catalog_db, payload.sku)
        if edition is None:
            if not payload.title:
                raise ValueError("A title is required to save a new ISBN or barcode")
            edition = get_or_create_manual_edition(
                catalog_db,
                sku=payload.sku,
                title=payload.title,
                publisher=get_or_create_publisher(catalog_db, payload.publisher),
                description=payload.description,
            )
        curriculum, _ = create_curriculum_from_edition(
            tenant_db,
            edition,
            CurriculumFromISBNRequest(
                isbn=payload.sku,
                title=payload.title,
                publisher=payload.publisher,
                subject=payload.subject,
                description=payload.description,
            ),
            source_type=payload.source_type,
        )
        return curriculum

    curriculum = Curriculum(
        title=payload.title,
        subject=payload.subject,
        description=payload.description,
        source_type=payload.source_type,
        publisher_name=(payload.publisher or "").strip() or None,
    )
    tenant_db.add(curriculum)
    tenant_db.flush()
    return curriculum
