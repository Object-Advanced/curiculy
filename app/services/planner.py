"""The Curriculum planner: build a subject's curriculum, then schedule it.

A curriculum is built around a **textbook**: its lesson list sets the pace,
one lesson each course day. Alongside it:

- **workbooks**: their pages spread over the same days, a chapter at a time,
  never the answer key
- **online sites**: sessions on their own number of days a week
- **books to read**: read one after another across the course, each over a
  share of the days in proportion to its length
- **for the parent** (a teacher's edition or answer key): kept with the
  curriculum, never put on a child's calendar

Scheduling makes a ``Course`` per child and its dated lessons, skipping the
family's days off and the child's own. Nothing is written until the parent
has seen the preview.

A fully built curriculum is contributed to the community catalog (no toggle),
so the next family with the same textbook can start from it. See
docs/6-planning/product-spine.md.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.enums import AssignmentStatus
from app.models import (
    Assignment,
    CalendarException,
    CommunityCurriculum,
    Course,
    LibraryItem,
    PlannedCurriculum,
    PlannedCurriculumItem,
    Student,
)
from app.reference.subjects import subject_name
from app.schemas.library import MissingRead, ProblemRead
from app.schemas.planner import (
    ROLE_HINTS,
    ROLES,
    CourseRead,
    PlannedCurriculumCreate,
    CurriculumItemRead,
    PlannedCurriculumRead,
    CurriculumReadiness,
    PlannedCurriculumUpdate,
    ScheduledItemPreview,
    SchedulePreview,
    ScheduleRequest,
    ScheduleResult,
    StudentPreview,
)
from app.services import community
from app.services.library import get_item, item_summary
from app.services.library_rules import ONLINE_PROGRAM, READING_BOOK, TEXTBOOK, WORKBOOK, readiness
from app.services.school_year import (
    encode_weekdays,
    ensure_operational_school_year,
    exception_dates_for_household,
    load_school_year_settings,
    parse_weekdays,
)

# Which kinds of library item can fill each role.
ROLE_KINDS = {
    "textbook": {TEXTBOOK},
    "workbook": {WORKBOOK},
    "online": {ONLINE_PROGRAM},
    "reading": {READING_BOOK},
    "teacher": {TEXTBOOK, WORKBOOK, READING_BOOK},
}
ROLE_ORDER = {"textbook": 0, "workbook": 1, "online": 2, "reading": 3, "teacher": 4}
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
CALENDAR_URL = "/#/assignments"


# --- Reading and building curricula -------------------------------------------

def _options():
    return (
        selectinload(PlannedCurriculum.items)
        .selectinload(PlannedCurriculumItem.library_item)
        .selectinload(LibraryItem.lessons),
        selectinload(PlannedCurriculum.items)
        .selectinload(PlannedCurriculumItem.library_item)
        .selectinload(LibraryItem.chapters),
        selectinload(PlannedCurriculum.courses),
    )


def get_curriculum(db: Session, curriculum_id: int) -> PlannedCurriculum:
    curriculum = db.scalars(
        select(PlannedCurriculum).where(PlannedCurriculum.id == curriculum_id).options(*_options())
    ).first()
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return curriculum


def list_curricula(db: Session) -> list[PlannedCurriculum]:
    return list(db.scalars(select(PlannedCurriculum).options(*_options()).order_by(PlannedCurriculum.name)))


def curricula_using(db: Session, library_item_id: int) -> list[int]:
    return sorted(set(db.scalars(
        select(PlannedCurriculumItem.curriculum_id).where(PlannedCurriculumItem.library_item_id == library_item_id)
    )))


def textbook_of(curriculum: PlannedCurriculum) -> LibraryItem | None:
    return next((link.library_item for link in curriculum.items if link.role == "textbook"), None)


def curriculum_readiness(curriculum: PlannedCurriculum) -> CurriculumReadiness:
    missing: list[MissingRead] = []
    problems: list[ProblemRead] = []
    if not curriculum.subject_code:
        missing.append(MissingRead(
            field="subject_code", label="Subject",
            reason="The subject connects this curriculum to your child's subjects and your state's requirements.",
        ))
    textbook = textbook_of(curriculum)
    if textbook is None:
        missing.append(MissingRead(
            field="textbook", label="A textbook",
            reason="A curriculum is built around a textbook: its lessons set the pace, one lesson each school day.",
        ))
    for link in curriculum.items:
        item = link.library_item
        result = readiness(item)
        if link.role != "teacher" and not result.ready:
            first = result.missing[0].label if result.missing else result.problems[0].message
            problems.append(ProblemRead(
                level="fix", where=item.title,
                message=f"Not ready to schedule yet ({first}). Finish it in your Library.",
            ))
    return CurriculumReadiness(ready=not missing and not problems, missing=missing, problems=problems)


def _course_read(db: Session, course: Course) -> CourseRead:
    student = db.get(Student, course.student_id)
    lessons = db.scalar(select(func.count()).select_from(Assignment).where(Assignment.course_id == course.id))
    return CourseRead(
        id=course.id,
        curriculum_id=course.curriculum_id,
        student_id=course.student_id,
        student_name=student.name if student else "",
        start_date=course.start_date,
        end_date=course.end_date,
        weekdays=parse_weekdays(course.weekdays),
        lessons_scheduled=lessons or 0,
    )


def curriculum_read(db: Session, curriculum: PlannedCurriculum) -> PlannedCurriculumRead:
    links = sorted(curriculum.items, key=lambda link: (ROLE_ORDER.get(link.role, 9), link.position, link.id))
    return PlannedCurriculumRead(
        id=curriculum.id,
        name=curriculum.name,
        subject_code=curriculum.subject_code,
        subject_name=subject_name(curriculum.subject_code),
        grade=curriculum.grade,
        days_per_week=curriculum.days_per_week,
        notes=curriculum.notes,
        items=[
            CurriculumItemRead(
                id=link.id, library_item_id=link.library_item_id, role=link.role,
                role_label=ROLES[link.role], role_hint=ROLE_HINTS[link.role], item=item_summary(link.library_item),
            )
            for link in links
        ],
        readiness=curriculum_readiness(curriculum),
        courses=[_course_read(db, course) for course in sorted(curriculum.courses, key=lambda c: c.id)],
        community_curriculum_id=curriculum.community_curriculum_id,
    )


def _check_role(curriculum: PlannedCurriculum, item: LibraryItem, role: str) -> None:
    if item.kind not in ROLE_KINDS[role]:
        raise HTTPException(
            status_code=409,
            detail=f"{item.title} can't be the {ROLES[role].lower()}: it's a {item.kind.replace('_', ' ')}.",
        )
    if role == "textbook":
        if item.for_parent:
            raise HTTPException(status_code=409, detail="A teacher's edition is for you; add it as “For the parent”.")
        current = textbook_of(curriculum)
        if current is not None and current.id != item.id:
            raise HTTPException(
                status_code=409, detail=f"This curriculum's textbook is already {current.title}. Remove it first."
            )
    if any(link.library_item_id == item.id for link in curriculum.items):
        raise HTTPException(status_code=409, detail=f"{item.title} is already part of this curriculum.")


def add_item(db: Session, curriculum: PlannedCurriculum, item: LibraryItem, role: str) -> None:
    _check_role(curriculum, item, role)
    curriculum.items.append(
        PlannedCurriculumItem(library_item_id=item.id, role=role, position=len(curriculum.items))
    )
    db.flush()
    if role == "textbook":
        curriculum.subject_code = curriculum.subject_code or item.subject_code
        curriculum.grade = curriculum.grade or item.grade
        curriculum.days_per_week = curriculum.days_per_week or item.days_per_week


def remove_item(curriculum: PlannedCurriculum, library_item_id: int) -> None:
    link = next((link for link in curriculum.items if link.library_item_id == library_item_id), None)
    if link is None:
        raise HTTPException(status_code=404, detail="That isn't part of this curriculum")
    curriculum.items.remove(link)


def create_curriculum(db: Session, payload: PlannedCurriculumCreate) -> PlannedCurriculum:
    textbook = get_item(db, payload.textbook_id) if payload.textbook_id else None
    name = payload.name or (textbook.title if textbook else None)
    if not name:
        raise HTTPException(status_code=422, detail="Give the curriculum a name, or start from a textbook.")
    curriculum = PlannedCurriculum(
        name=name,
        subject_code=payload.subject_code,
        grade=payload.grade,
        days_per_week=payload.days_per_week,
        notes=payload.notes,
    )
    db.add(curriculum)
    db.flush()
    if textbook is not None:
        add_item(db, curriculum, textbook, "textbook")
    db.commit()
    return get_curriculum(db, curriculum.id)


def update_curriculum(db: Session, curriculum: PlannedCurriculum, payload: PlannedCurriculumUpdate) -> None:
    for name, value in payload.model_dump(exclude_unset=True).items():
        if name == "name" and not value:
            continue
        setattr(curriculum, name, value)
    db.commit()


def delete_curriculum(db: Session, curriculum: PlannedCurriculum) -> None:
    if curriculum.courses:
        names = ", ".join(sorted({_course_read(db, course).student_name for course in curriculum.courses}))
        raise HTTPException(
            status_code=409,
            detail=f"It's scheduled for {names}. Unschedule it first (finished lessons stay on the calendar).",
        )
    db.delete(curriculum)
    db.commit()


# --- Contributing to the community catalog ------------------------------------

def refresh_contribution(db: Session, catalog_db: Session, curriculum_id: int, family: str | None) -> None:
    """Contribute (or refresh, or withdraw) the curriculum, never breaking the family's save."""
    curriculum = db.get(PlannedCurriculum, curriculum_id)
    if curriculum is None:
        community.safely(catalog_db, community.curriculum_removed, catalog_db, curriculum_id, family)
        return
    curriculum = get_curriculum(db, curriculum_id)
    ready = curriculum_readiness(curriculum).ready
    community.safely(catalog_db, community.curriculum_changed, db, catalog_db, curriculum, family, ready)


def refresh_contributions_for_item(db: Session, catalog_db: Session, library_item_id: int, family: str | None) -> None:
    for curriculum_id in curricula_using(db, library_item_id):
        refresh_contribution(db, catalog_db, curriculum_id, family)


def from_community(
    db: Session,
    catalog_db: Session,
    community_curriculum_id: int,
    entry_ids: list[int] | None,
    name: str | None,
    *,
    counted: bool = True,
) -> PlannedCurriculum:
    """Start from a curriculum other families built: its books are added to the
    library (or the family's copies reused), and the parent can change anything."""
    source = catalog_db.get(CommunityCurriculum, community_curriculum_id)
    if source is None or source.status != "published":
        raise HTTPException(status_code=404, detail="That suggestion isn't available")
    keep = set(entry_ids) if entry_ids is not None else None
    if keep is not None and source.textbook_entry_id not in keep:
        keep.add(source.textbook_entry_id)  # the textbook is what the curriculum is built around

    curriculum = PlannedCurriculum(
        name=name or source.name,
        subject_code=source.subject_code,
        grade=source.grade,
        days_per_week=source.days_per_week,
        community_curriculum_id=source.id,
    )
    db.add(curriculum)
    db.flush()
    for position, link in enumerate(source.items):
        if keep is not None and link.entry_id not in keep:
            continue
        entry = community.get_published_entry(catalog_db, link.entry_id)
        item, _ = community.adopt_entry(db, catalog_db, entry, counted=counted)
        curriculum.items.append(PlannedCurriculumItem(library_item_id=item.id, role=link.role, position=position))
    if keep is None and counted:
        source.families_count += 1
        catalog_db.commit()
    db.commit()
    return get_curriculum(db, curriculum.id)


# --- Scheduling -----------------------------------------------------------------

@dataclass
class Planned:
    """One dated lesson, before it's written."""

    day: date
    title: str
    item: LibraryItem
    role: str
    library_lesson_id: int | None = None


def _course_weekdays(curriculum: PlannedCurriculum, school_weekdays: list[int], requested: list[int] | None) -> list[int]:
    if requested:
        return requested
    days = sorted(school_weekdays) or [0, 1, 2, 3, 4]
    if curriculum.days_per_week and curriculum.days_per_week < len(days):
        # A 4-day program on a 5-day week leaves the last day free (a flex day).
        days = days[: curriculum.days_per_week]
    return days


def _days_off(db: Session, student_id: int) -> set[date]:
    off = set(exception_dates_for_household(db))
    for row in db.scalars(select(CalendarException).where(CalendarException.student_id == student_id)):
        day = row.start_date
        while day <= row.end_date:
            off.add(day)
            day += timedelta(days=1)
    return off


def course_days(start: date, weekdays: list[int], off: set[date], count: int) -> list[date]:
    days: list[date] = []
    day = start
    limit = start + timedelta(days=366 * 3)
    while len(days) < count and day <= limit:
        if day.weekday() in weekdays and day not in off:
            days.append(day)
        day += timedelta(days=1)
    return days


def _split(total: int, parts: int) -> list[int]:
    """Split ``total`` into ``parts`` near-equal whole numbers (bigger ones first)."""
    if parts <= 0:
        return []
    base, extra = divmod(total, parts)
    return [base + (1 if index < extra else 0) for index in range(parts)]


def _apportion(sizes: list[int], slots: int) -> list[int]:
    """Give each part a share of ``slots`` in proportion to its size, at least one each."""
    if not sizes:
        return []
    total = sum(sizes) or len(sizes)
    raw = [slots * (size or 1) / total for size in sizes]
    shares = [max(1, int(value)) for value in raw]
    while sum(shares) < slots:
        index = max(range(len(sizes)), key=lambda i: raw[i] - shares[i])
        shares[index] += 1
    while sum(shares) > slots and any(share > 1 for share in shares):
        index = max((i for i in range(len(shares)) if shares[i] > 1), key=lambda i: shares[i] - raw[i])
        shares[index] -= 1
    return shares


def _page_sections(item: LibraryItem) -> list[tuple[str | None, int, int]]:
    """The pages to schedule, split at chapter starts: (chapter name, first, last).
    Front matter before the first chapter and the answer key are left out."""
    last = item.total_pages or 0
    if item.answer_key_start_page:
        last = min(last, item.answer_key_start_page - 1)
    chapters = [chapter for chapter in item.chapters if chapter.start_page <= last]
    if not chapters:
        return [(None, 1, last)] if last >= 1 else []
    sections = []
    for index, chapter in enumerate(chapters):
        end = chapters[index + 1].start_page - 1 if index + 1 < len(chapters) else last
        if end >= chapter.start_page:
            sections.append((chapter.name, chapter.start_page, end))
    return sections


def _pages(first: int, last: int) -> str:
    return f"p. {first}" if first == last else f"pp. {first}–{last}"


def page_plan(item: LibraryItem, days: list[date]) -> list[tuple[date, int, int, str | None]]:
    """Spread an item's pages over ``days``, keeping each day inside one chapter
    when there are enough days (otherwise whole chapters share a day)."""
    sections = _page_sections(item)
    if not sections or not days:
        return []
    plan: list[tuple[date, int, int, str | None]] = []
    if len(sections) > len(days):
        first, last = sections[0][1], sections[-1][2]
        cursor = first
        for day, count in zip(days, _split(last - first + 1, len(days))):
            if count:
                plan.append((day, cursor, cursor + count - 1, None))
                cursor += count
        return plan
    shares = _apportion([end - start + 1 for _, start, end in sections], len(days))
    day_index = 0
    for (name, start, end), share in zip(sections, shares):
        cursor = start
        for count in _split(end - start + 1, share):
            day = days[day_index]
            day_index += 1
            if count:
                plan.append((day, cursor, cursor + count - 1, name))
                cursor += count
    return plan


def _sessions(days: list[date], per_week: int) -> list[date]:
    """The first ``per_week`` course days of each week."""
    weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
    for day in days:
        weeks[day.isocalendar()[:2]].append(day)
    chosen: list[date] = []
    for week in sorted(weeks):
        chosen.extend(weeks[week][:per_week])
    return chosen


def _lesson_title(item: LibraryItem, lesson) -> str:
    label = {"test": "Test", "quiz": "Quiz", "review": "Review", "project": "Project"}.get(lesson.type, "Lesson")
    title = f"{item.title} · {label} {lesson.number}" if lesson.number is not None else f"{item.title} · {label}"
    if lesson.name:
        title += f": {lesson.name}"
    if lesson.start_page and lesson.end_page:
        title += f" ({_pages(lesson.start_page, lesson.end_page)})"
    return title[:255]


def plan_lessons(curriculum: PlannedCurriculum, days: list[date]) -> list[Planned]:
    """Every dated lesson for one child, given the course days (one per textbook lesson)."""
    planned: list[Planned] = []
    textbook = textbook_of(curriculum)
    if textbook is None:
        return planned
    for day, lesson in zip(days, textbook.lessons):
        planned.append(Planned(day, _lesson_title(textbook, lesson), textbook, "textbook", lesson.id))

    readers = [link.library_item for link in curriculum.items if link.role == "reading"]
    for link in curriculum.items:
        item = link.library_item
        if link.role == "workbook":
            for day, first, last, chapter in page_plan(item, days):
                where = f" ({chapter})" if chapter else ""
                planned.append(Planned(day, f"{item.title} · {_pages(first, last)}{where}"[:255], item, "workbook"))
        elif link.role == "online":
            sessions = _sessions(days, item.days_per_week or len(days))
            if item.measure == "lessons" and item.lesson_count:
                number = 1
                for day, count in zip(sessions, _split(item.lesson_count, len(sessions))):
                    if not count:
                        continue
                    label = f"Lesson {number}" if count == 1 else f"Lessons {number}–{number + count - 1}"
                    planned.append(Planned(day, f"{item.title} · {label}"[:255], item, "online"))
                    number += count
            else:
                minutes = item.minutes_per_session or 0
                for day in sessions:
                    planned.append(Planned(day, f"{item.title} · {minutes} minutes"[:255], item, "online"))

    if readers:
        # Books are read one after another, each over a share of the days.
        shares = _apportion([book.total_pages or 1 for book in readers], len(days)) if len(readers) <= len(days) else []
        start = 0
        for book, share in zip(readers, shares):
            for day, first, last, chapter in page_plan(book, days[start : start + share]):
                where = f" ({chapter})" if chapter else ""
                planned.append(Planned(day, f"Read {book.title}, {_pages(first, last)}{where}"[:255], book, "reading"))
            start += share
    return planned


def _summary(role: str, item: LibraryItem, rows: list[Planned]) -> str:
    if role == "textbook":
        return f"{len(rows)} lessons, one each school day"
    if role == "online":
        per_week = item.days_per_week or 0
        return f"{len(rows)} sessions, {per_week} days a week"
    return f"{item.total_pages or 0} pages over {len(rows)} days"


def preview(db: Session, curriculum: PlannedCurriculum, request: ScheduleRequest) -> SchedulePreview:
    status = curriculum_readiness(curriculum)
    if not status.ready:
        raise HTTPException(status_code=409, detail="Finish the curriculum first: " + "; ".join(
            [m.label for m in status.missing] + [p.message for p in status.problems]
        ))
    _, year_end, school_weekdays, _ = load_school_year_settings(db)
    weekdays = _course_weekdays(curriculum, school_weekdays, request.weekdays)
    textbook = textbook_of(curriculum)
    warnings: list[str] = []
    students: list[StudentPreview] = []
    for student_id in request.student_ids:
        student = db.get(Student, student_id)
        if student is None:
            raise HTTPException(status_code=404, detail="Child not found")
        if any(course.student_id == student_id for course in curriculum.courses):
            warnings.append(f"{student.name} already has this curriculum on the calendar. Unschedule it first.")
        days = course_days(request.start_date, weekdays, _days_off(db, student_id), len(textbook.lessons))
        rows = plan_lessons(curriculum, days)
        by_item: dict[int, list[Planned]] = defaultdict(list)
        for row in rows:
            by_item[row.item.id].append(row)
        items = []
        for link in sorted(curriculum.items, key=lambda link: (ROLE_ORDER.get(link.role, 9), link.position)):
            if link.role == "teacher":
                continue
            planned = by_item.get(link.library_item_id, [])
            items.append(ScheduledItemPreview(
                library_item_id=link.library_item_id,
                title=link.library_item.title,
                role=link.role,
                summary=_summary(link.role, link.library_item, planned),
                count=len(planned),
                first_date=min((row.day for row in planned), default=None),
                last_date=max((row.day for row in planned), default=None),
            ))
        finish = days[-1] if days else None
        if finish and year_end and finish > year_end:
            warnings.append(
                f"{student.name} would finish {finish:%B %-d}, after your school year ends {year_end:%B %-d}. "
                "Start sooner, add a school day each week, or extend the year."
            )
        students.append(StudentPreview(
            student_id=student.id, student_name=student.name, finish_date=finish, lessons=len(rows), items=items,
        ))
    return SchedulePreview(
        start_date=request.start_date,
        weekdays=weekdays,
        weekday_names=[DAY_NAMES[day] for day in weekdays],
        school_year_end=year_end,
        students=students,
        warnings=warnings,
    )


def schedule(db: Session, curriculum: PlannedCurriculum, request: ScheduleRequest) -> ScheduleResult:
    plan = preview(db, curriculum, request)
    already = [course.student_id for course in curriculum.courses]
    if any(student_id in already for student_id in request.student_ids):
        raise HTTPException(status_code=409, detail="Already on the calendar for that child. Unschedule it first.")
    year = ensure_operational_school_year(db)
    weekdays = plan.weekdays
    textbook = textbook_of(curriculum)
    created = 0
    courses: list[Course] = []
    for student_id in request.student_ids:
        days = course_days(request.start_date, weekdays, _days_off(db, student_id), len(textbook.lessons))
        course = Course(
            curriculum_id=curriculum.id,
            student_id=student_id,
            school_year_id=year.id if year else None,
            start_date=request.start_date,
            end_date=days[-1] if days else None,
            weekdays=encode_weekdays(weekdays),
        )
        db.add(course)
        db.flush()
        for row in plan_lessons(curriculum, days):
            db.add(Assignment(
                student_id=student_id,
                title=row.title,
                scheduled_date=row.day,
                status=AssignmentStatus.ASSIGNED,
                course_id=course.id,
                library_item_id=row.item.id,
                library_lesson_id=row.library_lesson_id,
            ))
            created += 1
        courses.append(course)
    db.commit()
    return ScheduleResult(
        courses=[_course_read(db, course) for course in courses],
        lessons_created=created,
        calendar_url=f"{CALENDAR_URL}?from=planner&date={request.start_date.isoformat()}",
    )


def get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def unschedule(db: Session, course: Course) -> tuple[int, int]:
    """Take a course off the calendar. Finished lessons stay where they were done."""
    lessons = list(db.scalars(select(Assignment).where(Assignment.course_id == course.id)))
    finished = [lesson for lesson in lessons if lesson.status == AssignmentStatus.COMPLETED]
    for lesson in lessons:
        if lesson.status != AssignmentStatus.COMPLETED:
            db.delete(lesson)
    db.delete(course)
    db.commit()
    return len(lessons) - len(finished), len(finished)

