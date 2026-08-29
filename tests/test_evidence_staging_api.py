"""Evidence staging: hold Chrome-extension captures until they are filed."""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Assignment,
    AssignmentEvidence,
    EvidenceStaging,
    Household,
    Student,
)

ANCHOR = date(2026, 9, 16)


@pytest.fixture
def student(db: Session) -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name="Ada")
    db.add(student)
    db.commit()
    return student


def add_assignment(db: Session, student: Student, title: str = "Lesson 1") -> Assignment:
    assignment = Assignment(
        student_id=student.id,
        title=title,
        scheduled_date=ANCHOR,
    )
    db.add(assignment)
    db.commit()
    return assignment


def jpeg_bytes(width: int = 640, height: int = 480) -> bytes:
    image = Image.new("RGB", (width, height), color=(12, 34, 56))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


class TestStageEvidence:
    @pytest.fixture(autouse=True)
    def _isolate_storage(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        return tmp_path

    def test_a_screenshot_is_stored_and_held_unlinked(
        self, client: TestClient, db: Session, tmp_path: Path
    ) -> None:
        payload = jpeg_bytes()

        response = client.post(
            "/api/evidence/staging",
            files={"file": ("capture.jpg", payload, "image/jpeg")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["id"] > 0
        assert body["tenant_id"] == "test"
        assert body["file_path"].startswith("test/")
        assert body["file_path"].endswith(".webp")
        assert body["source"] == "chrome_extension"
        assert body["captured_at"] is not None

        stored = tmp_path / body["file_path"]
        assert stored.is_file()
        with Image.open(stored) as image:
            assert image.format == "WEBP"

        row = db.get(EvidenceStaging, body["id"])
        assert row is not None
        assert row.file_path == body["file_path"]
        assert row.tenant_id == "test"
        assert db.query(AssignmentEvidence).count() == 0

    def test_an_explicit_source_is_stored(
        self, client: TestClient, db: Session
    ) -> None:
        response = client.post(
            "/api/evidence/staging",
            data={"source": "manual_upload"},
            files={"file": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
        )

        assert response.status_code == 201
        assert response.json()["source"] == "manual_upload"
        assert db.query(EvidenceStaging).one().source == "manual_upload"


class TestListStagedEvidence:
    def test_returns_unlinked_rows_newest_first(self, client: TestClient, db: Session) -> None:
        older = EvidenceStaging(
            tenant_id="test",
            file_path="test/older.webp",
            captured_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
        )
        newer = EvidenceStaging(
            tenant_id="test",
            file_path="test/newer.webp",
            captured_at=datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc),
        )
        other_tenant = EvidenceStaging(
            tenant_id="other",
            file_path="other/hidden.webp",
            captured_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        )
        db.add_all([older, newer, other_tenant])
        db.commit()

        response = client.get("/api/evidence/staging")

        assert response.status_code == 200
        body = response.json()
        assert [row["file_path"] for row in body] == ["test/newer.webp", "test/older.webp"]
        assert all(row["tenant_id"] == "test" for row in body)

    def test_an_empty_inbox_is_an_empty_list(self, client: TestClient) -> None:
        response = client.get("/api/evidence/staging")

        assert response.status_code == 200
        assert response.json() == []


class TestLinkStagedEvidence:
    @pytest.fixture(autouse=True)
    def _isolate_storage(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        return tmp_path

    def test_moves_the_file_onto_the_assignment_and_clears_staging(
        self, client: TestClient, db: Session, student: Student, tmp_path: Path
    ) -> None:
        assignment = add_assignment(db, student)
        staged = client.post(
            "/api/evidence/staging",
            files={"file": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
        ).json()

        response = client.post(
            "/api/evidence/link",
            json={"evidence_id": staged["id"], "assignment_id": assignment.id},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["file_path"] == staged["file_path"]
        assert body["captured_at"] == staged["captured_at"]
        assert (tmp_path / body["file_path"]).is_file()

        assert db.get(EvidenceStaging, staged["id"]) is None
        record = db.get(AssignmentEvidence, body["id"])
        assert record is not None
        assert record.assignment_id == assignment.id
        assert record.file_path == staged["file_path"]

        detail = client.get(f"/api/assignments/{assignment.id}").json()
        assert detail["evidence_count"] == 1
        assert detail["evidence"][0]["file_path"] == staged["file_path"]
        assert client.get("/api/evidence/staging").json() == []

    def test_an_unknown_staging_row_is_a_404(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student)

        response = client.post(
            "/api/evidence/link",
            json={"evidence_id": 4242, "assignment_id": assignment.id},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Staging evidence not found"
        assert db.query(AssignmentEvidence).count() == 0

    def test_an_unknown_assignment_is_a_404_and_leaves_staging(
        self, client: TestClient, db: Session
    ) -> None:
        staged = EvidenceStaging(tenant_id="test", file_path="test/held.webp")
        db.add(staged)
        db.commit()

        response = client.post(
            "/api/evidence/link",
            json={"evidence_id": staged.id, "assignment_id": 4242},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Assignment not found"
        assert db.get(EvidenceStaging, staged.id) is not None

    def test_another_tenant_cannot_link_a_staged_row(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student)
        staged = EvidenceStaging(
            tenant_id="other",
            file_path="other/secret.webp",
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(staged)
        db.commit()

        response = client.post(
            "/api/evidence/link",
            json={"evidence_id": staged.id, "assignment_id": assignment.id},
        )

        assert response.status_code == 404
        assert db.get(EvidenceStaging, staged.id) is not None
        assert db.query(AssignmentEvidence).count() == 0
