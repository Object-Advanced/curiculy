"""Attendance: suggested from the day's work, recorded only with the parent's tap.

A child who finished or started a lesson, or took part in an activity, on a
day is suggested **Present**; a sick day on the calendar suggests **Sick**.
Nothing is written until the parent confirms (the "School today?" card, the
weekly sweep, or the calendar). Whether a day with finished work may count
without a tap is an open question in the product spine, so it doesn't.

Days off fill themselves in: they aren't school days, so nothing is asked.
Work done on one anyway (a Saturday catch-up) is suggested as a school day.
See docs/6-planning/product-spine.md ("Attendance: per child, one tap").
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, AttendanceStatus, ExceptionKind
from app.models import (
    Activity,
    ActivityStudent,
    Assignment,
    Attendance,
    CalendarException,
    SchoolYear,
    Student,
)
from app.schemas.attendance import (
    AttendanceChildDay,
    AttendanceChildSummary,
    AttendanceDayCard,
    AttendanceDays,
    AttendanceMark,
    AttendanceSummary,
)
from app.services.clock import household_today
from app.services.households import get_default_household
from app.services.school_year import ensure_operational_school_year, load_school_year_settings

MAX_DAYS = 62
PRESENT_LIKE = {AttendanceStatus.PRESENT, AttendanceStatus.FIELD_TRIP}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


@dataclass
class _Calendar:
    """The family's school days around a window: weekdays, school years and days off."""

    weekdays: list[int]
    years: list[tuple[date, date]]
    household_off: dict[date, str] = field(default_factory=dict)
    # child -> day -> (title, kind)
    child_off: dict[int, dict[date, tuple[str, ExceptionKind]]] = field(default_factory=dict)

    def school_day(self, day: date) -> bool:
        return (
            day.weekday() in self.weekdays
            and any(start <= day <= end for start, end in self.years)
            and day not in self.household_off
        )

    def child_school_day(self, student_id: int, day: date) -> bool:
        """A school day for this child: a sick day still is (they're marked Sick); other days off aren't."""
        off = self.child_off.get(student_id, {}).get(day)
        return self.school_day(day) and (off is None or off[1] == ExceptionKind.SICK)


def _calendar(db: Session, start: date, end: date) -> _Calendar:
    weekdays = load_school_year_settings(db)[2]
    years = [(row.start_date, row.end_date) for row in db.scalars(select(SchoolYear))]
    cal = _Calendar(weekdays=weekdays, years=years)
    rows = db.scalars(
        select(CalendarException)
        .where(CalendarException.start_date <= end, CalendarException.end_date >= start)
        .order_by(CalendarException.id)
    )
    for row in rows:
        day = max(row.start_date, start)
        while day <= min(row.end_date, end):
            if row.student_id is None:
                cal.household_off.setdefault(day, row.title)
            else:
                cal.child_off.setdefault(row.student_id, {}).setdefault(day, (row.title, row.kind))
            day += timedelta(days=1)
    return cal


@dataclass
class _Work:
    """What each child did, by day."""

    planned: dict[tuple[int, date], int] = field(default_factory=lambda: defaultdict(int))
    done: dict[tuple[int, date], list[Assignment]] = field(default_factory=lambda: defaultdict(list))
    started: dict[tuple[int, date], int] = field(default_factory=lambda: defaultdict(int))
    activities: dict[tuple[int, date], list[Activity]] = field(default_factory=lambda: defaultdict(list))

    def minutes(self, key: tuple[int, date]) -> tuple[int, int]:
        """(minutes from finished lessons and activities, finished lessons without minutes)."""
        lessons = self.done.get(key, [])
        total = sum(lesson.minutes or 0 for lesson in lessons)
        total += sum(activity.minutes or 0 for activity in self.activities.get(key, []))
        return total, sum(1 for lesson in lessons if not lesson.minutes)


def _work(db: Session, student_ids: list[int], start: date, end: date) -> _Work:
    work = _Work()
    if not student_ids:
        return work
    lessons = db.scalars(
        select(Assignment).where(
            Assignment.student_id.in_(student_ids),
            or_(
                Assignment.scheduled_date.between(start, end),
                Assignment.completion_date.between(start, end),
            ),
        )
    )
    for lesson in lessons:
        if start <= lesson.scheduled_date <= end:
            work.planned[(lesson.student_id, lesson.scheduled_date)] += 1
            if lesson.status == AssignmentStatus.IN_PROGRESS:
                work.started[(lesson.student_id, lesson.scheduled_date)] += 1
        if lesson.status == AssignmentStatus.COMPLETED:
            # Done on the day it was checked off (or, for older rows, the day it was planned).
            day = lesson.completion_date or lesson.scheduled_date
            if start <= day <= end:
                work.done[(lesson.student_id, day)].append(lesson)
    links = db.execute(
        select(ActivityStudent.student_id, Activity)
        .join(Activity, Activity.id == ActivityStudent.activity_id)
        .where(ActivityStudent.student_id.in_(student_ids), Activity.on_date.between(start, end))
        .order_by(Activity.id)
    )
    for student_id, activity in links:
        work.activities[(student_id, activity.on_date)].append(activity)
    return work


def _child_day(
    cal: _Calendar, work: _Work, student: Student, day: date, record: Attendance | None
) -> AttendanceChildDay:
    key = (student.id, day)
    off = cal.child_off.get(student.id, {}).get(day)
    school_day = cal.child_school_day(student.id, day)
    done = len(work.done.get(key, []))
    started = work.started.get(key, 0)
    activities = work.activities.get(key, [])
    planned = work.planned.get(key, 0)

    suggestion: AttendanceStatus | None = None
    reasons: list[str] = []
    if off is not None and off[1] == ExceptionKind.SICK and school_day:
        suggestion = AttendanceStatus.SICK
        reasons.append(f"Sick day on the calendar: {off[0]}")
    elif done or started or activities:
        suggestion = AttendanceStatus.PRESENT
        if done:
            reasons.append(f"Finished {_plural(done, 'lesson')}")
        if started:
            reasons.append(f"Started {_plural(started, 'lesson')}")
        reasons.extend(f"Did an activity: {activity.title}" for activity in activities)
        if not school_day:
            reasons.append(f"Not a school day on your calendar. Count {WEEKDAYS[day.weekday()]} as one?")
    elif school_day:
        reasons.append(
            f"{_plural(planned, 'lesson')} planned, none checked off yet" if planned else "Nothing planned in Curiculy"
        )
    elif off is not None:
        reasons.append(f"Day off: {off[0]}")
    elif day in cal.household_off:
        reasons.append(f"Day off: {cal.household_off[day]}")
    else:
        reasons.append("Not a school day")

    from_work, without = work.minutes(key)
    recorded_minutes = record.minutes if record is not None else None
    return AttendanceChildDay(
        student_id=student.id,
        name=student.name,
        status=record.status if record is not None else None,
        source=record.source if record is not None else None,
        suggestion=suggestion,
        reasons=reasons,
        expected=school_day or suggestion is not None,
        lessons_planned=planned,
        lessons_done=done,
        activities=[activity.title for activity in activities],
        minutes=recorded_minutes if recorded_minutes is not None else (from_work or None),
        minutes_from_work=from_work,
        lessons_without_minutes=without,
    )


def _students(db: Session, student_id: int | None) -> list[Student]:
    query = select(Student).order_by(Student.id)
    if student_id is not None:
        query = query.where(Student.id == student_id)
    students = list(db.scalars(query))
    if student_id is not None and not students:
        raise HTTPException(status_code=404, detail="Student not found")
    return students


def _window(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date.")
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"Ask for up to {MAX_DAYS} days at a time.")


def day_cards(
    db: Session, start: date | None = None, end: date | None = None, student_id: int | None = None
) -> AttendanceDays:
    """Each day in the window, each child: what's marked and what's suggested. Saves nothing."""
    today = household_today(db)
    start = start or today
    end = end or start
    _window(start, end)
    students = _students(db, student_id)
    cal = _calendar(db, start, end)
    work = _work(db, [student.id for student in students], start, end)
    records = {
        (row.student_id, row.date): row
        for row in db.scalars(
            select(Attendance).where(
                Attendance.student_id.in_([student.id for student in students]),
                Attendance.date.between(start, end),
            )
        )
    }
    days = []
    day = start
    while day <= end:
        days.append(AttendanceDayCard(
            date=day,
            weekday=WEEKDAYS[day.weekday()],
            school_day=cal.school_day(day),
            day_off=cal.household_off.get(day),
            children=[_child_day(cal, work, student, day, records.get((student.id, day))) for student in students],
        ))
        day += timedelta(days=1)
    return AttendanceDays(today=today, count_by=get_default_household(db).count_by, days=days)


def confirm(db: Session, marks: list[AttendanceMark]) -> list[Attendance]:
    """Record the parent's marks. A mark that matches the suggestion is kept as a confirmed suggestion."""
    today = household_today(db)
    if any(mark.date > today for mark in marks):
        raise HTTPException(status_code=422, detail="That day hasn't happened yet. Days off go on the calendar.")
    start, end = min(mark.date for mark in marks), max(mark.date for mark in marks)
    _window(start, end)
    student_ids = {mark.student_id for mark in marks}
    students = {student.id: student for student in db.scalars(select(Student).where(Student.id.in_(student_ids)))}
    if len(students) != len(student_ids):
        raise HTTPException(status_code=404, detail="Student not found")
    cal = _calendar(db, start, end)
    work = _work(db, list(student_ids), start, end)
    existing = {
        (row.student_id, row.date): row
        for row in db.scalars(
            select(Attendance).where(Attendance.student_id.in_(student_ids), Attendance.date.between(start, end))
        )
    }
    saved = []
    for mark in marks:
        key = (mark.student_id, mark.date)
        suggested = _child_day(cal, work, students[mark.student_id], mark.date, None).suggestion
        row = existing.get(key)
        if row is None:
            row = Attendance(student_id=mark.student_id, date=mark.date, status=mark.status)
            db.add(row)
            existing[key] = row
        row.status = mark.status
        row.source = "suggestion" if suggested == mark.status else "parent"
        if "minutes" in mark.model_fields_set:
            row.minutes = mark.minutes
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return saved


def summary(db: Session, school_year_id: int | None = None) -> AttendanceSummary:
    """Each child's year so far: days present, sick and absent, days not marked, and what's ahead."""
    today = household_today(db)
    count_by = get_default_household(db).count_by
    year = db.get(SchoolYear, school_year_id) if school_year_id is not None else ensure_operational_school_year(db)
    if school_year_id is not None and year is None:
        raise HTTPException(status_code=404, detail="School year not found")
    if year is None:
        return AttendanceSummary(
            school_year_id=None, school_year_name=None, start_date=None, end_date=None,
            today=today, count_by=count_by, children=[],
        )
    students = _students(db, None)
    start, end = year.start_date, year.end_date
    cal = _calendar(db, start, end)
    work = _work(db, [student.id for student in students], start, end)
    records: dict[int, dict[date, Attendance]] = defaultdict(dict)
    for row in db.scalars(select(Attendance).where(Attendance.date.between(start, end))):
        records[row.student_id][row.date] = row

    children = []
    for student in students:
        marks = records.get(student.id, {})
        child = AttendanceChildSummary(student_id=student.id, name=student.name)
        for day, row in marks.items():
            if row.status in PRESENT_LIKE:
                child.present_days += 1
                if row.status == AttendanceStatus.FIELD_TRIP:
                    child.field_trip_days += 1
                from_work, without = work.minutes((student.id, day))
                if row.minutes is not None:
                    child.minutes += row.minutes
                else:
                    child.minutes += from_work
                    child.lessons_without_minutes += without
            elif row.status == AttendanceStatus.SICK:
                child.sick_days += 1
            elif row.status == AttendanceStatus.ABSENT:
                child.absent_days += 1
        day = start
        while day <= end:
            if cal.child_school_day(student.id, day):
                if day < today and day not in marks:
                    child.unmarked_days += 1
                elif day > today or (day == today and day not in marks):
                    child.school_days_left += 1
            day += timedelta(days=1)
        child.on_track_days = child.present_days + child.school_days_left
        children.append(child)
    return AttendanceSummary(
        school_year_id=year.id, school_year_name=year.name, start_date=start, end_date=end,
        today=today, count_by=count_by, children=children,
    )
