"""Curriculum catalog ISBN lookup and save.

These run the real resolver against respx-mocked providers, then assert the
curriculum, edition, and book land together so Auto-schedule can see the pages.
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import CurriculumSource, ResourceKind
from app.models import BookEdition, Curriculum, CurriculumEdition, CurriculumResource
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
        "notes": "Student edition.",
        "cover": {"large": "https://covers.openlibrary.org/b/id/1-L.jpg"},
    }
}

GOOGLE_EMPTY = {"totalItems": 0}


def mock_open_library() -> None:
    respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))


class TestLookupIsbn:
    @respx.mock
    def test_returns_title_publisher_pages_and_description(self, client: TestClient) -> None:
        mock_open_library()

        response = client.post("/api/catalog/lookup-isbn", json={"isbn": ISBN13})

        assert response.status_code == 200
        body = response.json()
        assert body["isbn13"] == ISBN13
        assert body["isbn10"] == ISBN10
        assert body["title"] == "Saxon Math 3"
        assert body["publisher"] == "Saxon Publishers"
        assert body["page_count"] == 627
        assert body["description"] == "Student edition."
        assert body["publication_year"] == 2004
        assert body["authors"] == ["Nancy Larson", "Stephen Hake"]

    @respx.mock
    def test_canonicalizes_a_hyphenated_isbn(self, client: TestClient) -> None:
        mock_open_library()

        response = client.post("/api/catalog/lookup-isbn", json={"isbn": "978-0-306-40615-7"})

        assert response.status_code == 200
        assert response.json()["isbn13"] == ISBN13

    @respx.mock
    def test_unknown_sku_is_a_404_without_any_provider_call(self, client: TestClient) -> None:
        mock_open_library()

        response = client.post("/api/catalog/lookup-isbn", json={"isbn": "SAXON-3-TG"})

        assert response.status_code == 404
        assert not respx.calls

    @respx.mock
    def test_unknown_book_is_a_404(self, client: TestClient) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(404))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_EMPTY))

        response = client.post("/api/catalog/lookup-isbn", json={"isbn": ISBN13})

        assert response.status_code == 404

    def test_a_missing_isbn_field_is_a_422(self, client: TestClient) -> None:
        assert client.post("/api/catalog/lookup-isbn", json={}).status_code == 422
        assert client.post("/api/catalog/lookup-isbn", json={"isbn": ""}).status_code == 422


class TestFromIsbn:
    @respx.mock
    def test_creates_curriculum_edition_and_linked_book(
        self, client: TestClient, db: Session
    ) -> None:
        mock_open_library()

        response = client.post(
            "/api/catalog/from-isbn",
            json={
                "isbn": ISBN13,
                "subject": "Mathematics",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Saxon Math 3"
        assert body["publisher_name"] == "Saxon Publishers"
        assert body["subject"] == "Mathematics"
        assert body["description"] == "Student edition."
        assert body["source_type"] == CurriculumSource.BARCODE
        assert body["edition_label"] == "1st edition"
        assert body["book_edition"]["isbn13"] == ISBN13
        assert body["book_edition"]["page_count"] == 627
        assert body["book_edition"]["work"]["title"] == "Saxon Math 3"

        curriculum = db.get(Curriculum, body["id"])
        edition = db.get(CurriculumEdition, body["curriculum_edition_id"])
        resource = db.query(CurriculumResource).one()
        book = db.query(BookEdition).one()

        assert curriculum is not None
        assert edition is not None
        assert edition.curriculum_id == curriculum.id
        assert edition.is_current is True
        assert edition.copyright_year == 2004
        assert resource.curriculum_edition_id == edition.id
        assert resource.book_edition_id == book.id
        assert resource.kind == ResourceKind.STUDENT_TEXT

    @respx.mock
    def test_form_overrides_replace_provider_title_and_publisher(
        self, client: TestClient
    ) -> None:
        mock_open_library()

        response = client.post(
            "/api/catalog/from-isbn",
            json={
                "isbn": ISBN13,
                "title": "Saxon Math 3 Homeschool",
                "publisher": "Saxon Homeschool",
                "description": "Our copy.",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Saxon Math 3 Homeschool"
        assert body["publisher_name"] == "Saxon Homeschool"
        assert body["description"] == "Our copy."
        assert body["book_edition"]["work"]["title"] == "Saxon Math 3"

    @respx.mock
    def test_lookup_then_save_reuses_the_cached_edition(
        self, client: TestClient, db: Session
    ) -> None:
        route = respx.get(OPEN_LIBRARY_URL).mock(
            return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK)
        )

        looked_up = client.post("/api/catalog/lookup-isbn", json={"isbn": ISBN13})
        saved = client.post("/api/catalog/from-isbn", json={"isbn": ISBN13})

        assert looked_up.status_code == 200
        assert saved.status_code == 201
        assert route.call_count == 1
        assert db.query(BookEdition).count() == 1
        assert saved.json()["book_edition"]["id"] == db.query(BookEdition).one().id

    @respx.mock
    def test_saved_book_is_listed_on_curriculum_resources(self, client: TestClient) -> None:
        mock_open_library()

        created = client.post("/api/catalog/from-isbn", json={"isbn": ISBN13}).json()
        response = client.get(f"/api/curricula/{created['id']}/resources")

        assert response.status_code == 200
        body = response.json()
        assert body["curriculum_edition_id"] == created["curriculum_edition_id"]
        assert len(body["resources"]) == 1
        resource = body["resources"][0]
        assert resource["book_edition"]["id"] == created["book_edition"]["id"]
        assert resource["book_edition"]["page_count"] == 627
        assert resource["kind"] == ResourceKind.STUDENT_TEXT

    @respx.mock
    def test_unknown_sku_is_a_404(self, client: TestClient) -> None:
        mock_open_library()

        response = client.post("/api/catalog/from-isbn", json={"isbn": "12345"})

        assert response.status_code == 404
        assert not respx.calls
        assert client.get("/api/curricula").json() == []

    @respx.mock
    def test_unknown_book_writes_nothing(self, client: TestClient, db: Session) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(404))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_EMPTY))

        response = client.post("/api/catalog/from-isbn", json={"isbn": ISBN13})

        assert response.status_code == 404
        assert db.query(Curriculum).count() == 0
        assert db.query(BookEdition).count() == 0


class TestLocalSku:
    @respx.mock
    def test_manual_save_with_a_custom_sku_is_found_on_the_next_lookup(
        self, client: TestClient, db: Session
    ) -> None:
        respx.get(OPEN_LIBRARY_URL).mock(return_value=httpx.Response(200, json=OPEN_LIBRARY_BOOK))
        respx.get(GOOGLE_URL).mock(return_value=httpx.Response(200, json=GOOGLE_EMPTY))

        created = client.post(
            "/api/curricula",
            json={
                "title": "Saxon Math 3 Teacher Guide",
                "publisher": "Saxon Publishers",
                "subject": "Math",
                "description": "Homeschool teacher's edition.",
                "source_type": "manual",
                "sku": "SAXON-3-TG",
            },
        )

        assert created.status_code == 201
        body = created.json()
        assert body["title"] == "Saxon Math 3 Teacher Guide"
        assert body["publisher_name"] == "Saxon Publishers"

        book = db.query(BookEdition).one()
        assert book.barcode == "SAXON-3-TG"
        assert book.isbn13 is None
        resource = db.query(CurriculumResource).one()
        assert resource.book_edition_id == book.id

        lookup = client.post("/api/catalog/lookup-isbn", json={"isbn": "SAXON-3-TG"})

        assert lookup.status_code == 200
        found = lookup.json()
        assert found["title"] == "Saxon Math 3 Teacher Guide"
        assert found["publisher"] == "Saxon Publishers"
        assert found["description"] == "Homeschool teacher's edition."
        assert found["barcode"] == "SAXON-3-TG"
        assert found["isbn13"] == "SAXON-3-TG"
        assert not respx.calls

    @respx.mock
    def test_sku_lookup_is_case_insensitive(self, client: TestClient) -> None:
        client.post(
            "/api/curricula",
            json={"title": "Saxon Math 3 Teacher Guide", "sku": "SAXON-3-TG"},
        )

        lookup = client.post("/api/catalog/lookup-isbn", json={"isbn": "saxon-3-tg"})

        assert lookup.status_code == 200
        assert lookup.json()["title"] == "Saxon Math 3 Teacher Guide"
        assert not respx.calls

    @respx.mock
    def test_saved_sku_book_is_listed_on_curriculum_resources(self, client: TestClient) -> None:
        created = client.post(
            "/api/curricula",
            json={"title": "Saxon Math 3 Teacher Guide", "sku": "SAXON-3-TG"},
        ).json()

        response = client.get(f"/api/curricula/{created['id']}/resources")

        assert response.status_code == 200
        resource = response.json()["resources"][0]
        assert resource["book_edition"]["barcode"] == "SAXON-3-TG"
        assert resource["book_edition"]["work"]["title"] == "Saxon Math 3 Teacher Guide"
