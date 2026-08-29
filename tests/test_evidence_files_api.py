"""Authenticated, tenant-scoped evidence file reads."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import CurrentUser, get_current_user
from app.db import get_admin_db, get_catalog_db, get_tenant_db
from app.evidence import stored_relative_path
from app.main import create_app
from app.models import Household, Student
from tests.test_evidence_staging_api import add_assignment, jpeg_bytes


@pytest.fixture
def student(db: Session) -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name="Ada")
    db.add(student)
    db.commit()
    return student


def sibling_of(db: Session, student: Student, name: str = "Blaise") -> Student:
    other = Student(household_id=student.household_id, name=name)
    db.add(other)
    db.commit()
    return other


def _child_user(student_id: int) -> CurrentUser:
    return CurrentUser(
        email="kid@local",
        tenant_uuid="test",
        role="child",
        student_id=student_id,
    )


def _unauthenticated_client(db: Session) -> TestClient:
    application = create_app()
    application.dependency_overrides[get_catalog_db] = lambda: db
    application.dependency_overrides[get_tenant_db] = lambda: db
    application.dependency_overrides[get_admin_db] = lambda: db
    return TestClient(application)


def _headers_blob(response) -> str:
    return " ".join(f"{key}:{value}" for key, value in response.headers.items())


def _upload_assignment_photo(client: TestClient, assignment_id: int) -> dict:
    response = client.post(
        f"/api/assignments/{assignment_id}/evidence",
        files={"file": ("worksheet.jpg", jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


class TestStoredRelativePath:
    def test_rejects_traversal_and_keeps_tenant_filename(self) -> None:
        assert stored_relative_path("test/page.webp") == "test/page.webp"
        assert stored_relative_path("data/evidence/test/page.webp") == "test/page.webp"
        assert stored_relative_path("/data/evidence/test/page.webp") == "test/page.webp"
        assert stored_relative_path("test/../other/secret.webp") is None
        assert stored_relative_path("../test/page.webp") is None
        assert stored_relative_path("page.webp") is None


class TestGetEvidenceFile:
    @pytest.fixture(autouse=True)
    def _isolate_storage(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        return tmp_path

    def test_unauthenticated_get_is_401(self, db: Session) -> None:
        client = _unauthenticated_client(db)
        response = client.get("/api/evidence/files/test/missing.webp")
        assert response.status_code == 401
        assert "missing.webp" not in response.text

    def test_parent_can_read_household_file(
        self, client: TestClient, db: Session, student: Student, tmp_path: Path
    ) -> None:
        assignment = add_assignment(db, student)
        uploaded = _upload_assignment_photo(client, assignment.id)
        stored = tmp_path / uploaded["file_path"]
        payload = stored.read_bytes()

        response = client.get(f"/api/evidence/files/{uploaded['file_path']}")

        assert response.status_code == 200
        assert response.content == payload
        assert response.headers["content-type"].startswith("image/webp")
        assert "private" in response.headers.get("cache-control", "")
        assert "no-store" in response.headers.get("cache-control", "")
        assert str(tmp_path) not in response.text
        assert str(tmp_path) not in _headers_blob(response)

    def test_wrong_tenant_is_denied(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        secret = tmp_path / "other" / "secret.webp"
        secret.parent.mkdir(parents=True)
        secret.write_bytes(b"not-for-this-household")

        response = client.get("/api/evidence/files/other/secret.webp")

        assert response.status_code == 404
        assert response.content != b"not-for-this-household"
        assert b"not-for-this-household" not in response.content
        assert "secret.webp" not in response.text

    def test_child_cannot_read_staging_or_sibling_file(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        staged = client.post(
            "/api/evidence/staging",
            files={"file": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
        ).json()
        sibling = sibling_of(db, student)
        sibling_work = add_assignment(db, sibling, title="Sibling lesson")
        sibling_file = _upload_assignment_photo(client, sibling_work.id)

        client.app.dependency_overrides[get_current_user] = lambda: _child_user(student.id)

        staging_get = client.get(f"/api/evidence/files/{staged['file_path']}")
        sibling_get = client.get(f"/api/evidence/files/{sibling_file['file_path']}")

        assert staging_get.status_code == 403
        assert sibling_get.status_code == 403
        assert staged["file_path"] not in staging_get.text
        assert sibling_file["file_path"] not in sibling_get.text

    def test_child_can_read_own_assignment_file(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student)
        uploaded = _upload_assignment_photo(client, assignment.id)
        payload = (Path(settings.evidence_dir) / uploaded["file_path"]).read_bytes()

        client.app.dependency_overrides[get_current_user] = lambda: _child_user(student.id)
        response = client.get(f"/api/evidence/files/{uploaded['file_path']}")

        assert response.status_code == 200
        assert response.content == payload

    def test_nonexistent_file_is_404(self, client: TestClient) -> None:
        response = client.get("/api/evidence/files/test/missing.webp")
        assert response.status_code == 404
        assert response.json()["detail"] == "Evidence not found"
        assert "missing.webp" not in response.text

    def test_path_traversal_is_404(self, client: TestClient, tmp_path: Path) -> None:
        secret = tmp_path / "other" / "secret.webp"
        secret.parent.mkdir(parents=True)
        secret.write_bytes(b"hidden")

        response = client.get("/api/evidence/files/test/../other/secret.webp")

        assert response.status_code == 404
        assert b"hidden" not in response.content

    def test_legacy_public_url_does_not_serve_files(
        self, client: TestClient, db: Session, student: Student, tmp_path: Path
    ) -> None:
        assignment = add_assignment(db, student)
        uploaded = _upload_assignment_photo(client, assignment.id)
        payload = (tmp_path / uploaded["file_path"]).read_bytes()

        response = client.get(f"/evidence/{uploaded['file_path']}")

        assert response.status_code != 200
        assert response.content != payload

    def test_upload_then_link_then_parent_can_read(
        self, client: TestClient, db: Session, student: Student, tmp_path: Path
    ) -> None:
        assignment = add_assignment(db, student)
        staged = client.post(
            "/api/evidence/staging",
            files={"file": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
        ).json()
        linked = client.post(
            "/api/evidence/link",
            json={"evidence_id": staged["id"], "assignment_id": assignment.id},
        )
        assert linked.status_code == 200
        assert linked.json()["file_path"] == staged["file_path"]

        response = client.get(f"/api/evidence/files/{staged['file_path']}")
        assert response.status_code == 200
        assert response.content == (tmp_path / staged["file_path"]).read_bytes()
        assert client.get("/api/evidence/staging").json() == []
        assert client.get(f"/api/assignments/{assignment.id}").json()["evidence_count"] == 1
