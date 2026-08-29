"""Life Happens recalibration: overdue counts and the two recovery strategies.

The fixtures sit on Friday 18 September 2026 so the weekend-catch-up case is
checkable by hand. Two leftover unique days starting that Friday land on Friday
and Monday if only weekdays count, but Friday and Saturday once Saturday is a
class day — which is what lets the following Monday keep its original work.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.services.recalibration as recalibration_service
from app.enums import AssignmentStatus, ExceptionKind
from app.models import Assignment, CalendarException, Household, Student

# Friday. The following Monday is 2026-09-21.
TODAY = date(2026, 9, 18)


@pytest.fixture
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recalibration_service, "_today", lambda: TODAY)


@pytest.fixture
def student(db: Session) -> Student:
    household = Household(name="Test Household")
    row = Student(household=household, name="Ada")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_assignment(
    db: Session,
    student: Student,
    scheduled_date: date,
    title: str | None = None,
    status: AssignmentStatus = AssignmentStatus.ASSIGNED,
) -> Assignment:
    assignment = Assignment(
        student_id=student.id,
        title=title or f"Work for {scheduled_date.isoformat()}",
        scheduled_date=scheduled_date,
        status=status,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def dates_for(db: Session, student_id: int) -> list[tuple[str, str, str]]:
    rows = (
        db.query(Assignment)
        .filter(Assignment.student_id == student_id)
        .order_by(Assignment.id)
        .all()
    )
    return [(row.title, row.scheduled_date.isoformat(), row.status.value) for row in rows]


class TestRecoveryOptions:
    def test_counts_overdue_open_work_and_skips_completed(
        self, client: TestClient, db: Session, student: Student, freeze_today: None
    ) -> None:
        add_assignment(db, student, date(2026, 9, 14), "Overdue Mon")
        add_assignment(db, student, date(2026, 9, 14), "Overdue Mon stacked")
        add_assignment(db, student, date(2026, 9, 15), "Overdue Tue")
        add_assignment(
            db,
            student,
            date(2026, 9, 16),
            "Already done",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(
            db,
            student,
            date(2026, 9, 17),
            "Skipped",
            status=AssignmentStatus.SKIPPED,
        )
        add_assignment(db, student, date(2026, 9, 21), "Next week")

        response = client.get(f"/api/recalibrate/{student.id}/options")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["student_id"] == student.id
        assert body["overdue_count"] == 3
        assert body["overdue_school_days"] == 2
        assert body["uncompleted_count"] == 4
        assert body["uncompleted_school_days"] == 3
        assert body["required_days"]["extend_year"] == 4
        assert body["required_days"]["add_weekends"] == 2
        assert body["strategies"]["extend_year"]["new_end_date"] == "2026-09-22"
        assert body["strategies"]["add_weekends"]["new_end_date"] == "2026-09-21"
        assert body["strategies"]["add_weekends"]["saturdays_used"] == 1

    def test_unknown_student_is_not_found(self, client: TestClient, freeze_today: None) -> None:
        response = client.get("/api/recalibrate/999/options")
        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"

    def test_nothing_overdue_reports_zero_days(
        self, client: TestClient, db: Session, student: Student, freeze_today: None
    ) -> None:
        add_assignment(db, student, date(2026, 9, 21), "Next week")
        response = client.get(f"/api/recalibrate/{student.id}/options")
        assert response.status_code == 200
        body = response.json()
        assert body["overdue_count"] == 0
        assert body["required_days"] == {"extend_year": 0, "add_weekends": 0}


class TestExtendYear:
    def test_pushes_open_work_forward_from_today_and_skips_exceptions(
        self, client: TestClient, db: Session, student: Student, freeze_today: None
    ) -> None:
        db.add(
            CalendarException(
                household_id=student.household_id,
                student_id=student.id,
                kind=ExceptionKind.HOLIDAY,
                title="In-service",
                start_date=date(2026, 9, 21),
                end_date=date(2026, 9, 21),
            )
        )
        db.commit()
        add_assignment(db, student, date(2026, 9, 14), "Overdue Mon")
        add_assignment(db, student, date(2026, 9, 14), "Overdue Mon stacked")
        add_assignment(db, student, date(2026, 9, 15), "Overdue Tue")
        completed = add_assignment(
            db,
            student,
            date(2026, 9, 16),
            "Already done",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(db, student, date(2026, 9, 22), "Next week")

        response = client.post(
            f"/api/recalibrate/{student.id}/execute",
            json={"strategy": "extend_year"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["strategy"] == "extend_year"
        assert body["assignments_moved"] == 4
        assert body["first_scheduled_date"] == "2026-09-18"
        # Friday 18, skip weekend, skip Monday 21 (holiday), so unique days
        # land 18, 22, 23 and the stacked Monday pair stays together.
        assert body["last_scheduled_date"] == "2026-09-23"

        by_title = {title: day for title, day, _status in dates_for(db, student.id)}
        assert by_title["Overdue Mon"] == "2026-09-18"
        assert by_title["Overdue Mon stacked"] == "2026-09-18"
        assert by_title["Overdue Tue"] == "2026-09-22"
        assert by_title["Next week"] == "2026-09-23"
        db.refresh(completed)
        assert completed.scheduled_date == date(2026, 9, 16)

    def test_leaves_the_schedule_alone_when_nothing_is_overdue(
        self, client: TestClient, db: Session, student: Student, freeze_today: None
    ) -> None:
        future = add_assignment(db, student, date(2026, 9, 21), "Next week")
        response = client.post(
            f"/api/recalibrate/{student.id}/execute",
            json={"strategy": "extend_year"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["assignments_moved"] == 0
        db.refresh(future)
        assert future.scheduled_date == date(2026, 9, 21)


class TestAddWeekends:
    def test_uses_saturday_to_catch_up_and_keeps_later_original_dates(
        self, client: TestClient, db: Session, student: Student, freeze_today: None
    ) -> None:
        add_assignment(db, student, date(2026, 9, 14), "Overdue Mon")
        add_assignment(db, student, date(2026, 9, 15), "Overdue Tue")
        add_assignment(db, student, date(2026, 9, 21), "Next week")

        response = client.post(
            f"/api/recalibrate/{student.id}/execute",
            json={"strategy": "add_weekends"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["strategy"] == "add_weekends"
        assert body["assignments_moved"] == 2
        assert body["last_scheduled_date"] == "2026-09-21"

        by_title = {title: day for title, day, _status in dates_for(db, student.id)}
        assert by_title["Overdue Mon"] == "2026-09-18"
        assert by_title["Overdue Tue"] == "2026-09-19"
        assert by_title["Next week"] == "2026-09-21"

    def test_unknown_strategy_is_rejected(
        self, client: TestClient, student: Student, freeze_today: None
    ) -> None:
        response = client.post(
            f"/api/recalibrate/{student.id}/execute",
            json={"strategy": "cram_evenings"},
        )
        assert response.status_code == 422
