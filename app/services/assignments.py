"""Read assignments over a date range.

Two concerns live here. Resolving a named period into explicit bounds is pure
date arithmetic and is kept free of the session so the calendar rules can be
tested on their own. Tenant rows are loaded in one query with grade and evidence
eagerly attached; catalog titles are copied on afterwards from ``catalog_db``,
because the two engines cannot be joined.

Bounds are always inclusive on both ends: a caller asking for a week means the
Monday and the Sunday, not a half-open interval.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import AssignmentStatus, CalendarPeriod
from app.models import (
    Assignment,
    Curriculum,
    CurriculumEdition,
    CurriculumResource,
    CurriculumUnit,
    Enrollment,
    SubjectTaxonomy,
)


class InvalidDateRangeError(ValueError):
    """The requested window cannot be resolved into bounds."""


@dataclass(frozen=True)
class DateRange:
    """An inclusive window. ``None`` on either side means open-ended."""

    start_date: date | None
    end_date: date | None

    def contains(self, day: date) -> bool:
        if self.start_date is not None and day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date


UNBOUNDED = DateRange(None, None)


@dataclass(frozen=True)
class StudentCourseProgress:
    """Lesson totals for one curriculum on one student's dashboard."""

    curriculum_id: int
    title: str
    total_assignments: int
    completed_assignments: int


def resolve_period(anchor: date, period: CalendarPeriod) -> DateRange:
    """Expand a named period around ``anchor`` into explicit inclusive bounds.

    Weeks run Monday to Sunday. Months and years are calendar ones, so the end
    of a month follows the actual month length, February in a leap year included.
    """
    match period:
        case CalendarPeriod.DAY:
            return DateRange(anchor, anchor)
        case CalendarPeriod.WEEK:
            monday = anchor - timedelta(days=anchor.weekday())
            return DateRange(monday, monday + timedelta(days=6))
        case CalendarPeriod.MONTH:
            last_day = monthrange(anchor.year, anchor.month)[1]
            return DateRange(anchor.replace(day=1), anchor.replace(day=last_day))
        case CalendarPeriod.YEAR:
            return DateRange(date(anchor.year, 1, 1), date(anchor.year, 12, 31))
        case _:
            raise InvalidDateRangeError(f"Unsupported period '{period}'")


def resolve_window(
    start_date: date | None = None,
    end_date: date | None = None,
    period: CalendarPeriod | None = None,
    today: date | None = None,
) -> DateRange:
    """Turn the query parameters a calendar sends into one inclusive window.

    ``period`` anchors on ``start_date`` when given and on today otherwise, which
    is what makes ``?period=week`` alone mean "this week". Combining it with
    ``end_date`` is rejected rather than guessed at, since the period already
    determines where the window ends.
    """
    if period is not None:
        if end_date is not None:
            raise InvalidDateRangeError(
                "Pass either 'period' or 'end_date'; a period computes its own end date"
            )
        return resolve_period(start_date or today or date.today(), period)

    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidDateRangeError(
            f"start_date {start_date} is after end_date {end_date}"
        )
    return DateRange(start_date, end_date)


class AssignmentQuery:
    """Loads assignments with everything the calendar and detail views render."""

    def __init__(self, db: Session, catalog_db: Session | None = None) -> None:
        self.db = db
        self.catalog_db = catalog_db

    def for_student(
        self,
        student_id: int,
        window: DateRange = UNBOUNDED,
    ) -> list[Assignment]:
        """Assignments scheduled inside ``window``, in the order a calendar reads."""
        stmt = (
            select(Assignment)
            .options(*self._eager_options())
            .where(Assignment.student_id == student_id)
            .order_by(Assignment.scheduled_date, Assignment.id)
        )
        if window.start_date is not None:
            stmt = stmt.where(Assignment.scheduled_date >= window.start_date)
        if window.end_date is not None:
            stmt = stmt.where(Assignment.scheduled_date <= window.end_date)
        assignments = list(self.db.execute(stmt).scalars().all())
        self._attach_catalog(assignments)
        return assignments

    def for_shared(
        self,
        window: DateRange = UNBOUNDED,
    ) -> list[Assignment]:
        """Joint household assignments (``shared_group_uuid`` set) inside ``window``."""
        stmt = (
            select(Assignment)
            .options(*self._eager_options())
            .where(Assignment.shared_group_uuid.isnot(None))
            .order_by(Assignment.scheduled_date, Assignment.student_id, Assignment.id)
        )
        if window.start_date is not None:
            stmt = stmt.where(Assignment.scheduled_date >= window.start_date)
        if window.end_date is not None:
            stmt = stmt.where(Assignment.scheduled_date <= window.end_date)
        assignments = list(self.db.execute(stmt).scalars().all())
        self._attach_catalog(assignments)
        return assignments

    def for_students(
        self,
        student_ids: list[int],
        window: DateRange = UNBOUNDED,
        *,
        completed_only: bool = False,
    ) -> list[Assignment]:
        """Assignments for any of ``student_ids`` inside ``window``."""
        if not student_ids:
            return []
        stmt = (
            select(Assignment)
            .options(*self._eager_options())
            .where(Assignment.student_id.in_(student_ids))
            .order_by(Assignment.student_id, Assignment.scheduled_date, Assignment.id)
        )
        if completed_only:
            stmt = stmt.where(Assignment.status == AssignmentStatus.COMPLETED)
        if window.start_date is not None:
            stmt = stmt.where(Assignment.scheduled_date >= window.start_date)
        if window.end_date is not None:
            stmt = stmt.where(Assignment.scheduled_date <= window.end_date)
        assignments = list(self.db.execute(stmt).scalars().all())
        self._attach_catalog(assignments)
        return assignments

    def completed_for_student_year(
        self,
        student_id: int,
        start_date: date,
        end_date: date,
    ) -> list[Assignment]:
        """Completed assignments scheduled inside an inclusive school-year window."""
        stmt = (
            select(Assignment)
            .options(*self._eager_options())
            .where(Assignment.student_id == student_id)
            .where(Assignment.status == AssignmentStatus.COMPLETED)
            .where(Assignment.scheduled_date >= start_date)
            .where(Assignment.scheduled_date <= end_date)
            .order_by(Assignment.scheduled_date, Assignment.id)
        )
        assignments = list(self.db.execute(stmt).scalars().all())
        self._attach_catalog(assignments)
        return assignments

    def for_shared_group(self, shared_group_uuid: str) -> list[Assignment]:
        """Every assignment tagged with the same shared-lesson UUID."""
        stmt = (
            select(Assignment)
            .where(Assignment.shared_group_uuid == shared_group_uuid)
            .order_by(Assignment.student_id, Assignment.id)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get(self, assignment_id: int) -> Assignment | None:
        stmt = (
            select(Assignment)
            .options(*self._eager_options())
            .where(Assignment.id == assignment_id)
        )
        assignment = self.db.execute(stmt).scalars().first()
        if assignment is not None:
            self._attach_catalog([assignment])
        return assignment

    def courses_for_student(self, student_id: int) -> list[StudentCourseProgress]:
        """Curricula this student is enrolled in or has scheduled, with completion counts."""
        assignment_rows = self.db.execute(
            select(
                Assignment.curriculum_id,
                Assignment.curriculum_resource_id,
                Assignment.curriculum_unit_id,
                Assignment.status,
            ).where(Assignment.student_id == student_id)
        ).all()
        resource_ids = {
            row.curriculum_resource_id
            for row in assignment_rows
            if row.curriculum_resource_id is not None
        }
        unit_ids = {
            row.curriculum_unit_id
            for row in assignment_rows
            if row.curriculum_unit_id is not None
        }
        resource_to_curriculum, unit_to_curriculum = self._catalog_curriculum_maps(
            resource_ids, unit_ids
        )

        counts: dict[int, tuple[int, int]] = {}
        for row in assignment_rows:
            curriculum_id = row.curriculum_id
            if curriculum_id is None and row.curriculum_resource_id is not None:
                curriculum_id = resource_to_curriculum.get(row.curriculum_resource_id)
            if curriculum_id is None and row.curriculum_unit_id is not None:
                curriculum_id = unit_to_curriculum.get(row.curriculum_unit_id)
            if curriculum_id is None:
                continue
            total, completed = counts.get(curriculum_id, (0, 0))
            total += 1
            if row.status == AssignmentStatus.COMPLETED:
                completed += 1
            counts[curriculum_id] = (total, completed)

        enrolled_ids = self.db.execute(
            select(Enrollment.curriculum_id).where(Enrollment.student_id == student_id)
        ).scalars()
        for enrolled_id in enrolled_ids:
            counts.setdefault(enrolled_id, (0, 0))
        if not counts:
            return []

        titles = self._curriculum_titles(list(counts))
        return [
            StudentCourseProgress(
                curriculum_id=item_id,
                title=titles[item_id],
                total_assignments=total,
                completed_assignments=completed,
            )
            for item_id, (total, completed) in sorted(
                counts.items(), key=lambda item: (titles[item[0]].lower(), item[0])
            )
            if item_id in titles
        ]

    def _catalog_curriculum_maps(
        self, resource_ids: set[int], unit_ids: set[int]
    ) -> tuple[dict[int, int], dict[int, int]]:
        if self.db is None:
            return {}, {}
        resource_to_curriculum: dict[int, int] = {}
        if resource_ids:
            resource_to_curriculum = dict(
                self.db.execute(
                    select(CurriculumResource.id, CurriculumEdition.curriculum_id)
                    .join(
                        CurriculumEdition,
                        CurriculumResource.curriculum_edition_id == CurriculumEdition.id,
                    )
                    .where(CurriculumResource.id.in_(resource_ids))
                ).all()
            )
        unit_to_curriculum: dict[int, int] = {}
        if unit_ids:
            unit_to_curriculum = dict(
                self.db.execute(
                    select(CurriculumUnit.id, CurriculumEdition.curriculum_id)
                    .join(
                        CurriculumEdition,
                        CurriculumUnit.curriculum_edition_id == CurriculumEdition.id,
                    )
                    .where(CurriculumUnit.id.in_(unit_ids))
                ).all()
            )
        return resource_to_curriculum, unit_to_curriculum

    def _curriculum_titles(self, curriculum_ids: list[int]) -> dict[int, str]:
        if not curriculum_ids:
            return {}
        return dict(
            self.db.execute(
                select(Curriculum.id, Curriculum.title).where(Curriculum.id.in_(curriculum_ids))
            ).all()
        )

    def _attach_catalog(self, assignments: list[Assignment]) -> None:
        """Copy library and taxonomy rows onto assignments so display properties resolve."""
        if not assignments:
            return

        resource_ids = {
            assignment.curriculum_resource_id
            for assignment in assignments
            if assignment.curriculum_resource_id is not None
        }
        unit_ids = {
            assignment.curriculum_unit_id
            for assignment in assignments
            if assignment.curriculum_unit_id is not None
        }
        subject_ids = {
            assignment.subject_taxonomy_id
            for assignment in assignments
            if assignment.subject_taxonomy_id is not None
        }

        resources: dict[int, CurriculumResource] = {}
        if resource_ids:
            resources = {
                resource.id: resource
                for resource in self.db.execute(
                    select(CurriculumResource)
                    .options(selectinload(CurriculumResource.curriculum_edition))
                    .where(CurriculumResource.id.in_(resource_ids))
                )
                .scalars()
                .all()
            }
        units: dict[int, CurriculumUnit] = {}
        if unit_ids:
            units = {
                unit.id: unit
                for unit in self.db.execute(
                    select(CurriculumUnit)
                    .options(selectinload(CurriculumUnit.curriculum_edition))
                    .where(CurriculumUnit.id.in_(unit_ids))
                )
                .scalars()
                .all()
            }
        subjects: dict[int, SubjectTaxonomy] = {}
        if subject_ids and self.catalog_db is not None:
            subjects = {
                subject.id: subject
                for subject in self.catalog_db.execute(
                    select(SubjectTaxonomy)
                    .options(
                        selectinload(SubjectTaxonomy.parent, recursion_depth=-1)
                    )
                    .where(SubjectTaxonomy.id.in_(subject_ids))
                )
                .scalars()
                .all()
            }

        for assignment in assignments:
            if assignment.curriculum_resource_id is not None:
                assignment._catalog_resource = resources.get(
                    assignment.curriculum_resource_id
                )
            if assignment.curriculum_unit_id is not None:
                assignment._catalog_unit = units.get(assignment.curriculum_unit_id)
            if assignment.subject_taxonomy_id is not None:
                assignment._catalog_subject = subjects.get(assignment.subject_taxonomy_id)

    @staticmethod
    def _eager_options() -> tuple:
        return (
            selectinload(Assignment.grade),
            selectinload(Assignment.evidence),
            selectinload(Assignment.student),
        )
