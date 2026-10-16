"""Attendance suggestions: the "School today?" card, the weekly sweep, and the counts."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.enums import AttendanceStatus


class AttendanceChildDay(BaseModel):
    """One child on one day: what's recorded, and what Curiculy suggests."""

    student_id: int
    name: str
    # The parent's mark, if there is one, and whether it confirmed a suggestion.
    status: AttendanceStatus | None = None
    source: str | None = None
    # What the day's work suggests (never recorded without the parent's tap).
    suggestion: AttendanceStatus | None = None
    reasons: list[str] = Field(default_factory=list)
    # A school day for this child, or work was done: it should be marked.
    expected: bool = False
    lessons_planned: int = 0
    lessons_done: int = 0
    activities: list[str] = Field(default_factory=list)
    # Hours mode: the parent's minutes if set, else the lessons' and activities'.
    minutes: int | None = None
    minutes_from_work: int = 0
    lessons_without_minutes: int = 0


class AttendanceDayCard(BaseModel):
    date: date
    weekday: str
    # On the family's calendar: a school weekday inside a school year, not a day off.
    school_day: bool
    # The family's day off, if it is one ("Thanksgiving").
    day_off: str | None = None
    children: list[AttendanceChildDay]


class AttendanceDays(BaseModel):
    today: date
    count_by: str
    days: list[AttendanceDayCard]


class AttendanceMark(BaseModel):
    """One child's day, as the parent marks it. ``minutes`` is only changed when sent."""

    student_id: int
    date: date
    status: AttendanceStatus
    minutes: int | None = Field(default=None, ge=1, le=1440)


class AttendanceConfirm(BaseModel):
    marks: list[AttendanceMark] = Field(min_length=1, max_length=400)


class AttendanceChildSummary(BaseModel):
    student_id: int
    name: str
    # Present and field-trip days (field trips count as present).
    present_days: int = 0
    field_trip_days: int = 0
    sick_days: int = 0
    absent_days: int = 0
    # School days before today with no mark yet.
    unmarked_days: int = 0
    # School days still ahead on the calendar, today included while it's unmarked.
    school_days_left: int = 0
    # Present days so far plus the school days left.
    on_track_days: int = 0
    # Hours mode: minutes on present days so far.
    minutes: int = 0
    lessons_without_minutes: int = 0


class AttendanceSummary(BaseModel):
    school_year_id: int | None
    school_year_name: str | None
    start_date: date | None
    end_date: date | None
    today: date
    count_by: str
    children: list[AttendanceChildSummary]
