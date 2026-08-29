"""Resolve an ISBN or barcode to a catalogued ``BookEdition``.

Resolution is cache-first: a scan that has been seen before is answered from
SQLite and costs no network at all. Only a miss reaches the providers, which are
tried in order — Open Library first because it needs no credentials, Google
Books second.

The two ways a provider can fail to answer are kept distinct. A provider that
returns nothing has told us the book is not in *its* catalog, which is an answer;
a provider that times out or errors has told us nothing. Both move on to the next
provider, but only the first can conclude "this book does not exist", so a
lookup where every provider broke raises :class:`ProvidersUnavailableError`
rather than reporting a missing book the caller would stop asking about.
"""

from collections.abc import Sequence
from types import TracebackType
from typing import Self

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.enums import ContributorRole
from app.models import Author, BookEdition, Work, WorkAuthor
from app.schemas.metadata import BookMetadataResult
from app.services.catalog import get_or_create_publisher
from app.services.providers import (
    BibliographicProvider,
    GoogleBooksProvider,
    OpenLibraryProvider,
    ProviderError,
)
from app.utils.isbn import barcode_to_isbn13, to_isbn13


class ResolutionError(RuntimeError):
    """A lookup that could not produce an edition."""


class InvalidISBNError(ResolutionError):
    """The submitted string is not an ISBN or a book barcode."""

    def __init__(self, value: str | None) -> None:
        super().__init__(f"'{value}' is not a valid ISBN or book barcode")
        self.value = value


class BookNotFoundError(ResolutionError):
    """Every provider answered, and none of them has this book."""

    def __init__(self, isbn13: str) -> None:
        super().__init__(f"No catalog record for '{isbn13}'")
        self.isbn13 = isbn13


class ProvidersUnavailableError(ResolutionError):
    """No provider could be reached, so whether the book exists is unknown."""

    def __init__(self, isbn13: str, errors: Sequence[ProviderError]) -> None:
        reasons = "; ".join(str(error) for error in errors)
        super().__init__(f"No metadata provider could be reached for ISBN {isbn13}: {reasons}")
        self.isbn13 = isbn13
        self.errors = list(errors)


def canonical_isbn13(value: str | None) -> str:
    """Normalize any accepted identifier to the catalog key, or reject it.

    Barcodes are tried second so a scan carrying a price add-on still resolves.
    """
    canonical = to_isbn13(value) or barcode_to_isbn13(value)
    if canonical is None:
        raise InvalidISBNError(value)
    return canonical


def _edition_options() -> tuple:
    """Eager-load everything the edition payload renders, in one round trip each."""
    return (
        selectinload(BookEdition.publisher),
        selectinload(BookEdition.work).selectinload(Work.publisher),
        selectinload(BookEdition.work)
        .selectinload(Work.author_links)
        .selectinload(WorkAuthor.author),
    )


def load_edition_by_isbn13(db: Session, isbn13: str) -> BookEdition | None:
    return db.execute(
        select(BookEdition).options(*_edition_options()).where(BookEdition.isbn13 == isbn13)
    ).scalar_one_or_none()


def load_edition_by_identifier(db: Session, value: str | None) -> BookEdition | None:
    """Return a locally stored edition for an ISBN, barcode, or custom SKU.

    ISBN-13 is tried first because that is the unique catalog key. The barcode
    column is the fallback so a proprietary SKU typed in by hand is found on
    the next scan without asking Google Books or Open Library.
    """
    raw = (value or "").strip()
    if not raw:
        return None

    canonical = to_isbn13(raw) or barcode_to_isbn13(raw)
    if canonical:
        found = load_edition_by_isbn13(db, canonical)
        if found is not None:
            return found

    found = db.execute(
        select(BookEdition).options(*_edition_options()).where(BookEdition.barcode == raw)
    ).scalar_one_or_none()
    if found is not None:
        return found

    return (
        db.execute(
            select(BookEdition)
            .options(*_edition_options())
            .where(func.lower(BookEdition.barcode) == raw.lower())
        )
        .scalars()
        .first()
    )


def load_edition(db: Session, edition_id: int) -> BookEdition | None:
    return db.execute(
        select(BookEdition).options(*_edition_options()).where(BookEdition.id == edition_id)
    ).scalar_one_or_none()


class BookResolver:
    """Cache-first ISBN lookup that ingests provider metadata into the catalog."""

    def __init__(
        self,
        db: Session,
        providers: Sequence[BibliographicProvider] | None = None,
    ) -> None:
        self._db = db
        self._owns_providers = providers is None
        self._providers: list[BibliographicProvider] = (
            list(providers)
            if providers is not None
            else [OpenLibraryProvider(), GoogleBooksProvider()]
        )

    async def aclose(self) -> None:
        if not self._owns_providers:
            return
        for provider in self._providers:
            await provider.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def resolve(self, isbn: str, *, commit: bool = True) -> BookEdition:
        """Return the stored edition for an ISBN or SKU, fetching on a miss.

        Local rows win: a custom SKU saved by hand is answered from SQLite and
        never reaches a provider. Only a miss of a real ISBN goes to the network.
        ``commit=False`` leaves a newly ingested edition on the caller's session
        so a curriculum can be attached in the same transaction.
        """
        cached = load_edition_by_identifier(self._db, isbn)
        if cached is not None:
            return cached

        try:
            canonical = canonical_isbn13(isbn)
        except InvalidISBNError as error:
            # A proprietary barcode is a miss, not malformed input: the parent
            # can save it locally and the next scan will hit the cache above.
            raise BookNotFoundError((isbn or "").strip() or str(error.value)) from error

        metadata = await self._fetch(canonical)
        return self.ingest(canonical, metadata, commit=commit)

    async def _fetch(self, isbn13: str) -> BookMetadataResult:
        errors: list[ProviderError] = []
        answered = False

        for provider in self._providers:
            try:
                result = await provider.lookup_by_isbn(isbn13)
            except ProviderError as error:
                errors.append(error)
                continue
            if result is not None:
                return result
            answered = True

        if errors and not answered:
            raise ProvidersUnavailableError(isbn13, errors)
        raise BookNotFoundError(isbn13)

    def ingest(
        self,
        isbn13: str,
        metadata: BookMetadataResult,
        *,
        commit: bool = True,
    ) -> BookEdition:
        """Persist a provider result as publisher, authors, work, and edition.

        Everything lands in one transaction so a partially catalogued book can
        never be served from the cache on the next scan. Pass ``commit=False``
        to leave the insert uncommitted for a caller that still has work to do.
        """
        existing = load_edition_by_isbn13(self._db, isbn13)
        if existing is not None:
            return existing

        db = self._db
        try:
            publisher = get_or_create_publisher(db, metadata.publisher)
            publisher_id = publisher.id if publisher is not None else None

            # Each resolved edition gets its own Work: titles are not reliable
            # enough to merge two printings automatically, and a wrong merge is
            # far harder to undo than a duplicate.
            work = Work(
                title=metadata.title,
                subtitle=metadata.subtitle,
                publisher_id=publisher_id,
                description=metadata.description,
            )
            db.add(work)
            db.flush()

            self._link_authors(work, metadata.authors)

            edition = BookEdition(
                work_id=work.id,
                publisher_id=publisher_id,
                isbn13=isbn13,
                isbn10=metadata.isbn10,
                barcode=isbn13,
                publication_year=metadata.publication_year,
                page_count=metadata.page_count,
                cover_image_path=metadata.cover_url,
            )
            db.add(edition)
            db.flush()
            if commit:
                db.commit()
        except IntegrityError:
            # A concurrent scan of the same barcode won the unique index on
            # isbn13; its row describes the same book, so use it.
            db.rollback()
            existing = load_edition_by_isbn13(db, isbn13)
            if existing is None:
                raise
            return existing
        except Exception:
            db.rollback()
            raise

        stored = load_edition_by_isbn13(db, isbn13)
        if stored is None:  # pragma: no cover - the insert above just flushed
            raise ResolutionError(f"ISBN {isbn13} vanished immediately after ingestion")
        return stored

    def _link_authors(self, work: Work, credits_: Sequence) -> None:
        linked: set[tuple[int, ContributorRole]] = set()
        for sort_order, credit in enumerate(credits_):
            author = self._get_or_create_author(credit.name)
            key = (author.id, credit.role)
            if key in linked:
                continue
            linked.add(key)
            self._db.add(
                WorkAuthor(
                    work_id=work.id,
                    author_id=author.id,
                    role=credit.role,
                    sort_order=sort_order,
                )
            )

    def _get_or_create_author(self, name: str) -> Author:
        cleaned = name.strip()
        author = (
            self._db.execute(
                select(Author).where(func.lower(Author.name) == cleaned.lower())
            )
            .scalars()
            .first()
        )
        if author is None:
            author = Author(name=cleaned)
            self._db.add(author)
            self._db.flush()
        return author
