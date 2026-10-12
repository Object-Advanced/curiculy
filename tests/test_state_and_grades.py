"""The family's state over time, and grades from a fixed list."""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Student
from app.reference.grades import GRADE_CODES, grade_needs_confirming, last_grade_check, normalize_grade
from app.reference.states import normalize_state
from app.services.clock import household_today


class TestGradeList:
    @pytest.mark.parametrize(
        ("typed", "code"),
        [
            ("3", "3"), ("3rd", "3"), ("Grade 3", "3"), ("3rd grade", "3"), ("third", "3"),
            ("12th", "12"), ("senior", "12"), ("freshman", "9"),
            ("K", "K"), ("kindergarten", "K"), ("Kinder", "K"),
            ("pre-k", "PreK"), ("PreK", "PreK"), ("preschool", "PreK"),
        ],
    )
    def test_common_spellings_become_codes(self, typed: str, code: str) -> None:
        assert normalize_grade(typed) == code

    @pytest.mark.parametrize("typed", ["13", "0", "college", "gbnuicnrnk", ""])
    def test_anything_else_is_refused(self, typed: str) -> None:
        with pytest.raises(ValueError):
            normalize_grade(typed)

    def test_the_list_runs_pre_k_to_12(self) -> None:
        assert GRADE_CODES == ["PreK", "K", *[str(n) for n in range(1, 13)]]

    def test_grades_are_reconfirmed_after_each_july_first(self) -> None:
        assert last_grade_check(date(2026, 6, 30)) == date(2025, 7, 1)
        assert last_grade_check(date(2026, 7, 1)) == date(2026, 7, 1)
        assert grade_needs_confirming("3", date(2026, 6, 30), date(2026, 7, 1))
        assert not grade_needs_confirming("3", date(2026, 7, 1), date(2026, 10, 12))
        assert grade_needs_confirming(None, date(2026, 10, 1), date(2026, 10, 12))


class TestStates:
    def test_codes_and_names(self) -> None:
        assert normalize_state(" pa ") == "PA"
        assert normalize_state("Pennsylvania") == "PA"
        with pytest.raises(ValueError):
            normalize_state("Narnia")


class TestStudentGrades:
    def test_a_typed_grade_is_stored_as_a_code_and_confirmed(self, client: TestClient, db: Session) -> None:
        response = client.post("/api/students", json={"name": "Ada", "grade": "3rd"})
        assert response.status_code == 201
        body = response.json()
        assert (body["grade"], body["grade_label"]) == ("3", "3rd grade")
        assert body["grade_confirmed_on"] == household_today(db).isoformat()
        assert body["grade_needs_confirming"] is False
        assert body["has_iep"] is False

    def test_an_unknown_grade_is_refused(self, client: TestClient) -> None:
        assert client.post("/api/students", json={"name": "Ada", "grade": "college"}).status_code == 422

    def test_resending_the_same_grade_is_not_a_confirmation(self, client: TestClient, db: Session) -> None:
        student_id = client.post("/api/students", json={"name": "Ada", "grade": "3"}).json()["id"]
        student = db.get(Student, student_id)
        student.grade_confirmed_on = date(2000, 1, 1)
        db.commit()

        same = client.put(f"/api/students/{student_id}", json={"name": "Ada B.", "grade": "3"}).json()
        assert same["grade_confirmed_on"] == "2000-01-01"
        assert same["grade_needs_confirming"] is True

        changed = client.put(f"/api/students/{student_id}", json={"name": "Ada", "grade": "4th"}).json()
        assert (changed["grade"], changed["grade_needs_confirming"]) == ("4", False)

    def test_confirming_a_grade_for_the_new_year(self, client: TestClient, db: Session) -> None:
        student_id = client.post("/api/students", json={"name": "Ada", "grade": "3"}).json()["id"]
        student = db.get(Student, student_id)
        student.grade_confirmed_on = date(2000, 1, 1)
        db.commit()

        body = client.post(f"/api/students/{student_id}/confirm-grade", json={"grade": "4"}).json()
        assert (body["grade"], body["grade_needs_confirming"]) == ("4", False)

    def test_older_screens_cant_clear_the_iep_flag(self, client: TestClient) -> None:
        student_id = client.post("/api/students", json={"name": "Ada", "has_iep": True}).json()["id"]
        body = client.put(f"/api/students/{student_id}", json={"name": "Ada", "grade": "K"}).json()
        assert body["has_iep"] is True
        cleared = client.put(f"/api/students/{student_id}", json={"name": "Ada", "has_iep": False}).json()
        assert cleared["has_iep"] is False


class TestHouseholdState:
    def test_picking_a_state(self, client: TestClient) -> None:
        body = client.post("/api/household/state", json={"state_code": "pa"}).json()
        assert (body["state_code"], body["state_name"]) == ("PA", "Pennsylvania")
        assert [period["state_code"] for period in body["states"]] == ["PA"]

    def test_a_move_takes_effect_from_its_date(self, client: TestClient, db: Session) -> None:
        today = household_today(db)
        client.post("/api/household/state", json={"state_code": "PA", "starts_on": (today - timedelta(days=30)).isoformat()})
        body = client.post(
            "/api/household/state", json={"state_code": "OH", "starts_on": (today + timedelta(days=10)).isoformat()}
        ).json()
        assert body["state_code"] == "PA"
        assert [(p["state_code"], p["state_name"]) for p in body["states"]] == [("PA", "Pennsylvania"), ("OH", "Ohio")]

    def test_the_same_date_replaces_rather_than_adds(self, client: TestClient) -> None:
        client.post("/api/household/state", json={"state_code": "PA", "starts_on": "2026-08-01"})
        body = client.post("/api/household/state", json={"state_code": "NY", "starts_on": "2026-08-01"}).json()
        assert [p["state_code"] for p in body["states"]] == ["NY"]

    def test_replacing_the_history(self, client: TestClient) -> None:
        body = client.put(
            "/api/household/states",
            json=[{"state_code": "OH", "starts_on": "2027-01-01"}, {"state_code": "PA", "starts_on": "2026-01-01"}],
        ).json()
        assert [p["state_code"] for p in body["states"]] == ["PA", "OH"]
        duplicate = client.put(
            "/api/household/states",
            json=[{"state_code": "OH", "starts_on": "2027-01-01"}, {"state_code": "PA", "starts_on": "2027-01-01"}],
        )
        assert duplicate.status_code == 422

    def test_an_unknown_state_is_refused(self, client: TestClient) -> None:
        assert client.post("/api/household/state", json={"state_code": "ZZ"}).status_code == 422


def test_the_migration_reads_old_free_text_grades() -> None:
    path = next(Path("migrations/versions").glob("*_0002_*.py"))
    spec = importlib.util.spec_from_file_location("migration_0002", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._grade_code("3rd grade") == "3"
    assert module._grade_code("Kindergarten") == "K"
    assert module._grade_code("whatever") is None
