"""Attendance suggestions: the "School today?" card, confirming it, and the
year's counts. Nothing is recorded without the parent's tap."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, AttendanceStatus, ExceptionKind
from app.models import Activity, ActivityStudent, Assignment, Attendance, CalendarException, SchoolYear, Student
from app.services import clock
from app.services.households import get_default_household

TODAY = date(2026, 10, 15)  # a Thursday
SATURDAY = date(2026, 10, 10)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr(clock, "_now", lambda: datetime(2026, 10, 15, 16, tzinfo=timezone.utc))
    return TODAY


@pytest.fixture
def kids(db: Session) -> tuple[int, int]:
    household = get_default_household(db)
    db.add(SchoolYear(household_id=household.id, name="2026–27", start_date=date(2026, 10, 5),
                      end_date=date(2026, 10, 30)))
    ada, ben = Student(household_id=household.id, name="Ada"), Student(household_id=household.id, name="Ben")
    db.add_all([ada, ben])
    db.flush()
    return ada.id, ben.id


def _lesson(db: Session, student_id: int, day: date, *, done_on: date | None = None, minutes: int | None = None,
            status: AssignmentStatus | None = None) -> Assignment:
    lesson = Assignment(
        student_id=student_id, title="Lesson", scheduled_date=day, minutes=minutes,
        status=status or (AssignmentStatus.COMPLETED if done_on else AssignmentStatus.ASSIGNED),
        completion_date=done_on,
    )
    db.add(lesson)
    db.flush()
    return lesson


def _activity(db: Session, student_id: int, day: date, title: str = "5K race", minutes: int | None = 40) -> None:
    activity = Activity(title=title, on_date=day, minutes=minutes, subject_codes=["pe"])
    activity.students.append(ActivityStudent(student_id=student_id))
    db.add(activity)
    db.flush()


def _day_off(db: Session, day: date, title: str, student_id: int | None = None,
             kind: ExceptionKind = ExceptionKind.HOLIDAY) -> None:
    household = get_default_household(db)
    db.add(CalendarException(household_id=household.id, student_id=student_id, kind=kind, title=title,
                             start_date=day, end_date=day))
    db.flush()


def _card(client: TestClient, **params) -> dict:
    response = client.get("/api/attendance/days", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _children(day: dict) -> dict[str, dict]:
    return {child["name"]: child for child in day["children"]}


class TestToday:
    def test_work_done_today_suggests_present_and_nothing_is_saved(
        self, client: TestClient, db: Session, kids: tuple[int, int]
    ) -> None:
        ada, ben = kids
        _lesson(db, ada, TODAY, done_on=TODAY)
        _lesson(db, ada, TODAY, done_on=TODAY)
        _lesson(db, ben, TODAY)
        _lesson(db, ben, TODAY, status=AssignmentStatus.IN_PROGRESS)
        body = _card(client)
        assert body["today"] == "2026-10-15" and body["count_by"] == "days"
        [day] = body["days"]
        assert (day["date"], day["weekday"], day["school_day"], day["day_off"]) == ("2026-10-15", "Thursday", True, None)
        children = _children(day)
        assert children["Ada"]["suggestion"] == "Present" and children["Ada"]["reasons"] == ["Finished 2 lessons"]
        assert children["Ada"]["status"] is None and children["Ada"]["expected"] is True
        assert children["Ben"]["suggestion"] == "Present" and children["Ben"]["reasons"] == ["Started 1 lesson"]
        assert db.scalars(select(Attendance)).all() == []

    def test_a_school_day_with_nothing_done_waits_for_the_parent(
        self, client: TestClient, db: Session, kids: tuple[int, int]
    ) -> None:
        ada, _ = kids
        _lesson(db, ada, TODAY)
        children = _children(_card(client)["days"][0])
        assert children["Ada"]["suggestion"] is None and children["Ada"]["expected"] is True
        assert children["Ada"]["reasons"] == ["1 lesson planned, none checked off yet"]
        assert children["Ben"]["reasons"] == ["Nothing planned in Curiculy"]

    def test_a_sick_day_on_the_calendar_suggests_sick(
        self, client: TestClient, db: Session, kids: tuple[int, int]
    ) -> None:
        ada, ben = kids
        _day_off(db, TODAY, "Flu", student_id=ada, kind=ExceptionKind.SICK)
        _day_off(db, TODAY, "Dentist", student_id=ben, kind=ExceptionKind.APPOINTMENT)
        children = _children(_card(client)["days"][0])
        assert (children["Ada"]["suggestion"], children["Ada"]["reasons"]) == ("Sick", ["Sick day on the calendar: Flu"])
        assert (children["Ben"]["expected"], children["Ben"]["reasons"]) == (False, ["Day off: Dentist"])

    def test_days_off_and_weekends_ask_nothing_unless_work_was_done(
        self, client: TestClient, db: Session, kids: tuple[int, int]
    ) -> None:
        ada, _ = kids
        _day_off(db, date(2026, 10, 12), "Columbus Day")
        _lesson(db, ada, date(2026, 10, 9), done_on=SATURDAY, minutes=30)
        body = _card(client, start_date="2026-10-10", end_date="2026-10-12")
        saturday, sunday, monday = body["days"]
        assert (saturday["school_day"], sunday["school_day"], monday["school_day"]) == (False, False, False)
        assert monday["day_off"] == "Columbus Day"
        ada_saturday = _children(saturday)["Ada"]
        assert ada_saturday["suggestion"] == "Present" and ada_saturday["expected"] is True
        assert ada_saturday["reasons"] == ["Finished 1 lesson", "Not a school day on your calendar. Count Saturday as one?"]
        assert _children(saturday)["Ben"]["expected"] is False
        assert _children(monday)["Ben"]["reasons"] == ["Day off: Columbus Day"]

    def test_activities_count_and_minutes_add_up(self, client: TestClient, db: Session, kids: tuple[int, int]) -> None:
        ada, ben = kids
        _activity(db, ben, TODAY)
        _lesson(db, ada, TODAY, done_on=TODAY, minutes=45)
        _lesson(db, ada, TODAY, done_on=TODAY)
        _activity(db, ada, TODAY, "Piano", 20)
        children = _children(_card(client)["days"][0])
        assert children["Ben"]["suggestion"] == "Present" and children["Ben"]["reasons"] == ["Did an activity: 5K race"]
        assert children["Ada"]["activities"] == ["Piano"]
        assert (children["Ada"]["minutes"], children["Ada"]["minutes_from_work"]) == (65, 65)
        assert children["Ada"]["lessons_without_minutes"] == 1

    def test_a_window_and_one_child(self, client: TestClient, kids: tuple[int, int]) -> None:
        ada, _ = kids
        body = _card(client, start_date="2026-10-05", end_date="2026-10-09", student_id=ada)
        assert len(body["days"]) == 5 and [c["name"] for c in body["days"][0]["children"]] == ["Ada"]
        too_long = client.get("/api/attendance/days", params={"start_date": "2026-08-01", "end_date": "2026-10-15"})
        assert too_long.status_code == 422
        backwards = client.get("/api/attendance/days", params={"start_date": "2026-10-15", "end_date": "2026-10-14"})
        assert backwards.status_code == 422
        assert client.get("/api/attendance/days", params={"student_id": 9999}).status_code == 404


class TestConfirm:
    def test_looks_right_records_each_child_and_how(self, client: TestClient, db: Session, kids: tuple[int, int]) -> None:
        ada, ben = kids
        _lesson(db, ada, TODAY, done_on=TODAY)
        response = client.post("/api/attendance/confirm", json={"marks": [
            {"student_id": ada, "date": "2026-10-15", "status": "Present"},
            {"student_id": ben, "date": "2026-10-15", "status": "Field trip"},
        ]})
        assert response.status_code == 200, response.text
        assert [(row["status"], row["source"]) for row in response.json()] == [
            ("Present", "suggestion"), ("Field trip", "parent")]
        children = _children(_card(client)["days"][0])
        assert (children["Ada"]["status"], children["Ada"]["source"]) == ("Present", "suggestion")
        listed = client.get("/api/attendance", params={"start_date": "2026-10-15", "end_date": "2026-10-15"}).json()
        assert {(row["status"], row["source"]) for row in listed} == {("Present", "suggestion"), ("Field trip", "parent")}

        # Changing it later is the parent's own choice, on the same row.
        again = client.post("/api/attendance/confirm", json={"marks": [
            {"student_id": ada, "date": "2026-10-15", "status": "Sick"}]}).json()
        assert (again[0]["status"], again[0]["source"]) == ("Sick", "parent")
        assert len(db.scalars(select(Attendance)).all()) == 2

    def test_minutes_change_only_when_sent(self, client: TestClient, kids: tuple[int, int]) -> None:
        ada, _ = kids
        mark = {"student_id": ada, "date": "2026-10-14", "status": "Present"}
        first = client.post("/api/attendance/confirm", json={"marks": [{**mark, "minutes": 240}]}).json()
        assert first[0]["minutes"] == 240
        kept = client.post("/api/attendance/confirm", json={"marks": [mark]}).json()
        assert kept[0]["minutes"] == 240
        cleared = client.post("/api/attendance/confirm", json={"marks": [{**mark, "minutes": None}]}).json()
        assert cleared[0]["minutes"] is None
        assert _children(_card(client, start_date="2026-10-14")["days"][0])["Ada"]["minutes"] is None

    def test_only_days_that_have_happened(self, client: TestClient, kids: tuple[int, int]) -> None:
        ada, _ = kids
        future = client.post("/api/attendance/confirm", json={"marks": [
            {"student_id": ada, "date": "2026-10-16", "status": "Present"}]})
        assert future.status_code == 422 and "hasn't happened" in future.json()["detail"]
        assert client.post("/api/attendance/confirm", json={"marks": [
            {"student_id": 9999, "date": "2026-10-15", "status": "Present"}]}).status_code == 404
        assert client.post("/api/attendance/confirm", json={"marks": []}).status_code == 422
        assert client.post("/api/attendance/confirm", json={"marks": [
            {"student_id": ada, "date": "2026-10-15", "status": "Napping"}]}).status_code == 422

    def test_the_calendar_radios_are_the_parents_own_choice(self, client: TestClient, kids: tuple[int, int]) -> None:
        ada, _ = kids
        row = client.post("/api/attendance", json={"student_id": ada, "date": "2026-10-15", "status": "Present"}).json()
        assert (row["source"], row["minutes"]) == ("parent", None)


class TestSummary:
    def test_the_year_so_far_and_whats_ahead(self, client: TestClient, db: Session, kids: tuple[int, int]) -> None:
        ada, ben = kids
        # School days Oct 5–30 (Mon–Fri), minus Columbus Day: 19. Before today (Oct 15): 7.
        _day_off(db, date(2026, 10, 12), "Columbus Day")
        _lesson(db, ada, date(2026, 10, 6), done_on=date(2026, 10, 6), minutes=50)
        _activity(db, ada, date(2026, 10, 7), "Museum", 120)
        _lesson(db, ada, date(2026, 10, 9), done_on=SATURDAY)
        for day, status in [
            (date(2026, 10, 5), AttendanceStatus.PRESENT),
            (date(2026, 10, 6), AttendanceStatus.PRESENT),
            (date(2026, 10, 7), AttendanceStatus.FIELD_TRIP),
            (date(2026, 10, 8), AttendanceStatus.SICK),
            (date(2026, 10, 9), AttendanceStatus.ABSENT),
            (SATURDAY, AttendanceStatus.PRESENT),
        ]:
            db.add(Attendance(student_id=ada, date=day, status=status))
        db.add(Attendance(student_id=ada, date=date(2026, 10, 13), status=AttendanceStatus.PRESENT, minutes=200))
        db.flush()

        body = client.get("/api/attendance/summary").json()
        assert (body["school_year_name"], body["today"], body["count_by"]) == ("2026–27", "2026-10-15", "days")
        children = {child["name"]: child for child in body["children"]}
        assert children["Ada"] == {
            "student_id": ada,
            "name": "Ada",
            "present_days": 5,  # Oct 5, 6, the field trip, Saturday, Oct 13
            "field_trip_days": 1,
            "sick_days": 1,
            "absent_days": 1,
            "unmarked_days": 1,  # Oct 14
            "school_days_left": 12,  # today (unmarked) through Oct 30
            "on_track_days": 17,
            "minutes": 50 + 120 + 200,  # Saturday's lesson has no minutes
            "lessons_without_minutes": 1,
        }
        assert children["Ben"]["unmarked_days"] == 7 and children["Ben"]["on_track_days"] == 12

    def test_no_school_year_yet(self, client: TestClient, db: Session) -> None:
        body = client.get("/api/attendance/summary").json()
        assert body["school_year_id"] is None and body["children"] == []
        assert client.get("/api/attendance/summary", params={"school_year_id": 9999}).status_code == 404
