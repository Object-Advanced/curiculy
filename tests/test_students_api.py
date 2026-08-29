"""Student roster: colors, edits, and cascading deletes."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, AttendanceStatus, ExceptionKind
from app.models import (
    DEFAULT_STUDENT_COLOR,
    STUDENT_COLOR_PALETTE,
    Assignment,
    AssignmentEvidence,
    AssignmentGrade,
    Attendance,
    CalendarException,
    Enrollment,
    Household,
    SchoolYear,
    Student,
)


def _add_student(db: Session, name: str = "Ada", **kwargs) -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name=name, **kwargs)
    db.add(student)
    db.commit()
    return student


class TestStudentColors:
    def test_create_defaults_to_the_household_green(self, client: TestClient) -> None:
        response = client.post("/api/students", json={"name": "Blaise"})

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Blaise"
        assert body["color_hex"] == DEFAULT_STUDENT_COLOR

    def test_a_second_student_gets_the_next_green(self, client: TestClient) -> None:
        first = client.post("/api/students", json={"name": "Blaise"})
        second = client.post("/api/students", json={"name": "Ada"})

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["color_hex"] == STUDENT_COLOR_PALETTE[0]
        assert second.json()["color_hex"] == STUDENT_COLOR_PALETTE[1]

    def test_create_keeps_an_explicit_shared_default(self, client: TestClient) -> None:
        client.post("/api/students", json={"name": "Blaise"})
        response = client.post(
            "/api/students",
            json={"name": "Ada", "color_hex": DEFAULT_STUDENT_COLOR},
        )

        assert response.status_code == 201
        assert response.json()["color_hex"] == DEFAULT_STUDENT_COLOR

    def test_create_stores_a_custom_color(self, client: TestClient, db: Session) -> None:
        response = client.post(
            "/api/students",
            json={"name": "Blaise", "color_hex": "#C45C26"},
        )

        assert response.status_code == 201
        assert response.json()["color_hex"] == "#c45c26"
        stored = db.query(Student).filter(Student.name == "Blaise").one()
        assert stored.color_hex == "#c45c26"

    def test_an_invalid_color_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/students",
            json={"name": "Blaise", "color_hex": "blue"},
        )

        assert response.status_code == 422

    def test_list_includes_color_hex(self, client: TestClient, db: Session) -> None:
        student = _add_student(db, "Ada", color_hex="#224466")

        response = client.get("/api/students")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": student.id,
                "household_id": student.household_id,
                "name": "Ada",
                "grade": None,
                "notes": None,
                "color_hex": "#224466",
                "has_login": False,
            }
        ]


class TestStudentUpdate:
    def test_put_updates_name_grade_and_color(
        self, client: TestClient, db: Session
    ) -> None:
        student = _add_student(db, "Ada")

        response = client.put(
            f"/api/students/{student.id}",
            json={"name": "Ada Lovelace", "grade": "4", "color_hex": "#112233"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Ada Lovelace"
        assert body["grade"] == "4"
        assert body["color_hex"] == "#112233"
        db.refresh(student)
        assert student.name == "Ada Lovelace"
        assert student.color_hex == "#112233"

    def test_put_without_color_keeps_the_existing_color(
        self, client: TestClient, db: Session
    ) -> None:
        student = _add_student(db, "Ada", color_hex="#c45c26")

        response = client.put(
            f"/api/students/{student.id}",
            json={"name": "Ada Lovelace", "grade": "4"},
        )

        assert response.status_code == 200
        assert response.json()["color_hex"] == "#c45c26"
        db.refresh(student)
        assert student.color_hex == "#c45c26"

    def test_an_unknown_student_is_a_404(self, client: TestClient) -> None:
        response = client.put(
            "/api/students/4242",
            json={"name": "Ghost"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"


class TestStudentDelete:
    def test_delete_removes_the_student_and_their_assignments(
        self, client: TestClient, db: Session
    ) -> None:
        student = _add_student(db, "Ada")
        assignment = Assignment(
            student_id=student.id,
            title="Lesson 1",
            scheduled_date=date(2026, 9, 16),
            status=AssignmentStatus.ASSIGNED,
        )
        assignment.grade = AssignmentGrade(score_value="A")
        assignment.evidence.append(AssignmentEvidence(file_path="test/page.webp"))
        year = SchoolYear(
            household_id=student.household_id,
            name="2026-2027",
            start_date=date(2026, 8, 1),
            end_date=date(2027, 5, 31),
        )
        db.add_all([assignment, year])
        db.commit()
        enrollment = Enrollment(
            student_id=student.id,
            curriculum_id=1,
            school_year_id=year.id,
        )
        exception = CalendarException(
            household_id=student.household_id,
            student_id=student.id,
            kind=ExceptionKind.SICK,
            title="Fever",
            start_date=date(2026, 9, 16),
            end_date=date(2026, 9, 16),
        )
        attendance = Attendance(
            student_id=student.id,
            date=date(2026, 9, 16),
            status=AttendanceStatus.SICK,
        )
        db.add_all([enrollment, exception, attendance])
        db.commit()
        student_id = student.id
        assignment_id = assignment.id
        grade_id = assignment.grade.id
        enrollment_id = enrollment.id
        exception_id = exception.id
        attendance_id = attendance.id

        response = client.delete(f"/api/students/{student_id}")

        assert response.status_code == 204
        assert db.get(Student, student_id) is None
        assert db.get(Assignment, assignment_id) is None
        assert db.get(AssignmentGrade, grade_id) is None
        assert db.query(AssignmentEvidence).count() == 0
        assert db.get(Enrollment, enrollment_id) is None
        assert db.get(CalendarException, exception_id) is None
        assert db.get(Attendance, attendance_id) is None

    def test_delete_clears_orphan_scheduled_work_rows(
        self, client: TestClient, db: Session
    ) -> None:
        student = _add_student(db, "Ada")
        db.execute(
            text(
                """
                CREATE TABLE scheduled_work (
                    id INTEGER PRIMARY KEY,
                    enrollment_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE TABLE evidence_captures (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    scheduled_work_id INTEGER,
                    path VARCHAR(255)
                )
                """
            )
        )
        db.execute(
            text(
                "INSERT INTO scheduled_work (id, enrollment_id, student_id, title) "
                "VALUES (1, 1, :student_id, 'legacy')"
            ),
            {"student_id": student.id},
        )
        db.execute(
            text(
                "INSERT INTO evidence_captures "
                "(id, student_id, scheduled_work_id, path) "
                "VALUES (1, :student_id, 1, 'old.webp')"
            ),
            {"student_id": student.id},
        )
        db.commit()

        response = client.delete(f"/api/students/{student.id}")

        assert response.status_code == 204
        leftover_work = db.execute(text("SELECT COUNT(*) FROM scheduled_work")).scalar()
        leftover_evidence = db.execute(
            text("SELECT COUNT(*) FROM evidence_captures")
        ).scalar()
        assert leftover_work == 0
        assert leftover_evidence == 0

    def test_an_unknown_student_is_a_404(self, client: TestClient) -> None:
        response = client.delete("/api/students/4242")

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"
