"""The Library: books, textbooks, workbooks and online sites; what each needs before scheduling; search; covers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.enums import MetadataSource
from app.routers.library import get_book_providers
from app.schemas.metadata import AuthorCredit, BookMetadataResult
from app.services.library import guess_kind
from app.services.providers.base import BibliographicProvider, ProviderUnavailable
from app.services.text_checks import keyboard_mash_reason


def _create(client: TestClient, **fields) -> dict:
    response = client.post("/api/library", json=fields)
    assert response.status_code == 201, response.text
    return response.json()


def _missing(item: dict) -> set[str]:
    return {missing["field"] for missing in item["readiness"]["missing"]}


def _fixes(item: dict) -> list[str]:
    return [p["message"] for p in item["readiness"]["problems"] if p["level"] == "fix"]


class TestKeyboardMash:
    @pytest.mark.parametrize("text", ["gbnuicnrnkfnsknduscn", "asdfghjkl", "sdfsdfsdfsdf", "Mathhhhhh"])
    def test_mashing_is_caught(self, text: str) -> None:
        assert keyboard_mash_reason(text)

    @pytest.mark.parametrize(
        "text",
        ["Saxon 5/4", "BJU Math 5", "The Good and the Beautiful", "Lingua Latina per se Illustrata",
         "Strengths and weaknesses", "Mississippi", "Explode the Code 2", "Rhythms of Africa", None],
    )
    def test_real_titles_pass(self, text: str | None) -> None:
        assert keyboard_mash_reason(text) is None


class TestGuessKind:
    def test_guesses(self) -> None:
        assert guess_kind("Math 5 Student Text", publisher="BJU Press") == "textbook"
        assert guess_kind("Saxon Math 5/4", publisher="Saxon Publishers") == "textbook"
        assert guess_kind("Spectrum Math Workbook Grade 3") == "workbook"
        assert guess_kind("The Lord of the Rings", publisher="Houghton Mifflin") == "reading_book"


class TestReadingBook:
    def test_total_pages_are_required_and_chapters_optional(self, client: TestClient) -> None:
        book = _create(client, kind="reading_book", title="The Hobbit", author="J. R. R. Tolkien")
        assert _missing(book) == {"total_pages"}
        reason = book["readiness"]["missing"][0]["reason"]
        assert "pages" in reason and "re-plans" in reason
        ready = client.patch(f"/api/library/{book['id']}", json={"total_pages": 310}).json()
        assert ready["ready"] is True and ready["chapters"] == []

    def test_chapters_must_run_in_order_inside_the_book(self, client: TestClient) -> None:
        book = _create(client, kind="reading_book", title="The Hobbit", author="Tolkien", total_pages=310)
        body = client.put(
            f"/api/library/{book['id']}/chapters",
            json=[{"name": "An Unexpected Party", "start_page": 1},
                  {"name": "Roast Mutton", "start_page": 40},
                  {"name": "A Short Rest", "start_page": 33},
                  {"name": "Way Past the End", "start_page": 400}],
        ).json()
        fixes = " ".join(_fixes(body))
        assert "not after the chapter before it" in fixes and "past the book's 310 pages" in fixes
        assert body["ready"] is False


class TestWorkbook:
    def test_total_pages_and_chapters_are_both_required(self, client: TestClient) -> None:
        workbook = _create(client, kind="workbook", title="Spectrum Math Grade 3")
        assert _missing(workbook) == {"subject_code", "grade", "total_pages", "chapters"}
        client.patch(f"/api/library/{workbook['id']}", json={"subject_code": "math", "grade": "3rd", "total_pages": 160, "answer_key_start_page": 145})
        body = client.put(
            f"/api/library/{workbook['id']}/chapters",
            json=[{"name": "Addition", "start_page": 5}, {"name": "Fractions", "start_page": 62}],
        ).json()
        assert (body["ready"], body["grade"], body["answer_key_start_page"]) == (True, "3", 145)
        assert [chapter["name"] for chapter in body["chapters"]] == ["Addition", "Fractions"]

    def test_a_chapter_inside_the_answer_key_is_worth_a_look(self, client: TestClient) -> None:
        workbook = _create(client, kind="workbook", title="Spectrum", subject_code="math", grade="3",
                           total_pages=160, answer_key_start_page=145)
        body = client.put(f"/api/library/{workbook['id']}/chapters", json=[{"name": "Bonus", "start_page": 150}]).json()
        assert any(p["level"] == "check" and "answer key" in p["message"] for p in body["readiness"]["problems"])


class TestTextbook:
    def _textbook(self, client: TestClient, **fields) -> dict:
        details = {"title": "Saxon Math 5/4", "publisher": "Saxon", "edition": "3rd", "subject_code": "math",
                   "grade": "4", "total_pages": 600, "days_per_week": 5}
        return _create(client, kind="textbook", **{**details, **fields})

    def test_it_needs_the_full_lesson_list_with_pages(self, client: TestClient) -> None:
        item = self._textbook(client)
        assert _missing(item) == {"lessons"}
        assert "catch up" in item["readiness"]["missing"][0]["reason"]
        generated = client.post(f"/api/library/{item['id']}/lessons/generate", json={"count": 3}).json()
        assert [lesson["number"] for lesson in generated["lessons"]] == [1, 2, 3]
        labels = {m["field"]: m["label"] for m in generated["readiness"]["missing"]}
        assert labels == {"lesson_names": "3 of 3 lessons need a name", "lesson_pages": "3 of 3 lessons need pages"}

        done = client.put(
            f"/api/library/{item['id']}/lessons",
            json=[
                {"number": 1, "name": "Adding", "start_page": 1, "end_page": 4},
                {"number": 2, "name": "Subtracting", "start_page": 5, "end_page": 8},
                {"number": 3, "name": "Test 1", "type": "test", "start_page": 9, "end_page": 10},
            ],
        ).json()
        assert done["ready"] is True
        assert (done["readiness"]["lessons_total"], done["readiness"]["lessons_with_pages"]) == (3, 3)
        assert done["lessons"][2]["type"] == "test"
        assert (done["lessons"][0]["start_page"], done["lessons"][0]["end_page"]) == (1, 4)

    def test_other_details_are_required_too(self, client: TestClient) -> None:
        item = _create(client, kind="textbook", title="Math 5 Student Text")
        assert _missing(item) == {"publisher", "edition", "subject_code", "grade", "total_pages", "lessons"}

    def test_lesson_mistakes_are_caught(self, client: TestClient) -> None:
        item = self._textbook(client, total_pages=20)
        body = client.put(
            f"/api/library/{item['id']}/lessons",
            json=[
                {"number": 1, "name": "One", "start_page": 1, "end_page": 4},
                {"number": 1, "name": "Again", "start_page": 18, "end_page": 25},
                {"number": 4, "name": "gbnuicnrnkfnsknduscn", "start_page": 6, "end_page": 5},
                {"number": 5, "name": "Half", "start_page": 7},
            ],
        ).json()
        fixes = " ".join(_fixes(body))
        assert "listed twice" in fixes and "past the book's 20 pages" in fixes
        assert "run backwards" in fixes and "doesn't look like real words" in fixes
        assert "Give both the first and the last page" in fixes
        assert any("No lesson numbered 2, 3" in p["message"] for p in body["readiness"]["problems"])
        assert body["ready"] is False

    def test_a_teachers_edition_needs_no_lessons(self, client: TestClient) -> None:
        item = self._textbook(client, title="Saxon Math 5/4 Teacher's Edition", for_parent=True)
        assert item["ready"] is True and item["for_parent"] is True

    def test_chapters_belong_to_books_and_workbooks(self, client: TestClient) -> None:
        item = self._textbook(client)
        assert client.put(f"/api/library/{item['id']}/chapters", json=[{"name": "One", "start_page": 1}]).status_code == 409

    def test_lesson_lists_belong_to_textbooks(self, client: TestClient) -> None:
        workbook = _create(client, kind="workbook", title="Spectrum Math")
        response = client.put(f"/api/library/{workbook['id']}/lessons", json=[{"number": 1, "name": "One"}])
        assert response.status_code == 409


class TestOnlineProgram:
    def test_it_needs_a_link_and_a_measure(self, client: TestClient) -> None:
        program = _create(client, kind="online_program", title="IXL Math")
        assert _missing(program) == {"website_url", "subject_code", "grade", "measure", "days_per_week"}
        body = client.patch(
            f"/api/library/{program['id']}",
            json={"website_url": "https://www.ixl.com", "subject_code": "math", "grade": "3",
                  "measure": "minutes", "days_per_week": 4},
        ).json()
        assert _missing(body) == {"minutes_per_session"}
        assert client.patch(f"/api/library/{program['id']}", json={"minutes_per_session": 20}).json()["ready"] is True

    def test_passwords_are_never_stored(self, client: TestClient) -> None:
        program = _create(client, kind="online_program", title="IXL")
        response = client.patch(f"/api/library/{program['id']}", json={"login_note": "user ada, password: hunter2"})
        assert response.status_code == 422
        ok = client.patch(f"/api/library/{program['id']}", json={"login_note": "Log in as Ada"})
        assert ok.json()["login_note"] == "Log in as Ada"


class TestLibraryList:
    def test_filtering_by_kind(self, client: TestClient) -> None:
        _create(client, kind="reading_book", title="Charlotte's Web", author="E. B. White", total_pages=184)
        _create(client, kind="workbook", title="Spectrum Math")
        everything = client.get("/api/library").json()
        assert [(i["title"], i["kind_label"], i["ready"]) for i in everything] == [
            ("Charlotte's Web", "Book", True), ("Spectrum Math", "Workbook", False)
        ]
        assert [i["title"] for i in client.get("/api/library", params={"kind": "workbook"}).json()] == ["Spectrum Math"]
        assert client.get("/api/library", params={"kind": "magazine"}).status_code == 422

    def test_kind_is_asked_first(self, client: TestClient) -> None:
        assert client.post("/api/library", json={"title": "Untitled"}).status_code == 422
        assert client.post("/api/library", json={"kind": "magazine", "title": "Highlights"}).status_code == 422

    def test_deleting_takes_its_structure_with_it(self, client: TestClient) -> None:
        book = _create(client, kind="reading_book", title="Holes", author="Sachar", total_pages=240)
        client.put(f"/api/library/{book['id']}/chapters", json=[{"name": "One", "start_page": 1}])
        assert client.delete(f"/api/library/{book['id']}").status_code == 204
        assert client.get(f"/api/library/{book['id']}").status_code == 404


class TestCovers:
    def _png(self) -> bytes:
        buffer = BytesIO()
        Image.new("RGB", (600, 900), (40, 90, 160)).save(buffer, format="PNG")
        return buffer.getvalue()

    def test_an_uploaded_cover_is_shown_and_waits_for_review(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        book = _create(client, kind="reading_book", title="Holes", author="Sachar", total_pages=240,
                       cover_url="https://covers.openlibrary.org/b/id/1-L.jpg")
        assert book["cover"]["source"] == "lookup"
        body = client.post(f"/api/library/{book['id']}/cover", files={"file": ("cover.png", self._png(), "image/png")}).json()
        assert body["cover"] == {"url": f"/api/library/{book['id']}/cover", "source": "upload", "review": "pending"}
        image = client.get(f"/api/library/{book['id']}/cover")
        assert image.status_code == 200 and image.headers["content-type"] == "image/webp"
        assert Image.open(BytesIO(image.content)).size[1] == 800
        after = client.delete(f"/api/library/{book['id']}/cover").json()
        assert after["cover"]["source"] == "lookup"

    def test_a_cover_must_be_an_image(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        book = _create(client, kind="reading_book", title="Holes")
        response = client.post(f"/api/library/{book['id']}/cover", files={"file": ("x.pdf", b"%PDF-1.4 not a cover", "application/pdf")})
        assert response.status_code == 415


class _Provider(BibliographicProvider):
    source = MetadataSource.OPEN_LIBRARY
    base_url = "https://example.invalid"

    def __init__(self, by_isbn=None, by_title=None, down=False) -> None:
        super().__init__()
        self.by_isbn = by_isbn or {}
        self.by_title = by_title or []
        self.down = down

    async def lookup_by_isbn(self, isbn: str):
        if self.down:
            raise ProviderUnavailable(self.source, "down")
        return self.by_isbn.get(isbn)

    async def search_by_title(self, title: str, author: str | None = None):
        if self.down:
            raise ProviderUnavailable(self.source, "down")
        return self.by_title


def _meta(title: str, isbn13: str | None = None, publisher: str | None = None, pages: int | None = None) -> BookMetadataResult:
    return BookMetadataResult(
        title=title, isbn13=isbn13, publisher=publisher, page_count=pages, publication_date="2004",
        authors=[AuthorCredit(name="Someone")], cover_url="https://covers.example/1.jpg",
        source=MetadataSource.OPEN_LIBRARY,
    )


class TestSearch:
    def _client_with(self, client: TestClient, provider: _Provider) -> TestClient:
        async def providers():
            yield [provider]

        client.app.dependency_overrides[get_book_providers] = providers
        return client

    def test_title_search_guesses_each_kind(self, client: TestClient) -> None:
        provider = _Provider(by_title=[
            _meta("Math 5 Student Text", "9781591669999", "BJU Press"),
            _meta("Spectrum Math Workbook", "9781483808666"),
            _meta("Math Curse", "9780670861941", "Viking", 32),
        ])
        body = self._client_with(client, provider).get("/api/library/search", params={"q": "math"}).json()
        assert [(r["title"], r["guessed_kind"]) for r in body["results"]] == [
            ("Math 5 Student Text", "textbook"), ("Spectrum Math Workbook", "workbook"), ("Math Curse", "reading_book"),
        ]
        assert body["results"][2]["total_pages"] == 32 and body["results"][2]["year"] == 2004

    def test_your_own_library_comes_first(self, client: TestClient) -> None:
        _create(client, kind="reading_book", title="Math Curse", author="Scieszka", total_pages=32)
        body = self._client_with(client, _Provider()).get("/api/library/search", params={"q": "math"}).json()
        assert body["results"][0]["source"] == "library" and body["results"][0]["library_item_id"]

    def test_isbn_search_looks_up_the_exact_book(self, client: TestClient) -> None:
        provider = _Provider(by_isbn={"9780547928227": _meta("The Hobbit", "9780547928227", "Mariner", 300)})
        body = self._client_with(client, provider).get("/api/library/search", params={"q": "978-0-547-92822-7"}).json()
        assert [(r["title"], r["isbn"], r["total_pages"]) for r in body["results"]] == [("The Hobbit", "9780547928227", 300)]

    def test_lookups_down_still_let_you_add_it_yourself(self, client: TestClient) -> None:
        body = self._client_with(client, _Provider(down=True)).get("/api/library/search", params={"q": "9780547928227"}).json()
        assert body["results"] == [] and "add it yourself" in body["notice"]
