"""Portfolio report aggregation: completed work for one student and school year.

Inclusive school-year bounds are the same trap the calendar tests cover: an
assignment on the first day and the last day must appear, and the neighbours
one day outside must not.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus
from app.models import (
    Assignment,
    AssignmentEvidence,
    Household,
    SchoolYear,
    Student,
)

YEAR_START = date(2026, 8, 1)
YEAR_END = date(2027, 5, 31)


@pytest.fixture
def student(db: Session) -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name="Ada", grade="4")
    db.add(student)
    db.commit()
    return student


@pytest.fixture
def other_student(db: Session, student: Student) -> Student:
    sibling = Student(household_id=student.household_id, name="Blaise")
    db.add(sibling)
    db.commit()
    return sibling


@pytest.fixture
def school_year(db: Session, student: Student) -> SchoolYear:
    year = SchoolYear(
        household_id=student.household_id,
        name="2026-2027",
        start_date=YEAR_START,
        end_date=YEAR_END,
    )
    db.add(year)
    db.commit()
    return year


def add_assignment(
    db: Session,
    student: Student,
    scheduled_date: date,
    *,
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
    return assignment


def report_path(
    student_id: int,
    school_year_id: int,
    report_type: str = "work_samples",
) -> str:
    return (
        f"/api/portfolios/report?student_id={student_id}"
        f"&school_year_id={school_year_id}&report_type={report_type}"
    )


class TestPortfolioReport:
    def test_returns_completed_assignments_and_webp_evidence_for_the_year(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        school_year: SchoolYear,
    ) -> None:
        inside = add_assignment(
            db,
            student,
            date(2026, 9, 16),
            title="Lesson 12 problem set",
            status=AssignmentStatus.COMPLETED,
        )
        inside.evidence.append(
            AssignmentEvidence(file_path="test/sample.webp", notes="front")
        )
        db.commit()

        response = client.get(report_path(student.id, school_year.id, "work_samples"))

        assert response.status_code == 200
        body = response.json()
        assert body["report_type"] == "work_samples"
        assert body["count"] == 1
        assert body["student"]["id"] == student.id
        assert body["student"]["name"] == "Ada"
        assert body["student"]["grade"] == "4"
        assert body["school_year"]["id"] == school_year.id
        assert body["school_year"]["name"] == "2026-2027"
        assert [item["title"] for item in body["assignments"]] == ["Lesson 12 problem set"]
        evidence = body["assignments"][0]["evidence"]
        assert evidence[0]["file_path"] == "test/sample.webp"
        assert evidence[0]["notes"] == "front"

    @pytest.mark.parametrize(
        "report_type",
        ["state_evaluation_log", "reading_list", "work_samples"],
    )
    def test_every_preset_returns_the_same_aggregation_shape(
        self,
        client: TestClient,
        student: Student,
        school_year: SchoolYear,
        report_type: str,
    ) -> None:
        response = client.get(report_path(student.id, school_year.id, report_type))

        assert response.status_code == 200
        body = response.json()
        assert body["report_type"] == report_type
        assert body["assignments"] == []
        assert body["count"] == 0

    def test_omits_incomplete_other_students_and_dates_outside_the_year(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
        school_year: SchoolYear,
    ) -> None:
        kept = add_assignment(
            db,
            student,
            YEAR_START,
            title="First day",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(
            db,
            student,
            YEAR_END,
            title="Last day",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(
            db,
            student,
            YEAR_START - timedelta(days=1),
            title="Day before",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(
            db,
            student,
            YEAR_END + timedelta(days=1),
            title="Day after",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(
            db,
            student,
            date(2026, 9, 16),
            title="Still assigned",
            status=AssignmentStatus.ASSIGNED,
        )
        add_assignment(
            db,
            other_student,
            date(2026, 9, 16),
            title="Sibling work",
            status=AssignmentStatus.COMPLETED,
        )
        kept.evidence.append(AssignmentEvidence(file_path="test/first.webp"))
        db.commit()

        response = client.get(report_path(student.id, school_year.id))

        assert response.status_code == 200
        titles = [item["title"] for item in response.json()["assignments"]]
        assert titles == ["First day", "Last day"]

    def test_an_unknown_student_is_a_404(
        self, client: TestClient, school_year: SchoolYear
    ) -> None:
        response = client.get(report_path(4242, school_year.id))

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"

    def test_an_unknown_school_year_is_a_404(
        self, client: TestClient, student: Student
    ) -> None:
        response = client.get(report_path(student.id, 4242))

        assert response.status_code == 404
        assert response.json()["detail"] == "School year not found"

    def test_an_invalid_report_type_is_a_422(
        self, client: TestClient, student: Student, school_year: SchoolYear
    ) -> None:
        response = client.get(report_path(student.id, school_year.id, "scrapbook"))

        assert response.status_code == 422

    def test_custom_via_get_is_rejected(
        self, client: TestClient, student: Student, school_year: SchoolYear
    ) -> None:
        response = client.get(report_path(student.id, school_year.id, "custom"))

        assert response.status_code == 400
        assert "generate" in response.json()["detail"]


class TestCustomPortfolio:
    def test_generate_aggregates_attendance_and_respects_date_bounds(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
    ) -> None:
        from app.enums import AttendanceStatus
        from app.models import Attendance

        db.add_all(
            [
                Attendance(
                    student_id=student.id,
                    date=date(2026, 9, 16),
                    status=AttendanceStatus.PRESENT,
                ),
                Attendance(
                    student_id=student.id,
                    date=date(2026, 9, 17),
                    status=AttendanceStatus.ABSENT,
                ),
                Attendance(
                    student_id=student.id,
                    date=date(2026, 9, 18),
                    status=AttendanceStatus.SICK,
                ),
                Attendance(
                    student_id=student.id,
                    date=date(2026, 9, 19),
                    status=AttendanceStatus.VACATION,
                ),
                Attendance(
                    student_id=student.id,
                    date=date(2026, 9, 15),
                    status=AttendanceStatus.PRESENT,
                ),
                Attendance(
                    student_id=other_student.id,
                    date=date(2026, 9, 16),
                    status=AttendanceStatus.PRESENT,
                ),
            ]
        )
        add_assignment(
            db,
            student,
            date(2026, 9, 16),
            title="Inside window",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(
            db,
            student,
            date(2026, 9, 20),
            title="After window",
            status=AssignmentStatus.COMPLETED,
        )
        db.commit()

        response = client.post(
            "/api/portfolios/generate",
            json={
                "report_type": "custom",
                "student_ids": [student.id],
                "start_date": "2026-09-16",
                "end_date": "2026-09-19",
                "include_attendance": True,
                "include_lessons": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["report_type"] == "custom"
        assert body["start_date"] == "2026-09-16"
        assert body["end_date"] == "2026-09-19"
        section = body["students"][0]
        assert section["attendance"]["present"] == 1
        assert section["attendance"]["absent"] == 1
        assert section["attendance"]["sick"] == 1
        assert section["attendance"]["vacation"] == 1
        assert [day["date"] for day in section["attendance"]["log"]] == [
            "2026-09-16",
            "2026-09-17",
            "2026-09-18",
            "2026-09-19",
        ]
        assert [item["title"] for item in section["lessons"]] == ["Inside window"]
        assert [item["title"] for item in body["assignments"]] == ["Inside window"]

    def test_preview_groups_students_and_omits_unchecked_modules(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
    ) -> None:
        add_assignment(
            db,
            student,
            date(2026, 9, 16),
            title="Ada lesson",
            status=AssignmentStatus.COMPLETED,
        )
        add_assignment(
            db,
            other_student,
            date(2026, 9, 16),
            title="Blaise lesson",
            status=AssignmentStatus.ASSIGNED,
        )
        db.commit()

        response = client.post(
            "/api/portfolios/preview",
            json={
                "report_type": "custom",
                "student_ids": [student.id, other_student.id],
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "include_assignments": True,
            },
        )

        assert response.status_code == 200
        html = response.json()["html"]
        assert "Ada" in html
        assert "Blaise" in html
        assert "page-break" in html
        assert "Assignments" in html
        assert "Attendance" not in html
        assert "Books / Reading Log" not in html
        assert "Photos / Attachments" not in html

    def test_generate_requires_students_and_a_window(self, client: TestClient) -> None:
        missing_students = client.post(
            "/api/portfolios/generate",
            json={"report_type": "custom", "start_date": "2026-09-01", "end_date": "2026-09-30"},
        )
        missing_dates = client.post(
            "/api/portfolios/generate",
            json={"report_type": "custom", "student_ids": [1]},
        )
        reversed_dates = client.post(
            "/api/portfolios/generate",
            json={
                "report_type": "custom",
                "student_ids": [1],
                "start_date": "2026-09-30",
                "end_date": "2026-09-01",
            },
        )

        assert missing_students.status_code == 422
        assert missing_dates.status_code == 422
        assert reversed_dates.status_code == 422


class TestPortfolioEmail:
    def test_queues_a_pdf_attachment_and_returns_without_waiting_for_smtp(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        school_year: SchoolYear,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        add_assignment(
            db,
            student,
            date(2026, 9, 16),
            title="Lesson 12 problem set",
            status=AssignmentStatus.COMPLETED,
        )
        captured: dict[str, object] = {}

        def fake_pdf(report: object) -> bytes:
            captured["student"] = getattr(report, "student").name
            captured["count"] = getattr(report, "count")
            return b"%PDF-1.4 fake"

        async def fake_send(message: object) -> None:
            captured["message"] = message

        monkeypatch.setattr("app.routers.portfolios.render_portfolio_pdf", fake_pdf)
        monkeypatch.setattr("app.routers.portfolios.send_portfolio_email", fake_send)

        response = client.post(
            "/api/portfolios/email",
            json={
                "student_id": student.id,
                "school_year_id": school_year.id,
                "report_type": "work_samples",
                "evaluator_email": "evaluator@example.com",
                "subject": "Ada's 2026-2027 portfolio",
                "message": "Please find Ada's work samples attached.",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        assert captured["student"] == "Ada"
        assert captured["count"] == 1
        message = captured["message"]
        assert message.subject == "Ada's 2026-2027 portfolio"
        recipient = message.recipients[0]
        assert "evaluator@example.com" in str(getattr(recipient, "email", recipient))
        assert message.body == "Please find Ada's work samples attached."
        upload = _attachment_file(message)
        assert upload.filename == "Ada_2026-2027_work_samples.pdf"
        upload.file.seek(0)
        assert upload.file.read() == b"%PDF-1.4 fake"

    def test_unknown_student_is_a_404_and_does_not_send(
        self,
        client: TestClient,
        school_year: SchoolYear,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sent: list[object] = []

        monkeypatch.setattr(
            "app.routers.portfolios.render_portfolio_pdf",
            lambda report: b"%PDF-fake",
        )
        monkeypatch.setattr(
            "app.routers.portfolios.send_portfolio_email",
            lambda message: sent.append(message),
        )

        response = client.post(
            "/api/portfolios/email",
            json={
                "student_id": 4242,
                "school_year_id": school_year.id,
                "report_type": "work_samples",
                "evaluator_email": "evaluator@example.com",
                "subject": "Portfolio",
                "message": "Hello",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"
        assert sent == []

    def test_invalid_evaluator_email_is_a_422(
        self, client: TestClient, student: Student, school_year: SchoolYear
    ) -> None:
        response = client.post(
            "/api/portfolios/email",
            json={
                "student_id": student.id,
                "school_year_id": school_year.id,
                "report_type": "work_samples",
                "evaluator_email": "not-an-email",
                "subject": "Portfolio",
                "message": "Hello",
            },
        )

        assert response.status_code == 422

    def test_custom_email_uses_the_filter_payload(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        add_assignment(
            db,
            student,
            date(2026, 9, 16),
            title="Lesson 12 problem set",
            status=AssignmentStatus.COMPLETED,
        )
        captured: dict[str, object] = {}

        def fake_pdf(report: object) -> bytes:
            captured["report_type"] = getattr(report, "report_type")
            captured["start"] = getattr(report, "start_date")
            captured["includes_attendance"] = getattr(report, "include_attendance")
            return b"%PDF-1.4 fake"

        async def fake_send(message: object) -> None:
            captured["filename"] = _attachment_file(message).filename

        monkeypatch.setattr("app.routers.portfolios.render_portfolio_pdf", fake_pdf)
        monkeypatch.setattr("app.routers.portfolios.send_portfolio_email", fake_send)

        response = client.post(
            "/api/portfolios/email",
            json={
                "report_type": "custom",
                "student_ids": [student.id],
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "include_lessons": True,
                "include_attendance": True,
                "evaluator_email": "evaluator@example.com",
                "subject": "Custom portfolio",
                "message": "Hello",
            },
        )

        assert response.status_code == 200
        assert str(captured["report_type"]) == "custom"
        assert captured["includes_attendance"] is True
        assert captured["start"] == date(2026, 9, 1)
        assert captured["filename"] == "Ada_01_Sep_2026_30_Sep_2026_custom.pdf"


def _attachment_file(message: object):
    attachment = message.attachments[0]
    if isinstance(attachment, tuple):
        return attachment[0]
    if isinstance(attachment, dict):
        return attachment["file"]
    return attachment
