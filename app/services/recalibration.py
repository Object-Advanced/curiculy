"""Life Happens: shift uncompleted work after a disruption, without touching done lessons.

Parents who miss a stretch of school days should not have to drag every leftover
assignment forward by hand. Two strategies share the same ingredients — open
assignments, household class days, and calendar exceptions — and differ only in
which weekdays the pacing engine is allowed to land on.

``extend_year`` keeps the usual cadence and walks school days forward from today,
so the year ends later. ``add_weekends`` temporarily adds Saturday (or Sunday if
Saturday is already a class day) while the overdue unique days are placed, then
returns to the original weekdays so the rest of the year can stay put once the
backlog is absorbed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.enums import AssignmentStatus
from app.models import Assignment, Student
from app.services.clock import household_today
from app.services.curriculum_plan_apply import exception_dates_for_student
from app.services.pacing import PacingEngine, PacingError
from app.services.school_year import load_school_year_settings

OPEN_STATUSES = (AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS)
STRATEGIES = frozenset({"extend_year", "add_weekends"})
SATURDAY = 5
SUNDAY = 6


class RecalibrationError(ValueError):
    """The schedule could not be recalibrated; nothing was written."""


def _today(db_session: Session) -> date:
    return household_today(db_session)


def calculate_recovery_options(student_id: int, db_session: Session) -> dict[str, Any]:
    """Count overdue open work and how many days each recovery strategy needs."""
    student = _require_student(db_session, student_id)
    today = _today(db_session)
    context = _schedule_context(db_session, student, today)
    overdue = [item for item in context.assignments if item.scheduled_date < today]
    overdue_days = _unique_dates(overdue)
    original_end = context.assignments[-1].scheduled_date if context.assignments else None

    required_days: dict[str, int] = {}
    strategies: dict[str, dict[str, Any]] = {}
    for strategy in ("extend_year", "add_weekends"):
        mapping = _date_mapping(strategy, context)
        overdue_end = _last_mapped(mapping, overdue_days)
        new_end = _last_mapped(mapping, context.unique_dates)
        required = _calendar_span(today, overdue_end)
        required_days[strategy] = required
        strategies[strategy] = {
            "required_days": required,
            "new_end_date": new_end.isoformat() if new_end else None,
            "assignments_moved": sum(
                1 for item in context.assignments if mapping.get(item.scheduled_date) != item.scheduled_date
            ),
            "saturdays_used": _saturdays_used(mapping) if strategy == "add_weekends" else 0,
        }

    return {
        "student_id": student.id,
        "overdue_count": len(overdue),
        "overdue_school_days": len(overdue_days),
        "uncompleted_count": len(context.assignments),
        "uncompleted_school_days": len(context.unique_dates),
        "original_end_date": original_end.isoformat() if original_end else None,
        "target_days": list(context.target_days),
        "required_days": required_days,
        "strategies": strategies,
    }


def execute_recalibration(
    student_id: int,
    strategy: str,
    options: dict | None,
    db_session: Session,
) -> dict[str, Any]:
    """Remap every open assignment for ``strategy`` and commit the new dates."""
    if strategy not in STRATEGIES:
        raise RecalibrationError(
            f"unknown strategy {strategy!r}; use 'extend_year' or 'add_weekends'"
        )

    student = _require_student(db_session, student_id)
    today = _today(db_session)
    target_days = _target_days_from_options(options)
    context = _schedule_context(db_session, student, today, target_days=target_days)
    original_end = context.assignments[-1].scheduled_date if context.assignments else None
    mapping = _date_mapping(strategy, context)

    moved = 0
    for item in context.assignments:
        new_date = mapping.get(item.scheduled_date)
        if new_date is None or new_date == item.scheduled_date:
            continue
        item.scheduled_date = new_date
        moved += 1

    scheduled = [item.scheduled_date for item in context.assignments]
    db_session.commit()
    return {
        "student_id": student.id,
        "strategy": strategy,
        "assignments_moved": moved,
        "first_scheduled_date": min(scheduled).isoformat() if scheduled else None,
        "last_scheduled_date": max(scheduled).isoformat() if scheduled else None,
        "original_end_date": original_end.isoformat() if original_end else None,
    }


class _ScheduleContext:
    """Open assignments plus the calendar rules used to place them."""

    __slots__ = ("student", "today", "target_days", "exceptions", "assignments", "unique_dates")

    def __init__(
        self,
        student: Student,
        today: date,
        target_days: list[int],
        exceptions: set[date],
        assignments: list[Assignment],
    ) -> None:
        self.student = student
        self.today = today
        self.target_days = target_days
        self.exceptions = exceptions
        self.assignments = assignments
        self.unique_dates = _unique_dates(assignments)


def _schedule_context(
    db: Session,
    student: Student,
    today: date,
    target_days: list[int] | None = None,
) -> _ScheduleContext:
    if target_days is None:
        _start, _end, weekdays, _year_id = load_school_year_settings(db)
        target_days = weekdays
    return _ScheduleContext(
        student=student,
        today=today,
        target_days=list(target_days),
        exceptions=exception_dates_for_student(db, student),
        assignments=_open_assignments(db, student.id),
    )


def _require_student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise RecalibrationError("Student not found")
    return student


def _open_assignments(db: Session, student_id: int) -> list[Assignment]:
    return (
        db.query(Assignment)
        .filter(
            Assignment.student_id == student_id,
            Assignment.status.in_(OPEN_STATUSES),
        )
        .order_by(Assignment.scheduled_date.asc(), Assignment.id.asc())
        .all()
    )


def _unique_dates(assignments: list[Assignment]) -> list[date]:
    dates: list[date] = []
    for item in assignments:
        if not dates or dates[-1] != item.scheduled_date:
            dates.append(item.scheduled_date)
    return dates


def _target_days_from_options(options: dict | None) -> list[int] | None:
    if not options:
        return None
    raw = options.get("target_days")
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise RecalibrationError("options.target_days must be a list of weekdays")
    try:
        days = [int(day) for day in raw]
    except (TypeError, ValueError) as error:
        raise RecalibrationError("options.target_days must be a list of weekdays") from error
    if not days:
        raise RecalibrationError("at least one class day is required")
    outside = sorted({day for day in days if not 0 <= day <= 6})
    if outside:
        raise RecalibrationError("weekdays must be 0 (Monday) through 6 (Sunday)")
    return sorted(set(days))


def _catchup_weekdays(target_days: list[int]) -> list[int]:
    days = set(target_days)
    if SATURDAY not in days:
        days.add(SATURDAY)
    elif SUNDAY not in days:
        days.add(SUNDAY)
    return sorted(days)


def _date_mapping(strategy: str, context: _ScheduleContext) -> dict[date, date]:
    if not context.unique_dates:
        return {}
    overdue = [day for day in context.unique_dates if day < context.today]
    if not overdue:
        return {day: day for day in context.unique_dates}
    try:
        if strategy == "add_weekends":
            return _add_weekends_mapping(context)
        return _extend_year_mapping(context)
    except PacingError as error:
        raise RecalibrationError(str(error)) from error


def _extend_year_mapping(context: _ScheduleContext) -> dict[date, date]:
    """One new school day per original unique date, starting today."""
    engine = PacingEngine()
    placed = engine.school_days_ahead(
        context.today,
        len(context.unique_dates),
        context.target_days,
        context.exceptions,
    )
    return dict(zip(context.unique_dates, placed, strict=True))


def _add_weekends_mapping(context: _ScheduleContext) -> dict[date, date]:
    """Park overdue unique days on extra weekend class days, then resume cadence."""
    engine = PacingEngine()
    overdue = [day for day in context.unique_dates if day < context.today]
    future = [day for day in context.unique_dates if day >= context.today]
    catchup_days = _catchup_weekdays(context.target_days)
    mapping: dict[date, date] = {}
    last_placed: date | None = None

    if overdue:
        placed = engine.school_days_ahead(
            context.today,
            len(overdue),
            catchup_days,
            context.exceptions,
        )
        mapping.update(zip(overdue, placed, strict=True))
        last_placed = placed[-1]

    if not future:
        return mapping

    original_weekdays = set(context.target_days)
    for original in future:
        if last_placed is not None and original <= last_placed:
            break
        if (
            original >= context.today
            and original.weekday() in original_weekdays
            and original not in context.exceptions
        ):
            mapping[original] = original
            last_placed = original
        else:
            break

    to_shift = [day for day in future if day not in mapping]
    if to_shift:
        resume = last_placed + timedelta(days=1) if last_placed is not None else context.today
        placed = engine.school_days_ahead(
            resume,
            len(to_shift),
            context.target_days,
            context.exceptions,
        )
        mapping.update(zip(to_shift, placed, strict=True))
    return mapping


def _last_mapped(mapping: dict[date, date], originals: list[date]) -> date | None:
    dates = [mapping[day] for day in originals if day in mapping]
    return max(dates) if dates else None


def _calendar_span(today: date, last_date: date | None) -> int:
    if last_date is None:
        return 0
    return max(0, (last_date - today).days + 1)


def _saturdays_used(mapping: dict[date, date]) -> int:
    return sum(1 for new_date in mapping.values() if new_date.weekday() == SATURDAY)
