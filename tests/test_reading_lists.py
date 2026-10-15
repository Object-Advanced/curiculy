"""Reading lists: tracked books move when the parent says; scheduled books also
move as their lessons are checked off. See docs/6-planning/product-spine.md."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus
from app.models import Assignment, Course, ReadingListEntry, SchoolYear, Student
from app.services import clock
from app.services.households import get_default_household
from tests.test_planner import MONDAY, _add, _curriculum, _novel, _textbook

TODAY = date(2026, 10, 15)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr(clock, "_now", lambda: datetime(2026, 10, 15, 16, tzinfo=timezone.utc))
    return TODAY


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


def _track(client: TestClient, student_id: int, book: dict, **fields) -> dict:
    response = client.post("/api/reading-list", json={"student_id": student_id, "library_item_id": book["id"], **fields})
    assert response.status_code == 201, response.text
    return response.json()


def _check_off(db: Session, lessons: list[Assignment], day: date) -> None:
    for lesson in lessons:
        lesson.status = AssignmentStatus.COMPLETED
        lesson.completion_date = day
    db.flush()


class TestTracking:
    def test_track_start_and_finish(self, client: TestClient, ada: int) -> None:
        entry = _track(client, ada, _novel(client))
        assert (entry["status"], entry["status_label"], entry["source"]) == ("up_next", "Up next", "tracked")
        assert (entry["counts_toward"], entry["counts_toward_name"]) == ("english", "English and language arts")
        assert entry["book"]["title"] == "Charlotte's Web" and entry["student_name"] == "Ada"
        assert entry["school_year_id"] is not None and entry["scheduled"] is False

        started = client.patch(f"/api/reading-list/{entry['id']}", json={"status": "reading"}).json()
        assert (started["status"], started["started_on"], started["finished_on"]) == ("reading", "2026-10-15", None)
        finished = client.patch(f"/api/reading-list/{entry['id']}", json={"status": "finished"}).json()
        assert (finished["started_on"], finished["finished_on"]) == ("2026-10-15", "2026-10-15")
        back = client.patch(f"/api/reading-list/{entry['id']}", json={"status": "up_next"}).json()
        assert (back["started_on"], back["finished_on"]) == (None, None)

    def test_a_book_read_last_summer_with_its_dates(self, client: TestClient, ada: int) -> None:
        entry = _track(client, ada, _novel(client), status="finished",
                       started_on="2026-06-01", finished_on="2026-06-20", counts_toward="us_history")
        assert (entry["started_on"], entry["finished_on"]) == ("2026-06-01", "2026-06-20")
        assert entry["counts_toward_name"] == "U.S. and state history"
        wrong = client.patch(f"/api/reading-list/{entry['id']}", json={"finished_on": "2026-05-01"})
        assert wrong.status_code == 422

    def test_finished_without_a_start_date_started_the_same_day(self, client: TestClient, ada: int) -> None:
        entry = _track(client, ada, _novel(client), status="finished", finished_on="2026-09-30")
        assert (entry["started_on"], entry["finished_on"]) == ("2026-09-30", "2026-09-30")

    def test_only_books_to_read_once_per_child(self, client: TestClient, ada: int) -> None:
        book = _novel(client)
        _track(client, ada, book)
        again = client.post("/api/reading-list", json={"student_id": ada, "library_item_id": book["id"]})
        assert again.status_code == 409
        textbook = _textbook(client)
        response = client.post("/api/reading-list", json={"student_id": ada, "library_item_id": textbook["id"]})
        assert response.status_code == 422 and "Only books to read" in response.json()["detail"]
        assert client.post("/api/reading-list", json={"student_id": 9999, "library_item_id": book["id"]}).status_code == 404
        assert client.post("/api/reading-list", json={
            "student_id": ada, "library_item_id": book["id"], "counts_toward": "basket_weaving"}).status_code == 422

    def test_a_family_read_aloud_and_the_lists(self, client: TestClient, db: Session, ada: int) -> None:
        household = get_default_household(db)
        ben = Student(household_id=household.id, name="Ben")
        db.add(ben)
        db.flush()
        hobbit, web = _novel(client, "The Hobbit"), _novel(client)
        for child in (ada, ben.id):
            _track(client, child, hobbit, status="reading")
        done = _track(client, ada, web, status="finished")

        adas = client.get("/api/reading-list", params={"student_id": ada}).json()
        assert [(row["book"]["title"], row["status"]) for row in adas] == [
            ("The Hobbit", "reading"), ("Charlotte's Web", "finished")]
        readers = client.get("/api/reading-list", params={"library_item_id": hobbit["id"]}).json()
        assert sorted(row["student_name"] for row in readers) == ["Ada", "Ben"]

        assert client.delete(f"/api/reading-list/{done['id']}").status_code == 204
        assert client.delete(f"/api/reading-list/{done['id']}").status_code == 404
        assert len(client.get("/api/reading-list", params={"student_id": ada}).json()) == 1

    def test_removing_the_book_takes_its_entries(self, client: TestClient, db: Session, ada: int) -> None:
        book = _novel(client)
        _track(client, ada, book)
        assert client.delete(f"/api/library/{book['id']}").status_code == 204
        assert client.get("/api/reading-list").json() == []


class TestScheduled:
    def _schedule_alone(self, client: TestClient, book: dict, student_id: int) -> None:
        response = client.post(f"/api/library/{book['id']}/schedule", json={
            "student_ids": [student_id], "start_date": MONDAY.isoformat(), "pages_per_day": 46})
        assert response.status_code == 201, response.text

    def _lessons(self, db: Session) -> list[Assignment]:
        return list(db.scalars(select(Assignment).order_by(Assignment.scheduled_date)).all())

    def test_scheduling_puts_it_on_the_list_and_lessons_move_it_along(
        self, client: TestClient, db: Session, ada: int
    ) -> None:
        book = _novel(client)
        self._schedule_alone(client, book, ada)
        [entry] = client.get("/api/reading-list", params={"student_id": ada}).json()
        assert (entry["status"], entry["source"], entry["scheduled"]) == ("up_next", "scheduled", True)
        assert (entry["lessons_total"], entry["lessons_done"]) == (4, 0)

        lessons = self._lessons(db)
        _check_off(db, lessons[:1], date(2026, 10, 12))
        [entry] = client.get("/api/reading-list", params={"student_id": ada}).json()
        assert (entry["status"], entry["started_on"], entry["lessons_done"]) == ("reading", "2026-10-12", 1)

        _check_off(db, lessons[1:], date(2026, 10, 15))
        [entry] = client.get("/api/reading-list", params={"student_id": ada}).json()
        assert (entry["status"], entry["finished_on"]) == ("finished", "2026-10-15")

    def test_a_skipped_day_still_lets_the_book_finish(self, client: TestClient, db: Session, ada: int) -> None:
        self._schedule_alone(client, _novel(client), ada)
        lessons = self._lessons(db)
        _check_off(db, lessons[:3], date(2026, 10, 14))
        lessons[3].status = AssignmentStatus.SKIPPED
        db.flush()
        [entry] = client.get("/api/reading-list").json()
        assert entry["status"] == "finished"

    def test_the_parent_can_mark_it_finished_early(self, client: TestClient, db: Session, ada: int) -> None:
        self._schedule_alone(client, _novel(client), ada)
        [entry] = client.get("/api/reading-list").json()
        early = client.patch(f"/api/reading-list/{entry['id']}", json={"status": "finished"}).json()
        assert (early["status"], early["finished_on"], early["lessons_done"]) == ("finished", "2026-10-15", 0)

    def test_a_book_inside_a_curriculum_counts_toward_its_subject(
        self, client: TestClient, ada: int
    ) -> None:
        textbook = _textbook(client, subject_code="us_history", title="Our Nation")
        book = _add(client, kind="reading_book", title="Johnny Tremain", author="Esther Forbes", total_pages=60)
        body = _curriculum(client, textbook, (book, "reading"))
        response = client.post(f"/api/planner/curricula/{body['id']}/schedule", json={
            "student_ids": [ada], "start_date": MONDAY.isoformat()})
        assert response.status_code == 201, response.text
        [entry] = client.get("/api/reading-list").json()
        assert (entry["book"]["title"], entry["counts_toward"]) == ("Johnny Tremain", "us_history")

    def test_unscheduling_keeps_what_was_read(self, client: TestClient, db: Session, ada: int) -> None:
        unread, started = _novel(client), _novel(client, "The Hobbit")
        self._schedule_alone(client, unread, ada)
        self._schedule_alone(client, started, ada)
        hobbit_lessons = [row for row in self._lessons(db) if "Hobbit" in row.title]
        _check_off(db, hobbit_lessons[:1], date(2026, 10, 12))

        for course in db.scalars(select(Course)).all():
            assert client.delete(f"/api/planner/courses/{course.id}").status_code == 200
        [entry] = client.get("/api/reading-list").json()
        assert (entry["book"]["title"], entry["status"], entry["source"]) == ("The Hobbit", "reading", "tracked")
        assert (entry["started_on"], entry["scheduled"]) == ("2026-10-12", False)

    def test_scheduling_a_tracked_book_keeps_its_entry(self, client: TestClient, db: Session, ada: int) -> None:
        book = _novel(client)
        tracked = _track(client, ada, book, counts_toward="science")
        self._schedule_alone(client, book, ada)
        [entry] = client.get("/api/reading-list").json()
        assert (entry["id"], entry["source"], entry["counts_toward"]) == (tracked["id"], "scheduled", "science")
        assert len(db.scalars(select(ReadingListEntry)).all()) == 1
