"""Curriculum import and structure tests.

The CSV cases use real Saxon and Math-U-See shapes because the failure modes that
matter — a lesson paged into the wrong book, a range that runs backwards — only
show up once the columns look like something a parent would actually type.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import MappingSource, ResourceKind, UnitKind
from app.models import (
    BookEdition,
    Curriculum,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
    Work,
)
from app.schemas.curriculum import CurriculumImportRequest
from app.services.curriculum_import import (
    CurriculumImporter,
    CurriculumImportError,
    parse_csv,
)

SAXON_ISBN13 = "9781565775039"

SAXON_CSV = """curriculum_name,edition,resource_type,unit_title,unit_type,sequence,start_page,end_page,isbn13
Saxon Math 5/4,3rd edition,student_text,Lesson 1,lesson,1,1,4,9781565775039
Saxon Math 5/4,3rd edition,student_text,Lesson 2,lesson,2,5,8,9781565775039
Saxon Math 5/4,3rd edition,student_text,Lesson 3,lesson,3,9,13,9781565775039
"""

MATH_U_SEE_CSV = """curriculum_name,edition,resource_type,unit_title,unit_type,parent_title,sequence,start_page,end_page
Math-U-See Gamma,Universal Set,student_text,Multiplication,unit,,1,,
Math-U-See Gamma,Universal Set,student_text,Lesson 1,lesson,Multiplication,1,7,10
Math-U-See Gamma,Universal Set,student_text,Lesson 2,lesson,Multiplication,2,11,14
"""

NESTED_JSON = {
    "curriculum_name": "Apologia General Science",
    "publisher": "Apologia",
    "subject": "Science",
    "edition": "3rd edition",
    "grade_level": "7",
    "resources": [
        {"key": "text", "kind": "student_text", "title": "Student Text"},
        {"key": "tests", "kind": "test_book", "title": "Test Booklet"},
    ],
    "units": [
        {
            "title": "Module 1: The History of Science",
            "kind": "module",
            "sequence": 1,
            "children": [
                {
                    "title": "Chapter 1: Early Science",
                    "kind": "chapter",
                    "children": [
                        {
                            "title": "Lesson 1: The Greeks",
                            "kind": "lesson",
                            "resource": "text",
                            "page_start": 1,
                            "page_end": 6,
                        },
                        {
                            "title": "Lesson 2: The Middle Ages",
                            "kind": "lesson",
                            "resource": "text",
                            "page_start": 7,
                            "page_end": 12,
                        },
                    ],
                },
                {
                    "title": "Module 1 Test",
                    "kind": "assessment",
                    "resource": "tests",
                    "page_start": 3,
                    "page_end": 4,
                },
            ],
        }
    ],
}


@pytest.fixture
def importer(db: Session) -> CurriculumImporter:
    return CurriculumImporter(db)


def seed_book(db: Session, isbn13: str = SAXON_ISBN13) -> BookEdition:
    work = Work(title="Saxon Math 5/4")
    db.add(work)
    db.flush()
    edition = BookEdition(work_id=work.id, isbn13=isbn13)
    db.add(edition)
    db.commit()
    db.refresh(edition)
    return edition


def units_by_title(db: Session) -> dict[str, CurriculumUnit]:
    return {unit.title: unit for unit in db.query(CurriculumUnit).all()}


class TestCsvImport:
    def test_lessons_are_mapped_to_page_ranges(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        seed_book(db)

        summary = importer.import_csv(SAXON_CSV)

        assert summary.curriculum_created is True
        assert summary.edition_created is True
        assert summary.units_created == 3
        assert summary.page_mappings_created == 3
        assert summary.errors == []

        curriculum = db.get(Curriculum, summary.curriculum_id)
        assert curriculum.title == "Saxon Math 5/4"
        edition = db.get(CurriculumEdition, summary.curriculum_edition_id)
        assert edition.edition_label == "3rd edition"
        assert edition.is_current is True

        ranges = {
            mapping.curriculum_unit.title: (mapping.page_start, mapping.page_end)
            for mapping in db.query(CurriculumPageMapping).all()
        }
        assert ranges == {"Lesson 1": (1, 4), "Lesson 2": (5, 8), "Lesson 3": (9, 13)}

    def test_the_resource_is_linked_to_the_scanned_book(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        book = seed_book(db)

        summary = importer.import_csv(SAXON_CSV)

        assert summary.resources_created == 1
        resource = db.query(CurriculumResource).one()
        assert resource.book_edition_id == book.id
        assert resource.kind == ResourceKind.STUDENT_TEXT
        assert resource.title == "Saxon Math 5/4 Student Text"

    def test_an_uncatalogued_isbn_is_a_warning_not_a_failure(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        summary = importer.import_csv(SAXON_CSV)

        assert summary.units_created == 3
        assert len(summary.errors) == 1
        assert SAXON_ISBN13 in summary.errors[0]
        assert db.query(CurriculumResource).one().book_edition_id is None

    def test_units_carry_sequence_kind_and_mapping_source(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        importer.import_csv(SAXON_CSV)

        units = db.query(CurriculumUnit).order_by(CurriculumUnit.sort_order).all()
        assert [unit.sort_order for unit in units] == [1, 2, 3]
        assert [unit.depth for unit in units] == [0, 0, 0]
        assert {unit.kind for unit in units} == {UnitKind.LESSON}
        assert db.query(CurriculumPageMapping).first().source == MappingSource.IMPORTED

    def test_a_parent_column_builds_a_csv_hierarchy(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        summary = importer.import_csv(MATH_U_SEE_CSV)

        assert summary.units_created == 3
        assert summary.page_mappings_created == 2

        units = units_by_title(db)
        parent = units["Multiplication"]
        assert parent.parent_id is None
        assert parent.depth == 0
        assert parent.kind == UnitKind.UNIT
        assert units["Lesson 1"].parent_id == parent.id
        assert units["Lesson 2"].depth == 1

    def test_column_names_are_matched_loosely(self, importer: CurriculumImporter) -> None:
        csv_text = (
            "Curriculum,Edition,Lesson Title,Page Start,Page End\n"
            "Saxon Math 5/4,3rd edition,Lesson 1,1,4\n"
        )

        summary = importer.import_csv(csv_text)

        assert summary.units_created == 1
        assert summary.page_mappings_created == 1

    def test_a_single_page_lesson_needs_only_a_start(self, db: Session, importer) -> None:
        csv_text = (
            "curriculum_name,unit_title,start_page\nSaxon Math 5/4,Lesson 1,42\n"
        )

        importer.import_csv(csv_text)

        mapping = db.query(CurriculumPageMapping).one()
        assert (mapping.page_start, mapping.page_end) == (42, 42)
        assert mapping.page_count == 1

    def test_reimporting_updates_instead_of_duplicating(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        importer.import_csv(SAXON_CSV)
        summary = importer.import_csv(SAXON_CSV.replace(",9,13,", ",9,20,"))

        assert summary.curriculum_created is False
        assert summary.edition_created is False
        assert summary.units_created == 0
        assert summary.units_updated == 3
        assert summary.page_mappings_created == 0
        assert summary.page_mappings_updated == 3
        assert db.query(CurriculumUnit).count() == 3

        lesson_three = units_by_title(db)["Lesson 3"]
        assert lesson_three.page_mappings[0].page_end == 20


class TestCsvParsing:
    def test_a_flat_file_becomes_a_structured_request(self) -> None:
        request = parse_csv(SAXON_CSV)

        assert isinstance(request, CurriculumImportRequest)
        assert request.curriculum_name == "Saxon Math 5/4"
        assert request.edition == "3rd edition"
        assert len(request.resources) == 1
        assert len(request.units) == 3
        assert request.units[0].source_ref == "row 2"

    @pytest.mark.parametrize(
        ("csv_text", "expected"),
        [
            ("", "empty"),
            ("curriculum_name,unit_title\n", "no data rows"),
            ("unit_title,start_page\nLesson 1,1\n", "curriculum_name"),
            ("curriculum_name,start_page\nSaxon,1\n", "unit_title"),
        ],
    )
    def test_unusable_files_are_rejected(self, csv_text: str, expected: str) -> None:
        with pytest.raises(CurriculumImportError) as excinfo:
            parse_csv(csv_text)

        assert expected in str(excinfo.value)

    def test_a_second_curriculum_in_one_file_is_rejected(self) -> None:
        csv_text = (
            "curriculum_name,unit_title\nSaxon Math 5/4,Lesson 1\nSaxon Math 6/5,Lesson 1\n"
        )

        with pytest.raises(CurriculumImportError) as excinfo:
            parse_csv(csv_text)

        assert "one curriculum per file" in str(excinfo.value)

    def test_a_forward_parent_reference_is_rejected(self) -> None:
        csv_text = (
            "curriculum_name,unit_title,parent_title\n"
            "Saxon Math 5/4,Lesson 1,Multiplication\n"
            "Saxon Math 5/4,Multiplication,\n"
        )

        with pytest.raises(CurriculumImportError) as excinfo:
            parse_csv(csv_text)

        assert "row 2" in str(excinfo.value)
        assert "earlier row" in str(excinfo.value)

    def test_every_bad_row_is_reported_at_once(self) -> None:
        csv_text = (
            "curriculum_name,unit_title,unit_type,start_page\n"
            "Saxon Math 5/4,Lesson 1,chapterr,1\n"
            "Saxon Math 5/4,Lesson 2,lesson,five\n"
            "Saxon Math 5/4,,lesson,9\n"
        )

        with pytest.raises(CurriculumImportError) as excinfo:
            parse_csv(csv_text)

        assert len(excinfo.value.errors) == 3
        assert "row 2" in excinfo.value.errors[0]
        assert "row 3" in excinfo.value.errors[1]
        assert "row 4" in excinfo.value.errors[2]


class TestJsonImport:
    def test_a_three_level_tree_is_persisted(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        summary = importer.import_payload(CurriculumImportRequest(**NESTED_JSON))

        assert summary.units_created == 5
        assert summary.resources_created == 2
        assert summary.page_mappings_created == 3

        units = units_by_title(db)
        module = units["Module 1: The History of Science"]
        chapter = units["Chapter 1: Early Science"]
        lesson = units["Lesson 1: The Greeks"]

        assert (module.parent_id, module.depth, module.kind) == (None, 0, UnitKind.MODULE)
        assert (chapter.parent_id, chapter.depth) == (module.id, 1)
        assert (lesson.parent_id, lesson.depth) == (chapter.id, 2)
        assert units["Module 1 Test"].parent_id == module.id

    def test_units_page_into_the_resource_they_name(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        importer.import_payload(CurriculumImportRequest(**NESTED_JSON))

        text = db.query(CurriculumResource).filter_by(kind=ResourceKind.STUDENT_TEXT).one()
        tests = db.query(CurriculumResource).filter_by(kind=ResourceKind.TEST_BOOK).one()
        units = units_by_title(db)

        assert units["Lesson 1: The Greeks"].page_mappings[0].curriculum_resource_id == text.id
        assert units["Module 1 Test"].page_mappings[0].curriculum_resource_id == tests.id

    def test_a_lone_resource_does_not_need_naming(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        request = CurriculumImportRequest(
            curriculum_name="Saxon Math 5/4",
            resources=[{"kind": "student_text", "title": "Student Text"}],
            units=[{"title": "Lesson 1", "page_start": 1, "page_end": 4}],
        )

        importer.import_payload(request)

        assert db.query(CurriculumPageMapping).one().page_start == 1

    def test_the_publisher_is_created_and_attached(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        summary = importer.import_payload(CurriculumImportRequest(**NESTED_JSON))

        curriculum = db.get(Curriculum, summary.curriculum_id)
        assert curriculum.publisher_name == "Apologia"
        assert curriculum.subject == "Science"


class TestRollback:
    def _assert_nothing_was_written(self, db: Session) -> None:
        assert db.query(Curriculum).count() == 0
        assert db.query(CurriculumEdition).count() == 0
        assert db.query(CurriculumResource).count() == 0
        assert db.query(CurriculumUnit).count() == 0
        assert db.query(CurriculumPageMapping).count() == 0

    def test_a_negative_page_number_rolls_the_whole_import_back(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        csv_text = SAXON_CSV.replace(",5,8,", ",-5,8,")

        with pytest.raises(CurriculumImportError) as excinfo:
            importer.import_csv(csv_text)

        assert "page numbers must be 1 or greater" in str(excinfo.value)
        self._assert_nothing_was_written(db)

    def test_a_backwards_range_rolls_the_whole_import_back(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        with pytest.raises(CurriculumImportError) as excinfo:
            importer.import_csv(SAXON_CSV.replace(",9,13,", ",40,4,"))

        assert "precedes start_page" in str(excinfo.value)
        self._assert_nothing_was_written(db)

    def test_an_end_page_without_a_start_rolls_back(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        request = CurriculumImportRequest(
            curriculum_name="Saxon Math 5/4",
            resources=[{"kind": "student_text"}],
            units=[{"title": "Lesson 1", "page_end": 4}],
        )

        with pytest.raises(CurriculumImportError) as excinfo:
            importer.import_payload(request)

        assert "without start_page" in str(excinfo.value)
        self._assert_nothing_was_written(db)

    def test_an_unknown_resource_reference_rolls_back(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        request = CurriculumImportRequest(
            curriculum_name="Saxon Math 5/4",
            resources=[{"key": "text", "kind": "student_text"}],
            units=[{"title": "Lesson 1", "resource": "workbook", "page_start": 1}],
        )

        with pytest.raises(CurriculumImportError) as excinfo:
            importer.import_payload(request)

        assert "no resource named 'workbook'" in str(excinfo.value)
        self._assert_nothing_was_written(db)

    def test_an_ambiguous_resource_reference_rolls_back(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        request = CurriculumImportRequest(
            curriculum_name="Saxon Math 5/4",
            units=[{"title": "Lesson 1", "page_start": 1}],
            resources=[
                {"key": "a", "kind": "student_text", "title": "Text A"},
                {"key": "b", "kind": "student_text", "title": "Text B"},
            ],
        )

        with pytest.raises(CurriculumImportError) as excinfo:
            importer.import_payload(request)

        assert "must name which one" in str(excinfo.value)
        self._assert_nothing_was_written(db)

    def test_an_invalid_isbn_rolls_back(self, db: Session, importer: CurriculumImporter) -> None:
        request = CurriculumImportRequest(
            curriculum_name="Saxon Math 5/4",
            resources=[{"kind": "student_text", "isbn13": "978-not-a-book"}],
            units=[{"title": "Lesson 1"}],
        )

        with pytest.raises(CurriculumImportError) as excinfo:
            importer.import_payload(request)

        assert "is not a valid ISBN" in str(excinfo.value)
        self._assert_nothing_was_written(db)

    def test_an_empty_payload_is_rejected(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        with pytest.raises(CurriculumImportError):
            importer.import_payload(CurriculumImportRequest(curriculum_name="Saxon Math 5/4"))

        self._assert_nothing_was_written(db)

    def test_a_failed_reimport_leaves_the_previous_import_intact(
        self, db: Session, importer: CurriculumImporter
    ) -> None:
        importer.import_csv(SAXON_CSV)

        with pytest.raises(CurriculumImportError):
            importer.import_csv(SAXON_CSV.replace(",5,8,", ",5,-8,"))

        assert db.query(CurriculumUnit).count() == 3
        mapping = next(
            item
            for item in db.query(CurriculumPageMapping).all()
            if item.curriculum_unit.title == "Lesson 2"
        )
        assert (mapping.page_start, mapping.page_end) == (5, 8)


class TestImportEndpoint:
    def test_csv_body(self, client: TestClient) -> None:
        response = client.post(
            "/api/curricula/import",
            content=SAXON_CSV,
            headers={"Content-Type": "text/csv"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["curriculum_title"] == "Saxon Math 5/4"
        assert body["units_created"] == 3
        assert body["page_mappings_created"] == 3

    def test_json_body(self, client: TestClient) -> None:
        response = client.post("/api/curricula/import", json=NESTED_JSON)

        assert response.status_code == 200
        assert response.json()["units_created"] == 5

    def test_csv_file_upload(self, client: TestClient) -> None:
        response = client.post(
            "/api/curricula/import",
            files={"file": ("saxon.csv", SAXON_CSV, "text/csv")},
        )

        assert response.status_code == 200
        assert response.json()["units_created"] == 3

    def test_json_file_upload(self, client: TestClient) -> None:
        response = client.post(
            "/api/curricula/import",
            files={"file": ("apologia.json", json.dumps(NESTED_JSON), "application/json")},
        )

        assert response.status_code == 200
        assert response.json()["units_created"] == 5

    def test_bad_page_numbers_are_a_400_listing_every_problem(
        self, client: TestClient, db: Session
    ) -> None:
        broken = SAXON_CSV.replace(",5,8,", ",-5,8,").replace(",9,13,", ",40,4,")

        response = client.post(
            "/api/curricula/import",
            content=broken,
            headers={"Content-Type": "text/csv"},
        )

        assert response.status_code == 400
        errors = response.json()["detail"]["errors"]
        assert len(errors) == 2
        assert any("1 or greater" in error for error in errors)
        assert any("precedes start_page" in error for error in errors)
        assert db.query(Curriculum).count() == 0

    def test_a_malformed_json_document_is_a_422(self, client: TestClient) -> None:
        response = client.post("/api/curricula/import", json={"units": []})

        assert response.status_code == 422
        assert "curriculum_name" in str(response.json()["detail"]["errors"])

    def test_an_empty_body_is_a_400(self, client: TestClient) -> None:
        response = client.post(
            "/api/curricula/import", content="", headers={"Content-Type": "text/csv"}
        )

        assert response.status_code == 400

    def test_an_unsupported_content_type_is_a_415(self, client: TestClient) -> None:
        response = client.post(
            "/api/curricula/import",
            content=b"\x00\x01",
            headers={"Content-Type": "application/octet-stream"},
        )

        assert response.status_code == 415

    @pytest.mark.parametrize("content_type", ["text/plain", ""])
    def test_an_unlabelled_body_is_sniffed(self, client: TestClient, content_type: str) -> None:
        headers = {"Content-Type": content_type} if content_type else {}

        csv_response = client.post("/api/curricula/import", content=SAXON_CSV, headers=headers)
        json_response = client.post(
            "/api/curricula/import", content=json.dumps(NESTED_JSON), headers=headers
        )

        assert csv_response.json()["units_created"] == 3
        assert json_response.json()["units_created"] == 5


class TestTreeEndpoint:
    def test_the_tree_nests_units_and_inlines_page_mappings(self, client: TestClient) -> None:
        summary = client.post("/api/curricula/import", json=NESTED_JSON).json()

        response = client.get(f"/api/curricula/{summary['curriculum_id']}/tree")

        assert response.status_code == 200
        body = response.json()
        assert body["edition_label"] == "3rd edition"
        assert len(body["units"]) == 1

        module = body["units"][0]
        assert module["title"] == "Module 1: The History of Science"
        assert [child["title"] for child in module["children"]] == [
            "Chapter 1: Early Science",
            "Module 1 Test",
        ]

        lesson = module["children"][0]["children"][0]
        assert lesson["depth"] == 2
        assert lesson["page_mappings"][0]["page_start"] == 1
        assert lesson["page_mappings"][0]["page_end"] == 6
        assert lesson["page_mappings"][0]["page_count"] == 6
        assert lesson["page_mappings"][0]["resource_title"] == "Student Text"

    def test_a_flat_import_yields_flat_units(self, client: TestClient) -> None:
        summary = client.post(
            "/api/curricula/import", content=SAXON_CSV, headers={"Content-Type": "text/csv"}
        ).json()

        body = client.get(f"/api/curricula/{summary['curriculum_id']}/tree").json()

        assert [unit["title"] for unit in body["units"]] == ["Lesson 1", "Lesson 2", "Lesson 3"]
        assert all(unit["children"] == [] for unit in body["units"])

    def test_an_unknown_curriculum_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/curricula/4242/tree").status_code == 404

    def test_an_edition_from_another_curriculum_is_a_404(self, client: TestClient) -> None:
        summary = client.post("/api/curricula/import", json=NESTED_JSON).json()

        response = client.get(
            f"/api/curricula/{summary['curriculum_id']}/tree", params={"edition_id": 999}
        )

        assert response.status_code == 404

    def test_a_curriculum_without_editions_is_a_404(self, client: TestClient) -> None:
        created = client.post("/api/curricula", json={"title": "Nothing Imported Yet"}).json()

        response = client.get(f"/api/curricula/{created['id']}/tree")

        assert response.status_code == 404
        assert "no editions" in response.json()["detail"]


class TestResourcesEndpoint:
    def test_resources_include_the_linked_book(self, client: TestClient, db: Session) -> None:
        book = seed_book(db)
        summary = client.post(
            "/api/curricula/import", content=SAXON_CSV, headers={"Content-Type": "text/csv"}
        ).json()

        response = client.get(f"/api/curricula/{summary['curriculum_id']}/resources")

        assert response.status_code == 200
        body = response.json()
        assert body["edition_label"] == "3rd edition"
        resource = body["resources"][0]
        assert resource["kind"] == "student_text"
        assert resource["title"] == "Saxon Math 5/4 Student Text"
        assert resource["book_edition"]["id"] == book.id
        assert resource["book_edition"]["isbn13"] == SAXON_ISBN13
        assert resource["book_edition"]["work"]["title"] == "Saxon Math 5/4"

    def test_an_unlinked_resource_reports_no_book(self, client: TestClient) -> None:
        summary = client.post("/api/curricula/import", json=NESTED_JSON).json()

        body = client.get(f"/api/curricula/{summary['curriculum_id']}/resources").json()

        assert [resource["title"] for resource in body["resources"]] == [
            "Student Text",
            "Test Booklet",
        ]
        assert all(resource["book_edition"] is None for resource in body["resources"])

    def test_an_unknown_curriculum_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/curricula/4242/resources").status_code == 404
