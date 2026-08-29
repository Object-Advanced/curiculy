"""Provider tests.

Every HTTP call is mocked with respx, which fails on any unmatched request, so a
regression that reaches the real Open Library or Google Books API shows up as a
test failure rather than a slow, flaky suite.
"""

import httpx
import pytest
import respx

from app.enums import ContributorRole, MetadataSource
from app.services.providers import (
    GoogleBooksProvider,
    OpenLibraryProvider,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
)

ISBN10 = "0306406152"
ISBN13 = "9780306406157"

OPEN_LIBRARY_URL = f"{OpenLibraryProvider.base_url}/api/books"
OPEN_LIBRARY_SEARCH_URL = f"{OpenLibraryProvider.base_url}/search.json"
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
        "cover": {
            "small": "https://covers.openlibrary.org/b/id/1-S.jpg",
            "medium": "https://covers.openlibrary.org/b/id/1-M.jpg",
            "large": "https://covers.openlibrary.org/b/id/1-L.jpg",
        },
        "notes": "Student edition.",
    }
}

OPEN_LIBRARY_SEARCH = {
    "numFound": 2,
    "docs": [
        {
            "title": "Everything Else",
            "author_name": ["Someone Unrelated"],
            "publisher": ["Other Press"],
            "first_publish_year": 1999,
            "isbn": ["0306406152"],
            "number_of_pages_median": 100,
            "cover_i": 42,
        },
        {
            "title": "Saxon Math 3",
            "subtitle": "An Incremental Development",
            "author_name": ["Nancy Larson"],
            "publisher": ["Saxon Publishers"],
            "first_publish_year": 2004,
            "isbn": ["not-an-isbn", ISBN13],
            "number_of_pages_median": 627,
            "cover_i": 7,
        },
    ],
}

GOOGLE_VOLUME = {
    "totalItems": 1,
    "items": [
        {
            "id": "abc123",
            "volumeInfo": {
                "title": "Saxon Math 3",
                "subtitle": "An Incremental Development",
                "authors": ["Nancy Larson", "Stephen Hake"],
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


@pytest.fixture
async def open_library():
    async with OpenLibraryProvider(timeout=1.0, max_results=5) as provider:
        yield provider


@pytest.fixture
async def google_books():
    async with GoogleBooksProvider(timeout=1.0, max_results=5, api_key=None) as provider:
        yield provider


class TestOpenLibraryLookup:
    @respx.mock
    async def test_successful_lookup(self, open_library: OpenLibraryProvider) -> None:
        route = respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK)
        )

        result = await open_library.lookup_by_isbn(ISBN13)

        assert route.called
        assert result is not None
        assert result.title == "Saxon Math 3"
        assert result.subtitle == "An Incremental Development"
        assert result.isbn13 == ISBN13
        assert result.isbn10 == ISBN10
        assert result.publisher == "Saxon Publishers"
        assert result.publication_date == "2004"
        assert result.publication_year == 2004
        assert result.page_count == 627
        assert result.description == "Student edition."
        assert result.cover_url.endswith("-L.jpg")
        assert result.source is MetadataSource.OPEN_LIBRARY
        assert result.confidence == 1.0
        assert result.author_names == ["Nancy Larson", "Stephen Hake"]
        assert all(credit.role is ContributorRole.AUTHOR for credit in result.authors)
        assert result.raw_payload is not None

    @respx.mock
    async def test_isbn10_is_upgraded_before_request(
        self, open_library: OpenLibraryProvider
    ) -> None:
        route = respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK)
        )

        result = await open_library.lookup_by_isbn("0-306-40615-2")

        assert result is not None
        assert route.calls.last.request.url.params["bibkeys"] == f"ISBN:{ISBN13}"

    @respx.mock
    async def test_empty_body_means_unknown_book(
        self, open_library: OpenLibraryProvider
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json={}))

        assert await open_library.lookup_by_isbn(ISBN13) is None

    @respx.mock
    async def test_not_found(self, open_library: OpenLibraryProvider) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(404))

        assert await open_library.lookup_by_isbn(ISBN13) is None

    @respx.mock
    async def test_rate_limited(self, open_library: OpenLibraryProvider) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "30"})
        )

        with pytest.raises(ProviderRateLimited) as exc_info:
            await open_library.lookup_by_isbn(ISBN13)

        assert exc_info.value.retry_after == 30.0
        assert exc_info.value.source is MetadataSource.OPEN_LIBRARY

    @respx.mock
    async def test_timeout(self, open_library: OpenLibraryProvider) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(side_effect=httpx.ReadTimeout("too slow"))

        with pytest.raises(ProviderTimeout):
            await open_library.lookup_by_isbn(ISBN13)

    @respx.mock
    async def test_server_error(self, open_library: OpenLibraryProvider) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(503))

        with pytest.raises(ProviderUnavailable):
            await open_library.lookup_by_isbn(ISBN13)

    @respx.mock
    async def test_client_error_is_generic_provider_error(
        self, open_library: OpenLibraryProvider
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(400))

        with pytest.raises(ProviderError) as exc_info:
            await open_library.lookup_by_isbn(ISBN13)

        assert type(exc_info.value) is ProviderError

    @respx.mock
    async def test_malformed_json(self, open_library: OpenLibraryProvider) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, text="<html>"))

        with pytest.raises(ProviderUnavailable):
            await open_library.lookup_by_isbn(ISBN13)

    @respx.mock
    async def test_invalid_isbn_makes_no_request(
        self, open_library: OpenLibraryProvider
    ) -> None:
        assert await open_library.lookup_by_isbn("not-an-isbn") is None
        assert not respx.calls


class TestOpenLibrarySearch:
    @respx.mock
    async def test_results_are_ranked_by_confidence(
        self, open_library: OpenLibraryProvider
    ) -> None:
        route = respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_SEARCH)
        )

        results = await open_library.search_by_title("Saxon Math 3", author="Nancy Larson")

        assert route.called
        assert [result.title for result in results] == ["Saxon Math 3", "Everything Else"]
        assert results[0].confidence == 0.95
        assert results[0].confidence > results[1].confidence
        assert results[0].isbn13 == ISBN13
        assert results[0].cover_url == "https://covers.openlibrary.org/b/id/7-L.jpg"
        assert results[0].publication_date == "2004"

    @respx.mock
    async def test_query_parameters(self, open_library: OpenLibraryProvider) -> None:
        route = respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"docs": []})
        )

        await open_library.search_by_title("Saxon Math 3", author="Nancy Larson")

        params = route.calls.last.request.url.params
        assert params["title"] == "Saxon Math 3"
        assert params["author"] == "Nancy Larson"
        assert params["limit"] == "5"

    @respx.mock
    async def test_author_omitted_when_not_given(
        self, open_library: OpenLibraryProvider
    ) -> None:
        route = respx.get(OPEN_LIBRARY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"docs": []})
        )

        await open_library.search_by_title("Saxon Math 3")

        assert "author" not in route.calls.last.request.url.params

    @respx.mock
    async def test_not_found_returns_empty_list(
        self, open_library: OpenLibraryProvider
    ) -> None:
        respx.get(OPEN_LIBRARY_SEARCH_URL).mock(return_value=httpx.Response(404))

        assert await open_library.search_by_title("Nothing") == []

    @respx.mock
    async def test_search_timeout(self, open_library: OpenLibraryProvider) -> None:
        respx.get(OPEN_LIBRARY_SEARCH_URL).mock(side_effect=httpx.ConnectTimeout("slow"))

        with pytest.raises(ProviderTimeout):
            await open_library.search_by_title("Saxon Math 3")


class TestGoogleBooksLookup:
    @respx.mock
    async def test_successful_lookup(self, google_books: GoogleBooksProvider) -> None:
        route = respx.get(GOOGLE_URL).mock(
            return_value=httpx.Response(200, json=GOOGLE_VOLUME)
        )

        result = await google_books.lookup_by_isbn(ISBN13)

        assert route.called
        assert route.calls.last.request.url.params["q"] == f"isbn:{ISBN13}"
        assert result is not None
        assert result.title == "Saxon Math 3"
        assert result.isbn13 == ISBN13
        assert result.isbn10 == ISBN10
        assert result.publisher == "Saxon Publishers"
        assert result.publication_date == "2004-05-17"
        assert result.publication_year == 2004
        assert result.page_count == 627
        assert result.description == "Incremental math for third grade."
        assert result.source is MetadataSource.GOOGLE_BOOKS
        assert result.confidence == 1.0

    @respx.mock
    async def test_http_cover_link_is_upgraded(
        self, google_books: GoogleBooksProvider
    ) -> None:
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        result = await google_books.lookup_by_isbn(ISBN13)

        assert result is not None
        assert result.cover_url == "https://books.google.com/cover.jpg"

    @respx.mock
    async def test_zero_items_means_unknown_book(
        self, google_books: GoogleBooksProvider
    ) -> None:
        respx.get(GOOGLE_URL).mock(
            return_value=httpx.Response(200, json={"totalItems": 0, "items": []})
        )

        assert await google_books.lookup_by_isbn(ISBN13) is None

    @respx.mock
    async def test_not_found(self, google_books: GoogleBooksProvider) -> None:
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(404))

        assert await google_books.lookup_by_isbn(ISBN13) is None

    @respx.mock
    async def test_rate_limited_without_retry_after(
        self, google_books: GoogleBooksProvider
    ) -> None:
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(429))

        with pytest.raises(ProviderRateLimited) as exc_info:
            await google_books.lookup_by_isbn(ISBN13)

        assert exc_info.value.retry_after is None
        assert exc_info.value.source is MetadataSource.GOOGLE_BOOKS

    @respx.mock
    async def test_timeout(self, google_books: GoogleBooksProvider) -> None:
        respx.get(GOOGLE_URL).mock(side_effect=httpx.ReadTimeout("too slow"))

        with pytest.raises(ProviderTimeout):
            await google_books.lookup_by_isbn(ISBN13)

    @respx.mock
    async def test_server_error(self, google_books: GoogleBooksProvider) -> None:
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(500))

        with pytest.raises(ProviderUnavailable):
            await google_books.lookup_by_isbn(ISBN13)

    @respx.mock
    async def test_transport_error(self, google_books: GoogleBooksProvider) -> None:
        respx.get(GOOGLE_URL).mock(side_effect=httpx.ConnectError("no route"))

        with pytest.raises(ProviderUnavailable):
            await google_books.lookup_by_isbn(ISBN13)

    @respx.mock
    async def test_invalid_isbn_makes_no_request(
        self, google_books: GoogleBooksProvider
    ) -> None:
        assert await google_books.lookup_by_isbn("junk") is None
        assert not respx.calls


class TestGoogleBooksApiKey:
    @respx.mock
    async def test_key_is_attached_when_configured(self) -> None:
        route = respx.get(GOOGLE_URL).mock(
            return_value=httpx.Response(200, json=GOOGLE_VOLUME)
        )

        async with GoogleBooksProvider(api_key="secret-key") as provider:
            await provider.lookup_by_isbn(ISBN13)

        assert route.calls.last.request.url.params["key"] == "secret-key"

    @respx.mock
    async def test_key_is_read_from_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "google_books_api_key", "from-config")
        route = respx.get(GOOGLE_URL).mock(
            return_value=httpx.Response(200, json=GOOGLE_VOLUME)
        )

        async with GoogleBooksProvider() as provider:
            await provider.lookup_by_isbn(ISBN13)

        assert route.calls.last.request.url.params["key"] == "from-config"

    @respx.mock
    async def test_no_key_sends_no_key_param(
        self, google_books: GoogleBooksProvider
    ) -> None:
        route = respx.get(GOOGLE_URL).mock(
            return_value=httpx.Response(200, json=GOOGLE_VOLUME)
        )

        await google_books.lookup_by_isbn(ISBN13)

        assert "key" not in route.calls.last.request.url.params


class TestGoogleBooksSearch:
    @respx.mock
    async def test_query_uses_field_qualifiers(
        self, google_books: GoogleBooksProvider
    ) -> None:
        route = respx.get(GOOGLE_URL).mock(
            return_value=httpx.Response(200, json=GOOGLE_VOLUME)
        )

        results = await google_books.search_by_title("Saxon Math 3", author="Nancy Larson")

        query = route.calls.last.request.url.params["q"]
        assert 'intitle:"Saxon Math 3"' in query
        assert 'inauthor:"Nancy Larson"' in query
        assert results[0].confidence == 0.95

    @respx.mock
    async def test_title_only_search_scores_lower(
        self, google_books: GoogleBooksProvider
    ) -> None:
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        results = await google_books.search_by_title("Saxon Math 3")

        assert results[0].confidence == 0.8

    @respx.mock
    async def test_empty_results(self, google_books: GoogleBooksProvider) -> None:
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json={"totalItems": 0}))

        assert await google_books.search_by_title("Nothing At All") == []

    @respx.mock
    async def test_volume_without_title_is_skipped(
        self, google_books: GoogleBooksProvider
    ) -> None:
        respx.get(GOOGLE_URL).mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"volumeInfo": {"authors": ["No Title"]}}]},
            )
        )

        assert await google_books.search_by_title("Whatever") == []
