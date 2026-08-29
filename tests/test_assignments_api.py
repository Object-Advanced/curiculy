"""Assignment calendar and detail endpoint tests.

The date fixtures are built around Wednesday 2026-09-16 so every boundary has a
neighbour one day outside it. Each period test seeds assignments on the day
before the window opens and the day after it closes, which is what catches an
off-by-one in either bound; asserting only on the days inside would pass even if
a bound were open-ended.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import AssignmentStatus, CalendarPeriod, ResourceKind, ScoreType, UnitKind
from app.models import (
    DEFAULT_STUDENT_COLOR,
    Assignment,
    AssignmentEvidence,
    AssignmentGrade,
    Curriculum,
    CurriculumEdition,
    CurriculumResource,
    CurriculumUnit,
    Enrollment,
    Household,
    SchoolYear,
    Student,
    SubjectTaxonomy,
)
from app.services.assignments import (
    UNBOUNDED,
    AssignmentQuery,
    DateRange,
    InvalidDateRangeError,
    resolve_period,
    resolve_window,
)

# Wednesday. Its week is 2026-09-14 (Mon) to 2026-09-20 (Sun).
ANCHOR = date(2026, 9, 16)


@pytest.fixture
def student(db: Session) -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name="Ada")
    db.add(student)
    db.commit()
    return student


@pytest.fixture
def other_student(db: Session, student: Student) -> Student:
    sibling = Student(household_id=student.household_id, name="Blaise")
    db.add(sibling)
    db.commit()
    return sibling


def add_assignment(
    db: Session,
    student: Student,
    scheduled_date: date,
    title: str | None = None,
) -> Assignment:
    assignment = Assignment(
        student_id=student.id,
        title=title or f"Work for {scheduled_date.isoformat()}",
        scheduled_date=scheduled_date,
    )
    db.add(assignment)
    db.commit()
    return assignment


def add_days(db: Session, student: Student, days: list[date]) -> None:
    for day in days:
        add_assignment(db, student, day)


def add_course_resource(db: Session, title: str) -> CurriculumResource:
    curriculum = Curriculum(title=title)
    edition = CurriculumEdition(curriculum=curriculum, edition_label="1st edition")
    resource = CurriculumResource(
        curriculum_edition=edition,
        kind=ResourceKind.STUDENT_TEXT,
        title=f"{title} Text",
    )
    db.add(resource)
    db.commit()
    return resource


def add_course_assignment(
    db: Session,
    student: Student,
    resource: CurriculumResource,
    scheduled_date: date,
    *,
    title: str | None = None,
    status: AssignmentStatus = AssignmentStatus.ASSIGNED,
) -> Assignment:
    assignment = Assignment(
        student_id=student.id,
        curriculum_resource=resource,
        title=title or f"{resource.title} {scheduled_date.isoformat()}",
        scheduled_date=scheduled_date,
        status=status,
    )
    db.add(assignment)
    db.commit()
    return assignment


def returned_dates(response) -> list[str]:
    return [item["scheduled_date"] for item in response.json()["assignments"]]


@contextmanager
def count_queries(db: Session) -> Iterator[list[str]]:
    statements: list[str] = []
    bind = db.get_bind()

    def record(_conn, _cursor, statement, _params, _context, _many) -> None:
        statements.append(statement)

    event.listen(bind, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", record)


class TestPeriodResolution:
    @pytest.mark.parametrize(
        ("anchor", "expected"),
        [
            (date(2026, 9, 14), (date(2026, 9, 14), date(2026, 9, 20))),  # Monday
            (date(2026, 9, 16), (date(2026, 9, 14), date(2026, 9, 20))),  # Wednesday
            (date(2026, 9, 20), (date(2026, 9, 14), date(2026, 9, 20))),  # Sunday
        ],
    )
    def test_a_week_runs_monday_to_sunday(
        self, anchor: date, expected: tuple[date, date]
    ) -> None:
        window = resolve_period(anchor, CalendarPeriod.WEEK)

        assert (window.start_date, window.end_date) == expected

    def test_a_week_can_straddle_a_month_and_a_year(self) -> None:
        assert resolve_period(date(2026, 12, 31), CalendarPeriod.WEEK) == DateRange(
            date(2026, 12, 28), date(2027, 1, 3)
        )

    @pytest.mark.parametrize(
        ("anchor", "expected"),
        [
            (date(2026, 9, 16), (date(2026, 9, 1), date(2026, 9, 30))),
            (date(2026, 2, 10), (date(2026, 2, 1), date(2026, 2, 28))),
            (date(2028, 2, 10), (date(2028, 2, 1), date(2028, 2, 29))),  # leap year
            (date(2026, 12, 25), (date(2026, 12, 1), date(2026, 12, 31))),
            (date(2026, 1, 1), (date(2026, 1, 1), date(2026, 1, 31))),
        ],
    )
    def test_a_month_ends_on_the_real_last_day(
        self, anchor: date, expected: tuple[date, date]
    ) -> None:
        window = resolve_period(anchor, CalendarPeriod.MONTH)

        assert (window.start_date, window.end_date) == expected

    def test_a_day_is_a_single_inclusive_date(self) -> None:
        assert resolve_period(ANCHOR, CalendarPeriod.DAY) == DateRange(ANCHOR, ANCHOR)

    def test_a_year_spans_january_to_december(self) -> None:
        assert resolve_period(ANCHOR, CalendarPeriod.YEAR) == DateRange(
            date(2026, 1, 1), date(2026, 12, 31)
        )

    def test_a_period_anchors_on_today_when_no_date_is_given(self) -> None:
        window = resolve_window(period=CalendarPeriod.MONTH, today=date(2028, 2, 10))

        assert window == DateRange(date(2028, 2, 1), date(2028, 2, 29))

    def test_explicit_bounds_pass_through_untouched(self) -> None:
        window = resolve_window(start_date=date(2026, 1, 5), end_date=date(2026, 3, 9))

        assert window == DateRange(date(2026, 1, 5), date(2026, 3, 9))

    def test_a_single_bound_stays_open_ended(self) -> None:
        assert resolve_window(start_date=ANCHOR) == DateRange(ANCHOR, None)
        assert resolve_window(end_date=ANCHOR) == DateRange(None, ANCHOR)
        assert resolve_window() == UNBOUNDED

    def test_an_inverted_range_is_rejected(self) -> None:
        with pytest.raises(InvalidDateRangeError):
            resolve_window(start_date=date(2026, 9, 20), end_date=date(2026, 9, 14))

    def test_a_period_combined_with_an_end_date_is_rejected(self) -> None:
        with pytest.raises(InvalidDateRangeError):
            resolve_window(end_date=ANCHOR, period=CalendarPeriod.WEEK)

    def test_equal_bounds_are_a_valid_single_day(self) -> None:
        assert resolve_window(start_date=ANCHOR, end_date=ANCHOR) == DateRange(ANCHOR, ANCHOR)

    @pytest.mark.parametrize(
        ("day", "inside"),
        [(date(2026, 9, 13), False), (date(2026, 9, 14), True), (date(2026, 9, 21), False)],
    )
    def test_contains_is_inclusive_on_both_ends(self, day: date, inside: bool) -> None:
        assert resolve_period(ANCHOR, CalendarPeriod.WEEK).contains(day) is inside


class TestCalendarPeriodFiltering:
    def test_a_week_excludes_the_days_on_either_side(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(
            db,
            student,
            [
                date(2026, 9, 13),  # Sunday before
                date(2026, 9, 14),  # Monday, first day in
                date(2026, 9, 16),
                date(2026, 9, 20),  # Sunday, last day in
                date(2026, 9, 21),  # Monday after
            ],
        )

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "period": "week"},
        )

        assert response.status_code == 200
        assert returned_dates(response) == ["2026-09-14", "2026-09-16", "2026-09-20"]
        assert response.json()["start_date"] == "2026-09-14"
        assert response.json()["end_date"] == "2026-09-20"
        assert response.json()["count"] == 3

    def test_a_month_excludes_the_days_on_either_side(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(
            db,
            student,
            [
                date(2026, 8, 31),
                date(2026, 9, 1),
                date(2026, 9, 30),
                date(2026, 10, 1),
            ],
        )

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "period": "month"},
        )

        assert returned_dates(response) == ["2026-09-01", "2026-09-30"]

    def test_a_february_month_in_a_leap_year_includes_the_29th(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 1)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2028-02-10", "period": "month"},
        )

        assert returned_dates(response) == ["2028-02-29"]
        assert response.json()["end_date"] == "2028-02-29"

    def test_a_december_month_stops_at_the_year_end(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2026, 12, 1), date(2026, 12, 31), date(2027, 1, 1)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-12-25", "period": "month"},
        )

        assert returned_dates(response) == ["2026-12-01", "2026-12-31"]

    def test_a_year_excludes_the_days_on_either_side(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(
            db,
            student,
            [
                date(2025, 12, 31),
                date(2026, 1, 1),
                date(2026, 6, 15),
                date(2026, 12, 31),
                date(2027, 1, 1),
            ],
        )

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "period": "year"},
        )

        assert returned_dates(response) == ["2026-01-01", "2026-06-15", "2026-12-31"]

    def test_a_day_returns_only_that_date(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2026, 9, 15), ANCHOR, date(2026, 9, 17)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "period": "day"},
        )

        assert returned_dates(response) == ["2026-09-16"]
        assert response.json()["start_date"] == response.json()["end_date"] == "2026-09-16"

    def test_a_week_straddling_a_year_boundary_spans_both_years(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(
            db,
            student,
            [date(2026, 12, 27), date(2026, 12, 28), date(2027, 1, 3), date(2027, 1, 4)],
        )

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-12-31", "period": "week"},
        )

        assert returned_dates(response) == ["2026-12-28", "2027-01-03"]

    def test_a_period_with_no_date_uses_today(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        today = date.today()
        add_days(db, student, [today, today + timedelta(days=400)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"period": "day"},
        )

        assert returned_dates(response) == [today.isoformat()]
        assert response.json()["start_date"] == today.isoformat()

    def test_an_empty_window_returns_an_empty_list(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2026, 9, 13), date(2026, 9, 21)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "period": "week"},
        )

        assert response.status_code == 200
        assert response.json()["assignments"] == []
        assert response.json()["count"] == 0


class TestExplicitDateBounds:
    def test_both_bounds_are_inclusive(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(
            db,
            student,
            [date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 20), date(2026, 9, 21)],
        )

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-10", "end_date": "2026-09-20"},
        )

        assert returned_dates(response) == ["2026-09-10", "2026-09-20"]

    def test_a_start_date_alone_is_an_open_ended_lower_bound(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2026, 9, 15), ANCHOR, date(2027, 5, 1)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16"},
        )

        assert returned_dates(response) == ["2026-09-16", "2027-05-01"]
        assert response.json()["end_date"] is None

    def test_an_end_date_alone_is_an_open_ended_upper_bound(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2025, 1, 1), ANCHOR, date(2026, 9, 17)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"end_date": "2026-09-16"},
        )

        assert returned_dates(response) == ["2025-01-01", "2026-09-16"]
        assert response.json()["start_date"] is None

    def test_no_parameters_returns_everything_in_date_order(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2027, 1, 1), date(2025, 1, 1), ANCHOR])

        response = client.get(f"/api/students/{student.id}/assignments")

        assert returned_dates(response) == ["2025-01-01", "2026-09-16", "2027-01-01"]
        assert response.json()["period"] is None

    def test_equal_bounds_select_a_single_day(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_days(db, student, [date(2026, 9, 15), ANCHOR, date(2026, 9, 17)])

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "end_date": "2026-09-16"},
        )

        assert returned_dates(response) == ["2026-09-16"]

    def test_same_day_assignments_are_ordered_by_id(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        first = add_assignment(db, student, ANCHOR, title="Math")
        second = add_assignment(db, student, ANCHOR, title="Reading")

        response = client.get(f"/api/students/{student.id}/assignments")

        assert [item["id"] for item in response.json()["assignments"]] == [first.id, second.id]


class TestRequestValidation:
    def test_an_inverted_range_is_a_400(self, client: TestClient, student: Student) -> None:
        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-20", "end_date": "2026-09-14"},
        )

        assert response.status_code == 400
        assert "after end_date" in response.json()["detail"]

    def test_a_period_with_an_end_date_is_a_400(
        self, client: TestClient, student: Student
    ) -> None:
        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"end_date": "2026-09-20", "period": "week"},
        )

        assert response.status_code == 400
        assert "period" in response.json()["detail"]

    @pytest.mark.parametrize("period", ["quarter", "fortnight", "WEEK", ""])
    def test_an_unknown_period_is_a_422(
        self, client: TestClient, student: Student, period: str
    ) -> None:
        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"period": period},
        )

        assert response.status_code == 422

    def test_a_malformed_date_is_a_422(self, client: TestClient, student: Student) -> None:
        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "the-16th"},
        )

        assert response.status_code == 422

    def test_an_unknown_student_is_a_404(self, client: TestClient) -> None:
        response = client.get("/api/students/4242/assignments")

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"


class TestStudentScoping:
    def test_only_the_requested_student_is_returned(
        self, client: TestClient, db: Session, student: Student, other_student: Student
    ) -> None:
        add_assignment(db, student, ANCHOR, title="Ada's math")
        add_assignment(db, other_student, ANCHOR, title="Blaise's math")

        response = client.get(f"/api/students/{student.id}/assignments")

        assert [item["title"] for item in response.json()["assignments"]] == ["Ada's math"]
        assert response.json()["student_id"] == student.id

    def test_a_student_with_no_assignments_returns_an_empty_window(
        self, client: TestClient, student: Student
    ) -> None:
        response = client.get(f"/api/students/{student.id}/assignments")

        assert response.status_code == 200
        assert response.json() == {
            "student_id": student.id,
            "period": None,
            "start_date": None,
            "end_date": None,
            "count": 0,
            "assignments": [],
        }


class TestStudentCourses:
    def test_counts_completed_and_total_assignments_per_curriculum(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        math = add_course_resource(db, "Saxon Math 3")
        reading = add_course_resource(db, "Ordinary Language")
        add_course_assignment(db, student, math, ANCHOR, status=AssignmentStatus.COMPLETED)
        add_course_assignment(db, student, math, ANCHOR + timedelta(days=1))
        add_course_assignment(db, student, math, ANCHOR + timedelta(days=2))
        add_course_assignment(
            db, student, reading, ANCHOR, status=AssignmentStatus.COMPLETED
        )
        add_course_assignment(
            db, student, reading, ANCHOR + timedelta(days=1), status=AssignmentStatus.COMPLETED
        )

        response = client.get(f"/api/students/{student.id}/courses")

        assert response.status_code == 200
        by_title = {row["title"]: row for row in response.json()}
        assert by_title["Ordinary Language"]["total_assignments"] == 2
        assert by_title["Ordinary Language"]["completed_assignments"] == 2
        assert by_title["Saxon Math 3"]["total_assignments"] == 3
        assert by_title["Saxon Math 3"]["completed_assignments"] == 1
        assert by_title["Saxon Math 3"]["curriculum_id"] == math.curriculum_edition.curriculum_id

    def test_an_enrollment_with_no_assignments_is_zero_of_zero(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        curriculum = Curriculum(title="History Quest")
        year = SchoolYear(
            household_id=student.household_id,
            name="2026-2027",
            start_date=date(2026, 8, 1),
            end_date=date(2027, 5, 31),
        )
        db.add_all([curriculum, year])
        db.commit()
        db.add(
            Enrollment(
                student_id=student.id,
                curriculum_id=curriculum.id,
                school_year_id=year.id,
            )
        )
        db.commit()

        response = client.get(f"/api/students/{student.id}/courses")

        assert response.json() == [
            {
                "curriculum_id": curriculum.id,
                "title": "History Quest",
                "total_assignments": 0,
                "completed_assignments": 0,
            }
        ]

    def test_a_sibling_student_is_not_counted(
        self, client: TestClient, db: Session, student: Student, other_student: Student
    ) -> None:
        math = add_course_resource(db, "Saxon Math 3")
        add_course_assignment(db, student, math, ANCHOR)
        add_course_assignment(
            db, other_student, math, ANCHOR, status=AssignmentStatus.COMPLETED
        )

        response = client.get(f"/api/students/{student.id}/courses")

        assert response.json() == [
            {
                "curriculum_id": math.curriculum_edition.curriculum_id,
                "title": "Saxon Math 3",
                "total_assignments": 1,
                "completed_assignments": 0,
            }
        ]

    def test_manual_assignments_without_a_curriculum_are_omitted(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_assignment(db, student, ANCHOR, title="Dentist")

        response = client.get(f"/api/students/{student.id}/courses")

        assert response.status_code == 200
        assert response.json() == []

    def test_an_unknown_student_is_a_404(self, client: TestClient) -> None:
        response = client.get("/api/students/4242/courses")

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"


class TestCalendarPayload:
    @pytest.fixture
    def furnished(self, db: Session, student: Student) -> Assignment:
        curriculum = Curriculum(title="Saxon Math 3")
        edition = CurriculumEdition(curriculum=curriculum, edition_label="3rd edition")
        resource = CurriculumResource(
            curriculum_edition=edition,
            kind=ResourceKind.STUDENT_TEXT,
            title="Student Text",
        )
        unit = CurriculumUnit(
            curriculum_edition=edition,
            kind=UnitKind.LESSON,
            title="Lesson 1: Sequences",
        )
        root = SubjectTaxonomy(name="Language Arts", code="language_arts")
        subject = SubjectTaxonomy(name="Reading", parent=root, depth=1)
        db.add_all([resource, unit, subject])
        db.flush()
        assignment = Assignment(
            student_id=student.id,
            curriculum_resource_id=resource.id,
            curriculum_unit_id=unit.id,
            subject_taxonomy_id=subject.id,
            title="Lesson 1 problem set",
            scheduled_date=ANCHOR,
            completion_date=date(2026, 9, 17),
            status=AssignmentStatus.COMPLETED,
            notes="Show the work on the back page.",
        )
        assignment.grade = AssignmentGrade(
            score_type=ScoreType.POINTS,
            score_value="18/20",
            graded_on=date(2026, 9, 17),
        )
        assignment.evidence.append(AssignmentEvidence(file_path="/data/evidence/a.jpg"))
        assignment.evidence.append(AssignmentEvidence(url="https://example.com/work"))
        db.add(assignment)
        db.commit()
        assignment.curriculum_resource = resource
        assignment.curriculum_unit = unit
        assignment.subject_taxonomy = subject
        return assignment

    def test_a_calendar_tile_carries_the_text_it_needs_to_render(
        self, client: TestClient, student: Student, furnished: Assignment
    ) -> None:
        response = client.get(f"/api/students/{student.id}/assignments")

        tile = response.json()["assignments"][0]
        assert tile["title"] == "Lesson 1 problem set"
        assert tile["status"] == "completed"
        assert tile["completion_date"] == "2026-09-17"
        assert tile["subject_name"] == "Reading"
        assert tile["resource_title"] == "Student Text"
        assert tile["unit_title"] == "Lesson 1: Sequences"
        assert tile["curriculum_id"] == furnished.curriculum_id
        assert tile["grade"]["score_value"] == "18/20"
        assert tile["grade"]["score_type"] == "points"
        assert tile["evidence_count"] == 2

    def test_an_unfurnished_assignment_has_null_display_fields(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        add_assignment(db, student, ANCHOR)

        tile = client.get(f"/api/students/{student.id}/assignments").json()["assignments"][0]

        assert tile["subject_name"] is None
        assert tile["resource_title"] is None
        assert tile["unit_title"] is None
        assert tile["curriculum_id"] is None
        assert tile["grade"] is None
        assert tile["evidence_count"] == 0
        assert tile["status"] == "assigned"
        assert tile["shared_group_uuid"] is None

    def test_the_list_view_omits_the_evidence_records(
        self, client: TestClient, student: Student, furnished: Assignment
    ) -> None:
        tile = client.get(f"/api/students/{student.id}/assignments").json()["assignments"][0]

        assert "evidence" not in tile

    def test_the_query_count_does_not_grow_with_the_number_of_assignments(
        self, db: Session, student: Student, furnished: Assignment
    ) -> None:
        """Eager loading costs one query per relationship, not one per assignment."""

        def render() -> tuple[int, int]:
            db.expire_all()
            with count_queries(db) as statements:
                rows = AssignmentQuery(db, db).for_student(student.id, UNBOUNDED)
                rendered = [
                    (
                        row.subject_name,
                        row.resource_title,
                        row.unit_title,
                        row.evidence_count,
                        row.grade,
                    )
                    for row in rows
                ]
            return len(rendered), len(statements)

        for offset in range(1, 5):
            add_assignment(db, student, ANCHOR + timedelta(days=offset))
        few_rows, few_queries = render()

        for offset in range(5, 40):
            add_assignment(db, student, ANCHOR + timedelta(days=offset))
        many_rows, many_queries = render()

        assert (few_rows, many_rows) == (5, 40)
        assert few_queries == many_queries


class TestAssignmentDetail:
    def test_the_detail_view_returns_the_grade_evidence_and_notes(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = Assignment(
            student_id=student.id,
            title="Lesson 1 problem set",
            scheduled_date=ANCHOR,
            notes="Show the work on the back page.",
        )
        assignment.grade = AssignmentGrade(score_type=ScoreType.LETTER, score_value="A+")
        assignment.evidence.append(
            AssignmentEvidence(file_path="/data/evidence/a.jpg", notes="front")
        )
        assignment.evidence.append(
            AssignmentEvidence(url="https://example.com/work", notes="link")
        )
        db.add(assignment)
        db.commit()

        response = client.get(f"/api/assignments/{assignment.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["notes"] == "Show the work on the back page."
        assert body["grade"]["score_value"] == "A+"
        assert [item["notes"] for item in body["evidence"]] == ["front", "link"]
        assert body["evidence"][0]["file_path"] == "/data/evidence/a.jpg"
        assert body["evidence"][1]["url"] == "https://example.com/work"
        assert body["evidence_count"] == 2

    def test_the_detail_view_renders_the_full_subject_path(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        root = SubjectTaxonomy(name="Language Arts", code="language_arts")
        child = SubjectTaxonomy(name="Reading", parent=root, depth=1)
        db.add(child)
        db.flush()
        assignment = Assignment(
            student_id=student.id,
            subject_taxonomy_id=child.id,
            title="Read aloud",
            scheduled_date=ANCHOR,
        )
        db.add(assignment)
        db.commit()

        body = client.get(f"/api/assignments/{assignment.id}").json()

        assert body["subject_taxonomy"]["name"] == "Reading"
        assert body["subject_taxonomy"]["full_name"] == "Language Arts > Reading"
        assert body["subject_taxonomy"]["depth"] == 1

    def test_an_ungraded_assignment_has_no_grade_and_no_evidence(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        body = client.get(f"/api/assignments/{assignment.id}").json()

        assert body["grade"] is None
        assert body["evidence"] == []
        assert body["subject_taxonomy"] is None

    def test_an_unknown_assignment_is_a_404(self, client: TestClient) -> None:
        response = client.get("/api/assignments/4242")

        assert response.status_code == 404
        assert response.json()["detail"] == "Assignment not found"


class TestAssignmentCreate:
    def test_a_minimal_assignment_is_created_as_assigned(
        self, client: TestClient, student: Student
    ) -> None:
        response = client.post(
            "/api/assignments",
            json={
                "student_id": student.id,
                "title": "Lesson 4 problem set",
                "scheduled_date": "2026-09-16",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Lesson 4 problem set"
        assert body["scheduled_date"] == "2026-09-16"
        assert body["status"] == "assigned"
        assert body["completion_date"] is None
        assert body["grade"] is None
        assert body["evidence"] == []
        assert body["id"] > 0

    def test_a_created_assignment_appears_on_the_calendar(
        self, client: TestClient, student: Student
    ) -> None:
        created = client.post(
            "/api/assignments",
            json={
                "student_id": student.id,
                "title": "Read aloud",
                "scheduled_date": "2026-09-16",
            },
        ).json()

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "period": "week"},
        )

        assert [item["id"] for item in response.json()["assignments"]] == [created["id"]]

    def test_the_catalog_links_are_stored_and_echoed_back(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        curriculum = Curriculum(title="Saxon Math 3")
        edition = CurriculumEdition(curriculum=curriculum, edition_label="3rd edition")
        resource = CurriculumResource(
            curriculum_edition=edition,
            kind=ResourceKind.STUDENT_TEXT,
            title="Student Text",
        )
        unit = CurriculumUnit(
            curriculum_edition=edition,
            kind=UnitKind.LESSON,
            title="Lesson 1: Sequences",
        )
        root = SubjectTaxonomy(name="Language Arts", code="language_arts")
        subject = SubjectTaxonomy(name="Reading", parent=root, depth=1)
        db.add_all([resource, unit, subject])
        db.commit()

        response = client.post(
            "/api/assignments",
            json={
                "student_id": student.id,
                "title": "Lesson 1 problem set",
                "scheduled_date": "2026-09-16",
                "completion_date": "2026-09-17",
                "status": "completed",
                "notes": "Show the work on the back page.",
                "curriculum_resource_id": resource.id,
                "curriculum_unit_id": unit.id,
                "subject_taxonomy_id": subject.id,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "completed"
        assert body["completion_date"] == "2026-09-17"
        assert body["notes"] == "Show the work on the back page."
        assert body["resource_title"] == "Student Text"
        assert body["unit_title"] == "Lesson 1: Sequences"
        assert body["subject_name"] == "Reading"
        assert body["subject_taxonomy"]["full_name"] == "Language Arts > Reading"

    def test_an_unknown_student_is_a_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/assignments",
            json={"student_id": 4242, "title": "Orphan", "scheduled_date": "2026-09-16"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"

    @pytest.mark.parametrize(
        ("field", "detail"),
        [
            ("curriculum_resource_id", "Curriculum resource not found"),
            ("curriculum_unit_id", "Curriculum unit not found"),
            ("subject_taxonomy_id", "Subject not found"),
        ],
    )
    def test_an_unknown_catalog_reference_is_a_404(
        self, client: TestClient, student: Student, field: str, detail: str
    ) -> None:
        response = client.post(
            "/api/assignments",
            json={
                "student_id": student.id,
                "title": "Dangling reference",
                "scheduled_date": "2026-09-16",
                field: 4242,
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == detail

    def test_a_completion_date_before_the_scheduled_date_is_a_400(
        self, client: TestClient, student: Student
    ) -> None:
        response = client.post(
            "/api/assignments",
            json={
                "student_id": student.id,
                "title": "Finished early",
                "scheduled_date": "2026-09-16",
                "completion_date": "2026-09-15",
            },
        )

        assert response.status_code == 400
        assert "on or after scheduled_date" in response.json()["detail"]

    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "No student", "scheduled_date": "2026-09-16"},
            {"student_id": 1, "scheduled_date": "2026-09-16"},
            {"student_id": 1, "title": "", "scheduled_date": "2026-09-16"},
            {"student_id": 1, "title": "No date"},
            {"student_id": 1, "title": "Bad date", "scheduled_date": "the-16th"},
            {
                "student_id": 1,
                "title": "Bad status",
                "scheduled_date": "2026-09-16",
                "status": "nearly",
            },
        ],
    )
    def test_an_incomplete_payload_is_a_422(
        self, client: TestClient, student: Student, payload: dict
    ) -> None:
        response = client.post("/api/assignments", json=payload)

        assert response.status_code == 422


class TestAssignmentUpdate:
    def test_the_date_and_status_are_updated_together(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR, title="Lesson 1")

        response = client.put(
            f"/api/assignments/{assignment.id}",
            json={
                "scheduled_date": "2026-09-18",
                "completion_date": "2026-09-19",
                "status": "completed",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["scheduled_date"] == "2026-09-18"
        assert body["completion_date"] == "2026-09-19"
        assert body["status"] == "completed"

    def test_an_update_is_persisted_not_just_echoed(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        client.put(f"/api/assignments/{assignment.id}", json={"status": "in_progress"})

        assert client.get(f"/api/assignments/{assignment.id}").json()["status"] == "in_progress"
        assert assignment.status is AssignmentStatus.IN_PROGRESS

    def test_omitted_fields_are_left_alone(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = Assignment(
            student_id=student.id,
            title="Lesson 1",
            scheduled_date=ANCHOR,
            completion_date=date(2026, 9, 17),
            status=AssignmentStatus.COMPLETED,
            notes="Keep me.",
        )
        db.add(assignment)
        db.commit()

        body = client.put(
            f"/api/assignments/{assignment.id}",
            json={"scheduled_date": "2026-09-17"},
        ).json()

        assert body["scheduled_date"] == "2026-09-17"
        assert body["completion_date"] == "2026-09-17"
        assert body["status"] == "completed"
        assert body["notes"] == "Keep me."

    def test_an_explicit_null_clears_the_completion_date(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = Assignment(
            student_id=student.id,
            title="Reopened",
            scheduled_date=ANCHOR,
            completion_date=date(2026, 9, 17),
            status=AssignmentStatus.COMPLETED,
        )
        db.add(assignment)
        db.commit()

        body = client.put(
            f"/api/assignments/{assignment.id}",
            json={"completion_date": None, "status": "in_progress"},
        ).json()

        assert body["completion_date"] is None
        assert body["status"] == "in_progress"

    def test_rescheduling_moves_the_assignment_between_windows(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        client.put(f"/api/assignments/{assignment.id}", json={"scheduled_date": "2026-10-05"})

        this_week = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-16", "period": "week"},
        )
        that_week = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-10-05", "period": "week"},
        )

        assert this_week.json()["count"] == 0
        assert returned_dates(that_week) == ["2026-10-05"]

    def test_an_empty_body_is_accepted_and_changes_nothing(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR, title="Untouched")

        response = client.put(f"/api/assignments/{assignment.id}", json={})

        assert response.status_code == 200
        assert response.json()["title"] == "Untouched"
        assert response.json()["scheduled_date"] == ANCHOR.isoformat()

    def test_a_completion_date_before_the_stored_scheduled_date_is_a_400(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        response = client.put(
            f"/api/assignments/{assignment.id}",
            json={"completion_date": "2026-09-15"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "completion_date must be on or after scheduled_date"
        )

    def test_rescheduling_past_a_stored_completion_date_is_a_400(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        """The two dates are compared after the merge, not field by field."""
        assignment = Assignment(
            student_id=student.id,
            title="Lesson 1",
            scheduled_date=ANCHOR,
            completion_date=date(2026, 9, 17),
        )
        db.add(assignment)
        db.commit()

        response = client.put(
            f"/api/assignments/{assignment.id}",
            json={"scheduled_date": "2026-09-20"},
        )

        assert response.status_code == 400

    @pytest.mark.parametrize(
        "payload",
        [
            {"status": "nearly"},
            {"scheduled_date": "the-18th"},
            {"scheduled_date": None},
            {"status": None},
        ],
    )
    def test_an_invalid_value_is_a_422(
        self, client: TestClient, db: Session, student: Student, payload: dict
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        response = client.put(f"/api/assignments/{assignment.id}", json=payload)

        assert response.status_code == 422

    def test_an_unknown_assignment_is_a_404(self, client: TestClient) -> None:
        response = client.put("/api/assignments/4242", json={"status": "completed"})

        assert response.status_code == 404
        assert response.json()["detail"] == "Assignment not found"


class TestAssignmentStatusPatch:
    def test_patching_status_to_completed_updates_the_assignment(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR, title="Lesson 1 problem set")

        response = client.patch(
            f"/api/assignments/{assignment.id}/status",
            json={"status": "completed"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == assignment.id
        assert body["status"] == "completed"
        assert body["title"] == "Lesson 1 problem set"
        assert client.get(f"/api/assignments/{assignment.id}").json()["status"] == "completed"
        assert assignment.status is AssignmentStatus.COMPLETED

    def test_completing_a_shared_assignment_marks_the_siblings(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
    ) -> None:
        group = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        target = Assignment(
            student_id=student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        sibling = Assignment(
            student_id=other_student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        unrelated = add_assignment(db, student, ANCHOR, title="Private work")
        db.add_all([target, sibling])
        db.commit()

        response = client.patch(
            f"/api/assignments/{target.id}/status",
            json={"status": "completed"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert client.get(f"/api/assignments/{sibling.id}").json()["status"] == "completed"
        assert client.get(f"/api/assignments/{unrelated.id}").json()["status"] == "assigned"

    def test_reopening_a_shared_assignment_reopens_the_siblings(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
    ) -> None:
        group = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        target = Assignment(
            student_id=student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            status=AssignmentStatus.COMPLETED,
            shared_group_uuid=group,
        )
        sibling = Assignment(
            student_id=other_student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            status=AssignmentStatus.COMPLETED,
            shared_group_uuid=group,
        )
        db.add_all([target, sibling])
        db.commit()

        response = client.patch(
            f"/api/assignments/{target.id}/status",
            json={"status": "assigned"},
        )

        assert response.status_code == 200
        assert client.get(f"/api/assignments/{sibling.id}").json()["status"] == "assigned"

    def test_put_status_also_syncs_the_shared_group(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
    ) -> None:
        group = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        target = Assignment(
            student_id=student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        sibling = Assignment(
            student_id=other_student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        db.add_all([target, sibling])
        db.commit()

        response = client.put(
            f"/api/assignments/{target.id}",
            json={"status": "completed", "completion_date": "2026-09-16"},
        )

        assert response.status_code == 200
        sibling_body = client.get(f"/api/assignments/{sibling.id}").json()
        assert sibling_body["status"] == "completed"
        assert sibling_body["completion_date"] == "2026-09-16"


class TestGradeUpsert:
    """The grade is one row per assignment, so a second write must not insert.

    ``Assignment.grade`` is a ``delete-orphan`` relationship guarded by a unique
    constraint on ``assignment_id``. Replacing the object rather than mutating it
    makes the flush insert the new row before deleting the old one, which is an
    ``IntegrityError``; every test here goes through the endpoint twice or more so
    that mistake cannot pass.
    """

    def test_the_first_write_creates_the_grade(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        response = client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={
                "score_type": "points",
                "score_value": "18/20",
                "graded_on": "2026-09-17",
                "notes": "Careless on question 4.",
            },
        )

        assert response.status_code == 200
        grade = response.json()["grade"]
        assert grade["score_type"] == "points"
        assert grade["score_value"] == "18/20"
        assert grade["graded_on"] == "2026-09-17"
        assert grade["notes"] == "Careless on question 4."

    def test_a_second_write_mutates_the_existing_row(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        first = client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={"score_type": "letter", "score_value": "B"},
        )
        second = client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={"score_type": "letter", "score_value": "A+"},
        )

        assert (first.status_code, second.status_code) == (200, 200)
        assert second.json()["grade"]["score_value"] == "A+"
        # Same primary key, so the row was updated rather than replaced.
        assert second.json()["grade"]["id"] == first.json()["grade"]["id"]
        assert db.query(AssignmentGrade).count() == 1

    def test_regrading_an_assignment_seeded_with_a_grade_does_not_conflict(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        """The pre-existing row is loaded from the database, not from the session."""
        assignment = add_assignment(db, student, ANCHOR)
        assignment.grade = AssignmentGrade(
            score_type=ScoreType.PERCENTAGE,
            score_value="72",
            graded_on=date(2026, 9, 17),
            notes="First attempt.",
        )
        db.commit()
        original_id = assignment.grade.id
        db.expire_all()

        response = client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={"score_type": "percentage", "score_value": "94"},
        )

        assert response.status_code == 200
        assert response.json()["grade"]["id"] == original_id
        assert response.json()["grade"]["score_value"] == "94"
        assert db.query(AssignmentGrade).count() == 1

    def test_repeated_writes_never_accumulate_rows(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        for score in ("50", "60", "70", "80", "90"):
            response = client.put(
                f"/api/assignments/{assignment.id}/grade",
                json={"score_value": score},
            )
            assert response.status_code == 200

        assert db.query(AssignmentGrade).count() == 1
        assert client.get(f"/api/assignments/{assignment.id}").json()["grade"][
            "score_value"
        ] == "90"

    def test_omitted_optional_fields_are_cleared_on_replacement(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        """The grade is replaced wholesale, which is how a note gets erased."""
        assignment = add_assignment(db, student, ANCHOR)

        client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={"score_value": "88", "graded_on": "2026-09-17", "notes": "Marked in ink."},
        )
        body = client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={"score_value": "88"},
        ).json()

        assert body["grade"]["graded_on"] is None
        assert body["grade"]["notes"] is None

    def test_the_score_type_defaults_to_percentage(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        body = client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={"score_value": "92"},
        ).json()

        assert body["grade"]["score_type"] == "percentage"

    def test_grading_leaves_the_rest_of_the_assignment_alone(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = Assignment(
            student_id=student.id,
            title="Lesson 1",
            scheduled_date=ANCHOR,
            status=AssignmentStatus.COMPLETED,
            completion_date=date(2026, 9, 17),
            notes="Keep me.",
        )
        assignment.evidence.append(AssignmentEvidence(url="https://example.com/work"))
        db.add(assignment)
        db.commit()

        body = client.put(
            f"/api/assignments/{assignment.id}/grade",
            json={"score_value": "92"},
        ).json()

        assert body["status"] == "completed"
        assert body["completion_date"] == "2026-09-17"
        assert body["notes"] == "Keep me."
        assert body["evidence_count"] == 1

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"score_value": ""},
            {"score_value": None},
            {"score_value": "92", "score_type": "vibes"},
            {"score_value": "92", "graded_on": "the-17th"},
        ],
    )
    def test_an_invalid_grade_is_a_422(
        self, client: TestClient, db: Session, student: Student, payload: dict
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        response = client.put(f"/api/assignments/{assignment.id}/grade", json=payload)

        assert response.status_code == 422
        assert db.query(AssignmentGrade).count() == 0

    def test_an_unknown_assignment_is_a_404(self, client: TestClient) -> None:
        response = client.put("/api/assignments/4242/grade", json={"score_value": "A"})

        assert response.status_code == 404
        assert response.json()["detail"] == "Assignment not found"


class TestAssignmentDelete:
    def test_deleting_removes_the_assignment(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        response = client.delete(f"/api/assignments/{assignment.id}")

        assert response.status_code == 204
        assert not response.content
        assert client.get(f"/api/assignments/{assignment.id}").status_code == 404

    def test_the_grade_and_evidence_go_with_it(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)
        assignment.grade = AssignmentGrade(score_type=ScoreType.LETTER, score_value="A")
        assignment.evidence.append(AssignmentEvidence(file_path="/data/evidence/a.jpg"))
        assignment.evidence.append(AssignmentEvidence(url="https://example.com/work"))
        db.commit()

        client.delete(f"/api/assignments/{assignment.id}")

        assert db.query(Assignment).count() == 0
        assert db.query(AssignmentGrade).count() == 0
        assert db.query(AssignmentEvidence).count() == 0

    def test_the_tile_disappears_from_the_calendar(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        kept = add_assignment(db, student, ANCHOR, title="Kept")
        removed = add_assignment(db, student, ANCHOR, title="Removed")

        client.delete(f"/api/assignments/{removed.id}")

        response = client.get(f"/api/students/{student.id}/assignments")
        assert [item["id"] for item in response.json()["assignments"]] == [kept.id]
        assert response.json()["count"] == 1

    def test_the_student_and_their_other_work_survive(
        self, client: TestClient, db: Session, student: Student, other_student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)
        sibling_work = add_assignment(db, other_student, ANCHOR)

        client.delete(f"/api/assignments/{assignment.id}")

        assert db.get(Student, student.id) is not None
        assert db.get(Assignment, sibling_work.id) is not None

    def test_deleting_twice_is_a_404(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        assert client.delete(f"/api/assignments/{assignment.id}").status_code == 204
        assert client.delete(f"/api/assignments/{assignment.id}").status_code == 404

    def test_an_unknown_assignment_is_a_404(self, client: TestClient) -> None:
        response = client.delete("/api/assignments/4242")

        assert response.status_code == 404
        assert response.json()["detail"] == "Assignment not found"


class TestEvidenceUpload:
    @pytest.fixture(autouse=True)
    def _isolate_storage(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        return tmp_path

    def _jpeg_bytes(self, width: int = 640, height: int = 480) -> bytes:
        image = Image.new("RGB", (width, height), color=(12, 34, 56))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()

    def test_a_photo_is_stored_and_linked_to_the_assignment(
        self, client: TestClient, db: Session, student: Student, tmp_path: Path
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)
        payload = self._jpeg_bytes()

        response = client.post(
            f"/api/assignments/{assignment.id}/evidence",
            files={"file": ("worksheet.jpg", payload, "image/jpeg")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["id"] > 0
        assert body["file_path"].startswith("test/")
        assert body["file_path"].endswith(".webp")
        assert body["captured_at"] is not None

        stored = tmp_path / body["file_path"]
        assert stored.is_file()
        with Image.open(stored) as image:
            assert image.format == "WEBP"

        record = db.get(AssignmentEvidence, body["id"])
        assert record is not None
        assert record.assignment_id == assignment.id
        assert record.file_path == body["file_path"]
        assert record.captured_at is not None

        detail = client.get(f"/api/assignments/{assignment.id}").json()
        assert detail["evidence_count"] == 1
        assert detail["evidence"][0]["id"] == body["id"]
        assert detail["evidence"][0]["file_path"] == body["file_path"]

    def test_an_oversized_photo_is_resized_and_saved_as_webp(
        self, client: TestClient, db: Session, student: Student, tmp_path: Path
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)

        response = client.post(
            f"/api/assignments/{assignment.id}/evidence",
            files={"file": ("scan.png", self._jpeg_bytes(2000, 1000), "image/png")},
        )

        assert response.status_code == 201
        stored = tmp_path / response.json()["file_path"]
        with Image.open(stored) as image:
            assert image.format == "WEBP"
            assert image.size == (1600, 800)
            assert image.mode == "RGB"

    def test_a_pdf_is_stored_without_compression(
        self, client: TestClient, db: Session, student: Student, tmp_path: Path
    ) -> None:
        assignment = add_assignment(db, student, ANCHOR)
        payload = b"%PDF-1.4 test document"

        response = client.post(
            f"/api/assignments/{assignment.id}/evidence",
            files={"file": ("notes.pdf", payload, "application/pdf")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["file_path"].startswith("test/")
        assert body["file_path"].endswith(".pdf")
        stored = tmp_path / body["file_path"]
        assert stored.read_bytes() == payload
        assert db.get(AssignmentEvidence, body["id"]).file_path == body["file_path"]

    def test_an_unknown_assignment_is_a_404(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        response = client.post(
            "/api/assignments/4242/evidence",
            files={"file": ("worksheet.jpg", b"bytes", "image/jpeg")},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Assignment not found"
        assert list(tmp_path.iterdir()) == []

    def test_apply_to_group_attaches_the_file_to_every_shared_assignment(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
        tmp_path: Path,
    ) -> None:
        group = "11111111-2222-3333-4444-555555555555"
        target = Assignment(
            student_id=student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        sibling = Assignment(
            student_id=other_student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        unrelated = add_assignment(db, student, ANCHOR, title="Private work")
        db.add_all([target, sibling])
        db.commit()

        payload = self._jpeg_bytes()
        response = client.post(
            f"/api/assignments/{target.id}/evidence",
            params={"apply_to_group": True},
            files={"file": ("worksheet.jpg", payload, "image/jpeg")},
        )

        assert response.status_code == 201
        stored_path = response.json()["file_path"]
        assert stored_path.endswith(".webp")
        assert (tmp_path / stored_path).is_file()

        rows = db.query(AssignmentEvidence).all()
        assert {row.assignment_id for row in rows} == {target.id, sibling.id}
        assert all(row.file_path == stored_path for row in rows)
        assert client.get(f"/api/assignments/{sibling.id}").json()["evidence_count"] == 1
        assert client.get(f"/api/assignments/{unrelated.id}").json()["evidence_count"] == 0

    def test_a_shared_upload_copies_evidence_without_the_group_flag(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
        tmp_path: Path,
    ) -> None:
        group = "11111111-2222-3333-4444-555555555555"
        target = Assignment(
            student_id=student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        sibling = Assignment(
            student_id=other_student.id,
            title="Shared lesson",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        db.add_all([target, sibling])
        db.commit()

        response = client.post(
            f"/api/assignments/{target.id}/evidence",
            files={"file": ("worksheet.jpg", self._jpeg_bytes(), "image/jpeg")},
        )

        assert response.status_code == 201
        stored_path = response.json()["file_path"]
        rows = db.query(AssignmentEvidence).all()
        assert {row.assignment_id for row in rows} == {target.id, sibling.id}
        assert all(row.file_path == stored_path for row in rows)

    def test_apply_to_group_without_a_uuid_only_touches_the_target(
        self, client: TestClient, db: Session, student: Student, other_student: Student
    ) -> None:
        target = add_assignment(db, student, ANCHOR, title="Solo")
        other = add_assignment(db, other_student, ANCHOR, title="Sibling")

        response = client.post(
            f"/api/assignments/{target.id}/evidence",
            params={"apply_to_group": True},
            files={"file": ("worksheet.jpg", self._jpeg_bytes(), "image/jpeg")},
        )

        assert response.status_code == 201
        assert db.query(AssignmentEvidence).count() == 1
        assert db.query(AssignmentEvidence).one().assignment_id == target.id
        assert client.get(f"/api/assignments/{other.id}").json()["evidence_count"] == 0


class TestSharedCalendar:
    def test_returns_only_assignments_with_a_shared_group(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        other_student: Student,
    ) -> None:
        group = "11111111-2222-3333-4444-555555555555"
        shared_ada = Assignment(
            student_id=student.id,
            title="Family read-aloud",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        shared_blaise = Assignment(
            student_id=other_student.id,
            title="Family read-aloud",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        private = add_assignment(db, student, ANCHOR, title="Private math")
        db.add_all([shared_ada, shared_blaise])
        db.commit()

        response = client.get("/api/calendar", params={"start_date": ANCHOR.isoformat()})

        assert response.status_code == 200
        body = response.json()
        assert body["student_id"] is None
        assert body["count"] == 2
        titles = sorted(item["title"] for item in body["assignments"])
        assert titles == ["Family read-aloud", "Family read-aloud"]
        assert {item["student_id"] for item in body["assignments"]} == {
            student.id,
            other_student.id,
        }
        assert all(item["shared_group_uuid"] == group for item in body["assignments"])
        assert all(item["color_hex"] == DEFAULT_STUDENT_COLOR for item in body["assignments"])
        assert private.id not in {item["id"] for item in body["assignments"]}

    def test_respects_the_requested_window(
        self, client: TestClient, db: Session, student: Student
    ) -> None:
        group = "11111111-2222-3333-4444-555555555555"
        inside = Assignment(
            student_id=student.id,
            title="Inside",
            scheduled_date=ANCHOR,
            shared_group_uuid=group,
        )
        outside = Assignment(
            student_id=student.id,
            title="Outside",
            scheduled_date=ANCHOR + timedelta(days=1),
            shared_group_uuid=group,
        )
        db.add_all([inside, outside])
        db.commit()

        response = client.get(
            "/api/calendar",
            params={"start_date": ANCHOR.isoformat(), "period": "day"},
        )

        assert returned_dates(response) == [ANCHOR.isoformat()]
        assert response.json()["start_date"] == ANCHOR.isoformat()
        assert response.json()["end_date"] == ANCHOR.isoformat()

