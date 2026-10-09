"""Stamp a saved pacing guide onto a student's assignment calendar.

Each Week W / Day D slot in the plan consumes the next school day, even when
that slot has no titled lesson. Extra lessons on the same slot share the date.
Weekends, unticked weekdays, and calendar exceptions are skipped.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, CurriculumPlanStatus
from app.models import Assignment, CalendarException, CurriculumLesson, CurriculumPlan, Student
from app.schemas.curriculum_plans import (
    CurriculumPlanApplyRead,
    is_schedulable_lesson,
    parse_json_string_list,
    time_slot_sort_key,
)
from app.services.enrollments import curriculum_for_plan, ensure_enrollment
from app.services.pacing import PacingEngine, PacingError
from app.services.school_year import require_operational_school_year


class CurriculumPlanApplyError(ValueError):
    """The plan could not be applied; nothing was written."""


def exception_dates_for_student(db: Session, student: Student) -> set[date]:
    """Household-wide and student-specific exception ranges, inclusive."""
    rows = (
        db.query(CalendarException)
        .filter(
            CalendarException.household_id == student.household_id,
            or_(
                CalendarException.student_id.is_(None),
                CalendarException.student_id == student.id,
            ),
        )
        .all()
    )
    skipped: set[date] = set()
    for row in rows:
        day = row.start_date
        while day <= row.end_date:
            skipped.add(day)
            day += timedelta(days=1)
    return skipped


def _lesson_resources(lesson: CurriculumLesson) -> list[str]:
    return parse_json_string_list(lesson.resources) or []


def _assignment_notes(lesson: CurriculumLesson) -> str | None:
    parts: list[str] = []
    time_slot = (lesson.time_slot or "").strip()
    if time_slot:
        parts.append(time_slot)
    notes = (lesson.notes or "").strip()
    if notes:
        parts.append(notes)
    urls = _lesson_resources(lesson)
    if urls:
        parts.append("Resources:\n" + "\n".join(urls))
    return "\n\n".join(parts) or None


def _lessons_by_slot(
    lessons: list[CurriculumLesson],
) -> dict[tuple[int, int], list[CurriculumLesson]]:
    buckets: dict[tuple[int, int], list[CurriculumLesson]] = defaultdict(list)
    for lesson in lessons:
        week = lesson.week_number if lesson.week_number is not None else 1
        buckets[(week, lesson.day_number)].append(lesson)
    for slot_lessons in buckets.values():
        slot_lessons.sort(
            key=lambda lesson: (
                time_slot_sort_key(lesson.time_slot),
                lesson.id or 0,
            )
        )
    return buckets


def apply_curriculum_plan(
    db: Session,
    plan: CurriculumPlan,
    student: Student,
    start_date: date,
    target_days: list[int],
) -> CurriculumPlanApplyRead:
    """Write dated assignments for every titled lesson, preserving empty slots."""
    if plan.status == CurriculumPlanStatus.PROCESSING:
        raise CurriculumPlanApplyError("the plan is still being processed")
    lessons = (
        db.query(CurriculumLesson)
        .filter(CurriculumLesson.plan_id == plan.id)
        .order_by(
            CurriculumLesson.week_number.asc(),
            CurriculumLesson.day_number.asc(),
            CurriculumLesson.id.asc(),
        )
        .all()
    )
    titled = [
        lesson
        for lesson in lessons
        if is_schedulable_lesson(lesson.title, lesson.category)
    ]
    if not titled:
        raise CurriculumPlanApplyError("the plan has no assignments to schedule")

    slot_count = plan.total_weeks * plan.frequency_days
    if slot_count < 1:
        raise CurriculumPlanApplyError("the plan has no school days to schedule")

    engine = PacingEngine()
    try:
        school_days = engine.school_days_ahead(
            start_date,
            slot_count,
            target_days,
            exception_dates_for_student(db, student),
        )
    except PacingError as error:
        raise CurriculumPlanApplyError(str(error)) from error

    buckets = _lessons_by_slot(lessons)
    assignments: list[Assignment] = []
    index = 0
    for week in range(1, plan.total_weeks + 1):
        for day in range(1, plan.frequency_days + 1):
            scheduled = school_days[index]
            index += 1
            for lesson in buckets.get((week, day), ()):
                title = (lesson.title or "").strip()
                if not is_schedulable_lesson(title, lesson.category):
                    continue
                assignments.append(
                    Assignment(
                        student_id=student.id,
                        title=title[:255],
                        scheduled_date=scheduled,
                        status=AssignmentStatus.ASSIGNED,
                        notes=_assignment_notes(lesson),
                    )
                )

    if not assignments:
        raise CurriculumPlanApplyError("the plan has no assignments to schedule")

    try:
        year = require_operational_school_year(db)
        curriculum = curriculum_for_plan(db, plan)
        for item in assignments:
            item.curriculum_id = curriculum.id
        ensure_enrollment(
            db,
            student_id=student.id,
            curriculum_id=curriculum.id,
            school_year_id=year.id,
        )
        db.add_all(assignments)
        db.flush()
        scheduled = [item.scheduled_date for item in assignments]
        db.commit()
    except Exception:
        db.rollback()
        raise
    return CurriculumPlanApplyRead(
        plan_id=plan.id,
        student_id=student.id,
        assignments_created=len(assignments),
        assignment_ids=[item.id for item in assignments],
        first_scheduled_date=min(scheduled),
        last_scheduled_date=max(scheduled),
    )
