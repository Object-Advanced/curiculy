"""Enrollment as a side effect of scheduling, plus the existing Settings POST."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Assignment, Curriculum, CurriculumEdition, Enrollment, Student
from app.services import curriculum_plan_apply as plan_apply_service
from app.services import pacing as pacing_service
from tests.test_curriculum_plans import _create_plan
from tests.test_pacing import preview_body, seed_book, seed_curriculum_edition, seed_student


def _commit_body(
    student: Student,
    curriculum_edition: CurriculumEdition,
    book=None,
    lessons: list[dict] | None = None,
    **overrides: object,
) -> dict:
    body: dict = {
        "student_id": student.id,
        "curriculum_edition_id": curriculum_edition.id,
        "course_title": "Saxon Math 3, autumn term",
        "lessons": lessons
        if lessons is not None
        else [
            {
                "sequence": 1,
                "title": "Lesson 1: Saxon Math 3 (pp. 1-40)",
                "start_page": 1,
                "end_page": 40,
                "scheduled_date": "2026-09-07",
            },
            {
                "sequence": 2,
                "title": "Lesson 2: Saxon Math 3 (pp. 41-80)",
                "start_page": 41,
                "end_page": 80,
                "scheduled_date": "2026-09-11",
            },
            {
                "sequence": 3,
                "title": "Lesson 3: Saxon Math 3 (pp. 81-120)",
                "start_page": 81,
                "end_page": 120,
                "scheduled_date": "2026-09-17",
            },
        ],
    }
    if book is not None:
        body["book_id"] = book.id
    body.update(overrides)
    return body


def _commit(
    client: TestClient,
    student: Student,
    edition,
    book=None,
    **overrides: object,
) -> dict:
    body = _commit_body(student, edition, book, **overrides)
    response = client.post("/api/pacing/commit", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _year(
    client: TestClient,
    name: str,
    start: str,
    end: str,
) -> dict:
    response = client.post(
        "/api/school-years",
        json={"name": name, "start_date": start, "end_date": end},
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestSettingsEnrollmentStillWorks:
    def test_parent_can_still_post_an_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        curriculum = Curriculum(title="History Quest")
        db.add(curriculum)
        db.commit()
        db.refresh(curriculum)
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")

        created = client.post(
            "/api/enrollments",
            json={
                "student_id": student.id,
                "curriculum_id": curriculum.id,
                "school_year_id": year["id"],
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["student_id"] == student.id
        assert body["curriculum_id"] == curriculum.id
        assert body["school_year_id"] == year["id"]

        listed = client.get("/api/enrollments")
        assert any(row["id"] == body["id"] for row in listed.json())

        duplicate = client.post(
            "/api/enrollments",
            json={
                "student_id": student.id,
                "curriculum_id": curriculum.id,
                "school_year_id": year["id"],
            },
        )
        assert duplicate.status_code == 409


class TestPacingCommitEnrolls:
    def test_first_commit_creates_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")

        _commit(client, student, edition)

        rows = db.query(Enrollment).all()
        assert len(rows) == 1
        assert rows[0].student_id == student.id
        assert rows[0].curriculum_id == edition.curriculum_id
        assert rows[0].school_year_id == year["id"]

    def test_second_commit_does_not_duplicate_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        _year(client, "2026-2027", "2026-08-01", "2027-06-30")

        _commit(client, student, edition)
        _commit(
            client,
            student,
            edition,
            lessons=[
                {
                    "sequence": 1,
                    "title": "Extra lesson",
                    "start_page": 121,
                    "end_page": 140,
                    "scheduled_date": "2026-09-18",
                }
            ],
        )

        assert db.query(Enrollment).count() == 1
        assert db.query(Assignment).count() == 4

    def test_settings_enrollment_is_reused_on_pacing_commit(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        created = client.post(
            "/api/enrollments",
            json={
                "student_id": student.id,
                "curriculum_id": edition.curriculum_id,
                "school_year_id": year["id"],
            },
        )
        assert created.status_code == 201
        enrollment_id = created.json()["id"]

        _commit(client, student, edition)

        rows = db.query(Enrollment).all()
        assert len(rows) == 1
        assert rows[0].id == enrollment_id
        assert db.query(Assignment).count() == 3

    def test_different_student_creates_separate_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        sibling = Student(household_id=student.household_id, name="Blaise")
        db.add(sibling)
        db.commit()
        db.refresh(sibling)
        edition = seed_curriculum_edition(db)
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")

        body = _commit_body(student, edition)
        del body["student_id"]
        body["student_ids"] = [student.id, sibling.id]
        response = client.post("/api/pacing/commit", json=body)
        assert response.status_code == 201

        rows = db.query(Enrollment).order_by(Enrollment.student_id).all()
        assert [row.student_id for row in rows] == [student.id, sibling.id]
        assert {row.curriculum_id for row in rows} == {edition.curriculum_id}
        assert {row.school_year_id for row in rows} == {year["id"]}

    def test_different_school_year_creates_separate_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        first = _year(client, "2025-2026", "2025-08-01", "2026-06-30")
        _commit(client, student, edition)
        second = _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        _commit(
            client,
            student,
            edition,
            lessons=[
                {
                    "sequence": 1,
                    "title": "Year two lesson",
                    "start_page": 1,
                    "end_page": 10,
                    "scheduled_date": "2026-09-07",
                }
            ],
        )

        rows = db.query(Enrollment).order_by(Enrollment.school_year_id).all()
        assert len(rows) == 2
        assert {row.school_year_id for row in rows} == {first["id"], second["id"]}
        assert {row.student_id for row in rows} == {student.id}
        assert {row.curriculum_id for row in rows} == {edition.curriculum_id}

    def test_preview_creates_no_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        book = seed_book(db)
        seed_student(db)
        seed_curriculum_edition(db)
        _year(client, "2026-2027", "2026-08-01", "2027-06-30")

        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, target_lessons=5),
        )
        assert response.status_code == 200
        assert db.query(Enrollment).count() == 0
        assert client.get("/api/enrollments").json() == []

    def test_failed_commit_does_not_create_enrollment(
        self,
        client: TestClient,
        db: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        real_write = pacing_service.SyllabusCommitter._write

        def boom(self, payload):
            real_write(self, payload)
            raise RuntimeError("forced commit failure")

        monkeypatch.setattr(pacing_service.SyllabusCommitter, "_write", boom)

        with pytest.raises(RuntimeError, match="forced commit failure"):
            client.post(
                "/api/pacing/commit",
                json=_commit_body(student, edition),
            )

        assert db.query(Enrollment).count() == 0
        assert db.query(Assignment).count() == 0


class TestPlanApplyEnrolls:
    def test_first_apply_creates_enrollment_from_plan_title(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        plan = _create_plan(client, {"title": "Abeka Arithmetic 3"})

        response = client.post(
            f"/api/curriculum/plans/{plan['id']}/apply",
            json={
                "student_id": student.id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 201, response.text

        curriculum = (
            db.query(Curriculum).filter(Curriculum.title == "Abeka Arithmetic 3").one()
        )
        row = db.query(Enrollment).one()
        assert row.student_id == student.id
        assert row.curriculum_id == curriculum.id
        assert row.school_year_id == year["id"]
        stamped = db.query(Assignment).filter_by(student_id=student.id).all()
        assert stamped
        assert {item.curriculum_id for item in stamped} == {curriculum.id}
        assert all(item.student_id == student.id for item in stamped)
        assert all(item.curriculum_resource_id is None for item in stamped)
        assert all(item.curriculum_unit_id is None for item in stamped)

    def test_second_apply_does_not_duplicate_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        plan = _create_plan(client, {"title": "Abeka Arithmetic 3"})
        payload = {
            "student_id": student.id,
            "start_date": "2026-08-31",
            "target_days": [0, 1, 2, 3, 4],
        }
        first = client.post(f"/api/curriculum/plans/{plan['id']}/apply", json=payload)
        second = client.post(f"/api/curriculum/plans/{plan['id']}/apply", json=payload)
        assert first.status_code == 201
        assert second.status_code == 201
        assert db.query(Enrollment).count() == 1
        assert db.query(Curriculum).filter(Curriculum.title == "Abeka Arithmetic 3").count() == 1

    def test_reuses_library_curriculum_with_the_same_title(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db, title="Saxon Math 3")
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        plan = _create_plan(client, {"title": "Saxon Math 3"})

        client.post(
            f"/api/curriculum/plans/{plan['id']}/apply",
            json={
                "student_id": student.id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )

        row = db.query(Enrollment).one()
        assert row.curriculum_id == edition.curriculum_id
        assert row.school_year_id == year["id"]
        assert db.query(Curriculum).filter(Curriculum.title == "Saxon Math 3").count() == 1

    def test_different_student_creates_separate_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        sibling = Student(household_id=student.household_id, name="Blaise")
        db.add(sibling)
        db.commit()
        db.refresh(sibling)
        _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        plan = _create_plan(client, {"title": "Abeka Arithmetic 3"})
        for child in (student, sibling):
            response = client.post(
                f"/api/curriculum/plans/{plan['id']}/apply",
                json={
                    "student_id": child.id,
                    "start_date": "2026-08-31",
                    "target_days": [0, 1, 2, 3, 4],
                },
            )
            assert response.status_code == 201, response.text

        rows = db.query(Enrollment).order_by(Enrollment.student_id).all()
        assert [row.student_id for row in rows] == [student.id, sibling.id]
        assert rows[0].curriculum_id == rows[1].curriculum_id

    def test_empty_plan_creates_no_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        created = client.post(
            "/api/curriculum/plans",
            json={
                "title": "Empty days",
                "frequency_days": 1,
                "total_weeks": 1,
                "lessons": [
                    {"week_number": 1, "day_number": 1, "title": "", "notes": "only notes"}
                ],
            },
        )
        assert created.status_code == 201
        response = client.post(
            f"/api/curriculum/plans/{created.json()['id']}/apply",
            json={
                "student_id": student.id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )
        assert response.status_code == 400
        assert db.query(Enrollment).count() == 0

    def test_failed_apply_does_not_leave_enrollment(
        self,
        client: TestClient,
        db: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        student = seed_student(db)
        _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        plan = _create_plan(client, {"title": "Rollback Science"})
        real = plan_apply_service.ensure_enrollment

        def boom(db_session, **kwargs):
            real(db_session, **kwargs)
            raise RuntimeError("forced apply failure")

        monkeypatch.setattr(plan_apply_service, "ensure_enrollment", boom)

        with pytest.raises(RuntimeError, match="forced apply failure"):
            client.post(
                f"/api/curriculum/plans/{plan['id']}/apply",
                json={
                    "student_id": student.id,
                    "start_date": "2026-08-31",
                    "target_days": [0, 1, 2, 3, 4],
                },
            )

        assert db.query(Enrollment).count() == 0
        assert db.query(Assignment).count() == 0
        assert db.query(Curriculum).filter(Curriculum.title == "Rollback Science").count() == 0


class TestPortfolioFindsScheduledCurriculum:
    def test_pacing_commit_shows_on_the_reading_list(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db, title="Saxon Math 3")
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        _commit(client, student, edition)

        response = client.post(
            "/api/portfolios/generate",
            json={
                "report_type": "custom",
                "student_ids": [student.id],
                "school_year_id": year["id"],
                "include_books_completed": True,
                "include_books_in_progress": True,
                "include_books_incomplete": True,
            },
        )
        assert response.status_code == 200, response.text
        books = response.json()["students"][0]["books"]
        assert [book["title"] for book in books] == ["Saxon Math 3"]
        assert books[0]["curriculum_id"] == edition.curriculum_id

        courses = client.get(f"/api/students/{student.id}/courses")
        assert courses.status_code == 200
        assert any(row["curriculum_id"] == edition.curriculum_id for row in courses.json())

    def test_plan_apply_shows_on_the_reading_list_through_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        plan = _create_plan(client, {"title": "Abeka Arithmetic 3"})
        client.post(
            f"/api/curriculum/plans/{plan['id']}/apply",
            json={
                "student_id": student.id,
                "start_date": "2026-08-31",
                "target_days": [0, 1, 2, 3, 4],
            },
        )

        response = client.post(
            "/api/portfolios/generate",
            json={
                "report_type": "custom",
                "student_ids": [student.id],
                "school_year_id": year["id"],
                "include_books_completed": True,
                "include_books_in_progress": True,
                "include_books_incomplete": True,
            },
        )
        assert response.status_code == 200, response.text
        books = response.json()["students"][0]["books"]
        assert [book["title"] for book in books] == ["Abeka Arithmetic 3"]
        assert books[0]["progress"] == "incomplete"
        assert books[0]["total_assignments"] == 2
        assert books[0]["completed_assignments"] == 0
