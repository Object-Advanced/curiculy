"""Turn a page range and a deadline into dated work.

Two concerns live here, split the same way :mod:`app.services.assignments`
splits them. :class:`PacingEngine` is pure date and integer arithmetic with no
session, so the calendar rules can be tested on their own.
:class:`SyllabusCommitter` is the write half: it takes an approved syllabus and
lands it in the catalog and on the student's calendar in one transaction.

A schedule is never refused for being too full. A parent asking to finish a book
by June may be asking for three lessons a day, and the useful answer is to build
that schedule and flag it as rigorous rather than reject the request. Bounds are
inclusive on both ends, matching the rest of the calendar: a window ending on the
target completion date may schedule work on that date.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, MappingSource, UnitKind
from app.models import (
    Assignment,
    BookEdition,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
)
from app.schemas.pacing import PacingCommitRead, PacingCommitRequest
from app.services.enrollments import enroll_students
from app.services.school_year import require_operational_school_year


class PacingError(ValueError):
    """The requested pacing cannot be computed."""


class SyllabusCommitError(ValueError):
    """The approved syllabus could not be written; nothing was created."""


@dataclass(frozen=True)
class LessonDistribution:
    """How many lessons land on a school day, and how often a day carries one.

    The two rates are reciprocal views of the same ratio and only one of them is
    ever interesting: a stretched course has ``lessons_per_day`` of 1 and a
    ``day_interval`` above 1, a compressed course the other way around.
    """

    total_lessons: int
    available_days: int
    lessons_per_day: int
    day_interval: int
    is_rigorous: bool
    warning: str | None = None

    @property
    def spare_days(self) -> int:
        """School days left over once every lesson has one, never negative."""
        return max(0, self.available_days - self.total_lessons)


@dataclass(frozen=True)
class PacingPlan:
    """A distribution together with the days it resolved to."""

    distribution: LessonDistribution
    school_days: tuple[date, ...]
    scheduled_dates: tuple[date, ...]


class PacingEngine:
    """Counts the school days in a window and lays lessons out across them."""

    def school_days(
        self,
        start_date: date,
        end_date: date,
        active_weekdays: Iterable[int],
        excluded_dates: Iterable[date] = (),
    ) -> list[date]:
        """Every teachable day in the inclusive window, in calendar order."""
        weekdays = self._normalize_weekdays(active_weekdays)
        if end_date < start_date:
            raise PacingError(f"start_date {start_date} is after end_date {end_date}")

        skipped = set(excluded_dates)
        days: list[date] = []
        day = start_date
        while day <= end_date:
            if day.weekday() in weekdays and day not in skipped:
                days.append(day)
            day += timedelta(days=1)
        return days

    def calculate_available_days(
        self,
        start_date: date,
        end_date: date,
        active_weekdays: Iterable[int],
        excluded_dates: Iterable[date] = (),
    ) -> int:
        """How many school days the window holds.

        Derived from the day list rather than computed in closed form, so the
        count can never disagree with the dates the schedule is actually built
        from. A school year is a few hundred iterations.
        """
        return len(self.school_days(start_date, end_date, active_weekdays, excluded_dates))

    def school_days_ahead(
        self,
        start_date: date,
        count: int,
        active_weekdays: Iterable[int],
        excluded_dates: Iterable[date] = (),
    ) -> list[date]:
        """The next ``count`` teachable days, starting at ``start_date``.

        Walks the calendar forward, skipping inactive weekdays and excluded
        dates, until every lesson has a day. Used when pacing is a pages-per-day
        rate rather than a deadline.
        """
        weekdays = self._normalize_weekdays(active_weekdays)
        if count < 1:
            raise PacingError("a syllabus needs at least one lesson")

        skipped = set(excluded_dates)
        days: list[date] = []
        day = start_date
        # A pathological weekday/exclusion set could otherwise walk forever.
        limit = start_date + timedelta(days=max(count * 14, 366) + len(skipped))
        while len(days) < count:
            if day > limit:
                raise PacingError(
                    "could not find enough school days; add active weekdays or "
                    "remove excluded dates"
                )
            if day.weekday() in weekdays and day not in skipped:
                days.append(day)
            day += timedelta(days=1)
        return days

    def distribute_lessons(self, total_lessons: int, available_days: int) -> LessonDistribution:
        """Work out the pace, and say so when that pace is punishing.

        More lessons than days is allowed but flagged: the caller is expected to
        surface the warning and let the parent decide between a harder schedule
        and a later deadline.
        """
        # An empty window is reported before an empty syllabus, because a caller
        # that sizes the syllabus from the window ends up with neither and the
        # window is the one it can act on.
        if available_days < 1:
            raise PacingError(
                "the window contains no school days; move the target completion date "
                "out or add active weekdays"
            )
        if total_lessons < 1:
            raise PacingError("a syllabus needs at least one lesson")

        if total_lessons > available_days:
            lessons_per_day = ceil(total_lessons / available_days)
            return LessonDistribution(
                total_lessons=total_lessons,
                available_days=available_days,
                lessons_per_day=lessons_per_day,
                day_interval=1,
                is_rigorous=True,
                warning=(
                    f"{total_lessons} lessons must fit into {available_days} school days, "
                    f"which means up to {lessons_per_day} lessons a day. Move the target "
                    "completion date out, add active weekdays, or cover fewer pages to "
                    "ease the pace."
                ),
            )

        return LessonDistribution(
            total_lessons=total_lessons,
            available_days=available_days,
            lessons_per_day=1,
            day_interval=available_days // total_lessons,
            is_rigorous=False,
        )

    def assign_dates(self, school_days: Sequence[date], total_lessons: int) -> list[date]:
        """One date per lesson, in order, spread as evenly as the days allow.

        The same proportional walk covers both directions. Stretching gives each
        lesson its own day roughly every ``day_interval`` days; compressing
        repeats a day until its share of the lessons is used up. Either way the
        first lesson is on the first school day and none fall past the last.
        """
        if total_lessons < 1:
            raise PacingError("a syllabus needs at least one lesson")
        if not school_days:
            raise PacingError("the window contains no school days to schedule on")

        return [
            school_days[index * len(school_days) // total_lessons]
            for index in range(total_lessons)
        ]

    def plan(
        self,
        start_date: date,
        end_date: date,
        active_weekdays: Iterable[int],
        total_lessons: int,
        excluded_dates: Iterable[date] = (),
    ) -> PacingPlan:
        """The whole calculation: which days are available and what lands where."""
        days = self.school_days(start_date, end_date, active_weekdays, excluded_dates)
        distribution = self.distribute_lessons(total_lessons, len(days))
        return PacingPlan(
            distribution=distribution,
            school_days=tuple(days),
            scheduled_dates=tuple(self.assign_dates(days, total_lessons)),
        )

    @staticmethod
    def _normalize_weekdays(active_weekdays: Iterable[int]) -> frozenset[int]:
        weekdays = frozenset(active_weekdays)
        if not weekdays:
            raise PacingError("at least one active weekday is required")
        outside = sorted(day for day in weekdays if not 0 <= day <= 6)
        if outside:
            raise PacingError(
                f"{outside} are not weekdays; use 0 for Monday through 6 for Sunday"
            )
        return weekdays


class SyllabusCommitter:
    """Writes an approved syllabus as catalog structure plus dated assignments.

    One lesson becomes three rows: a ``CurriculumUnit`` for the teachable step, a
    ``CurriculumPageMapping`` holding the pages it covers, and an ``Assignment``
    putting it on a date for one student. The units hang off a single course unit
    so a generated syllabus can be found, and dropped, as a whole.

    Catalog rows are written on ``catalog_db``; assignments are written on
    ``tenant_db``. Callers are expected to have already checked that the student,
    edition, book, and subject exist; this class reports only the failures that
    surface once the rows are in flight.
    """

    def __init__(self, catalog_db: Session, tenant_db: Session) -> None:
        self._catalog_db = catalog_db
        self._tenant_db = tenant_db

    def commit(self, payload: PacingCommitRequest) -> PacingCommitRead:
        """Write the whole syllabus or none of it."""
        try:
            summary = self._write(payload)
            self._tenant_db.commit()
            if self._catalog_db is not self._tenant_db:
                self._catalog_db.commit()
        except IntegrityError as error:
            self._tenant_db.rollback()
            if self._catalog_db is not self._tenant_db:
                self._catalog_db.rollback()
            raise SyllabusCommitError(
                f"the syllabus conflicts with existing catalog rows: {error.orig}"
            ) from error
        except Exception:
            self._tenant_db.rollback()
            if self._catalog_db is not self._tenant_db:
                self._catalog_db.rollback()
            raise
        return summary

    def _write(self, payload: PacingCommitRequest) -> PacingCommitRead:
        lessons = sorted(payload.lessons, key=lambda lesson: (lesson.sequence, lesson.start_page))
        resource, resource_created = self._get_or_create_resource(payload)

        course = CurriculumUnit(
            curriculum_edition_id=payload.curriculum_edition_id,
            kind=payload.course_kind,
            title=payload.course_title,
            sort_order=0,
            depth=0,
        )
        self._tenant_db.add(course)
        self._tenant_db.flush()

        units = [
            CurriculumUnit(
                curriculum_edition_id=payload.curriculum_edition_id,
                parent_id=course.id,
                kind=UnitKind.LESSON,
                label=f"Lesson {lesson.sequence}",
                title=lesson.title,
                sort_order=index,
                depth=1,
                estimated_sessions=1,
            )
            for index, lesson in enumerate(lessons)
        ]
        self._tenant_db.add_all(units)
        # Flushed as a batch rather than per lesson, because the page mappings and
        # assignments below are the only reason the unit ids are needed.
        self._tenant_db.flush()

        student_ids = payload.students_to_schedule()
        # One UUID per lesson, shared across students, so a work sample for
        # "Lesson 3" can land on every child who was given that same event.
        group_uuids = [
            str(uuid4()) if len(student_ids) > 1 else None for _ in lessons
        ]
        assignments = [
            Assignment(
                student_id=student_id,
                curriculum_resource_id=resource.id,
                curriculum_unit_id=unit.id,
                subject_taxonomy_id=payload.subject_taxonomy_id,
                title=lesson.title,
                scheduled_date=lesson.scheduled_date,
                status=AssignmentStatus.ASSIGNED,
                shared_group_uuid=group_uuid,
            )
            for student_id in student_ids
            for lesson, unit, group_uuid in zip(
                lessons, units, group_uuids, strict=True
            )
        ]
        self._tenant_db.add_all(assignments)
        self._tenant_db.add_all(
            CurriculumPageMapping(
                curriculum_unit_id=unit.id,
                curriculum_resource_id=resource.id,
                page_start=lesson.start_page,
                page_end=lesson.end_page,
                is_primary=True,
                source=MappingSource.AI_PARSED,
            )
            for lesson, unit in zip(lessons, units, strict=True)
        )
        edition = self._tenant_db.get(CurriculumEdition, payload.curriculum_edition_id)
        if edition is None:
            raise SyllabusCommitError("Curriculum edition not found")
        year = require_operational_school_year(self._tenant_db)
        enroll_students(
            self._tenant_db,
            student_ids,
            edition.curriculum_id,
            year.id,
        )
        self._tenant_db.flush()

        scheduled = [lesson.scheduled_date for lesson in lessons]
        return PacingCommitRead(
            student_id=student_ids[0],
            student_ids=student_ids,
            curriculum_edition_id=payload.curriculum_edition_id,
            curriculum_resource_id=resource.id,
            resource_created=resource_created,
            course_unit_id=course.id,
            lesson_unit_ids=[unit.id for unit in units],
            assignment_ids=[assignment.id for assignment in assignments],
            units_created=len(units) + 1,
            page_mappings_created=len(units),
            assignments_created=len(assignments),
            first_scheduled_date=min(scheduled),
            last_scheduled_date=max(scheduled),
        )

    def _get_or_create_resource(
        self,
        payload: PacingCommitRequest,
    ) -> tuple[CurriculumResource, bool]:
        """Reuse the edition's resource for this book, so re-running adds no copy."""
        stmt = select(CurriculumResource).where(
            CurriculumResource.curriculum_edition_id == payload.curriculum_edition_id,
            CurriculumResource.kind == payload.resource_kind,
        )
        title = self._resource_title(payload)
        if payload.book_id is not None:
            stmt = stmt.where(CurriculumResource.book_edition_id == payload.book_id)
        else:
            stmt = stmt.where(func.lower(CurriculumResource.title) == title.lower())

        resource = self._tenant_db.execute(stmt).scalars().first()
        if resource is not None:
            return resource, False

        resource = CurriculumResource(
            curriculum_edition_id=payload.curriculum_edition_id,
            book_edition_id=payload.book_id,
            kind=payload.resource_kind,
            title=title,
        )
        self._tenant_db.add(resource)
        self._tenant_db.flush()
        return resource, True

    def _resource_title(self, payload: PacingCommitRequest) -> str:
        if payload.resource_title:
            return payload.resource_title
        if payload.book_id is not None:
            book = self._catalog_db.get(BookEdition, payload.book_id)
            if book is not None:
                return book.work.title
        return payload.course_title
