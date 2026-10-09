"""Historical Enrollment backfill from book-paced assignment provenance."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.enums import AssignmentStatus, ResourceKind, UnitKind
from app.models import (
    Assignment,
    Curriculum,
    CurriculumEdition,
    CurriculumResource,
    CurriculumUnit,
    Enrollment,
    Household,
    SchoolYear,
    Student,
)
from app.schema_patches import apply_tenant_schema
from app.services.enrollment_backfill import (
    backfill_data_dir,
    discover_missing_enrollments,
    reconcile_enrollments,
)
from tests.test_enrollments import _year
from tests.test_pacing import seed_curriculum_edition, seed_student


def _year_row(
    db: Session,
    household_id: int,
    name: str = "2026-2027",
    start: date = date(2026, 8, 1),
    end: date = date(2027, 6, 30),
) -> SchoolYear:
    year = SchoolYear(
        household_id=household_id,
        name=name,
        start_date=start,
        end_date=end,
    )
    db.add(year)
    db.commit()
    db.refresh(year)
    return year


def _resource(db: Session, edition: CurriculumEdition) -> CurriculumResource:
    resource = CurriculumResource(
        curriculum_edition_id=edition.id,
        kind=ResourceKind.STUDENT_TEXT,
        title="Student text",
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def _book_assignment(
    db: Session,
    student: Student,
    *,
    resource: CurriculumResource | None = None,
    unit: CurriculumUnit | None = None,
    scheduled: date = date(2026, 9, 8),
    title: str = "Lesson 1",
) -> Assignment:
    assignment = Assignment(
        student_id=student.id,
        curriculum_resource_id=resource.id if resource is not None else None,
        curriculum_unit_id=unit.id if unit is not None else None,
        title=title,
        scheduled_date=scheduled,
        status=AssignmentStatus.ASSIGNED,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def _snapshot_assignments(db: Session) -> list[tuple[int, str, date, int | None, int | None]]:
    return [
        (
            row.id,
            row.title,
            row.scheduled_date,
            row.curriculum_resource_id,
            row.curriculum_unit_id,
        )
        for row in db.query(Assignment).order_by(Assignment.id).all()
    ]


def _snapshot_curricula(db: Session) -> list[tuple[int, str]]:
    return [
        (row.id, row.title)
        for row in db.query(Curriculum).order_by(Curriculum.id).all()
    ]


class TestDiscoverAndInsert:
    def test_missing_enrollment_is_reconstructed_when_the_trio_is_provable(
        self, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db, title="Saxon Math 3")
        year = _year_row(db, student.household_id)
        resource = _resource(db, edition)
        _book_assignment(db, student, resource=resource)

        before_assignments = _snapshot_assignments(db)
        before_curricula = _snapshot_curricula(db)
        assert db.query(Enrollment).count() == 0

        report = reconcile_enrollments(db, dry_run=False)

        assert report.inserted == 1
        assert report.dry_run is False
        row = db.query(Enrollment).one()
        assert row.student_id == student.id
        assert row.curriculum_id == edition.curriculum_id
        assert row.school_year_id == year.id
        assert row.start_date is None
        assert row.end_date is None
        db.refresh(year)
        assert year.start_date == date(2026, 8, 1)
        assert year.end_date == date(2027, 6, 30)
        assert _snapshot_assignments(db) == before_assignments
        assert _snapshot_curricula(db) == before_curricula

    def test_dry_run_does_not_insert(self, db: Session) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        _year_row(db, student.household_id)
        _book_assignment(db, student, resource=_resource(db, edition))

        report = reconcile_enrollments(db, dry_run=True)
        assert report.dry_run is True
        assert report.inserted == 0
        assert len(report.candidates) == 1
        assert db.query(Enrollment).count() == 0

    def test_existing_enrollment_is_not_duplicated(self, db: Session) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        year = _year_row(db, student.household_id)
        _book_assignment(db, student, resource=_resource(db, edition))
        db.add(
            Enrollment(
                student_id=student.id,
                curriculum_id=edition.curriculum_id,
                school_year_id=year.id,
            )
        )
        db.commit()

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 0
        assert report.already_present == 1
        assert db.query(Enrollment).count() == 1

    def test_rerunning_is_idempotent(self, db: Session) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        _year_row(db, student.household_id)
        _book_assignment(db, student, resource=_resource(db, edition))

        first = reconcile_enrollments(db, dry_run=False)
        second = reconcile_enrollments(db, dry_run=False)
        assert first.inserted == 1
        assert second.inserted == 0
        assert second.already_present == 1
        assert db.query(Enrollment).count() == 1

    def test_unlinked_plan_style_assignments_are_skipped(self, db: Session) -> None:
        student = seed_student(db)
        _year_row(db, student.household_id)
        _book_assignment(db, student, title="Week 1 Day 1")

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 0
        assert report.skipped_unlinked_assignments == 1
        assert db.query(Enrollment).count() == 0

    def test_stored_curriculum_id_without_resource_is_reconstructed(
        self, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db, title="Abeka Arithmetic 3")
        year = _year_row(db, student.household_id)
        assignment = Assignment(
            student_id=student.id,
            curriculum_id=edition.curriculum_id,
            title="Week 1 Day 1",
            scheduled_date=date(2026, 9, 8),
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(assignment)
        db.commit()

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 1
        assert report.skipped_unlinked_assignments == 0
        row = db.query(Enrollment).one()
        assert row.student_id == student.id
        assert row.curriculum_id == edition.curriculum_id
        assert row.school_year_id == year.id

    def test_orphan_stored_curriculum_id_is_skipped(self, db: Session) -> None:
        student = seed_student(db)
        _year_row(db, student.household_id)
        assignment = Assignment(
            student_id=student.id,
            curriculum_id=4242,
            title="Ghost curriculum",
            scheduled_date=date(2026, 9, 8),
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(assignment)
        db.commit()

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 0
        assert report.skipped_orphan_links == 1
        assert db.query(Enrollment).count() == 0

    def test_orphan_resource_id_is_skipped(self, db: Session) -> None:
        student = seed_student(db)
        _year_row(db, student.household_id)
        assignment = Assignment(
            student_id=student.id,
            curriculum_resource_id=4242,
            title="Ghost resource",
            scheduled_date=date(2026, 9, 8),
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(assignment)
        db.commit()

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 0
        assert report.skipped_orphan_links == 1
        assert db.query(Enrollment).count() == 0

    def test_date_outside_every_year_is_skipped(self, db: Session) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        _year_row(db, student.household_id)
        _book_assignment(
            db,
            student,
            resource=_resource(db, edition),
            scheduled=date(2024, 1, 15),
        )

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 0
        assert report.skipped_no_year == 1
        assert db.query(Enrollment).count() == 0

    def test_overlapping_years_are_not_guessed(self, db: Session) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        _year_row(db, student.household_id, "A", date(2026, 8, 1), date(2027, 6, 30))
        _year_row(db, student.household_id, "B", date(2026, 9, 1), date(2026, 12, 31))
        _book_assignment(
            db,
            student,
            resource=_resource(db, edition),
            scheduled=date(2026, 9, 15),
        )

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 0
        assert report.skipped_ambiguous_year == 1
        assert db.query(Enrollment).count() == 0

    def test_multiple_students_stay_distinct(self, db: Session) -> None:
        student = seed_student(db)
        sibling = Student(household_id=student.household_id, name="Blaise")
        db.add(sibling)
        db.commit()
        db.refresh(sibling)
        edition = seed_curriculum_edition(db)
        year = _year_row(db, student.household_id)
        resource = _resource(db, edition)
        _book_assignment(db, student, resource=resource, title="Ada lesson")
        _book_assignment(db, sibling, resource=resource, title="Blaise lesson")

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 2
        rows = db.query(Enrollment).order_by(Enrollment.student_id).all()
        assert [row.student_id for row in rows] == [student.id, sibling.id]
        assert {row.curriculum_id for row in rows} == {edition.curriculum_id}
        assert {row.school_year_id for row in rows} == {year.id}

    def test_multiple_school_years_stay_distinct(self, db: Session) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        first = _year_row(
            db, student.household_id, "2025-2026", date(2025, 8, 1), date(2026, 6, 30)
        )
        second = _year_row(
            db, student.household_id, "2026-2027", date(2026, 8, 1), date(2027, 6, 30)
        )
        resource = _resource(db, edition)
        _book_assignment(
            db, student, resource=resource, scheduled=date(2025, 9, 8), title="Y1"
        )
        _book_assignment(
            db, student, resource=resource, scheduled=date(2026, 9, 8), title="Y2"
        )

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 2
        rows = db.query(Enrollment).order_by(Enrollment.school_year_id).all()
        assert {row.school_year_id for row in rows} == {first.id, second.id}
        assert {row.student_id for row in rows} == {student.id}

    def test_unit_only_assignment_still_proves_curriculum(self, db: Session) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db)
        year = _year_row(db, student.household_id)
        unit = CurriculumUnit(
            curriculum_edition_id=edition.id,
            kind=UnitKind.LESSON,
            title="Lesson 1",
            sort_order=0,
            depth=0,
        )
        db.add(unit)
        db.commit()
        db.refresh(unit)
        _book_assignment(db, student, unit=unit)

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 1
        assert db.query(Enrollment).one().curriculum_id == edition.curriculum_id
        assert db.query(Enrollment).one().school_year_id == year.id

    def test_curriculum_without_assignments_is_not_enrolled(self, db: Session) -> None:
        student = seed_student(db)
        seed_curriculum_edition(db, title="Unused")
        _year_row(db, student.household_id)

        report = reconcile_enrollments(db, dry_run=False)
        assert report.inserted == 0
        assert db.query(Enrollment).count() == 0

    def test_empty_session_has_enrollments_table(self, db: Session) -> None:
        report = discover_missing_enrollments(db)
        assert report.candidates == []
        assert inspect(db.get_bind()).has_table("enrollments")


class TestPortfolioSeesBackfill:
    def test_reading_list_includes_reconstructed_enrollment(
        self, client: TestClient, db: Session
    ) -> None:
        student = seed_student(db)
        edition = seed_curriculum_edition(db, title="Saxon Math 3")
        year = _year(client, "2026-2027", "2026-08-01", "2027-06-30")
        _book_assignment(db, student, resource=_resource(db, edition))
        assert db.query(Enrollment).count() == 0

        reconcile_enrollments(db, dry_run=False)
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
        assert db.query(Enrollment).one().school_year_id == year["id"]


class TestTenantFileIsolation:
    def test_two_tenant_files_stay_isolated(self, tmp_path: Path) -> None:
        def _build(path: Path, household_name: str, title: str) -> None:
            engine = create_engine(
                f"sqlite:///{path}",
                connect_args={"check_same_thread": False},
            )
            apply_tenant_schema(engine)
            factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            session = factory()
            try:
                household = Household(name=household_name)
                student = Student(household=household, name="Ada")
                curriculum = Curriculum(title=title)
                edition = CurriculumEdition(curriculum=curriculum, edition_label="1")
                session.add_all([student, edition])
                session.flush()
                year = SchoolYear(
                    household_id=household.id,
                    name="2026-2027",
                    start_date=date(2026, 8, 1),
                    end_date=date(2027, 6, 30),
                )
                resource = CurriculumResource(
                    curriculum_edition_id=edition.id,
                    kind=ResourceKind.STUDENT_TEXT,
                    title="Text",
                )
                session.add_all([year, resource])
                session.flush()
                session.add(
                    Assignment(
                        student_id=student.id,
                        curriculum_resource_id=resource.id,
                        title="Lesson",
                        scheduled_date=date(2026, 9, 8),
                        status=AssignmentStatus.ASSIGNED,
                    )
                )
                session.commit()
            finally:
                session.close()
                engine.dispose()

        family_a = tmp_path / "tenant_family-a.db"
        family_b = tmp_path / "tenant_family-b.db"
        _build(family_a, "A", "Saxon Math 3")
        _build(family_b, "B", "History Quest")

        dry = dict(backfill_data_dir(tmp_path, dry_run=True))
        assert len(dry[family_a].candidates) == 1
        assert len(dry[family_b].candidates) == 1
        assert dry[family_a].inserted == 0

        backfill_data_dir(tmp_path, dry_run=False)

        def _enrollments(path: Path) -> list[tuple[int, int, int]]:
            engine = create_engine(
                f"sqlite:///{path}",
                connect_args={"check_same_thread": False},
            )
            factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            session = factory()
            try:
                rows = session.query(Enrollment).all()
                return [
                    (row.student_id, row.curriculum_id, row.school_year_id)
                    for row in rows
                ]
            finally:
                session.close()
                engine.dispose()

        a_rows = _enrollments(family_a)
        b_rows = _enrollments(family_b)
        assert len(a_rows) == 1
        assert len(b_rows) == 1

        engine_a = create_engine(f"sqlite:///{family_a}")
        try:
            with engine_a.connect() as conn:
                titles = {
                    row[0]
                    for row in conn.execute(text("SELECT title FROM curricula"))
                }
                assignment_count = conn.execute(
                    text("SELECT COUNT(*) FROM assignments")
                ).scalar()
            assert titles == {"Saxon Math 3"}
            assert assignment_count == 1
        finally:
            engine_a.dispose()
