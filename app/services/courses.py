"""Courses as the planner and the Library show them."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Assignment, Course, PlannedCurriculum, PlannedCurriculumItem, Student
from app.schemas.courses import CourseRead
from app.services.school_year import parse_weekdays


def course_read(db: Session, course: Course) -> CourseRead:
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
        default_minutes=course.default_minutes,
    )


def solo_curriculum_id(db: Session, library_item_id: int) -> int | None:
    """The one-item curriculum the Library's "Schedule" made for this item, if any."""
    return db.scalars(
        select(PlannedCurriculum.id)
        .join(PlannedCurriculumItem, PlannedCurriculumItem.curriculum_id == PlannedCurriculum.id)
        .where(PlannedCurriculum.solo.is_(True), PlannedCurriculumItem.library_item_id == library_item_id)
    ).first()


def solo_courses(db: Session, library_item_id: int) -> list[CourseRead]:
    """Where an item is on the calendar on its own."""
    curriculum_id = solo_curriculum_id(db, library_item_id)
    if curriculum_id is None:
        return []
    courses = db.scalars(select(Course).where(Course.curriculum_id == curriculum_id).order_by(Course.id))
    return [course_read(db, course) for course in courses]
