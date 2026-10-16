"""The move engine: every calendar change is worked out, previewed, then applied.

A move never changes anything until the parent applies it, and applying works
the plan out again: if the calendar changed since the preview (a lesson was
checked off in another tab), nothing is saved. Finished lessons never move.

A course's lessons are a sequence, so moves keep their order:

- **A course day** is everything the course has on one date (Saxon's lesson
  and its worktext pages). Pushing back moves whole course days onto the
  course's own weekdays, skipping days off.
- **One lesson, "just this one"** moves only that lesson; the same book's
  lessons between the two days slide by one so lesson 43 never lands before 42.
- **The catch-up sheet** offers several ways to absorb missed work (push back,
  a whole week, a free day, doubling up, skipping review lessons), each with
  its result in plain words and one recommended.

The plan checker turns each plan into warnings, never blocks: finishing after
the school year, a day over the family's lesson limit, a test that moves, a
lesson on a day that isn't a school day. See docs/6-planning/product-spine.md
("Calendar: move things, stay within the guidelines").
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import AssignmentStatus, ExceptionKind
from app.models import Assignment, CalendarException, Course, LibraryLesson, Student
from app.schemas.moves import (
    BehindCourse,
    CatchUpChoice,
    CatchUpRequest,
    CatchUpSheet,
    CourseEffect,
    CourseMoveRequest,
    DayMoveRequest,
    LessonChange,
    LessonMoveRequest,
    MovePreview,
    MoveRequest,
    MoveResult,
)
from app.services.clock import household_today
from app.services.households import get_default_household
from app.services.planner import _days_off
from app.services.school_year import (
    encode_weekdays,
    ensure_operational_school_year,
    load_school_year_settings,
    parse_weekdays,
)

OPEN = (AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS)
SKIPPABLE = {"review"}
TEST = "test"
# How far "use a day off" looks for free days when no test comes first.
HORIZON_DAYS = 21
SCAN_DAYS = 3 * 366
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
LONG_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def day_label(day: date) -> str:
    """"Tue, Oct 13"."""
    return f"{DAY_NAMES[day.weekday()]}, {day:%b} {day.day}"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


class NotWorkable(Exception):
    """A catch-up option that doesn't fit this course right now, and why."""


@dataclass
class _Group:
    """One course day: everything a course has on one date."""

    day: date
    rows: list[Assignment]


@dataclass
class _Plan:
    moves: dict[int, date] = field(default_factory=dict)
    skips: set[int] = field(default_factory=set)
    rows: dict[int, Assignment] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    exceptions: list[CalendarException] = field(default_factory=list)
    course_weekdays: dict[int, list[int]] = field(default_factory=dict)

    def move(self, row: Assignment, day: date) -> None:
        self.rows[row.id] = row
        if day == row.scheduled_date:
            self.moves.pop(row.id, None)
        else:
            self.moves[row.id] = day

    def relay(self, groups: list[_Group], slots: list[date]) -> None:
        for group, slot in zip(groups, slots):
            for row in group.rows:
                self.move(row, slot)

    def skip(self, row: Assignment) -> None:
        self.rows[row.id] = row
        self.moves.pop(row.id, None)
        self.skips.add(row.id)

    def new_date(self, row: Assignment) -> date:
        return self.moves.get(row.id, row.scheduled_date)

    def digest(self) -> str:
        parts = [f"m{key}:{value.isoformat()}" for key, value in sorted(self.moves.items())]
        parts += [f"s{key}" for key in sorted(self.skips)]
        parts += [f"c{key}:{value}" for key, value in sorted(self.course_weekdays.items())]
        parts += [
            f"e{row.student_id}:{row.kind}:{row.start_date.isoformat()}:{row.title}" for row in self.exceptions
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


class _Context:
    """What every move needs: today, the family's weekdays, days off, the year's end, the lesson limit."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.today = household_today(db)
        self.weekdays = load_school_year_settings(db)[2]
        year = ensure_operational_school_year(db)
        self.year_end = year.end_date if year else None
        self.limit = get_default_household(db).daily_lesson_limit
        self._off: dict[int, set[date]] = {}
        self._types: dict[int, str] = {}
        self._positions: dict[int, int] = {}

    def off(self, student_id: int) -> set[date]:
        if student_id not in self._off:
            self._off[student_id] = _days_off(self.db, student_id)
        return self._off[student_id]

    def student(self, student_id: int) -> Student:
        student = self.db.get(Student, student_id)
        if student is None:
            raise HTTPException(status_code=404, detail="Student not found")
        return student

    def course(self, course_id: int) -> Course:
        course = self.db.get(Course, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        return course

    def course_weekdays(self, course: Course) -> list[int]:
        return parse_weekdays(course.weekdays) or list(self.weekdays)

    def course_days(
        self,
        course: Course,
        start: date,
        count: int,
        *,
        skip: set[date] | frozenset[date] = frozenset(),
        weekdays: list[int] | None = None,
    ) -> list[date]:
        """The next ``count`` days this course meets, from ``start``: its weekdays, not days off."""
        wanted = set(weekdays if weekdays is not None else self.course_weekdays(course))
        off = self.off(course.student_id)
        days: list[date] = []
        day = start
        while len(days) < count:
            if (day - start).days > SCAN_DAYS:
                raise HTTPException(status_code=409, detail="There aren't enough school days ahead for this move.")
            if day.weekday() in wanted and day not in off and day not in skip:
                days.append(day)
            day += timedelta(days=1)
        return days

    def course_days_between(self, course: Course, start: date, end: date) -> list[date]:
        wanted = set(self.course_weekdays(course))
        off = self.off(course.student_id)
        days, day = [], start
        while day <= end:
            if day.weekday() in wanted and day not in off:
                days.append(day)
            day += timedelta(days=1)
        return days

    def next_school_day(self, student_id: int, start: date, skip: set[date]) -> date:
        off = self.off(student_id)
        day = start
        while day.weekday() not in self.weekdays or day in off or day in skip:
            day += timedelta(days=1)
            if (day - start).days > SCAN_DAYS:
                raise HTTPException(status_code=409, detail="There aren't enough school days ahead for this move.")
        return day

    def school_day(self, student_id: int, day: date) -> bool:
        return day.weekday() in self.weekdays and day not in self.off(student_id)

    def learn(self, rows: list[Assignment]) -> None:
        """Each textbook lesson's type (test, review…) and place in its book."""
        wanted = {row.library_lesson_id for row in rows if row.library_lesson_id} - set(self._positions)
        if wanted:
            for lesson in self.db.scalars(select(LibraryLesson).where(LibraryLesson.id.in_(wanted))):
                self._types[lesson.id] = lesson.type
                self._positions[lesson.id] = lesson.position

    def kind(self, row: Assignment) -> str:
        return self._types.get(row.library_lesson_id or 0, "lesson")

    def position(self, row: Assignment) -> int:
        return self._positions.get(row.library_lesson_id or 0, 0)

    def is_test(self, group: _Group) -> bool:
        return any(self.kind(row) == TEST for row in group.rows)


def _open_rows(ctx: _Context, course_id: int) -> list[Assignment]:
    rows = list(ctx.db.scalars(
        select(Assignment)
        .where(Assignment.course_id == course_id, Assignment.status.in_(OPEN))
        .order_by(Assignment.scheduled_date, Assignment.id)
    ))
    ctx.learn(rows)
    return rows


def _groups(rows: list[Assignment]) -> list[_Group]:
    groups: list[_Group] = []
    for row in rows:
        if groups and groups[-1].day == row.scheduled_date:
            groups[-1].rows.append(row)
        else:
            groups.append(_Group(row.scheduled_date, [row]))
    return groups


def _course_name(course: Course) -> str:
    return course.curriculum.name


# --- The moves --------------------------------------------------------------------


def _lesson_move(ctx: _Context, request: LessonMoveRequest) -> _Plan:
    row = ctx.db.get(Assignment, request.assignment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if row.status not in OPEN:
        raise HTTPException(status_code=409, detail="A finished lesson stays on the day it was done.")
    target, current = request.to_date, row.scheduled_date
    if target < ctx.today:
        raise HTTPException(status_code=422, detail="Pick today or a later day.")
    if target == current:
        raise HTTPException(status_code=422, detail="It's already on that day.")
    plan = _Plan()
    if row.course_id is None:
        plan.move(row, target)
        return plan
    course = ctx.course(row.course_id)
    rows = _open_rows(ctx, course.id)

    if request.mode == "ripple":
        groups = _groups(rows)
        if target < current:
            between = [group for group in groups if target <= group.day < current]
            if between:
                first = between[0]
                raise HTTPException(
                    status_code=409,
                    detail=f"{first.rows[0].title} is on {day_label(first.day)}, and it comes first. "
                    "Move it, or choose “Just this one”.",
                )
        moving = [group for group in groups if group.day >= current]
        plan.relay(moving, [target, *ctx.course_days(course, target + timedelta(days=1), len(moving) - 1)])
        return plan

    # Just this one: only this book's lessons between the two days slide by one.
    sequence = sorted(
        (other for other in rows if other.library_item_id == row.library_item_id),
        key=lambda other: (other.scheduled_date, ctx.position(other), other.id),
    )
    index = next(position for position, other in enumerate(sequence) if other.id == row.id)
    if target > current:
        window = [row, *(other for other in sequence[index + 1:] if other.scheduled_date <= target)]
        slots = [other.scheduled_date for other in window[1:]] + [target]
    else:
        before = [other for other in sequence[:index] if other.scheduled_date >= target]
        window = [*before, row]
        slots = [target, *(other.scheduled_date for other in before)]
    for other, slot in zip(window, slots):
        plan.move(other, slot)
    return plan


def _day_move(ctx: _Context, request: DayMoveRequest) -> _Plan:
    day = request.date
    if request.add_to_calendar and day < ctx.today:
        raise HTTPException(
            status_code=422, detail="Only days ahead go on the calendar; attendance records the days that have passed."
        )
    students = [ctx.student(student_id) for student_id in request.student_ids] or list(
        ctx.db.scalars(select(Student).order_by(Student.id))
    )
    plan = _Plan()
    start = max(day + timedelta(days=1), ctx.today)
    for student in students:
        rows = list(ctx.db.scalars(
            select(Assignment)
            .where(Assignment.student_id == student.id, Assignment.scheduled_date == day, Assignment.status.in_(OPEN))
            .order_by(Assignment.id)
        ))
        for course_id in dict.fromkeys(row.course_id for row in rows if row.course_id is not None):
            course = ctx.course(course_id)
            moving = [group for group in _groups(_open_rows(ctx, course_id)) if group.day >= day]
            plan.relay(moving, ctx.course_days(course, start, len(moving), skip={day}))
        loose = [row for row in rows if row.course_id is None]
        if loose:
            target = ctx.next_school_day(student.id, start, {day})
            for row in loose:
                plan.move(row, target)

    if request.add_to_calendar:
        everyone = not request.student_ids
        if request.add_to_calendar == "off" and everyone:
            household = get_default_household(ctx.db)
            plan.exceptions.append(CalendarException(
                household_id=household.id, student_id=None, kind=ExceptionKind.OTHER,
                title=request.title, start_date=day, end_date=day,
            ))
            plan.notes.append(f"Adds “{request.title}” to the family calendar on {day_label(day)}.")
        else:
            kind = ExceptionKind.SICK if request.add_to_calendar == "sick" else ExceptionKind.OTHER
            for student in students:
                plan.exceptions.append(CalendarException(
                    household_id=student.household_id, student_id=student.id, kind=kind,
                    title=request.title, start_date=day, end_date=day,
                ))
            names = " and ".join(student.name for student in students)
            plan.notes.append(f"Adds “{request.title}” on {day_label(day)} to {names}'s calendar.")
    return plan


def _free_days(ctx: _Context, course: Course, future: list[_Group], needed: int, allow_weekends: bool) -> list[date]:
    """Days the course doesn't meet, before its next test: weekdays first, then weekends if allowed."""
    weekdays = set(ctx.course_weekdays(course))
    off = ctx.off(course.student_id)
    tests = [group.day for group in future if ctx.is_test(group)]
    end = tests[0] - timedelta(days=1) if tests else ctx.today + timedelta(days=HORIZON_DAYS)
    candidates, day = [], ctx.today
    while day <= end:
        if day.weekday() not in weekdays and day not in off and (day.weekday() < 5 or allow_weekends):
            candidates.append(day)
        day += timedelta(days=1)
    candidates.sort(key=lambda candidate: (candidate.weekday() >= 5, candidate))
    if len(candidates) >= needed:
        return sorted(candidates[:needed])
    if not allow_weekends and all(weekday in weekdays for weekday in range(5)):
        raise NotWorkable(f"{_course_name(course)} meets every weekday. Allow weekends to use one.")
    if tests:
        raise NotWorkable(f"Not enough free days before the test on {day_label(tests[0])}.")
    raise NotWorkable("Not enough free days in the next three weeks.")


def _double_up(ctx: _Context, course: Course, groups: list[_Group], doubles: int, plan: _Plan) -> None:
    """Missed course days share upcoming days, two to a day, until caught up; never on a test day.

    A course with fewer lessons left than it's behind simply finishes sooner.
    """
    others = _load(ctx, course.student_id, exclude_course=course.id)
    queue = list(groups)
    day = ctx.today
    weekdays = set(ctx.course_weekdays(course))
    off = ctx.off(course.student_id)
    doubled = 0
    blocked_by_limit = blocked_by_test = False
    while queue:
        if (day - ctx.today).days > SCAN_DAYS:
            raise HTTPException(status_code=409, detail="There aren't enough school days ahead for this move.")
        if day.weekday() in weekdays and day not in off:
            first = queue.pop(0)
            plan.relay([first], [day])
            if doubled < doubles and queue:
                second = queue[0]
                total = others.get(day, 0) + len(first.rows) + len(second.rows)
                if ctx.is_test(first) or ctx.is_test(second):
                    blocked_by_test = True
                elif ctx.limit is not None and total > ctx.limit:
                    blocked_by_limit = True
                else:
                    plan.relay([queue.pop(0)], [day])
                    doubled += 1
        day += timedelta(days=1)
    if doubled == 0:
        if blocked_by_limit:
            raise NotWorkable(f"Every day is at your limit of {_plural(ctx.limit or 0, 'lesson')}.")
        if blocked_by_test:
            raise NotWorkable("Every day left has a test, and tests aren't doubled up.")
        raise NotWorkable("There's only one lesson left, so there's nothing to double up with.")


def _catch_up(ctx: _Context, course: Course, option: str, allow_weekends: bool) -> _Plan:
    rows = _open_rows(ctx, course.id)
    groups = _groups(rows)
    overdue = [group for group in groups if group.day < ctx.today]
    if not overdue:
        raise HTTPException(status_code=409, detail="Nothing to catch up: every lesson is on today or later.")
    future = groups[len(overdue):]
    plan = _Plan()
    if option == "push_back":
        plan.relay(groups, ctx.course_days(course, ctx.today, len(groups)))
    elif option == "push_week":
        monday = ctx.today + timedelta(days=7 - ctx.today.weekday())
        plan.relay(groups, ctx.course_days(course, monday, len(groups)))
    elif option == "use_day_off":
        free = _free_days(ctx, course, future, len(overdue), allow_weekends)
        last = free[-1]
        window = overdue + [group for group in future if group.day <= last]
        slots = sorted(set(ctx.course_days_between(course, ctx.today, last)) | set(free))
        if len(slots) < len(window):
            raise NotWorkable("Not enough free days before the next lessons.")
        plan.relay(window, slots)
    elif option == "double_up":
        _double_up(ctx, course, groups, len(overdue), plan)
    elif option == "skip":
        missed = [row for group in overdue for row in group.rows]
        keep = [row for row in missed if ctx.kind(row) not in SKIPPABLE]
        if keep:
            raise NotWorkable(f"Only review lessons are skipped, and “{keep[0].title}” isn't one.")
        for row in missed:
            plan.skip(row)
    return plan


def _course_move(ctx: _Context, request: CourseMoveRequest) -> _Plan:
    course = ctx.course(request.course_id)
    if (request.pause_from is None) != (request.pause_to is None):
        raise HTTPException(status_code=422, detail="A pause needs a first and a last day.")
    if request.pause_from and request.pause_to and request.pause_to < request.pause_from:
        raise HTTPException(status_code=422, detail="The pause ends before it starts.")
    if request.weekdays is None and request.pause_from is None:
        raise HTTPException(status_code=422, detail="Choose new days, or a pause.")
    weekdays = request.weekdays or ctx.course_weekdays(course)
    paused: set[date] = set()
    if request.pause_from and request.pause_to:
        day = request.pause_from
        while day <= request.pause_to:
            paused.add(day)
            day += timedelta(days=1)
    first = ctx.today
    if not request.weekdays and request.pause_from:
        first = max(ctx.today, request.pause_from)
    moving = [group for group in _groups(_open_rows(ctx, course.id)) if group.day >= first]
    plan = _Plan()
    plan.relay(moving, ctx.course_days(course, first, len(moving), skip=paused, weekdays=weekdays))
    name = _course_name(course)
    if request.weekdays and request.weekdays != ctx.course_weekdays(course):
        plan.course_weekdays[course.id] = weekdays
        plan.notes.append(f"{name} meets on {', '.join(LONG_DAY_NAMES[day] for day in weekdays)} from now on.")
    if request.pause_from and request.pause_to:
        plan.notes.append(f"{name} pauses from {day_label(request.pause_from)} to {day_label(request.pause_to)}.")
    return plan


def build(ctx: _Context, request: MoveRequest) -> _Plan:
    if isinstance(request, LessonMoveRequest):
        return _lesson_move(ctx, request)
    if isinstance(request, DayMoveRequest):
        return _day_move(ctx, request)
    if isinstance(request, CatchUpRequest):
        try:
            return _catch_up(ctx, ctx.course(request.course_id), request.option, request.allow_weekends)
        except NotWorkable as reason:
            raise HTTPException(status_code=409, detail=str(reason)) from reason
    return _course_move(ctx, request)


# --- The plan checker and the preview -----------------------------------------------


def _load(ctx: _Context, student_id: int, *, exclude_course: int | None = None) -> dict[date, int]:
    """Open lessons per day for one child."""
    query = (
        select(Assignment.scheduled_date, func.count())
        .where(Assignment.student_id == student_id, Assignment.status.in_(OPEN))
        .group_by(Assignment.scheduled_date)
    )
    if exclude_course is not None:
        query = query.where((Assignment.course_id.is_(None)) | (Assignment.course_id != exclude_course))
    return {day: count for day, count in ctx.db.execute(query)}


def _after(ctx: _Context, plan: _Plan, student_id: int) -> dict[date, int]:
    """A child's open lessons per day once the plan is applied."""
    load = defaultdict(int, _load(ctx, student_id))
    for row in plan.rows.values():
        if row.student_id != student_id:
            continue
        load[row.scheduled_date] -= 1
        if row.id not in plan.skips:
            load[plan.new_date(row)] += 1
    return load


def _finish(rows: list[Assignment], plan: _Plan | None) -> date | None:
    days = [plan.new_date(row) if plan else row.scheduled_date for row in rows if not plan or row.id not in plan.skips]
    return max(days) if days else None


@dataclass
class _Effects:
    preview: MovePreview
    late: bool
    peak: int


def _effects(ctx: _Context, plan: _Plan) -> _Effects:
    touched = [plan.rows[key] for key in sorted(set(plan.moves) | plan.skips)]
    names = {student.id: student.name for student in ctx.db.scalars(
        select(Student).where(Student.id.in_({row.student_id for row in touched} or {0}))
    )}
    courses = {course_id: ctx.course(course_id) for course_id in {row.course_id for row in touched if row.course_id}}
    changes = [
        LessonChange(
            assignment_id=row.id,
            title=row.title,
            student_id=row.student_id,
            student_name=names.get(row.student_id, ""),
            course_name=_course_name(courses[row.course_id]) if row.course_id else None,
            from_date=row.scheduled_date,
            to_date=None if row.id in plan.skips else plan.new_date(row),
            skipped=row.id in plan.skips,
        )
        for row in sorted(touched, key=lambda row: (row.student_id, row.scheduled_date, row.id))
    ]
    warnings: list[str] = []
    effects: list[CourseEffect] = []
    late = False
    for course in courses.values():
        rows = _open_rows(ctx, course.id)
        before, after = _finish(rows, None), _finish(rows, plan)
        moved = sum(1 for row in touched if row.course_id == course.id)
        effects.append(CourseEffect(
            course_id=course.id, course_name=_course_name(course), student_name=names.get(course.student_id, ""),
            finish_before=before, finish_after=after, lessons_moved=moved,
        ))
        if ctx.year_end and after and after > ctx.year_end:
            late = True
            warnings.append(
                f"{_course_name(course)} now finishes {day_label(after)}, after your school year ends "
                f"{day_label(ctx.year_end)}."
            )
    peak = 0
    for student_id in {row.student_id for row in touched}:
        load = _after(ctx, plan, student_id)
        landing: dict[date, int] = defaultdict(int)
        for row in touched:
            if row.student_id == student_id and row.id not in plan.skips:
                landing[plan.new_date(row)] += 1
        for day in sorted(landing):
            peak = max(peak, load[day])
            if ctx.limit is not None and load[day] > ctx.limit:
                warnings.append(
                    f"{day_label(day)} becomes {_plural(load[day], 'lesson')} for {names[student_id]} "
                    f"(your limit is {ctx.limit})."
                )
            if not ctx.school_day(student_id, day):
                warnings.append(
                    f"{_plural(landing[day], 'lesson')} {'lands' if landing[day] == 1 else 'land'} on "
                    f"{day_label(day)}, not a school day for {names[student_id]}."
                )
    for row in touched:
        if row.id not in plan.skips and ctx.kind(row) == TEST:
            warnings.append(f"{row.title} moves from {day_label(row.scheduled_date)} to {day_label(plan.new_date(row))}.")

    moved = sum(1 for change in changes if not change.skipped)
    skipped = len(changes) - moved
    if not changes and not plan.notes:
        summary = "Nothing needs to move."
    else:
        parts = []
        if moved:
            parts.append(f"{_plural(moved, 'lesson')} {'moves' if moved == 1 else 'move'}")
        if skipped:
            parts.append(f"{_plural(skipped, 'lesson')} skipped")
        summary = (", ".join(parts) or "No lessons move") + "."
    preview = MovePreview(
        summary=summary, changes=changes, courses=effects, warnings=warnings, notes=plan.notes,
        plan_hash=plan.digest(),
    )
    return _Effects(preview=preview, late=late, peak=peak)


def preview(db: Session, request: MoveRequest) -> MovePreview:
    ctx = _Context(db)
    return _effects(ctx, build(ctx, request)).preview


def apply(db: Session, request: MoveRequest, plan_hash: str) -> MoveResult:
    ctx = _Context(db)
    plan = build(ctx, request)
    effects = _effects(ctx, plan).preview
    if plan.digest() != plan_hash:
        raise HTTPException(
            status_code=409, detail="The calendar changed since this preview. Look at it again before moving anything."
        )
    for key, day in plan.moves.items():
        plan.rows[key].scheduled_date = day
    for key in plan.skips:
        plan.rows[key].status = AssignmentStatus.SKIPPED
    for row in plan.exceptions:
        db.add(row)
    for course_id, weekdays in plan.course_weekdays.items():
        ctx.course(course_id).weekdays = encode_weekdays(weekdays)
    db.flush()
    for course_id in {row.course_id for row in plan.rows.values() if row.course_id}:
        last = db.scalar(select(func.max(Assignment.scheduled_date)).where(Assignment.course_id == course_id))
        ctx.course(course_id).end_date = last
    db.commit()
    return MoveResult(moved=len(plan.moves), skipped=len(plan.skips), summary=effects.summary)


# --- Behind, and the catch-up sheet -----------------------------------------------------

CHOICES = [
    ("use_day_off", "Use a day off", "Puts the missed work on days {name} doesn't usually meet. Nothing else moves."),
    ("double_up", "Double up", "Adds the missed lessons to the coming days, one extra a day, never on a test day."),
    ("push_back", "Push everything back", "Every lesson from the missed one on slides forward, in order."),
    ("push_week", "Push back a whole week", "Starts again next Monday, and the rest follows."),
    ("skip", "Skip it", "Marks the missed review lessons skipped. Nothing moves."),
]


def behind(db: Session) -> list[BehindCourse]:
    """Courses with lessons left on days that have passed."""
    ctx = _Context(db)
    rows = db.execute(
        select(Assignment.course_id, func.count(), func.min(Assignment.scheduled_date))
        .where(Assignment.course_id.is_not(None), Assignment.status.in_(OPEN), Assignment.scheduled_date < ctx.today)
        .group_by(Assignment.course_id)
    ).all()
    found = []
    for course_id, count, since in rows:
        course = ctx.course(course_id)
        found.append(BehindCourse(
            course_id=course.id, course_name=_course_name(course), student_id=course.student_id,
            student_name=ctx.student(course.student_id).name, behind=count, behind_since=since,
        ))
    return sorted(found, key=lambda item: (item.student_name, item.behind_since, item.course_name))


def catch_up_sheet(db: Session, course_id: int, allow_weekends: bool = False) -> CatchUpSheet:
    """Every way to catch this course up, each with its result; only workable ones can be picked."""
    ctx = _Context(db)
    course = ctx.course(course_id)
    rows = _open_rows(ctx, course.id)
    overdue = [row for row in rows if row.scheduled_date < ctx.today]
    name = _course_name(course)
    choices: list[CatchUpChoice] = []
    ranked: list[tuple[tuple, CatchUpChoice]] = []
    for option, label, description in CHOICES:
        choice = CatchUpChoice(option=option, label=label, description=description.format(name=name), workable=False)
        choices.append(choice)
        if not overdue:
            choice.why_not = "Nothing to catch up."
            continue
        try:
            plan = _catch_up(ctx, course, option, allow_weekends)
        except NotWorkable as reason:
            choice.why_not = str(reason)
            continue
        effects = _effects(ctx, plan)
        choice.workable = True
        choice.preview = effects.preview
        finish = _finish(rows, plan)
        if option == "skip":
            choice.result = f"Skips {_plural(len(plan.skips), 'review lesson')}; finishes {day_label(finish)}" if finish \
                else f"Skips {_plural(len(plan.skips), 'review lesson')}"
            continue
        if finish and ctx.year_end and finish > ctx.year_end:
            choice.result = f"Finishes {day_label(finish)}, after your school year ends {day_label(ctx.year_end)}"
        elif finish:
            choice.result = f"Finishes {day_label(finish)}, on time"
        # Recommended: finishes on time, with the smallest change to any single day, then the fewest moves.
        ranked.append(((effects.late, effects.peak, len(plan.moves)), choice))
    if ranked:
        min(ranked, key=lambda pair: pair[0])[1].recommended = True
    student = ctx.student(course.student_id)
    return CatchUpSheet(
        course_id=course.id, course_name=name, student_id=student.id, student_name=student.name,
        behind=len(overdue), behind_since=min((row.scheduled_date for row in overdue), default=None),
        school_year_end=ctx.year_end, daily_lesson_limit=ctx.limit, allow_weekends=allow_weekends,
        choices=choices,
    )
