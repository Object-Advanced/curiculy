"""Book endpoint tests.

The endpoints run the real resolver against respx-mocked providers, so these
cover the wiring end to end: request validation, cache reuse across requests, the
fallback chain, and the shape of the serialized edition.
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BookEdition, Work
from app.services.providers import GoogleBooksProvider, OpenLibraryProvider

ISBN10 = "0306406152"
ISBN13 = "9780306406157"

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
    }
}

GOOGLE_VOLUME = {
    "totalItems": 1,
    "items": [
        {
            "id": "abc123",
            "volumeInfo": {
                "title": "Saxon Math 3",
                "authors": ["Nancy Larson"],
                "publisher": "Saxon Publishers",
                "publishedDate": "2004-05-17",
                "pageCount": 627,
                "industryIdentifiers": [{"type": "ISBN_13", "identifier": ISBN13}],
            },
        }
    ],
}

GOOGLE_EMPTY = {"totalItems": 0}


def seed_edition(db: Session, isbn13: str = ISBN13) -> BookEdition:
    work = Work(title="Saxon Math 3")
    db.add(work)
    db.flush()
    edition = BookEdition(work_id=work.id, isbn13=isbn13, barcode=isbn13)
    db.add(edition)
    db.commit()
    db.refresh(edition)
    return edition


class TestResolveEndpoint:
    @respx.mock
    def test_resolves_and_returns_the_full_edition(self, client: TestClient) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))

        response = client.post("/api/books/resolve", json={"isbn": ISBN13})

        assert response.status_code == 200
        body = response.json()
        assert body["isbn13"] == ISBN13
        assert body["isbn10"] == ISBN10
        assert body["publication_year"] == 2004
        assert body["page_count"] == 627
        assert body["book_format"] == "softcover"
        assert body["work"]["title"] == "Saxon Math 3"
        assert body["work"]["subtitle"] == "An Incremental Development"
        assert body["work"]["publisher"]["name"] == "Saxon Publishers"
        assert body["publisher"]["name"] == "Saxon Publishers"
        assert [author["author_name"] for author in body["work"]["authors"]] == [
            "Nancy Larson",
            "Stephen Hake",
        ]
        assert body["work"]["authors"][0]["role"] == "author"

    @respx.mock
    def test_a_repeat_scan_is_served_from_the_cache(self, client: TestClient) -> None:
        route = respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK)
        )

        first = client.post("/api/books/resolve", json={"isbn": ISBN13})
        second = client.post("/api/books/resolve", json={"isbn": "978-0-306-40615-7"})

        assert route.call_count == 1
        assert first.json()["id"] == second.json()["id"]

    @respx.mock
    def test_an_already_stored_edition_never_calls_a_provider(
        self, client: TestClient, db: Session
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))
        stored = seed_edition(db)

        response = client.post("/api/books/resolve", json={"isbn": ISBN13})

        assert not respx.calls
        assert response.status_code == 200
        assert response.json()["id"] == stored.id

    @respx.mock
    def test_falls_back_to_the_secondary_provider(self, client: TestClient) -> None:
        open_library = respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(404))
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        response = client.post("/api/books/resolve", json={"isbn": ISBN13})

        assert open_library.called
        assert google.called
        assert response.status_code == 200
        assert response.json()["isbn13"] == ISBN13

    @respx.mock
    def test_falls_back_when_the_primary_times_out(self, client: TestClient) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        google = respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_VOLUME))

        response = client.post("/api/books/resolve", json={"isbn": ISBN13})

        assert google.called
        assert response.status_code == 200

    @respx.mock
    def test_unknown_book_is_a_404(self, client: TestClient) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(404))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_EMPTY))

        response = client.post("/api/books/resolve", json={"isbn": ISBN13})

        assert response.status_code == 404

    @respx.mock
    def test_unreachable_providers_are_a_503(self, client: TestClient) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(side_effect=httpx.ReadTimeout("slow"))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(500))

        response = client.post("/api/books/resolve", json={"isbn": ISBN13})

        assert response.status_code == 503

    @respx.mock
    @pytest.mark.parametrize("isbn", ["not-a-book", "9780306406158", "12345", "0306406153"])
    def test_unknown_sku_is_a_404_without_any_provider_call(
        self, client: TestClient, isbn: str
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))

        response = client.post("/api/books/resolve", json={"isbn": isbn})

        assert response.status_code == 404
        assert not respx.calls

    def test_a_missing_isbn_field_is_a_422(self, client: TestClient) -> None:
        assert client.post("/api/books/resolve", json={}).status_code == 422
        assert client.post("/api/books/resolve", json={"isbn": ""}).status_code == 422


class TestReadEndpoints:
    def test_get_by_isbn(self, client: TestClient, db: Session) -> None:
        stored = seed_edition(db)

        response = client.get(f"/api/books/isbn/{ISBN13}")

        assert response.status_code == 200
        assert response.json()["id"] == stored.id
        assert response.json()["work"]["title"] == "Saxon Math 3"

    def test_get_by_isbn_canonicalizes_the_path(self, client: TestClient, db: Session) -> None:
        stored = seed_edition(db)

        assert client.get(f"/api/books/isbn/{ISBN10}").json()["id"] == stored.id
        assert client.get("/api/books/isbn/978-0-306-40615-7").json()["id"] == stored.id

    def test_get_by_isbn_rejects_an_invalid_identifier(self, client: TestClient) -> None:
        response = client.get("/api/books/isbn/not-a-book")

        assert response.status_code == 400

    def test_get_by_isbn_is_a_404_when_not_catalogued(self, client: TestClient) -> None:
        response = client.get(f"/api/books/isbn/{ISBN13}")

        assert response.status_code == 404

    def test_get_by_id(self, client: TestClient, db: Session) -> None:
        stored = seed_edition(db)

        response = client.get(f"/api/books/{stored.id}")

        assert response.status_code == 200
        assert response.json()["isbn13"] == ISBN13

    def test_get_by_id_is_a_404_when_unknown(self, client: TestClient) -> None:
        assert client.get("/api/books/4242").status_code == 404
