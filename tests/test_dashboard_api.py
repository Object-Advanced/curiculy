"""Family dashboard analytics: today's progress and the 7-day completion trend."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus
from app.models import Assignment, Household, Student

TODAY = date.today()


def _add_student(db: Session, household: Household, name: str, color_hex: str) -> Student:
    student = Student(household=household, name=name, color_hex=color_hex)
    db.add(student)
    db.commit()
    return student


def _add_assignment(
    db: Session,
    student: Student,
    scheduled_date: date,
    *,
    status: AssignmentStatus = AssignmentStatus.ASSIGNED,
) -> Assignment:
    assignment = Assignment(
        student_id=student.id,
        title=f"{student.name} {scheduled_date.isoformat()}",
        scheduled_date=scheduled_date,
        status=status,
    )
    db.add(assignment)
    db.commit()
    return assignment


class TestDashboardStats:
    def test_empty_household_returns_seven_dates_and_no_students(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["today"] == TODAY.isoformat()
        assert body["today_progress"] == []
        assert body["weekly_trend"] == []
        assert body["trend_dates"] == [
            (TODAY - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)
        ]

    def test_today_progress_is_grouped_by_student_with_color(
        self, client: TestClient, db: Session
    ) -> None:
        household = Household(name="Test Household")
        db.add(household)
        db.commit()
        ada = _add_student(db, household, "Ada", "#c45c26")
        blaise = _add_student(db, household, "Blaise", "#224466")
        _add_assignment(db, ada, TODAY, status=AssignmentStatus.COMPLETED)
        _add_assignment(db, ada, TODAY, status=AssignmentStatus.ASSIGNED)
        _add_assignment(db, ada, TODAY, status=AssignmentStatus.IN_PROGRESS)
        _add_assignment(db, blaise, TODAY, status=AssignmentStatus.COMPLETED)
        _add_assignment(db, blaise, TODAY - timedelta(days=1), status=AssignmentStatus.ASSIGNED)

        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        progress = {row["name"]: row for row in response.json()["today_progress"]}
        assert progress["Ada"] == {
            "student_id": ada.id,
            "name": "Ada",
            "color_hex": "#c45c26",
            "total": 3,
            "completed": 1,
        }
        assert progress["Blaise"] == {
            "student_id": blaise.id,
            "name": "Blaise",
            "color_hex": "#224466",
            "total": 1,
            "completed": 1,
        }

    def test_weekly_trend_counts_completed_work_per_day(
        self, client: TestClient, db: Session
    ) -> None:
        household = Household(name="Test Household")
        db.add(household)
        db.commit()
        ada = _add_student(db, household, "Ada", "#c45c26")
        blaise = _add_student(db, household, "Blaise", "#224466")
        three_days_ago = TODAY - timedelta(days=3)
        _add_assignment(db, ada, three_days_ago, status=AssignmentStatus.COMPLETED)
        _add_assignment(db, ada, three_days_ago, status=AssignmentStatus.COMPLETED)
        _add_assignment(db, ada, TODAY, status=AssignmentStatus.COMPLETED)
        _add_assignment(db, ada, TODAY, status=AssignmentStatus.ASSIGNED)
        _add_assignment(db, blaise, TODAY, status=AssignmentStatus.COMPLETED)
        _add_assignment(
            db, ada, TODAY - timedelta(days=8), status=AssignmentStatus.COMPLETED
        )
        _add_assignment(
            db, blaise, TODAY - timedelta(days=2), status=AssignmentStatus.SKIPPED
        )

        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        body = response.json()
        dates = body["trend_dates"]
        assert dates[-1] == TODAY.isoformat()
        assert dates[3] == three_days_ago.isoformat()
        by_name = {row["name"]: row for row in body["weekly_trend"]}
        assert by_name["Ada"]["color_hex"] == "#c45c26"
        assert by_name["Ada"]["completed"][3] == 2
        assert by_name["Ada"]["completed"][-1] == 1
        assert sum(by_name["Ada"]["completed"]) == 3
        assert by_name["Blaise"]["completed"][-1] == 1
        assert sum(by_name["Blaise"]["completed"]) == 1

    def test_students_with_no_work_still_appear_as_zeros(
        self, client: TestClient, db: Session
    ) -> None:
        household = Household(name="Test Household")
        db.add(household)
        db.commit()
        idle = _add_student(db, household, "Idle", "#356b46")

        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["today_progress"] == [
            {
                "student_id": idle.id,
                "name": "Idle",
                "color_hex": "#356b46",
                "total": 0,
                "completed": 0,
            }
        ]
        assert body["weekly_trend"] == [
            {
                "student_id": idle.id,
                "name": "Idle",
                "color_hex": "#356b46",
                "completed": [0, 0, 0, 0, 0, 0, 0],
            }
        ]
