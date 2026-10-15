"""Activities: "5K race, PE, 40 minutes", for one child or several, with a
photo. See docs/6-planning/product-spine.md ("Activities")."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Activity, ActivityEvidence, Student
from app.services.households import get_default_household


@pytest.fixture
def kids(db: Session) -> tuple[int, int]:
    household = get_default_household(db)
    ada, ben = Student(household_id=household.id, name="Ada"), Student(household_id=household.id, name="Ben")
    db.add_all([ada, ben])
    db.flush()
    return ada.id, ben.id


def _log(client: TestClient, student_ids: list[int], **fields) -> dict:
    body = {"title": "5K race", "on_date": "2026-10-10", "student_ids": student_ids, "subject_codes": ["pe"],
            "minutes": 40, **fields}
    response = client.post("/api/activities", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), color=(40, 120, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


class TestLogging:
    def test_log_one_for_two_children(self, client: TestClient, kids: tuple[int, int]) -> None:
        ada, ben = kids
        body = _log(client, [ada, ben, ada], subject_codes=["pe", "health", "pe"], notes="  Ran the whole way ",
                    link_url="https://youtu.be/abc")
        assert [child["name"] for child in body["students"]] == ["Ada", "Ben"]
        assert [subject["name"] for subject in body["subjects"]] == ["Physical education", "Health"]
        assert (body["minutes"], body["notes"], body["link_url"]) == (40, "Ran the whole way", "https://youtu.be/abc")
        assert client.get(f"/api/activities/{body['id']}").json() == body

    def test_it_needs_a_child_and_real_subjects(self, client: TestClient, kids: tuple[int, int]) -> None:
        ada, _ = kids
        base = {"title": "Recital", "on_date": "2026-10-10"}
        assert client.post("/api/activities", json={**base, "student_ids": []}).status_code == 422
        assert client.post("/api/activities", json={**base, "student_ids": [9999]}).status_code == 404
        assert client.post("/api/activities", json={
            **base, "student_ids": [ada], "subject_codes": ["juggling"]}).status_code == 422
        assert client.post("/api/activities", json={
            **base, "student_ids": [ada], "link_url": "javascript:alert(1)"}).status_code == 422
        no_subject = client.post("/api/activities", json={**base, "student_ids": [ada]})
        assert no_subject.status_code == 201 and no_subject.json()["subjects"] == []

    def test_list_by_child_and_dates_newest_first(self, client: TestClient, kids: tuple[int, int]) -> None:
        ada, ben = kids
        _log(client, [ada], title="Piano lesson", on_date="2026-09-02", subject_codes=["music"])
        _log(client, [ada, ben], title="Fire station visit", on_date="2026-10-01", subject_codes=["safety"])
        _log(client, [ben], title="Swim", on_date="2026-10-05")
        titles = lambda **params: [row["title"] for row in client.get("/api/activities", params=params).json()]  # noqa: E731
        assert titles() == ["Swim", "Fire station visit", "Piano lesson"]
        assert titles(student_id=ada) == ["Fire station visit", "Piano lesson"]
        assert titles(**{"from": "2026-10-01", "to": "2026-10-04"}) == ["Fire station visit"]

    def test_edit_and_delete(self, client: TestClient, db: Session, kids: tuple[int, int]) -> None:
        ada, ben = kids
        body = _log(client, [ada])
        edited = client.patch(f"/api/activities/{body['id']}", json={
            "student_ids": [ben], "minutes": None, "title": " 5K fun run ", "notes": None}).json()
        assert ([c["name"] for c in edited["students"]], edited["minutes"], edited["title"]) == (
            ["Ben"], None, "5K fun run")
        assert edited["subjects"] == body["subjects"]  # left alone
        assert client.patch(f"/api/activities/{body['id']}", json={"student_ids": []}).status_code == 422
        assert client.delete(f"/api/activities/{body['id']}").status_code == 204
        assert client.get(f"/api/activities/{body['id']}").status_code == 404
        assert db.scalars(select(Activity)).all() == []

    def test_removing_a_child_keeps_shared_activities(self, client: TestClient, db: Session, kids: tuple[int, int]) -> None:
        ada, ben = kids
        _log(client, [ada], title="Ada's recital")
        _log(client, [ada, ben], title="Zoo trip")
        assert client.delete(f"/api/students/{ada}").status_code == 204
        rows = client.get("/api/activities").json()
        assert [(row["title"], [c["name"] for c in row["students"]]) for row in rows] == [("Zoo trip", ["Ben"])]


class TestPhotos:
    @pytest.fixture(autouse=True)
    def _isolate_storage(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        return tmp_path

    def test_a_photo_is_a_work_sample(self, client: TestClient, db: Session, kids: tuple[int, int],
                                      tmp_path: Path) -> None:
        body = _log(client, [kids[0]])
        response = client.post(f"/api/activities/{body['id']}/evidence",
                               files={"file": ("finish.jpg", _jpeg(), "image/jpeg")})
        assert response.status_code == 201, response.text
        photo = response.json()
        assert photo["file_path"].endswith(".webp")
        assert (tmp_path / photo["file_path"]).is_file()
        assert client.get(f"/api/evidence/files/{photo['file_path']}").status_code == 200
        assert [row["id"] for row in client.get(f"/api/activities/{body['id']}").json()["evidence"]] == [photo["id"]]

        assert client.delete(f"/api/activities/{body['id']}/evidence/{photo['id']}").status_code == 204
        assert client.delete(f"/api/activities/{body['id']}/evidence/{photo['id']}").status_code == 404
        assert db.scalars(select(ActivityEvidence)).all() == []

    def test_only_photos_and_pdfs(self, client: TestClient, kids: tuple[int, int]) -> None:
        body = _log(client, [kids[0]])
        response = client.post(f"/api/activities/{body['id']}/evidence",
                               files={"file": ("page.html", b"<script>alert(1)</script>", "text/html")})
        assert response.status_code == 415
