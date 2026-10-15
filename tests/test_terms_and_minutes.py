"""Terms on the school year, days or hours, and minutes on lessons: what the
records count by. See docs/6-planning/product-spine.md."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus
from app.models import Assignment, Course, SchoolYear, Student
from app.services.households import get_default_household
from app.services.terms import even_quarters
from tests.test_planner import MONDAY, _curriculum, _online, _textbook

YEAR = {"name": "2026-2027", "start_date": "2026-08-03", "end_date": "2027-06-04"}


@pytest.fixture
def ada(db: Session) -> int:
    """Ada, in a 2026–27 school year."""
    household = get_default_household(db)
    db.add(SchoolYear(household_id=household.id, name="2026–27", start_date=date(2026, 8, 1),
                      end_date=date(2027, 6, 4)))
    student = Student(household_id=household.id, name="Ada")
    db.add(student)
    db.flush()
    return student.id


def _terms(body: dict) -> list[tuple[str, str, str]]:
    return [(term["name"], term["start_date"], term["end_date"]) for term in body["terms"]]


class TestTerms:
    def test_even_quarters_cover_the_year_back_to_back(self) -> None:
        quarters = even_quarters(date(2026, 8, 3), date(2027, 6, 4))
        assert [name for name, _, _ in quarters] == ["Quarter 1", "Quarter 2", "Quarter 3", "Quarter 4"]
        assert quarters[0][1] == date(2026, 8, 3) and quarters[-1][2] == date(2027, 6, 4)
        for (_, _, end), (_, start, _) in zip(quarters, quarters[1:]):
            assert (start - end).days == 1
        lengths = [(last - first).days + 1 for _, first, last in quarters]
        assert max(lengths) - min(lengths) <= 1

    def test_a_tiny_year_is_one_term(self) -> None:
        assert even_quarters(date(2026, 8, 3), date(2026, 8, 5)) == [
            ("Quarter 1", date(2026, 8, 3), date(2026, 8, 5))]

    def test_a_new_year_gets_quarters_that_follow_its_dates(self, client: TestClient) -> None:
        body = client.post("/api/school-years", json=YEAR).json()
        assert body["terms_by_parent"] is False
        assert len(body["terms"]) == 4 and body["terms"][0]["start_date"] == "2026-08-03"
        moved = client.patch(f"/api/school-years/{body['id']}", json={"end_date": "2027-05-28"}).json()
        assert moved["terms"][-1]["end_date"] == "2027-05-28"

    def test_the_parents_own_terms_stay_until_reset(self, client: TestClient) -> None:
        year = client.post("/api/school-years", json=YEAR).json()
        semesters = [
            {"name": " Fall ", "start_date": "2026-08-03", "end_date": "2026-12-18"},
            {"name": "Spring", "start_date": "2027-01-04", "end_date": "2027-06-04"},
        ]
        body = client.put(f"/api/school-years/{year['id']}/terms", json=semesters[::-1]).json()
        assert _terms(body) == [("Fall", "2026-08-03", "2026-12-18"), ("Spring", "2027-01-04", "2027-06-04")]
        assert body["terms_by_parent"] is True
        renamed = client.patch(f"/api/school-years/{year['id']}", json={"name": "Our year"}).json()
        assert [term["name"] for term in renamed["terms"]] == ["Fall", "Spring"]

        reset = client.post(f"/api/school-years/{year['id']}/terms/reset").json()
        assert reset["terms_by_parent"] is False and len(reset["terms"]) == 4

    def test_moving_the_year_past_the_parents_terms_goes_back_to_quarters(self, client: TestClient) -> None:
        year = client.post("/api/school-years", json=YEAR).json()
        client.put(f"/api/school-years/{year['id']}/terms", json=[
            {"name": "Fall", "start_date": "2026-08-03", "end_date": "2026-12-18"},
            {"name": "Spring", "start_date": "2027-01-04", "end_date": "2027-06-04"},
        ])
        shorter = client.patch(f"/api/school-years/{year['id']}", json={"end_date": "2027-05-28"}).json()
        assert shorter["terms_by_parent"] is False and len(shorter["terms"]) == 4

    def test_terms_must_fit_the_year_and_not_overlap(self, client: TestClient) -> None:
        year = client.post("/api/school-years", json=YEAR).json()
        put = lambda terms: client.put(f"/api/school-years/{year['id']}/terms", json=terms)  # noqa: E731
        outside = put([{"name": "Summer", "start_date": "2027-06-01", "end_date": "2027-07-30"}])
        assert outside.status_code == 422 and "outside the school year" in outside.json()["detail"]
        overlap = put([
            {"name": "Fall", "start_date": "2026-08-03", "end_date": "2027-01-10"},
            {"name": "Spring", "start_date": "2027-01-04", "end_date": "2027-06-04"},
        ])
        assert overlap.status_code == 422 and overlap.json()["detail"] == "Fall and Spring overlap."
        assert put([]).status_code == 422
        backwards = put([{"name": "Fall", "start_date": "2026-12-01", "end_date": "2026-09-01"}])
        assert backwards.status_code == 422
        assert put([{"name": "  ", "start_date": "2026-08-03", "end_date": "2026-12-18"}]).status_code == 422


class TestCountBy:
    def test_days_by_default_and_hours_when_chosen(self, client: TestClient) -> None:
        assert client.get("/api/household").json()["count_by"] == "days"
        changed = client.patch("/api/household", json={"count_by": "hours"})
        assert changed.status_code == 200, changed.text
        assert changed.json()["count_by"] == "hours"
        assert client.get("/api/household").json()["count_by"] == "hours"
        assert client.patch("/api/household", json={"count_by": "weeks"}).status_code == 422


class TestMinutes:
    def _lesson(self, db: Session) -> Assignment:
        household = get_default_household(db)
        student = Student(household_id=household.id, name="Ada")
        db.add(student)
        db.flush()
        lesson = Assignment(student_id=student.id, title="Spelling list 3", scheduled_date=MONDAY,
                            status=AssignmentStatus.ASSIGNED)
        db.add(lesson)
        db.flush()
        return lesson

    def test_minutes_at_check_off_and_in_the_editor(self, client: TestClient, db: Session) -> None:
        lesson = self._lesson(db)
        done = client.patch(f"/api/assignments/{lesson.id}/status", json={"status": "completed", "minutes": 25})
        assert done.status_code == 200 and done.json()["minutes"] == 25
        # Checking off again without minutes keeps them.
        again = client.patch(f"/api/assignments/{lesson.id}/status", json={"status": "completed"}).json()
        assert again["minutes"] == 25
        edited = client.put(f"/api/assignments/{lesson.id}", json={"minutes": 30}).json()
        assert edited["minutes"] == 30
        cleared = client.put(f"/api/assignments/{lesson.id}", json={"minutes": None}).json()
        assert cleared["minutes"] is None
        assert client.put(f"/api/assignments/{lesson.id}", json={"minutes": 0}).status_code == 422

    def test_scheduling_estimates_minutes(self, client: TestClient, db: Session, ada: int) -> None:
        textbook = _textbook(client, lessons=3)
        # The second lesson has its own length in the lesson list.
        lessons = client.get(f"/api/library/{textbook['id']}").json()["lessons"]
        client.put(f"/api/library/{textbook['id']}/lessons", json=[
            {"number": row["number"], "name": row["name"], "start_page": row["start_page"],
             "end_page": row["end_page"], **({"minutes": 50} if row["number"] == 2 else {})}
            for row in lessons
        ])
        body = _curriculum(client, textbook, (_online(client), "online"))
        result = client.post(f"/api/planner/curricula/{body['id']}/schedule", json={
            "student_ids": [ada], "start_date": MONDAY.isoformat(), "minutes_per_lesson": 40})
        assert result.status_code == 201, result.text
        assert result.json()["courses"][0]["default_minutes"] == 40
        assert db.scalars(select(Course)).one().default_minutes == 40
        rows = db.scalars(select(Assignment).order_by(Assignment.scheduled_date, Assignment.id)).all()
        by_title = {row.title: row.minutes for row in rows}
        assert by_title["BJU Reading 4 · Lesson 1: Story 1 (pp. 1–2)"] == 40
        assert by_title["BJU Reading 4 · Lesson 2: Story 2 (pp. 3–4)"] == 50
        assert {row.minutes for row in rows if "IXL" in row.title} == {15}  # the site's session length
