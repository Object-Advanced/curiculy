"""A curriculum (or one book) on a child's calendar: shown by the planner and the Library."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CourseRead(BaseModel):
    id: int
    curriculum_id: int
    student_id: int
    student_name: str
    start_date: date
    end_date: date | None
    weekdays: list[int]
    lessons_scheduled: int
    default_minutes: int | None = None
