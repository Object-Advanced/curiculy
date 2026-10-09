"""Curriculum catalog listing, unscheduling, and deletion."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.enums import MappingSource, ResourceKind, UnitKind
from app.models import (
    Assignment,
    BookEdition,
    Curriculum,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
    Enrollment,
    Household,
    SchoolYear,
    Student,
    Work,
)


def seed_student(db: Session, name: str = "Ada") -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name=name)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def seed_unscheduled_curriculum(db: Session, title: str = "Saxon Math 3") -> Curriculum:
    work = Work(title=title)
    book = BookEdition(work=work, page_count=200)
    db.add_all([work, book])
    db.flush()
    curriculum = Curriculum(title=title)
    edition = CurriculumEdition(
        curriculum=curriculum, edition_label="1st edition", is_current=True
    )
    resource = CurriculumResource(
        curriculum_edition=edition,
        book_edition_id=book.id,
        kind=ResourceKind.STUDENT_TEXT,
        title=title,
    )
    db.add_all([curriculum, edition, resource])
    db.commit()
    db.refresh(curriculum)
    db.refresh(book)
    return curriculum


def seed_scheduled_curriculum(db: Session) -> tuple[Curriculum, BookEdition, Assignment]:
    student = seed_student(db)
    curriculum = seed_unscheduled_curriculum(db)
    edition = curriculum.editions[0]
    resource = edition.resources[0]
    book = db.get(BookEdition, resource.book_edition_id)
    assert book is not None

    course = CurriculumUnit(
        curriculum_edition=edition,
        kind=UnitKind.COURSE,
        title="Saxon Math 3",
        sort_order=0,
        depth=0,
    )
    db.add(course)
    db.flush()
    lesson = CurriculumUnit(
        curriculum_edition=edition,
        parent_id=course.id,
        kind=UnitKind.LESSON,
        title="Lesson 1",
        sort_order=0,
        depth=1,
    )
    db.add(lesson)
    db.flush()
    db.add(
        CurriculumPageMapping(
            curriculum_unit_id=lesson.id,
            curriculum_resource_id=resource.id,
            page_start=1,
            page_end=10,
            source=MappingSource.AI_PARSED,
        )
    )
    assignment = Assignment(
        student_id=student.id,
        curriculum_resource_id=resource.id,
        curriculum_unit_id=lesson.id,
        title="Lesson 1",
        scheduled_date=date(2026, 9, 7),
    )
    db.add(assignment)
    db.commit()
    db.refresh(curriculum)
    db.refresh(book)
    db.refresh(assignment)
    return curriculum, book, assignment


class TestCurriculumScheduleFlag:
    def test_list_marks_whether_each_curriculum_is_scheduled(
        self, client: TestClient, db: Session
    ) -> None:
        unscheduled = seed_unscheduled_curriculum(db, title="Idle Book")
        scheduled, _, _ = seed_scheduled_curriculum(db)

        body = client.get("/api/curricula").json()
        by_id = {item["id"]: item for item in body}

        assert by_id[unscheduled.id]["is_scheduled"] is False
        assert by_id[scheduled.id]["is_scheduled"] is True


class TestUnscheduleCurriculum:
    def test_removes_assignments_and_generated_units_but_keeps_the_curriculum(
        self, client: TestClient, db: Session
    ) -> None:
        curriculum, book, assignment = seed_scheduled_curriculum(db)
        curriculum_id = curriculum.id
        book_id = book.id
        assignment_id = assignment.id

        response = client.delete(f"/api/curricula/{curriculum_id}/schedule")

        assert response.status_code == 204
        db.expire_all()
        assert db.get(Curriculum, curriculum_id) is not None
        assert db.get(BookEdition, book_id) is not None
        assert db.get(Assignment, assignment_id) is None
        assert db.query(CurriculumUnit).count() == 0
        assert db.query(CurriculumPageMapping).count() == 0
        assert db.query(CurriculumResource).count() == 1
        listed = client.get("/api/curricula").json()
        match = next(item for item in listed if item["id"] == curriculum_id)
        assert match["is_scheduled"] is False

    def test_unschedule_clears_orphan_scheduled_work_for_generated_units(
        self, client: TestClient, db: Session
    ) -> None:
        curriculum, _, assignment = seed_scheduled_curriculum(db)
        assert assignment.curriculum_unit_id is not None
        db.execute(
            text(
                """
                CREATE TABLE scheduled_work (
                    id INTEGER PRIMARY KEY,
                    enrollment_id INTEGER,
                    student_id INTEGER,
                    unit_id INTEGER,
                    title VARCHAR(255) NOT NULL
                )
                """
            )
        )
        db.execute(
            text(
                "INSERT INTO scheduled_work (id, enrollment_id, student_id, unit_id, title) "
                "VALUES (1, 1, 1, :unit_id, 'legacy')"
            ),
            {"unit_id": assignment.curriculum_unit_id},
        )
        db.commit()

        response = client.delete(f"/api/curricula/{curriculum.id}/schedule")

        assert response.status_code == 204
        leftover = db.execute(text("SELECT COUNT(*) FROM scheduled_work")).scalar()
        assert leftover == 0

    def test_unknown_curriculum_is_a_404(self, client: TestClient) -> None:
        assert client.delete("/api/curricula/4242/schedule").status_code == 404


class TestDeleteCurriculum:
    def test_deletes_an_unscheduled_curriculum_cleanly(
        self, client: TestClient, db: Session
    ) -> None:
        curriculum = seed_unscheduled_curriculum(db)
        book_id = curriculum.editions[0].resources[0].book_edition_id
        curriculum_id = curriculum.id

        response = client.delete(f"/api/curricula/{curriculum_id}")

        assert response.status_code == 204
        db.expire_all()
        assert db.get(Curriculum, curriculum_id) is None
        assert db.query(CurriculumEdition).count() == 0
        assert db.query(CurriculumResource).count() == 0
        assert db.get(BookEdition, book_id) is not None

    def test_delete_clears_orphan_scheduled_work_for_units_and_enrollments(
        self, client: TestClient, db: Session
    ) -> None:
        curriculum = seed_unscheduled_curriculum(db)
        student = seed_student(db)
        year = SchoolYear(
            household_id=student.household_id,
            name="2026-2027",
            start_date=date(2026, 8, 1),
            end_date=date(2027, 5, 31),
        )
        db.add(year)
        db.flush()
        unit = CurriculumUnit(
            curriculum_edition=curriculum.editions[0],
            kind=UnitKind.COURSE,
            title="Imported tree",
            sort_order=0,
            depth=0,
        )
        enrollment = Enrollment(
            student_id=student.id,
            curriculum_id=curriculum.id,
            school_year_id=year.id,
        )
        db.add_all([unit, enrollment])
        db.commit()
        db.execute(
            text(
                """
                CREATE TABLE scheduled_work (
                    id INTEGER PRIMARY KEY,
                    enrollment_id INTEGER,
                    student_id INTEGER,
                    unit_id INTEGER,
                    title VARCHAR(255) NOT NULL
                )
                """
            )
        )
        db.execute(
            text(
                "INSERT INTO scheduled_work "
                "(id, enrollment_id, student_id, unit_id, title) "
                "VALUES (1, :enrollment_id, :student_id, :unit_id, 'by-enroll'), "
                "(2, 99, :student_id, :unit_id, 'by-unit')"
            ),
            {
                "enrollment_id": enrollment.id,
                "student_id": student.id,
                "unit_id": unit.id,
            },
        )
        db.commit()

        response = client.delete(f"/api/curricula/{curriculum.id}")

        assert response.status_code == 204
        leftover = db.execute(text("SELECT COUNT(*) FROM scheduled_work")).scalar()
        assert leftover == 0

    def test_refuses_to_delete_a_curriculum_that_is_still_scheduled(
        self, client: TestClient, db: Session
    ) -> None:
        curriculum, _, assignment = seed_scheduled_curriculum(db)

        response = client.delete(f"/api/curricula/{curriculum.id}")

        assert response.status_code == 409
        db.expire_all()
        assert db.get(Curriculum, curriculum.id) is not None
        assert db.get(Assignment, assignment.id) is not None

    def test_unknown_curriculum_is_a_404(self, client: TestClient) -> None:
        assert client.delete("/api/curricula/4242").status_code == 404


class TestTenantIsolation:
    def test_shared_catalog_books_are_not_listed_as_household_curricula(
        self, client: TestClient, db: Session
    ) -> None:
        work = Work(title="A book another family scanned")
        db.add(BookEdition(work=work, isbn13="9780306406157"))
        db.commit()

        assert client.get("/api/curricula").json() == []

    def test_saving_a_curriculum_writes_the_household_library_and_catalog_isbn(
        self, client: TestClient, db: Session
    ) -> None:
        response = client.post(
            "/api/curricula",
            json={
                "title": "Our Saxon 3",
                "publisher": "Saxon Publishers",
                "subject": "Math",
                "description": "Homeschool copy.",
                "sku": "9780306406157",
            },
        )

        assert response.status_code == 201
        listed = client.get("/api/curricula").json()
        assert [item["title"] for item in listed] == ["Our Saxon 3"]
        book = db.query(BookEdition).one()
        assert book.isbn13 == "9780306406157"
        assert book.work.title == "Our Saxon 3"
