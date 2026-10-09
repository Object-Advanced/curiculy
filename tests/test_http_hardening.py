"""Security headers, the request size cap, compression, and evidence upload checks."""

from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

import app.evidence as evidence
from app.config import settings
from app.main import create_app
from app.models import Assignment, Household, Student

ROOT = Path(__file__).resolve().parent.parent


def _png(width: int = 64, height: int = 48) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(40, 90, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << >>\n%%EOF\n"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


@pytest.fixture
def assignment(db: Session) -> Assignment:
    student = Student(household=Household(name="Home"), name="Ada")
    db.add(student)
    db.flush()
    row = Assignment(student_id=student.id, title="Fractions", scheduled_date=date(2026, 10, 8))
    db.add(row)
    db.commit()
    return row


@pytest.fixture(autouse=True)
def isolated_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "evidence_dir", tmp_path)
    return tmp_path


def _upload(client: TestClient, assignment_id: int, name: str, data: bytes, content_type: str):
    return client.post(
        f"/api/assignments/{assignment_id}/evidence",
        files={"file": (name, data, content_type)},
    )


class TestSecurityHeaders:
    def test_app_shell_has_a_strict_script_policy(self, client: TestClient) -> None:
        response = client.get("/")
        policy = response.headers["content-security-policy"]
        assert "script-src 'self'" in policy
        assert "unsafe-eval" not in policy
        assert "frame-ancestors 'none'" in policy
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_api_responses_carry_the_headers_too(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_shell_has_no_inline_or_third_party_scripts(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        assert "<script>" not in html
        assert "cdn.jsdelivr.net" not in html
        assert "/static/js/theme-boot.js" in html
        assert (ROOT / "static/vendor/chartjs-4.5.1/chart.umd.min.js").is_file()


class TestCompression:
    def test_scripts_are_gzipped(self, client: TestClient) -> None:
        response = client.get("/static/js/app.js", headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"

    def test_photos_are_not_recompressed(self, client: TestClient) -> None:
        response = client.get("/static/night-mountains.jpg", headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200
        assert "content-encoding" not in response.headers


class TestRequestSizeCap:
    def test_oversized_upload_is_refused_before_auth_or_routing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "max_upload_megabytes", 1)
        client = TestClient(create_app())  # no auth overrides: 413 comes first

        response = _upload(client, 1, "big.png", b"0" * (2 * 1024 * 1024), "image/png")

        assert response.status_code == 413
        assert "1 MB" in response.json()["detail"]


class TestEvidenceUploads:
    def test_photos_are_stored_as_webp(
        self, client: TestClient, assignment: Assignment, isolated_evidence: Path
    ) -> None:
        response = _upload(client, assignment.id, "page.png", _png(), "image/png")
        assert response.status_code == 201
        assert response.json()["file_path"].endswith(".webp")

    def test_pdfs_are_kept_as_pdfs(self, client: TestClient, assignment: Assignment) -> None:
        response = _upload(client, assignment.id, "worksheet.pdf", PDF, "application/pdf")
        assert response.status_code == 201
        assert response.json()["file_path"].endswith(".pdf")

    @pytest.mark.parametrize(
        ("name", "data", "content_type"),
        [
            ("drawing.svg", SVG, "image/svg+xml"),
            ("page.png", b"<html><script>alert(1)</script></html>", "image/png"),
            ("notes.txt", b"just some text", "text/plain"),
        ],
    )
    def test_anything_else_is_refused_and_not_stored(
        self,
        client: TestClient,
        assignment: Assignment,
        isolated_evidence: Path,
        name: str,
        data: bytes,
        content_type: str,
    ) -> None:
        response = _upload(client, assignment.id, name, data, content_type)
        assert response.status_code == 415
        assert response.json()["detail"] == "Work samples must be a photo or a PDF."
        assert not any(path.is_file() for path in isolated_evidence.rglob("*"))

    def test_large_files_are_refused(
        self, client: TestClient, assignment: Assignment, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(evidence, "MAX_EVIDENCE_BYTES", 1024)
        response = _upload(client, assignment.id, "worksheet.pdf", PDF + b"0" * 2048, "application/pdf")
        assert response.status_code == 413

    def test_decompression_bombs_are_refused(
        self, client: TestClient, assignment: Assignment, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
        response = _upload(client, assignment.id, "huge.png", _png(64, 48), "image/png")
        assert response.status_code == 413

    def test_staging_uploads_are_checked_too(self, client: TestClient) -> None:
        response = client.post(
            "/api/evidence/staging", files={"file": ("x.svg", SVG, "image/svg+xml")}
        )
        assert response.status_code == 415


class TestServingStoredEvidence:
    def test_photos_are_sandboxed(self, client: TestClient, assignment: Assignment) -> None:
        stored = _upload(client, assignment.id, "page.png", _png(), "image/png").json()
        response = client.get(f"/api/evidence/files/{stored['file_path']}")
        assert response.status_code == 200
        assert "sandbox" in response.headers["content-security-policy"]
        assert response.headers["content-disposition"].startswith("inline")

    def test_older_unchecked_files_download_instead_of_rendering(
        self, client: TestClient, isolated_evidence: Path
    ) -> None:
        legacy = isolated_evidence / "test" / "old.svg"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(SVG)

        response = client.get("/api/evidence/files/test/old.svg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.headers["content-disposition"].startswith("attachment")
