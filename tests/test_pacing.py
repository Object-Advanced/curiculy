"""Pacing engine, syllabus generator, and the two endpoints over them.

The engine and the generator are pure, so most of this exercises them directly
against a fixed four-week window: 7 September 2026 is a Monday and the window
ending 2 October holds exactly twenty Monday-to-Friday school days. That makes
the two cases the pacing has to get right checkable by hand — five lessons across
twenty days is one every fourth day, sixty lessons is three a day.
"""

from datetime import date, timedelta
from itertools import count as counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, MappingSource, ResourceKind, UnitKind
from app.models import (
    Assignment,
    BookEdition,
    Curriculum,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
    Household,
    Student,
    SubjectTaxonomy,
    Work,
)
from app.services import pacing as pacing_service
from app.services.ai_generator import SyllabusGenerationError, SyllabusGenerator
from app.services.pacing import PacingEngine, PacingError

MONDAY = date(2026, 9, 7)
FRIDAY_FOUR_WEEKS_LATER = date(2026, 10, 2)
WEEKDAYS = (0, 1, 2, 3, 4)
SCHOOL_DAYS_IN_WINDOW = 20

BOOK_TITLE = "Saxon Math 3"
FIRST_PAGE = 1
LAST_PAGE = 200
TOTAL_PAGES = LAST_PAGE - FIRST_PAGE + 1


def seed_student(db: Session, name: str = "Ada") -> Student:
    household = Household(name="Test Household")
    student = Student(household=household, name=name)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def seed_book(db: Session, title: str = BOOK_TITLE, page_count: int | None = LAST_PAGE) -> BookEdition:
    work = Work(title=title)
    db.add(work)
    db.flush()
    book = BookEdition(work_id=work.id, page_count=page_count)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def seed_curriculum_edition(db: Session, title: str = BOOK_TITLE) -> CurriculumEdition:
    curriculum = Curriculum(title=title)
    edition = CurriculumEdition(curriculum=curriculum, edition_label="3rd edition")
    db.add(edition)
    db.commit()
    db.refresh(edition)
    return edition


def count(db: Session, model: type) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


@pytest.fixture
def engine_under_test() -> PacingEngine:
    return PacingEngine()


@pytest.fixture
def book(db: Session) -> BookEdition:
    return seed_book(db)


@pytest.fixture
def student(db: Session) -> Student:
    return seed_student(db)


@pytest.fixture
def curriculum_edition(db: Session) -> CurriculumEdition:
    return seed_curriculum_edition(db)


def preview_body(**overrides: object) -> dict:
    body: dict = {
        "book_id": 1,
        "start_date": MONDAY.isoformat(),
        "target_completion_date": FRIDAY_FOUR_WEEKS_LATER.isoformat(),
        "start_page": FIRST_PAGE,
        "end_page": LAST_PAGE,
    }
    body.update(overrides)
    return body


class TestAvailableDays:
    def test_counts_only_the_active_weekdays(self, engine_under_test: PacingEngine) -> None:
        available = engine_under_test.calculate_available_days(
            MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS
        )

        assert available == SCHOOL_DAYS_IN_WINDOW

    def test_both_bounds_are_inclusive(self, engine_under_test: PacingEngine) -> None:
        # Monday through Friday of one week is five days, not four.
        assert engine_under_test.calculate_available_days(MONDAY, date(2026, 9, 11), WEEKDAYS) == 5
        assert engine_under_test.calculate_available_days(MONDAY, MONDAY, WEEKDAYS) == 1

    def test_a_single_inactive_day_is_no_days(self, engine_under_test: PacingEngine) -> None:
        sunday = date(2026, 9, 13)

        assert engine_under_test.calculate_available_days(sunday, sunday, WEEKDAYS) == 0

    @pytest.mark.parametrize(
        ("active_weekdays", "expected"),
        [
            ((0, 1, 2, 3, 4, 5, 6), 26),
            ((0, 2, 4), 12),
            ((5, 6), 6),
            ((2,), 4),
        ],
    )
    def test_the_weekday_pattern_drives_the_count(
        self,
        engine_under_test: PacingEngine,
        active_weekdays: tuple[int, ...],
        expected: int,
    ) -> None:
        available = engine_under_test.calculate_available_days(
            MONDAY, FRIDAY_FOUR_WEEKS_LATER, active_weekdays
        )

        assert available == expected

    def test_excluded_dates_are_removed(self, engine_under_test: PacingEngine) -> None:
        holidays = [date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 12)]

        available = engine_under_test.calculate_available_days(
            MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS, holidays
        )

        # The Saturday was never a school day, so only the two weekdays come off.
        assert available == SCHOOL_DAYS_IN_WINDOW - 2

    def test_the_days_come_back_in_calendar_order(self, engine_under_test: PacingEngine) -> None:
        days = engine_under_test.school_days(MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS)

        assert days == sorted(days)
        assert days[0] == MONDAY
        assert days[-1] == FRIDAY_FOUR_WEEKS_LATER
        assert all(day.weekday() in WEEKDAYS for day in days)

    def test_a_reversed_window_is_rejected(self, engine_under_test: PacingEngine) -> None:
        with pytest.raises(PacingError, match="is after end_date"):
            engine_under_test.calculate_available_days(FRIDAY_FOUR_WEEKS_LATER, MONDAY, WEEKDAYS)

    def test_no_active_weekdays_is_rejected(self, engine_under_test: PacingEngine) -> None:
        with pytest.raises(PacingError, match="at least one active weekday"):
            engine_under_test.calculate_available_days(MONDAY, FRIDAY_FOUR_WEEKS_LATER, [])

    @pytest.mark.parametrize("weekday", [-1, 7, 12])
    def test_a_weekday_outside_the_week_is_rejected(
        self,
        engine_under_test: PacingEngine,
        weekday: int,
    ) -> None:
        with pytest.raises(PacingError, match="not weekdays"):
            engine_under_test.calculate_available_days(
                MONDAY, FRIDAY_FOUR_WEEKS_LATER, [weekday]
            )

    def test_school_days_ahead_matches_the_closed_window(
        self, engine_under_test: PacingEngine
    ) -> None:
        days = engine_under_test.school_days_ahead(MONDAY, SCHOOL_DAYS_IN_WINDOW, WEEKDAYS)

        assert days == engine_under_test.school_days(MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS)
        assert days[-1] == FRIDAY_FOUR_WEEKS_LATER

    def test_school_days_ahead_skips_weekends(self, engine_under_test: PacingEngine) -> None:
        friday = date(2026, 9, 11)

        assert engine_under_test.school_days_ahead(friday, 3, WEEKDAYS) == [
            date(2026, 9, 11),
            date(2026, 9, 14),
            date(2026, 9, 15),
        ]


class TestStretchingACourse:
    """More school days than lessons: the course spreads out over the window."""

    def test_the_pace_is_every_other_day(self, engine_under_test: PacingEngine) -> None:
        distribution = engine_under_test.distribute_lessons(total_lessons=10, available_days=20)

        assert distribution.is_rigorous is False
        assert distribution.warning is None
        assert distribution.lessons_per_day == 1
        assert distribution.day_interval == 2
        assert distribution.spare_days == 10

    @pytest.mark.parametrize(
        ("total_lessons", "expected_interval"),
        [(1, 20), (2, 10), (4, 5), (5, 4), (7, 2), (20, 1)],
    )
    def test_the_interval_follows_the_ratio(
        self,
        engine_under_test: PacingEngine,
        total_lessons: int,
        expected_interval: int,
    ) -> None:
        distribution = engine_under_test.distribute_lessons(total_lessons, SCHOOL_DAYS_IN_WINDOW)

        assert distribution.day_interval == expected_interval
        assert distribution.lessons_per_day == 1
        assert distribution.is_rigorous is False

    def test_an_exact_fit_is_one_lesson_a_day_and_not_rigorous(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        distribution = engine_under_test.distribute_lessons(total_lessons=20, available_days=20)

        assert distribution.is_rigorous is False
        assert distribution.day_interval == 1
        assert distribution.lessons_per_day == 1
        assert distribution.spare_days == 0

    def test_each_lesson_gets_its_own_day(self, engine_under_test: PacingEngine) -> None:
        plan = engine_under_test.plan(MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS, total_lessons=5)

        assert plan.scheduled_dates == (
            date(2026, 9, 7),
            date(2026, 9, 11),
            date(2026, 9, 17),
            date(2026, 9, 23),
            date(2026, 9, 29),
        )
        assert len(set(plan.scheduled_dates)) == 5

    def test_the_schedule_starts_at_once_and_stays_inside_the_window(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        plan = engine_under_test.plan(MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS, total_lessons=6)

        assert plan.scheduled_dates[0] == MONDAY
        assert plan.scheduled_dates[-1] <= FRIDAY_FOUR_WEEKS_LATER
        assert all(day in plan.school_days for day in plan.scheduled_dates)
        assert list(plan.scheduled_dates) == sorted(plan.scheduled_dates)


class TestCompressingACourse:
    """More lessons than school days: doubling up, and saying so."""

    def test_it_warns_and_stacks_lessons_onto_each_day(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        distribution = engine_under_test.distribute_lessons(total_lessons=60, available_days=20)

        assert distribution.is_rigorous is True
        assert distribution.lessons_per_day == 3
        assert distribution.day_interval == 1
        assert distribution.spare_days == 0
        assert distribution.warning is not None
        assert "3 lessons a day" in distribution.warning

    @pytest.mark.parametrize(
        ("total_lessons", "expected_per_day"),
        [(21, 2), (40, 2), (41, 3), (60, 3), (200, 10)],
    )
    def test_the_daily_load_rounds_up(
        self,
        engine_under_test: PacingEngine,
        total_lessons: int,
        expected_per_day: int,
    ) -> None:
        distribution = engine_under_test.distribute_lessons(total_lessons, SCHOOL_DAYS_IN_WINDOW)

        assert distribution.is_rigorous is True
        assert distribution.lessons_per_day == expected_per_day

    def test_one_lesson_over_capacity_still_trips_the_warning(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        distribution = engine_under_test.distribute_lessons(total_lessons=21, available_days=20)

        assert distribution.is_rigorous is True
        assert distribution.warning is not None
        assert "21 lessons" in distribution.warning
        assert "20 school days" in distribution.warning

    def test_every_lesson_is_still_scheduled_inside_the_window(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        plan = engine_under_test.plan(MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS, total_lessons=60)

        assert len(plan.scheduled_dates) == 60
        assert set(plan.scheduled_dates) == set(plan.school_days)
        assert plan.scheduled_dates[0] == MONDAY
        assert plan.scheduled_dates[-1] == FRIDAY_FOUR_WEEKS_LATER
        assert list(plan.scheduled_dates) == sorted(plan.scheduled_dates)

    def test_no_day_carries_more_than_the_reported_load(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        plan = engine_under_test.plan(MONDAY, FRIDAY_FOUR_WEEKS_LATER, WEEKDAYS, total_lessons=47)

        per_day = {day: plan.scheduled_dates.count(day) for day in plan.school_days}
        assert max(per_day.values()) == plan.distribution.lessons_per_day
        assert min(per_day.values()) >= 1

    def test_a_window_with_no_school_days_is_impossible(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        with pytest.raises(PacingError, match="no school days"):
            engine_under_test.plan(MONDAY, date(2026, 9, 11), [5, 6], total_lessons=4)

    def test_a_syllabus_needs_at_least_one_lesson(
        self,
        engine_under_test: PacingEngine,
    ) -> None:
        with pytest.raises(PacingError, match="at least one lesson"):
            engine_under_test.distribute_lessons(total_lessons=0, available_days=20)


class TestSyllabusGenerator:
    def test_it_splits_the_range_into_equal_chunks(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus(BOOK_TITLE, 1, 200, 5)

        assert [(lesson.start_page, lesson.end_page) for lesson in lessons] == [
            (1, 40),
            (41, 80),
            (81, 120),
            (121, 160),
            (161, 200),
        ]
        assert [lesson.sequence for lesson in lessons] == [1, 2, 3, 4, 5]

    def test_the_range_is_covered_exactly_once(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus(BOOK_TITLE, 17, 203, 23)

        assert lessons[0].start_page == 17
        assert lessons[-1].end_page == 203
        for earlier, later in zip(lessons, lessons[1:], strict=False):
            assert later.start_page == earlier.end_page + 1
        assert sum(lesson.page_count for lesson in lessons) == 203 - 17 + 1

    def test_an_uneven_split_differs_by_at_most_one_page(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus(BOOK_TITLE, 1, 100, 7)

        page_counts = {lesson.page_count for lesson in lessons}
        assert page_counts <= {14, 15}
        assert sum(lesson.page_count for lesson in lessons) == 100

    def test_it_is_deterministic(self) -> None:
        generator = SyllabusGenerator()
        first = generator.generate_syllabus(BOOK_TITLE, 5, 137, 11)
        second = generator.generate_syllabus(BOOK_TITLE, 5, 137, 11)

        assert first == second

    def test_titles_name_the_book_and_the_pages(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus(BOOK_TITLE, 1, 200, 5)

        assert lessons[0].title == "Lesson 1: Saxon Math 3 (pp. 1-40)"
        assert lessons[4].title == "Lesson 5: Saxon Math 3 (pp. 161-200)"

    def test_a_one_page_lesson_reads_as_one_page(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus(BOOK_TITLE, 10, 12, 3)

        assert [lesson.title for lesson in lessons] == [
            "Lesson 1: Saxon Math 3 (p. 10)",
            "Lesson 2: Saxon Math 3 (p. 11)",
            "Lesson 3: Saxon Math 3 (p. 12)",
        ]

    def test_a_long_book_title_is_truncated_to_fit_the_column(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus("Arithmetic " * 40, 1, 10, 1)

        assert len(lessons[0].title) <= 255
        assert lessons[0].title.startswith("Lesson 1: Arithmetic")
        assert lessons[0].title.endswith("... (pp. 1-10)")

    def test_a_whole_book_in_one_lesson(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus(BOOK_TITLE, 1, 200, 1)

        assert len(lessons) == 1
        assert (lessons[0].start_page, lessons[0].end_page) == (1, 200)

    def test_more_lessons_than_pages_is_rejected(self) -> None:
        with pytest.raises(SyllabusGenerationError, match="only 10 pages"):
            SyllabusGenerator().generate_syllabus(BOOK_TITLE, 1, 10, 11)

    @pytest.mark.parametrize(
        ("start_page", "end_page", "target_lessons", "message"),
        [
            (0, 10, 2, "start_page must be 1 or greater"),
            (40, 4, 2, "precedes start_page"),
            (1, 10, 0, "target_lessons must be 1 or greater"),
        ],
    )
    def test_an_impossible_request_is_rejected(
        self,
        start_page: int,
        end_page: int,
        target_lessons: int,
        message: str,
    ) -> None:
        with pytest.raises(SyllabusGenerationError, match=message):
            SyllabusGenerator().generate_syllabus(BOOK_TITLE, start_page, end_page, target_lessons)

    def test_an_untitled_book_is_rejected(self) -> None:
        with pytest.raises(SyllabusGenerationError, match="book title is required"):
            SyllabusGenerator().generate_syllabus("   ", 1, 10, 2)

    def test_pages_per_day_chunks_strictly_and_leaves_the_remainder(self) -> None:
        lessons = SyllabusGenerator().generate_syllabus(
            BOOK_TITLE, 1, 21, target_lessons=3, pages_per_day=10
        )

        assert [(lesson.start_page, lesson.end_page) for lesson in lessons] == [
            (1, 10),
            (11, 20),
            (21, 21),
        ]
        assert [lesson.page_count for lesson in lessons] == [10, 10, 1]


class TestGeneratePreviewEndpoint:
    def test_a_stretched_course_spreads_over_the_window(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, target_lessons=5),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["book_title"] == BOOK_TITLE
        assert body["pacing"] == {
            "start_date": MONDAY.isoformat(),
            "target_completion_date": FRIDAY_FOUR_WEEKS_LATER.isoformat(),
            "active_weekdays": [0, 1, 2, 3, 4],
            "available_days": SCHOOL_DAYS_IN_WINDOW,
            "total_lessons": 5,
            "total_pages": TOTAL_PAGES,
            "pages_per_lesson": 40.0,
            "lessons_per_day": 1,
            "day_interval": 4,
            "is_rigorous": False,
            "warning": None,
        }
        assert [lesson["scheduled_date"] for lesson in body["lessons"]] == [
            "2026-09-07",
            "2026-09-11",
            "2026-09-17",
            "2026-09-23",
            "2026-09-29",
        ]

    def test_a_compressed_course_comes_back_with_the_warning(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, target_lessons=60),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["pacing"]["is_rigorous"] is True
        assert body["pacing"]["lessons_per_day"] == 3
        assert "3 lessons a day" in body["pacing"]["warning"]
        assert len(body["lessons"]) == 60
        # Still a real schedule: every lesson has a day, and the pages all fit.
        assert all(lesson["scheduled_date"] for lesson in body["lessons"])
        assert sum(lesson["page_count"] for lesson in body["lessons"]) == TOTAL_PAGES

    def test_the_lesson_count_defaults_to_one_a_day(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id),
        )

        body = response.json()
        assert body["pacing"]["total_lessons"] == SCHOOL_DAYS_IN_WINDOW
        assert body["pacing"]["is_rigorous"] is False
        assert body["pacing"]["day_interval"] == 1
        assert len(body["lessons"]) == SCHOOL_DAYS_IN_WINDOW

    def test_a_short_page_range_never_makes_more_lessons_than_pages(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, start_page=1, end_page=5),
        )

        body = response.json()
        assert body["pacing"]["total_lessons"] == 5
        assert body["pacing"]["day_interval"] == 4
        assert [lesson["page_count"] for lesson in body["lessons"]] == [1, 1, 1, 1, 1]

    def test_weekends_are_left_alone_by_default(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id),
        )

        scheduled = [date.fromisoformat(item["scheduled_date"]) for item in response.json()["lessons"]]
        assert all(day.weekday() < 5 for day in scheduled)

    def test_excluded_dates_are_skipped(self, client: TestClient, book: BookEdition) -> None:
        holiday = date(2026, 9, 8)

        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, excluded_dates=[holiday.isoformat()]),
        )

        body = response.json()
        assert body["pacing"]["available_days"] == SCHOOL_DAYS_IN_WINDOW - 1
        assert holiday.isoformat() not in [item["scheduled_date"] for item in body["lessons"]]

    def test_the_lessons_tile_the_page_range(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, start_page=30, end_page=99, target_lessons=8),
        )

        lessons = response.json()["lessons"]
        assert lessons[0]["start_page"] == 30
        assert lessons[-1]["end_page"] == 99
        for earlier, later in zip(lessons, lessons[1:], strict=False):
            assert later["start_page"] == earlier["end_page"] + 1

    def test_an_unknown_book_is_a_404(self, client: TestClient) -> None:
        response = client.post("/api/pacing/generate-preview", json=preview_body(book_id=4242))

        assert response.status_code == 404
        assert response.json()["detail"] == "Book edition not found"

    def test_a_window_without_school_days_is_a_400(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(
                book_id=book.id,
                target_completion_date=date(2026, 9, 11).isoformat(),
                active_weekdays=[5, 6],
            ),
        )

        assert response.status_code == 400
        assert "no school days" in response.json()["detail"]

    def test_a_deadline_before_the_start_is_a_400(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(
                book_id=book.id,
                target_completion_date=date(2026, 9, 1).isoformat(),
            ),
        )

        assert response.status_code == 400
        assert "is after end_date" in response.json()["detail"]

    def test_asking_for_more_lessons_than_pages_is_a_400(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, start_page=1, end_page=3, target_lessons=10),
        )

        assert response.status_code == 400
        assert "only 3 pages" in response.json()["detail"]

    @pytest.mark.parametrize(
        "overrides",
        [
            {"active_weekdays": []},
            {"active_weekdays": [7]},
            {"active_weekdays": [-1]},
            {"start_page": 0},
            {"start_page": 90, "end_page": 12},
            {"target_lessons": 0},
            {"pages_per_day": 0},
            {"target_completion_date": "not-a-date"},
            {"nonsense": True},
        ],
    )
    def test_a_malformed_request_is_a_422(
        self,
        client: TestClient,
        book: BookEdition,
        overrides: dict,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, **overrides),
        )

        assert response.status_code == 422

    def test_duplicate_weekdays_are_folded_together(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, active_weekdays=[2, 0, 2, 0]),
        )

        assert response.json()["pacing"]["active_weekdays"] == [0, 2]

    def test_pages_per_day_chunks_lessons_and_returns_the_finish_date(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        body = preview_body(book_id=book.id, pages_per_day=10)
        del body["target_completion_date"]

        response = client.post("/api/pacing/generate-preview", json=body)

        assert response.status_code == 200
        payload = response.json()
        pacing = payload["pacing"]
        lessons = payload["lessons"]
        assert pacing["total_lessons"] == SCHOOL_DAYS_IN_WINDOW
        assert pacing["available_days"] == SCHOOL_DAYS_IN_WINDOW
        assert pacing["pages_per_lesson"] == 10.0
        assert pacing["target_completion_date"] == FRIDAY_FOUR_WEEKS_LATER.isoformat()
        assert pacing["is_rigorous"] is False
        assert [lesson["scheduled_date"] for lesson in lessons][-1] == "2026-10-02"
        assert [(lesson["start_page"], lesson["end_page"]) for lesson in lessons] == [
            (index * 10 + 1, (index + 1) * 10) for index in range(SCHOOL_DAYS_IN_WINDOW)
        ]
        scheduled = [date.fromisoformat(item["scheduled_date"]) for item in lessons]
        assert all(day.weekday() in WEEKDAYS for day in scheduled)
        assert scheduled[0] == MONDAY
        assert scheduled[-1] == FRIDAY_FOUR_WEEKS_LATER

    def test_pages_per_day_skips_weekends_and_keeps_the_remainder(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        friday = date(2026, 9, 11)
        body = preview_body(
            book_id=book.id,
            pages_per_day=10,
            start_page=1,
            end_page=21,
            start_date=friday.isoformat(),
        )
        del body["target_completion_date"]

        response = client.post("/api/pacing/generate-preview", json=body)

        assert response.status_code == 200
        payload = response.json()
        lessons = payload["lessons"]
        assert [(lesson["start_page"], lesson["end_page"]) for lesson in lessons] == [
            (1, 10),
            (11, 20),
            (21, 21),
        ]
        assert [lesson["scheduled_date"] for lesson in lessons] == [
            "2026-09-11",
            "2026-09-14",
            "2026-09-15",
        ]
        assert payload["pacing"]["target_completion_date"] == "2026-09-15"
        assert payload["pacing"]["total_lessons"] == 3

    def test_neither_a_deadline_nor_a_pace_is_a_422(
        self,
        client: TestClient,
        book: BookEdition,
    ) -> None:
        body = preview_body(book_id=book.id)
        del body["target_completion_date"]

        response = client.post("/api/pacing/generate-preview", json=body)

        assert response.status_code == 422

    def test_a_missing_page_count_is_stored_from_the_end_page(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        book = seed_book(db, page_count=None)

        response = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, end_page=150),
        )

        assert response.status_code == 200
        db.refresh(book)
        assert book.page_count == 150

    def test_commit_stores_a_custom_end_page_on_the_book(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
    ) -> None:
        book = seed_book(db, page_count=None)
        body = TestCommitEndpoint.commit_body(
            student, curriculum_edition, book, end_page=175
        )

        response = client.post("/api/pacing/commit", json=body)

        assert response.status_code == 201
        db.refresh(book)
        assert book.page_count == 175


class TestCommitEndpoint:
    @staticmethod
    def commit_body(
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition | None = None,
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

    def test_it_creates_the_structure_and_the_assignments(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        response = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, book),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["units_created"] == 4
        assert body["page_mappings_created"] == 3
        assert body["assignments_created"] == 3
        assert body["resource_created"] is True
        assert len(body["lesson_unit_ids"]) == 3
        assert len(body["assignment_ids"]) == 3
        assert body["first_scheduled_date"] == "2026-09-07"
        assert body["last_scheduled_date"] == "2026-09-17"

        assert count(db, CurriculumUnit) == 4
        assert count(db, CurriculumPageMapping) == 3
        assert count(db, Assignment) == 3
        assert count(db, CurriculumResource) == 1

    def test_the_lessons_hang_off_one_course_unit(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        body = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, book),
        ).json()

        course = db.get(CurriculumUnit, body["course_unit_id"])
        assert course is not None
        assert course.kind is UnitKind.COURSE
        assert course.title == "Saxon Math 3, autumn term"
        assert course.parent_id is None
        assert course.depth == 0

        lessons = [db.get(CurriculumUnit, unit_id) for unit_id in body["lesson_unit_ids"]]
        assert [unit.parent_id for unit in lessons] == [course.id] * 3
        assert [unit.kind for unit in lessons] == [UnitKind.LESSON] * 3
        assert [unit.label for unit in lessons] == ["Lesson 1", "Lesson 2", "Lesson 3"]
        assert [unit.sort_order for unit in lessons] == [0, 1, 2]
        assert [unit.depth for unit in lessons] == [1, 1, 1]

    def test_each_lesson_keeps_its_pages(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        client.post("/api/pacing/commit", json=self.commit_body(student, curriculum_edition, book))

        mappings = (
            db.execute(select(CurriculumPageMapping).order_by(CurriculumPageMapping.page_start))
            .scalars()
            .all()
        )
        assert [(item.page_start, item.page_end) for item in mappings] == [
            (1, 40),
            (41, 80),
            (81, 120),
        ]
        assert all(item.source is MappingSource.AI_PARSED for item in mappings)
        assert all(item.is_primary for item in mappings)

    def test_the_assignments_land_on_the_students_calendar(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        client.post("/api/pacing/commit", json=self.commit_body(student, curriculum_edition, book))

        assignments = (
            db.execute(select(Assignment).order_by(Assignment.scheduled_date)).scalars().all()
        )
        assert [item.student_id for item in assignments] == [student.id] * 3
        assert [item.scheduled_date for item in assignments] == [
            date(2026, 9, 7),
            date(2026, 9, 11),
            date(2026, 9, 17),
        ]
        assert [item.status for item in assignments] == [AssignmentStatus.ASSIGNED] * 3
        assert assignments[0].title == "Lesson 1: Saxon Math 3 (pp. 1-40)"
        assert all(item.curriculum_unit_id is not None for item in assignments)
        assert all(item.curriculum_resource_id is not None for item in assignments)
        assert all(item.shared_group_uuid is None for item in assignments)

    def test_student_ids_write_identical_lessons_tagged_with_a_group_uuid(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        sibling = Student(household_id=student.household_id, name="Blaise")
        db.add(sibling)
        db.commit()

        body = self.commit_body(student, curriculum_edition, book)
        del body["student_id"]
        body["student_ids"] = [student.id, sibling.id]

        response = client.post("/api/pacing/commit", json=body)

        assert response.status_code == 201
        payload = response.json()
        assert payload["student_id"] == student.id
        assert payload["student_ids"] == [student.id, sibling.id]
        assert payload["assignments_created"] == 6
        assert len(payload["assignment_ids"]) == 6
        assert payload["units_created"] == 4

        assignments = (
            db.execute(select(Assignment).order_by(Assignment.id)).scalars().all()
        )
        assert len(assignments) == 6
        assert {item.student_id for item in assignments} == {student.id, sibling.id}
        assert all(item.shared_group_uuid for item in assignments)

        by_title: dict[str, list[Assignment]] = {}
        for item in assignments:
            by_title.setdefault(item.title, []).append(item)
        assert len(by_title) == 3
        for copies in by_title.values():
            assert {copy.student_id for copy in copies} == {student.id, sibling.id}
            assert len({copy.shared_group_uuid for copy in copies}) == 1
        assert len({item.shared_group_uuid for item in assignments}) == 3

    def test_a_single_id_in_student_ids_is_not_grouped(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        body = self.commit_body(student, curriculum_edition, book)
        del body["student_id"]
        body["student_ids"] = [student.id]

        response = client.post("/api/pacing/commit", json=body)

        assert response.status_code == 201
        assert response.json()["student_ids"] == [student.id]
        assert response.json()["assignments_created"] == 3
        assignments = db.execute(select(Assignment)).scalars().all()
        assert all(item.shared_group_uuid is None for item in assignments)

    def test_duplicate_student_ids_are_collapsed(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        body = self.commit_body(student, curriculum_edition, book)
        del body["student_id"]
        body["student_ids"] = [student.id, student.id]

        response = client.post("/api/pacing/commit", json=body)

        assert response.status_code == 201
        assert response.json()["assignments_created"] == 3
        assert count(db, Assignment) == 3

    def test_an_unknown_student_in_student_ids_is_a_404(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        body = self.commit_body(student, curriculum_edition, book)
        del body["student_id"]
        body["student_ids"] = [student.id, 4242]

        response = client.post("/api/pacing/commit", json=body)

        assert response.status_code == 404
        assert response.json()["detail"] == "Student not found"
        assert count(db, Assignment) == 0

    def test_omitting_every_student_is_a_422(
        self,
        client: TestClient,
        student: Student,
        curriculum_edition: CurriculumEdition,
    ) -> None:
        body = self.commit_body(student, curriculum_edition)
        del body["student_id"]

        response = client.post("/api/pacing/commit", json=body)

        assert response.status_code == 422

    def test_the_calendar_reads_the_committed_work_back(
        self,
        client: TestClient,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        client.post("/api/pacing/commit", json=self.commit_body(student, curriculum_edition, book))

        response = client.get(
            f"/api/students/{student.id}/assignments",
            params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3
        assert body["assignments"][0]["unit_title"] == "Lesson 1: Saxon Math 3 (pp. 1-40)"
        assert body["assignments"][0]["resource_title"] == BOOK_TITLE

    def test_the_resource_is_linked_to_the_scanned_book(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        body = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, book),
        ).json()

        resource = db.get(CurriculumResource, body["curriculum_resource_id"])
        assert resource is not None
        assert resource.book_edition_id == book.id
        assert resource.curriculum_edition_id == curriculum_edition.id
        assert resource.kind is ResourceKind.STUDENT_TEXT
        assert resource.title == BOOK_TITLE

    def test_a_second_syllabus_reuses_the_same_resource(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        first = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, book),
        ).json()
        second = client.post(
            "/api/pacing/commit",
            json=self.commit_body(
                student,
                curriculum_edition,
                book,
                course_title="Saxon Math 3, spring term",
            ),
        ).json()

        assert second["resource_created"] is False
        assert second["curriculum_resource_id"] == first["curriculum_resource_id"]
        assert second["course_unit_id"] != first["course_unit_id"]
        assert count(db, CurriculumResource) == 1

    def test_a_syllabus_without_a_book_titles_the_resource_after_the_course(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
    ) -> None:
        body = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition),
        ).json()

        resource = db.get(CurriculumResource, body["curriculum_resource_id"])
        assert resource is not None
        assert resource.book_edition_id is None
        assert resource.title == "Saxon Math 3, autumn term"

    def test_a_subject_is_carried_onto_every_assignment(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        subject = SubjectTaxonomy(name="Mathematics")
        db.add(subject)
        db.commit()

        client.post(
            "/api/pacing/commit",
            json=self.commit_body(
                student,
                curriculum_edition,
                book,
                subject_taxonomy_id=subject.id,
            ),
        )

        assignments = db.execute(select(Assignment)).scalars().all()
        assert [item.subject_taxonomy_id for item in assignments] == [subject.id] * 3

    def test_lessons_out_of_order_are_committed_in_sequence(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        lessons = [
            {
                "sequence": 2,
                "title": "Lesson 2",
                "start_page": 41,
                "end_page": 80,
                "scheduled_date": "2026-09-11",
            },
            {
                "sequence": 1,
                "title": "Lesson 1",
                "start_page": 1,
                "end_page": 40,
                "scheduled_date": "2026-09-07",
            },
        ]

        body = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, book, lessons=lessons),
        ).json()

        units = [db.get(CurriculumUnit, unit_id) for unit_id in body["lesson_unit_ids"]]
        assert [unit.title for unit in units] == ["Lesson 1", "Lesson 2"]
        assert body["first_scheduled_date"] == "2026-09-07"

    @pytest.mark.parametrize(
        ("field", "detail"),
        [
            ("student_id", "Student not found"),
            ("curriculum_edition_id", "Curriculum edition not found"),
            ("book_id", "Book edition not found"),
            ("subject_taxonomy_id", "Subject not found"),
        ],
    )
    def test_an_unknown_reference_is_a_404(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
        field: str,
        detail: str,
    ) -> None:
        body = self.commit_body(student, curriculum_edition, book)
        body[field] = 4242

        response = client.post("/api/pacing/commit", json=body)

        assert response.status_code == 404
        assert response.json()["detail"] == detail
        assert count(db, CurriculumUnit) == 0

    @pytest.mark.parametrize(
        "overrides",
        [
            {"lessons": []},
            {"course_title": ""},
            {"resource_kind": "not_a_kind"},
            {"nonsense": True},
        ],
    )
    def test_a_malformed_commit_is_a_422(
        self,
        client: TestClient,
        student: Student,
        curriculum_edition: CurriculumEdition,
        overrides: dict,
    ) -> None:
        response = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, **overrides),
        )

        assert response.status_code == 422

    def test_an_undated_lesson_is_a_422(
        self,
        client: TestClient,
        student: Student,
        curriculum_edition: CurriculumEdition,
    ) -> None:
        lessons = [{"sequence": 1, "title": "Lesson 1", "start_page": 1, "end_page": 40}]

        response = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, lessons=lessons),
        )

        assert response.status_code == 422

    def test_repeated_sequence_numbers_are_a_422(
        self,
        client: TestClient,
        student: Student,
        curriculum_edition: CurriculumEdition,
    ) -> None:
        lesson = {
            "sequence": 1,
            "title": "Lesson 1",
            "start_page": 1,
            "end_page": 40,
            "scheduled_date": "2026-09-07",
        }

        response = client.post(
            "/api/pacing/commit",
            json=self.commit_body(student, curriculum_edition, lessons=[lesson, dict(lesson)]),
        )

        assert response.status_code == 422
        assert "distinct sequence" in response.text

    def test_a_failure_partway_through_leaves_nothing_behind(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The commit is one transaction, so a late failure rolls the units back."""
        real_assignment = pacing_service.Assignment
        attempts = counter()

        def exploding_assignment(**fields: object) -> Assignment:
            if next(attempts) == 1:
                raise RuntimeError("the database went away")
            return real_assignment(**fields)

        monkeypatch.setattr(pacing_service, "Assignment", exploding_assignment)

        with pytest.raises(RuntimeError, match="the database went away"):
            client.post(
                "/api/pacing/commit",
                json=self.commit_body(student, curriculum_edition, book),
            )

        assert count(db, CurriculumUnit) == 0
        assert count(db, CurriculumPageMapping) == 0
        assert count(db, Assignment) == 0
        assert count(db, CurriculumResource) == 0


class TestPreviewThenCommit:
    def test_a_preview_can_be_committed_unchanged(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        """The preview response is the commit request, which is the whole point."""
        preview = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(book_id=book.id, target_lessons=12),
        ).json()

        response = client.post(
            "/api/pacing/commit",
            json={
                "student_id": student.id,
                "curriculum_edition_id": curriculum_edition.id,
                "book_id": book.id,
                "course_title": preview["book_title"],
                "lessons": preview["lessons"],
            },
        )

        assert response.status_code == 201
        assert response.json()["assignments_created"] == 12
        assert count(db, Assignment) == 12
        assert count(db, CurriculumUnit) == 13

    def test_a_rigorous_preview_commits_several_lessons_to_one_day(
        self,
        client: TestClient,
        db: Session,
        student: Student,
        curriculum_edition: CurriculumEdition,
        book: BookEdition,
    ) -> None:
        preview = client.post(
            "/api/pacing/generate-preview",
            json=preview_body(
                book_id=book.id,
                target_completion_date=(MONDAY + timedelta(days=4)).isoformat(),
                target_lessons=15,
            ),
        ).json()
        assert preview["pacing"]["is_rigorous"] is True

        client.post(
            "/api/pacing/commit",
            json={
                "student_id": student.id,
                "curriculum_edition_id": curriculum_edition.id,
                "book_id": book.id,
                "course_title": "Catch-up week",
                "lessons": preview["lessons"],
            },
        )

        scheduled = db.execute(select(Assignment.scheduled_date)).scalars().all()
        assert len(scheduled) == 15
        assert len(set(scheduled)) == 5
