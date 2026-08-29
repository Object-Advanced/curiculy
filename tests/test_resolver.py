"""Resolver tests.

Provider HTTP is mocked with respx, which fails on any unmatched request, so a
resolution that unexpectedly reaches the network shows up as a test failure. The
cache tests assert on ``respx.calls`` directly: "no request was made" is the
whole point of the local cache, and only the call record can prove it.
"""

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import ContributorRole, MetadataSource
from app.models import Author, BookEdition, Publisher, Work, WorkAuthor
from app.schemas.metadata import AuthorCredit, BookMetadataResult
from app.services.providers import GoogleBooksProvider, OpenLibraryProvider
from app.services.resolver import (
    BookNotFoundError,
    BookResolver,
    InvalidISBNError,
    ProvidersUnavailableError,
    canonical_isbn13,
)

ISBN10 = "0306406152"
ISBN13 = "9780306406157"
OTHER_ISBN13 = "9781565925083"

OPEN_LIBRARY_URL = f"{OpenLibraryProvider.base_url}/api/books"
GOOGLE_URL = f"{GoogleBooksProvider.base_url}/volumes"

OPEN_LIBRARY_BOOK = {
    f"ISBN:{ISBN13}": {
        "title": "Saxon Math 3",
        "subtitle": "An Incremental Development",
        "authors": [{"name": "Nancy Larson"}, {"name": "Stephen Hake"}],
        "publishers": [{"name": "Saxon Publishers"}],
        "publish_date": "2004",
        "number_of_pages": 627,
        "identifiers": {"isbn_10": [ISBN10], "isbn_13": [ISBN13]},
        "cover": {"large": "https://covers.openlibrary.org/b/id/1-L.jpg"},
        "notes": "Student edition.",
    }
}

GOOGLE_VOLUME = {
    "totalItems": 1,
    "items": [
        {
            "id": "abc123",
            "volumeInfo": {
                "title": "Saxon Math 3",
                "subtitle": "An Incremental Development",
                "authors": ["Nancy Larson"],
                "publisher": "Saxon Publishers",
                "publishedDate": "2004-05-17",
                "pageCount": 627,
                "description": "Incremental math for third grade.",
                "industryIdentifiers": [
                    {"type": "ISBN_10", "identifier": ISBN10},
                    {"type": "ISBN_13", "identifier": ISBN13},
                ],
                "imageLinks": {"thumbnail": "http://books.google.com/cover.jpg"},
            },
        }
    ],
}

GOOGLE_EMPTY = {"totalItems": 0}


@pytest.fixture
async def resolver(db: Session):
    async with (
        OpenLibraryProvider(timeout=1.0) as open_library,
        GoogleBooksProvider(timeout=1.0, api_key=None) as google_books,
        BookResolver(db, providers=[open_library, google_books]) as book_resolver,
    ):
        yield book_resolver


@pytest.fixture
def ingester(db: Session) -> BookResolver:
    """Ingestion never reaches a provider, so none are wired in."""
    return BookResolver(db, providers=[])


def metadata(**overrides) -> BookMetadataResult:
    payload = {
        "isbn13": ISBN13,
        "title": "Saxon Math 3",
        "authors": [AuthorCredit(name="Nancy Larson")],
        "publisher": "Saxon Publishers",
        "publication_date": "2004",
        "source": MetadataSource.OPEN_LIBRARY,
    }
    payload.update(overrides)
    return BookMetadataResult(**payload)


class TestCanonicalization:
    def test_accepts_isbn10_and_punctuation(self) -> None:
        assert canonical_isbn13(ISBN10) == ISBN13
        assert canonical_isbn13("978-0-306-40615-7") == ISBN13
        assert canonical_isbn13("ISBN-13: 9780306406157") == ISBN13

    def test_accepts_a_scanned_barcode_with_a_price_add_on(self) -> None:
        assert canonical_isbn13(f"{ISBN13}52499") == ISBN13

    @pytest.mark.parametrize("value", ["", "   ", "not-a-book", "9780306406158", "12345"])
    def test_rejects_anything_that_is_not_a_book_identifier(self, value: str) -> None:
        with pytest.raises(InvalidISBNError):
            canonical_isbn13(value)

    async def test_resolve_treats_an_unknown_sku_as_a_miss_without_any_request(
        self, resolver: BookResolver
    ) -> None:
        with respx.mock:
            with pytest.raises(BookNotFoundError):
                await resolver.resolve("not-a-book")
            assert not respx.calls


class TestCacheHit:
    @respx.mock
    async def test_a_cached_edition_is_returned_without_calling_a_provider(
        self, resolver: BookResolver, db: Session
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))
        work = Work(title="Saxon Math 3")
        db.add(work)
        db.flush()
        db.add(BookEdition(work_id=work.id, isbn13=ISBN13))
        db.commit()

        edition = await resolver.resolve(ISBN13)

        assert not respx.calls
        assert edition.isbn13 == ISBN13
        assert edition.work.title == "Saxon Math 3"

    @respx.mock
    async def test_a_custom_sku_is_served_from_the_barcode_column(
        self, resolver: BookResolver, db: Session
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))
        work = Work(title="Saxon Math 3 Teacher Guide")
        db.add(work)
        db.flush()
        db.add(BookEdition(work_id=work.id, barcode="SAXON-3-TG"))
        db.commit()

        edition = await resolver.resolve("saxon-3-tg")

        assert not respx.calls
        assert edition.barcode == "SAXON-3-TG"
        assert edition.work.title == "Saxon Math 3 Teacher Guide"

    @respx.mock
    async def test_the_second_resolution_of_the_same_book_is_served_locally(
        self, resolver: BookResolver
    ) -> None:
        route = respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK)
        )

        first = await resolver.resolve(ISBN13)
        second = await resolver.resolve(ISBN13)

        assert route.call_count == 1
        assert first.id == second.id

    @respx.mock
    async def test_an_isbn10_scan_hits_the_cache_written_by_its_isbn13(
        self, resolver: BookResolver
    ) -> None:
        route = respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK)
        )

        first = await resolver.resolve(ISBN13)
        second = await resolver.resolve(ISBN10)

        assert route.call_count == 1
        assert first.id == second.id


class TestPrimaryProvider:
    @respx.mock
    async def test_open_library_result_is_ingested(
        self, resolver: BookResolver, db: Session
    ) -> None:
        open_library = respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK)
        )
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        edition = await resolver.resolve(ISBN13)

        assert open_library.called
        assert not google.called, "Google Books must not be paid for when the primary answers"
        assert edition.id is not None
        assert edition.isbn13 == ISBN13
        assert edition.isbn10 == ISBN10
        assert edition.barcode == ISBN13
        assert edition.publication_year == 2004
        assert edition.page_count == 627
        assert edition.cover_image_path == "https://covers.openlibrary.org/b/id/1-L.jpg"
        assert db.query(BookEdition).count() == 1

    @respx.mock
    async def test_work_publisher_and_authors_are_persisted(
        self, resolver: BookResolver, db: Session
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))

        edition = await resolver.resolve(ISBN13)

        assert edition.work.title == "Saxon Math 3"
        assert edition.work.subtitle == "An Incremental Development"
        assert edition.work.description == "Student edition."
        assert edition.publisher is not None
        assert edition.publisher.name == "Saxon Publishers"
        assert edition.work.publisher_id == edition.publisher_id
        assert [link.author_name for link in edition.work.authors] == [
            "Nancy Larson",
            "Stephen Hake",
        ]
        assert [link.sort_order for link in edition.work.authors] == [0, 1]
        assert {link.role for link in edition.work.authors} == {ContributorRole.AUTHOR}
        assert db.query(Author).count() == 2


class TestProviderFallback:
    @respx.mock
    async def test_falls_back_to_google_books_on_404(
        self, resolver: BookResolver, db: Session
    ) -> None:
        open_library = respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(404))
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        edition = await resolver.resolve(ISBN13)

        assert open_library.called
        assert google.called
        assert edition.isbn13 == ISBN13
        assert edition.work.description == "Incremental math for third grade."
        assert edition.cover_image_path == "https://books.google.com/cover.jpg"
        assert db.query(BookEdition).count() == 1

    @respx.mock
    async def test_falls_back_when_the_primary_is_empty(self, resolver: BookResolver) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json={}))
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        edition = await resolver.resolve(ISBN13)

        assert google.called
        assert edition.isbn13 == ISBN13

    @respx.mock
    async def test_falls_back_on_timeout(self, resolver: BookResolver) -> None:
        open_library = respx.get(OPEN_LIBRARY_URL).mock(
            side_effect=httpx.ReadTimeout("open library is slow")
        )
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        edition = await resolver.resolve(ISBN13)

        assert open_library.called
        assert google.called
        assert edition.isbn13 == ISBN13

    @respx.mock
    async def test_falls_back_when_the_primary_is_down(self, resolver: BookResolver) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(503))
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        edition = await resolver.resolve(ISBN13)

        assert google.called
        assert edition.isbn13 == ISBN13

    @respx.mock
    async def test_falls_back_when_the_primary_is_rate_limited(
        self, resolver: BookResolver
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "30"})
        )
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        edition = await resolver.resolve(ISBN13)

        assert google.called
        assert edition.isbn13 == ISBN13


class TestUnresolvable:
    @respx.mock
    async def test_no_provider_has_the_book(self, resolver: BookResolver, db: Session) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(404))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_EMPTY))

        with pytest.raises(BookNotFoundError):
            await resolver.resolve(ISBN13)

        assert db.query(BookEdition).count() == 0
        assert db.query(Work).count() == 0

    @respx.mock
    async def test_every_provider_is_unreachable(self, resolver: BookResolver) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(500))

        with pytest.raises(ProvidersUnavailableError) as excinfo:
            await resolver.resolve(ISBN13)

        assert excinfo.value.isbn13 == ISBN13
        assert len(excinfo.value.errors) == 2

    @respx.mock
    async def test_a_definitive_miss_outranks_a_broken_provider(
        self, resolver: BookResolver
    ) -> None:
        """One provider answering "not in my catalog" makes the book missing, not unknown."""
        respx.get(OPEN_LIBRARY_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_EMPTY))

        with pytest.raises(BookNotFoundError):
            await resolver.resolve(ISBN13)


class TestIngestion:
    def test_publishers_and_authors_are_reused_across_books(
        self, db: Session, ingester: BookResolver
    ) -> None:
        ingester.ingest(ISBN13, metadata())
        ingester.ingest(OTHER_ISBN13, metadata(isbn13=OTHER_ISBN13, title="Saxon Math 5/4"))

        assert db.query(Publisher).count() == 1
        assert db.query(Author).count() == 1
        assert db.query(Work).count() == 2
        assert db.query(BookEdition).count() == 2

    def test_publisher_matching_ignores_case(self, db: Session, ingester: BookResolver) -> None:
        ingester.ingest(ISBN13, metadata())
        ingester.ingest(
            OTHER_ISBN13,
            metadata(isbn13=OTHER_ISBN13, publisher="saxon publishers"),
        )

        assert db.query(Publisher).count() == 1

    def test_a_contributor_credited_twice_is_linked_once(
        self, db: Session, ingester: BookResolver
    ) -> None:
        edition = ingester.ingest(
            ISBN13,
            metadata(
                authors=[
                    AuthorCredit(name="Nancy Larson"),
                    AuthorCredit(name="Nancy Larson"),
                    AuthorCredit(name="Nancy Larson", role=ContributorRole.EDITOR),
                ]
            ),
        )

        links = db.execute(select(WorkAuthor).where(WorkAuthor.work_id == edition.work_id))
        roles = sorted(link.role for link in links.scalars())
        assert roles == [ContributorRole.AUTHOR, ContributorRole.EDITOR]

    def test_a_book_without_publisher_or_authors_still_ingests(
        self, db: Session, ingester: BookResolver
    ) -> None:
        edition = ingester.ingest(ISBN13, metadata(publisher=None, authors=[]))

        assert edition.publisher_id is None
        assert edition.work.authors == []
        assert db.query(Publisher).count() == 0

    def test_a_duplicate_isbn_returns_the_stored_edition(
        self, db: Session, ingester: BookResolver
    ) -> None:
        first = ingester.ingest(ISBN13, metadata())
        second = ingester.ingest(ISBN13, metadata())

        assert first.id == second.id
        assert db.query(BookEdition).count() == 1
        assert db.query(Work).count() == 1, "the rolled-back work must not linger"
