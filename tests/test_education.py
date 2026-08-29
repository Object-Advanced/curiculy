"""Core educational data model tests.

The delete rules are checked at both layers, because they are enforced in two
different places and each can regress without the other noticing. The ORM tests
cover what happens when application code calls ``Session.delete``; the
``fk_db`` tests re-check the same rules with SQLite foreign keys switched on, so
a bulk ``DELETE`` that never loads an object still behaves.
"""

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import CatalogBase, TenantBase
from app.enums import AssignmentStatus, AttendanceStatus, ResourceKind, ScoreType, UnitKind
from app.models import (
    Assignment,
    AssignmentEvidence,
    AssignmentGrade,
    Attendance,
    Curriculum,
    CurriculumClassification,
    CurriculumEdition,
    CurriculumResource,
    CurriculumUnit,
    Household,
    ReportingCategory,
    Student,
    SubjectTaxonomy,
)


@pytest.fixture
def fk_db() -> Iterator[Session]:
    """A session whose connection enforces foreign keys.

    SQLite ignores ``ON DELETE`` clauses unless the pragma is set per connection,
    which the application does not do, so it is set here to test the schema's own
    guarantees rather than the ORM's cascade bookkeeping.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record) -> None:  # type: ignore[no-untyped-def]
        connection.execute("PRAGMA foreign_keys=ON")

    CatalogBase.metadata.create_all(engine)
    TenantBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def seed_student(db: Session, name: str = "Ada") -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name=name)
    db.add(student)
    db.commit()
    return student


def seed_resource(db: Session, title: str = "Student Text") -> CurriculumResource:
    curriculum = Curriculum(title="Saxon Math 3")
    edition = CurriculumEdition(curriculum=curriculum, edition_label="3rd edition")
    resource = CurriculumResource(
        curriculum_edition=edition,
        kind=ResourceKind.STUDENT_TEXT,
        title=title,
    )
    db.add(resource)
    db.commit()
    return resource


def seed_assignment(
    db: Session,
    *,
    student: Student | None = None,
    resource: CurriculumResource | None = None,
    with_grade: bool = True,
    evidence_count: int = 2,
) -> Assignment:
    assignment = Assignment(
        student=student or seed_student(db),
        curriculum_resource=resource,
        title="Lesson 1 problem set",
        scheduled_date=date(2026, 9, 16),
        status=AssignmentStatus.ASSIGNED,
        notes="Show the work on the back page.",
    )
    if with_grade:
        assignment.grade = AssignmentGrade(score_type=ScoreType.LETTER, score_value="A+")
    for index in range(evidence_count):
        assignment.evidence.append(
            AssignmentEvidence(file_path=f"/data/evidence/page-{index}.jpg", notes="scan")
        )
    db.add(assignment)
    db.commit()
    return assignment


def count(db: Session, model: type) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


class TestAssignmentCascade:
    def test_deleting_an_assignment_deletes_its_grade_and_evidence(self, db: Session) -> None:
        assignment = seed_assignment(db)
        assert (count(db, AssignmentGrade), count(db, AssignmentEvidence)) == (1, 2)

        db.delete(assignment)
        db.commit()

        assert count(db, Assignment) == 0
        assert count(db, AssignmentGrade) == 0
        assert count(db, AssignmentEvidence) == 0

    def test_cascade_leaves_other_assignments_untouched(self, db: Session) -> None:
        student = seed_student(db)
        doomed = seed_assignment(db, student=student)
        kept = seed_assignment(db, student=student)

        db.delete(doomed)
        db.commit()

        assert count(db, Assignment) == 1
        assert [grade.assignment_id for grade in db.scalars(select(AssignmentGrade))] == [kept.id]
        assert {item.assignment_id for item in db.scalars(select(AssignmentEvidence))} == {kept.id}

    def test_cascade_holds_for_a_bulk_delete_in_the_database(self, fk_db: Session) -> None:
        assignment = seed_assignment(fk_db)

        fk_db.execute(Assignment.__table__.delete().where(Assignment.id == assignment.id))
        fk_db.commit()

        assert count(fk_db, AssignmentGrade) == 0
        assert count(fk_db, AssignmentEvidence) == 0

    def test_deleting_a_student_deletes_their_assignments(self, db: Session) -> None:
        student = seed_student(db)
        seed_assignment(db, student=student)
        db.add(
            Attendance(
                student=student,
                date=date(2026, 9, 16),
                status=AttendanceStatus.PRESENT,
            )
        )
        db.commit()

        db.delete(student)
        db.commit()

        assert count(db, Assignment) == 0
        assert count(db, AssignmentGrade) == 0
        assert count(db, AssignmentEvidence) == 0
        assert count(db, Attendance) == 0

    def test_regrading_in_place_keeps_a_single_row(self, db: Session) -> None:
        assignment = seed_assignment(db)

        assignment.grade.score_type = ScoreType.PERCENTAGE
        assignment.grade.score_value = "88"
        db.commit()
        db.expire_all()

        assert count(db, AssignmentGrade) == 1
        assert assignment.grade.score_value == "88"

    def test_swapping_in_a_new_grade_row_needs_a_flush_between(self, db: Session) -> None:
        """The unique key forces the old row out before the new one goes in.

        A single flush would order the insert first and trip the constraint, so
        re-grading either mutates the existing row or flushes the removal first.
        """
        assignment = seed_assignment(db)

        assignment.grade = None
        db.flush()
        assignment.grade = AssignmentGrade(score_type=ScoreType.PERCENTAGE, score_value="88")
        db.commit()

        assert count(db, AssignmentGrade) == 1
        assert assignment.grade.score_value == "88"


class TestCurriculumResourceUnlinkedReferences:
    def test_deleting_a_resource_keeps_the_assignment_and_its_catalog_id(
        self, db: Session
    ) -> None:
        resource = seed_resource(db)
        assignment = seed_assignment(db, resource=resource)
        resource_id = resource.id
        assert assignment.curriculum_resource_id == resource_id

        db.delete(resource)
        db.commit()
        db.refresh(assignment)

        assert count(db, Assignment) == 1
        assert assignment.curriculum_resource_id == resource_id
        assert assignment.title == "Lesson 1 problem set"
        assert assignment.grade is not None

    def test_a_bulk_delete_in_the_database_leaves_the_tenant_id(
        self, fk_db: Session
    ) -> None:
        resource = seed_resource(fk_db)
        assignment = seed_assignment(fk_db, resource=resource)
        resource_id = resource.id

        fk_db.execute(
            CurriculumResource.__table__.delete().where(CurriculumResource.id == resource.id)
        )
        fk_db.commit()
        fk_db.refresh(assignment)

        assert assignment.curriculum_resource_id == resource_id

    def test_deleting_a_unit_leaves_the_assignment_id_without_touching_history(
        self, db: Session
    ) -> None:
        resource = seed_resource(db)
        unit = CurriculumUnit(
            curriculum_edition_id=resource.curriculum_edition_id,
            kind=UnitKind.LESSON,
            title="Lesson 1",
        )
        db.add(unit)
        db.commit()
        assignment = seed_assignment(db, resource=resource)
        assignment.curriculum_unit = unit
        db.commit()
        unit_id = unit.id

        db.delete(unit)
        db.commit()
        db.refresh(assignment)

        assert count(db, Assignment) == 1
        assert assignment.curriculum_unit_id == unit_id

    def test_deleting_a_subject_leaves_the_assignment_id_without_touching_history(
        self, db: Session
    ) -> None:
        subject = SubjectTaxonomy(name="Reading")
        db.add(subject)
        db.commit()
        assignment = seed_assignment(db)
        assignment.subject_taxonomy = subject
        db.commit()
        subject_id = subject.id

        db.delete(subject)
        db.commit()
        db.refresh(assignment)

        assert count(db, Assignment) == 1
        assert assignment.subject_taxonomy_id == subject_id


class TestAssignmentGradeRoundTrip:
    @pytest.mark.parametrize(
        ("score_type", "score_value"),
        [
            (ScoreType.LETTER, "A+"),
            (ScoreType.LETTER, "B-"),
            (ScoreType.POINTS, "18/20"),
            (ScoreType.PERCENTAGE, "92"),
            (ScoreType.PERCENTAGE, "92.5"),
            (ScoreType.PASS_FAIL, "Pass"),
            (ScoreType.COMPLETE_INCOMPLETE, "Complete"),
            (ScoreType.CUSTOM, "Mastered with narration"),
        ],
    )
    def test_string_scores_survive_a_round_trip(
        self, db: Session, score_type: ScoreType, score_value: str
    ) -> None:
        assignment = seed_assignment(db, with_grade=False)
        assignment.grade = AssignmentGrade(
            score_type=score_type,
            score_value=score_value,
            graded_on=date(2026, 9, 17),
        )
        db.commit()
        db.expire_all()

        stored = db.scalars(select(AssignmentGrade)).one()
        assert stored.score_value == score_value
        assert stored.score_type is score_type
        assert stored.graded_on == date(2026, 9, 17)
        assert stored.assignment.id == assignment.id

    def test_score_type_is_stored_as_its_lowercase_value(self, db: Session) -> None:
        assignment = seed_assignment(db, with_grade=False)
        assignment.grade = AssignmentGrade(
            score_type=ScoreType.PASS_FAIL,
            score_value="Pass",
        )
        db.commit()

        raw = db.execute(
            select(AssignmentGrade.__table__.c.score_type).where(
                AssignmentGrade.__table__.c.assignment_id == assignment.id
            )
        ).scalar_one()
        assert raw == "pass_fail"

    def test_an_assignment_holds_at_most_one_grade(self, db: Session) -> None:
        first = seed_assignment(db)
        db.add(
            AssignmentGrade(assignment_id=first.id, score_type=ScoreType.LETTER, score_value="C")
        )

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_a_grade_is_optional(self, db: Session) -> None:
        assignment = seed_assignment(db, with_grade=False, evidence_count=0)

        assert assignment.grade is None
        assert count(db, AssignmentGrade) == 0


class TestTaxonomy:
    def test_the_tree_is_self_referential_and_renders_a_path(self, db: Session) -> None:
        root = SubjectTaxonomy(name="Language Arts", code="language_arts")
        child = SubjectTaxonomy(name="Reading", parent=root, depth=1)
        grandchild = SubjectTaxonomy(name="Phonics", parent=child, depth=2)
        db.add_all([root, child, grandchild])
        db.commit()

        assert [item.name for item in root.children] == ["Reading"]
        assert grandchild.full_name == "Language Arts > Reading > Phonics"
        assert root.full_name == "Language Arts"

    def test_deleting_a_parent_deletes_the_subtree(self, db: Session) -> None:
        root = SubjectTaxonomy(name="Language Arts")
        child = SubjectTaxonomy(name="Reading", parent=root, depth=1)
        db.add_all([root, SubjectTaxonomy(name="Phonics", parent=child, depth=2)])
        db.commit()

        db.delete(root)
        db.commit()

        assert count(db, SubjectTaxonomy) == 0

    def test_sibling_names_are_unique_within_a_parent(self, db: Session) -> None:
        root = SubjectTaxonomy(name="Language Arts")
        db.add_all(
            [
                SubjectTaxonomy(name="Reading", parent=root, depth=1),
                SubjectTaxonomy(name="Reading", parent=root, depth=1),
            ]
        )

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_a_classification_files_a_resource_under_a_subject_and_a_bucket(
        self, db: Session
    ) -> None:
        resource = seed_resource(db)
        subject = SubjectTaxonomy(name="Reading")
        bucket = ReportingCategory(name="Reading", code="reading")
        db.add_all([subject, bucket])
        db.flush()
        db.add(
            CurriculumClassification(
                curriculum_resource=resource,
                subject_taxonomy_id=subject.id,
                reporting_category_id=bucket.id,
            )
        )
        db.commit()

        classification = resource.classifications[0]
        assert classification.subject_taxonomy_id == subject.id
        assert classification.reporting_category_id == bucket.id
        assert classification.is_primary is True

    def test_deleting_a_reporting_category_keeps_the_classification(
        self, db: Session
    ) -> None:
        resource = seed_resource(db)
        subject = SubjectTaxonomy(name="Reading")
        bucket = ReportingCategory(name="Reading")
        db.add_all([subject, bucket])
        db.flush()
        classification = CurriculumClassification(
            curriculum_resource=resource,
            subject_taxonomy_id=subject.id,
            reporting_category_id=bucket.id,
        )
        db.add(classification)
        db.commit()

        db.delete(bucket)
        db.commit()
        db.refresh(classification)

        assert count(db, CurriculumClassification) == 1
        assert classification.subject_taxonomy_id == subject.id
        assert classification.reporting_category_id == bucket.id

    def test_deleting_a_resource_deletes_its_classifications(self, db: Session) -> None:
        resource = seed_resource(db)
        subject = SubjectTaxonomy(name="Reading")
        db.add(subject)
        db.flush()
        db.add(
            CurriculumClassification(
                curriculum_resource=resource,
                subject_taxonomy_id=subject.id,
            )
        )
        db.commit()

        db.delete(resource)
        db.commit()

        assert count(db, CurriculumClassification) == 0
        assert count(db, SubjectTaxonomy) == 1
