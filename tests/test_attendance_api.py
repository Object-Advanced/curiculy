"""Daily attendance: range reads and per-student upserts."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import AttendanceStatus
from app.models import Attendance, Household, Student

ANCHOR = date(2026, 9, 16)


def _add_student(db: Session, name: str = "Ada") -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name=name)
    db.add(student)
    db.commit()
    return student


def _add_attendance(
    db: Session,
    student: Student,
    on_date: date,
    status: AttendanceStatus = AttendanceStatus.PRESENT,
) -> Attendance:
    row = Attendance(student_id=student.id, date=on_date, status=status)
    db.add(row)
    db.commit()
    return row


class TestListAttendance:
    def test_returns_rows_inside_the_inclusive_window(
        self, client: TestClient, db: Session
    ) -> None:
        student = _add_student(db)
        _add_attendance(db, student, date(2026, 9, 15), AttendanceStatus.ABSENT)
        inside = _add_attendance(db, student, ANCHOR, AttendanceStatus.PRESENT)
        _add_attendance(db, student, date(2026, 9, 17), AttendanceStatus.SICK)

        response = client.get(
            "/api/attendance",
            params={"start_date": "2026-09-16", "end_date": "2026-09-16"},
        )

        assert response.status_code == 200
        body = response.json()
        assert [row["id"] for row in body] == [inside.id]
        assert body[0] == {
            "id": inside.id,
            "student_id": student.id,
            "date": "2026-09-16",
            "status": "Present",
        }

    def test_includes_both_bounds(self, client: TestClient, db: Session) -> None:
        student = _add_student(db)
        _add_attendance(db, student, date(2026, 9, 14), AttendanceStatus.PRESENT)
        _add_attendance(db, student, date(2026, 9, 20), AttendanceStatus.ABSENT)

        response = client.get(
            "/api/attendance",
            params={"start_date": "2026-09-14", "end_date": "2026-09-20"},
        )

        assert response.status_code == 200
        assert [row["date"] for row in response.json()] == ["2026-09-14", "2026-09-20"]

    def test_rejects_a_reversed_window(self, client: TestClient) -> None:
        response = client.get(
            "/api/attendance",
            params={"start_date": "2026-09-20", "end_date": "2026-09-14"},
        )

        assert response.status_code == 400
        assert "after" in response.json()["detail"]

    def test_requires_both_dates(self, client: TestClient) -> None:
        assert client.get("/api/attendance").status_code == 422
        assert (
            client.get("/api/attendance", params={"start_date": "2026-09-16"}).status_code
            == 422
        )


class TestUpsertAttendance:
    def test_inserts_a_new_row(self, client: TestClient, db: Session) -> None:
        student = _add_student(db)

        response = client.post(
            "/api/attendance",
            json={
                "student_id": student.id,
                "date": "2026-09-16",
                "status": "Present",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["student_id"] == student.id
        assert body["date"] == "2026-09-16"
        assert body["status"] == "Present"
        stored = db.get(Attendance, body["id"])
        assert stored is not None
        assert stored.status is AttendanceStatus.PRESENT

    def test_updates_the_existing_row_for_the_same_student_and_date(
        self, client: TestClient, db: Session
    ) -> None:
        student = _add_student(db)
        existing = _add_attendance(db, student, ANCHOR, AttendanceStatus.PRESENT)

        response = client.post(
            "/api/attendance",
            json={
                "student_id": student.id,
                "date": "2026-09-16",
                "status": "Absent",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == existing.id
        assert body["status"] == "Absent"
        db.refresh(existing)
        assert existing.status is AttendanceStatus.ABSENT
        assert db.query(Attendance).count() == 1

    def test_accepts_sick_and_vacation(self, client: TestClient, db: Session) -> None:
        student = _add_student(db)

        sick = client.post(
            "/api/attendance",
            json={"student_id": student.id, "date": "2026-09-16", "status": "Sick"},
        )
        vacation = client.post(
            "/api/attendance",
            json={"student_id": student.id, "date": "2026-09-17", "status": "Vacation"},
        )

        assert sick.status_code == 200
        assert sick.json()["status"] == "Sick"
        assert vacation.status_code == 200
        assert vacation.json()["status"] == "Vacation"

    def test_unknown_student_is_a_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/attendance",
            json={"student_id": 4242, "date": "2026-09-16", "status": "Present"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"

    def test_rejects_an_unknown_status(self, client: TestClient, db: Session) -> None:
        student = _add_student(db)

        response = client.post(
            "/api/attendance",
            json={"student_id": student.id, "date": "2026-09-16", "status": "Tardy"},
        )

        assert response.status_code == 422
