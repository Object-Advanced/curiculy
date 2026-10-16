"""The move engine: previews first, lessons keep their order, finished lessons
never move, and applying saves exactly what was previewed."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus
from app.models import Assignment, CalendarException, Course, SchoolYear, Student
from app.services import clock
from app.services.households import get_default_household
from tests.test_planner import _add, _curriculum, _workbook

MONDAY = date(2026, 10, 12)
TODAY = date(2026, 10, 15)  # a Thursday


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr(clock, "_now", lambda: datetime(2026, 10, 15, 16, tzinfo=timezone.utc))
    return TODAY


@pytest.fixture
def ada(db: Session) -> int:
    household = get_default_household(db)
    db.add(SchoolYear(household_id=household.id, name="2026–27", start_date=date(2026, 8, 1),
                      end_date=date(2027, 6, 4)))
    student = Student(household_id=household.id, name="Ada")
    db.add(student)
    db.flush()
    return student.id


def _course(client: TestClient, student_id: int, lessons: int = 40, types: dict[int, str] | None = None,
            workbook: bool = False) -> int:
    """Saxon 5/4, four days a week from Monday Oct 12: Mon–Thu, so Fridays are free."""
    textbook = _add(client, kind="textbook", title="Saxon 5/4", publisher="Saxon", edition="3rd",
                    subject_code="math", grade="4", total_pages=400, days_per_week=4)
    response = client.put(f"/api/library/{textbook['id']}/lessons", json=[
        {"number": n, "name": f"Part {n}", "type": (types or {}).get(n, "lesson"), "start_page": n * 2 - 1,
         "end_page": n * 2}
        for n in range(1, lessons + 1)
    ])
    assert response.status_code == 200, response.text
    body = _curriculum(client, textbook, *([(_workbook(client), "workbook")] if workbook else []))
    scheduled = client.post(f"/api/planner/curricula/{body['id']}/schedule",
                            json={"student_ids": [student_id], "start_date": MONDAY.isoformat()})
    assert scheduled.status_code == 201, scheduled.text
    return scheduled.json()["courses"][0]["id"]


def _rows(db: Session, course_id: int) -> list[Assignment]:
    """The textbook's lessons, in lesson order."""
    rows = db.scalars(select(Assignment).where(Assignment.course_id == course_id).order_by(Assignment.id)).all()
    return [row for row in rows if row.title.startswith("Saxon 5/4 ·")]


def _dates(db: Session, course_id: int) -> list[date]:
    return [row.scheduled_date for row in _rows(db, course_id)]


def _preview(client: TestClient, request: dict) -> dict:
    response = client.post("/api/moves/preview", json=request)
    assert response.status_code == 200, response.text
    return response.json()


def _apply(client: TestClient, request: dict) -> dict:
    plan = _preview(client, request)
    response = client.post("/api/moves/apply", json={"request": request, "plan_hash": plan["plan_hash"]})
    assert response.status_code == 200, response.text
    return response.json()


def _lesson(db: Session, course_id: int, number: int) -> Assignment:
    return _rows(db, course_id)[number - 1]


class TestCatchUp:
    def test_behind_lists_courses_with_missed_lessons(self, client: TestClient, ada: int) -> None:
        course_id = _course(client, ada)
        [behind] = client.get("/api/moves/behind").json()
        assert (behind["course_id"], behind["student_name"], behind["behind"], behind["behind_since"]) == (
            course_id, "Ada", 3, "2026-10-12")

    def test_the_sheet_offers_each_workable_option_and_recommends_one(
        self, client: TestClient, db: Session, ada: int
    ) -> None:
        course_id = _course(client, ada)
        sheet = client.get(f"/api/moves/catch-up/{course_id}").json()
        assert (sheet["course_name"], sheet["behind"], sheet["behind_since"]) == ("Saxon 5/4", 3, "2026-10-12")
        choices = {choice["option"]: choice for choice in sheet["choices"]}
        assert list(choices) == ["use_day_off", "double_up", "push_back", "push_week", "skip"]
        # Three free Fridays before Oct 30 absorb the three missed days; nothing after them moves.
        assert choices["use_day_off"]["workable"] and choices["use_day_off"]["recommended"]
        assert choices["use_day_off"]["result"] == "Finishes Thu, Dec 17, on time"
        assert choices["push_back"]["result"] == "Finishes Wed, Dec 23, on time"
        assert not choices["skip"]["workable"] and "Only review lessons" in choices["skip"]["why_not"]
        assert [c for c in sheet["choices"] if c["recommended"]] == [choices["use_day_off"]]
        assert db.scalars(select(Assignment).where(Assignment.scheduled_date < TODAY,
                                                   Assignment.status == AssignmentStatus.ASSIGNED)).all()

    def test_use_a_day_off(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        before = _dates(db, course_id)
        _apply(client, {"kind": "catch_up", "course_id": course_id, "option": "use_day_off"})
        after = _dates(db, course_id)
        assert after[:12] == [date(2026, 10, d) for d in (15, 16, 19, 20, 21, 22, 23, 26, 27, 28, 29, 30)]
        assert after[12:] == before[12:]  # nothing after the last free day moves
        assert after == sorted(after)  # lessons keep their order
        assert client.get("/api/moves/behind").json() == []

    def test_double_up_until_caught_up(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        before = _dates(db, course_id)
        _apply(client, {"kind": "catch_up", "course_id": course_id, "option": "double_up"})
        after = _dates(db, course_id)
        assert after[:6] == [date(2026, 10, d) for d in (15, 15, 19, 19, 20, 20)]
        assert after[6:] == before[6:]

    def test_push_back_and_a_whole_week(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        preview = _preview(client, {"kind": "catch_up", "course_id": course_id, "option": "push_week"})
        [effect] = preview["courses"]
        assert effect["course_name"] == "Saxon 5/4" and effect["lessons_moved"] == 40
        _apply(client, {"kind": "catch_up", "course_id": course_id, "option": "push_back"})
        assert _dates(db, course_id)[:4] == [date(2026, 10, 15), date(2026, 10, 19), date(2026, 10, 20),
                                             date(2026, 10, 21)]
        assert db.get(Course, course_id).end_date == date(2026, 12, 23)

    def test_skip_review_lessons(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada, types={1: "review", 2: "review", 3: "review"})
        sheet = client.get(f"/api/moves/catch-up/{course_id}").json()
        skip = next(choice for choice in sheet["choices"] if choice["option"] == "skip")
        assert skip["workable"] and skip["result"].startswith("Skips 3 review lessons") and not skip["recommended"]
        result = _apply(client, {"kind": "catch_up", "course_id": course_id, "option": "skip"})
        assert (result["moved"], result["skipped"]) == (0, 3)
        assert _lesson(db, course_id, 1).status == AssignmentStatus.SKIPPED

    def test_double_up_when_more_is_missed_than_is_left(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada, lessons=5)  # Oct 12–15 and 19: 3 missed, 2 left
        sheet = client.get(f"/api/moves/catch-up/{course_id}").json()
        double = next(choice for choice in sheet["choices"] if choice["option"] == "double_up")
        assert double["workable"] and double["result"] == "Finishes Tue, Oct 20, on time"
        _apply(client, {"kind": "catch_up", "course_id": course_id, "option": "double_up"})
        assert _dates(db, course_id) == [date(2026, 10, 15), date(2026, 10, 15), date(2026, 10, 19),
                                         date(2026, 10, 19), date(2026, 10, 20)]

    def test_double_up_never_on_a_test_day_and_stays_under_the_limit(
        self, client: TestClient, db: Session, ada: int
    ) -> None:
        course_id = _course(client, ada, workbook=True)  # two lessons a day: the textbook and the worktext
        assert client.patch("/api/household", json={"daily_lesson_limit": 3}).status_code == 200
        sheet = client.get(f"/api/moves/catch-up/{course_id}").json()
        double = next(choice for choice in sheet["choices"] if choice["option"] == "double_up")
        assert not double["workable"] and double["why_not"] == "Every day is at your limit of 3 lessons."
        assert sheet["daily_lesson_limit"] == 3
        assert client.patch("/api/household", json={"daily_lesson_limit": None}).json()["daily_lesson_limit"] is None

    def test_a_test_bounds_the_free_days(self, client: TestClient, ada: int) -> None:
        course_id = _course(client, ada, types={5: "test"})  # Lesson 5 is Mon, Oct 19
        sheet = client.get(f"/api/moves/catch-up/{course_id}").json()
        free = next(choice for choice in sheet["choices"] if choice["option"] == "use_day_off")
        assert not free["workable"] and free["why_not"] == "Not enough free days before the test on Mon, Oct 19."
        weekends = client.get(f"/api/moves/catch-up/{course_id}", params={"allow_weekends": True}).json()
        free = next(choice for choice in weekends["choices"] if choice["option"] == "use_day_off")
        assert free["workable"]
        assert any("lands on Sat, Oct 17, not a school day" in warning or "land on Sat, Oct 17" in warning
                   for warning in free["preview"]["warnings"])

    def test_nothing_to_catch_up(self, client: TestClient, ada: int) -> None:
        course_id = _course(client, ada)
        _apply(client, {"kind": "catch_up", "course_id": course_id, "option": "push_back"})
        response = client.post("/api/moves/preview", json={"kind": "catch_up", "course_id": course_id,
                                                           "option": "push_back"})
        assert response.status_code == 409 and "Nothing to catch up" in response.json()["detail"]


class TestOneLesson:
    def test_push_the_rest_back(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        before = _dates(db, course_id)
        lesson = _lesson(db, course_id, 5)  # Mon, Oct 19
        preview = _preview(client, {"kind": "lesson", "assignment_id": lesson.id, "to_date": "2026-10-20"})
        assert preview["summary"] == "36 lessons move."
        _apply(client, {"kind": "lesson", "assignment_id": lesson.id, "to_date": "2026-10-20"})
        after = _dates(db, course_id)
        assert after[:4] == before[:4]
        assert after[4:7] == [date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22)]
        assert after[39] > before[39]

    def test_just_this_one_keeps_the_order(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        before = _dates(db, course_id)
        lesson = _lesson(db, course_id, 5)  # Mon, Oct 19 → Wed, Oct 21
        request = {"kind": "lesson", "assignment_id": lesson.id, "to_date": "2026-10-21", "mode": "just_this"}
        assert _preview(client, request)["summary"] == "2 lessons move."
        _apply(client, request)
        after = _dates(db, course_id)
        assert after[4:7] == [date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 21)]  # Monday is free
        assert after[7:] == before[7:] and after == sorted(after)

    def test_just_this_one_earlier(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        lesson = _lesson(db, course_id, 6)  # Tue, Oct 20 → Fri, Oct 16
        _apply(client, {"kind": "lesson", "assignment_id": lesson.id, "to_date": "2026-10-16", "mode": "just_this"})
        after = _dates(db, course_id)
        # Lesson 5 takes Friday, Lesson 6 takes Monday; Tuesday is free.
        assert after[3:7] == [date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 19), date(2026, 10, 21)]
        assert after == sorted(after)

    def test_pulling_forward_past_earlier_lessons_is_refused(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        lesson = _lesson(db, course_id, 6)  # Tue, Oct 20; Lesson 5 is Mon, Oct 19
        response = client.post("/api/moves/preview", json={
            "kind": "lesson", "assignment_id": lesson.id, "to_date": "2026-10-16"})
        assert response.status_code == 409 and "comes first" in response.json()["detail"]

    def test_a_saturday_is_allowed_with_a_warning(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        lesson = _lesson(db, course_id, 40)
        preview = _preview(client, {"kind": "lesson", "assignment_id": lesson.id, "to_date": "2027-01-02"})
        assert preview["warnings"] == ["1 lesson lands on Sat, Jan 2, not a school day for Ada."]

    def test_finishing_after_the_year_is_flagged(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        lesson = _lesson(db, course_id, 40)
        preview = _preview(client, {"kind": "lesson", "assignment_id": lesson.id, "to_date": "2027-06-07"})
        assert preview["warnings"] == [
            "Saxon 5/4 now finishes Mon, Jun 7, after your school year ends Fri, Jun 4."]
        [effect] = preview["courses"]
        assert (effect["finish_before"], effect["finish_after"]) == ("2026-12-17", "2027-06-07")

    def test_finished_lessons_never_move(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        done = _lesson(db, course_id, 6)
        done.status = AssignmentStatus.COMPLETED
        done.completion_date = TODAY
        db.flush()
        response = client.post("/api/moves/preview", json={
            "kind": "lesson", "assignment_id": done.id, "to_date": "2026-10-22"})
        assert response.status_code == 409 and "finished lesson" in response.json()["detail"]
        _apply(client, {"kind": "lesson", "assignment_id": _lesson(db, course_id, 5).id, "to_date": "2026-10-22"})
        assert done.scheduled_date == date(2026, 10, 20)

    def test_bad_days(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        lesson = _lesson(db, course_id, 5)
        past = client.post("/api/moves/preview", json={"kind": "lesson", "assignment_id": lesson.id,
                                                       "to_date": "2026-10-14"})
        assert past.status_code == 422
        same = client.post("/api/moves/preview", json={"kind": "lesson", "assignment_id": lesson.id,
                                                       "to_date": "2026-10-19"})
        assert same.status_code == 422
        assert client.post("/api/moves/preview", json={"kind": "lesson", "assignment_id": 9999,
                                                       "to_date": "2026-10-19"}).status_code == 404


class TestDayAndCourse:
    def test_a_sick_day_moves_each_course_and_the_loose_lessons(
        self, client: TestClient, db: Session, ada: int
    ) -> None:
        course_id = _course(client, ada)
        loose = Assignment(student_id=ada, title="Piano", scheduled_date=TODAY, status=AssignmentStatus.ASSIGNED)
        db.add(loose)
        db.flush()
        before = _dates(db, course_id)
        preview = _preview(client, {"kind": "day", "date": "2026-10-15", "student_ids": [ada]})
        assert preview["changes"][0]["title"].startswith("Saxon 5/4 · Lesson 4")  # Thursday's lesson
        _apply(client, {"kind": "day", "date": "2026-10-15", "student_ids": [ada]})
        after = _dates(db, course_id)
        assert after[:3] == before[:3]  # days that passed before the sick day stay
        assert after[3] == date(2026, 10, 19) and after == sorted(after)
        assert loose.scheduled_date == date(2026, 10, 16)

    def test_a_day_off_ahead_goes_on_the_calendar(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        request = {"kind": "day", "date": "2026-10-20", "add_to_calendar": "off", "title": "Co-op field day"}
        preview = _preview(client, request)
        assert preview["notes"] == ["Adds “Co-op field day” to the family calendar on Tue, Oct 20."]
        _apply(client, request)
        [day_off] = db.scalars(select(CalendarException)).all()
        assert (day_off.title, day_off.student_id, day_off.start_date) == ("Co-op field day", None, date(2026, 10, 20))
        assert date(2026, 10, 20) not in _dates(db, course_id)
        past = client.post("/api/moves/preview", json={**request, "date": "2026-10-14"})
        assert past.status_code == 422

    def test_new_days_and_a_pause(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        request = {"kind": "course", "course_id": course_id, "weekdays": [0, 2, 4]}
        assert _preview(client, request)["notes"] == ["Saxon 5/4 meets on Monday, Wednesday, Friday from now on."]
        _apply(client, request)
        after = _dates(db, course_id)
        assert {day.weekday() for day in after if day >= TODAY} == {0, 2, 4}
        assert db.get(Course, course_id).weekdays == "0,2,4"

        pause = {"kind": "course", "course_id": course_id, "pause_from": "2026-11-23", "pause_to": "2026-11-27"}
        _apply(client, pause)
        assert not [day for day in _dates(db, course_id) if date(2026, 11, 23) <= day <= date(2026, 11, 27)]
        bad = client.post("/api/moves/preview", json={"kind": "course", "course_id": course_id,
                                                      "pause_from": "2026-11-23"})
        assert bad.status_code == 422


class TestApply:
    def test_a_stale_preview_saves_nothing(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        request = {"kind": "catch_up", "course_id": course_id, "option": "push_back"}
        plan = _preview(client, request)
        _lesson(db, course_id, 1).status = AssignmentStatus.COMPLETED  # checked off in another tab
        db.flush()
        before = _dates(db, course_id)
        response = client.post("/api/moves/apply", json={"request": request, "plan_hash": plan["plan_hash"]})
        assert response.status_code == 409 and "changed since this preview" in response.json()["detail"]
        assert _dates(db, course_id) == before

    def test_previews_save_nothing(self, client: TestClient, db: Session, ada: int) -> None:
        course_id = _course(client, ada)
        before = _dates(db, course_id)
        for option in ("push_back", "push_week", "use_day_off", "double_up"):
            _preview(client, {"kind": "catch_up", "course_id": course_id, "option": option})
        client.get(f"/api/moves/catch-up/{course_id}")
        assert _dates(db, course_id) == before
