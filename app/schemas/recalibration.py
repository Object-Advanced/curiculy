"""Payloads for the Life Happens recalibration endpoints."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RecalibrateExecuteRequest(BaseModel):
    strategy: Literal["extend_year", "add_weekends"]
    options: dict[str, Any] = Field(default_factory=dict)


class RecalibrateStrategyRead(BaseModel):
    required_days: int
    new_end_date: str | None = None
    assignments_moved: int = 0
    saturdays_used: int = 0


class RecalibrateOptionsRead(BaseModel):
    student_id: int
    overdue_count: int
    overdue_school_days: int
    uncompleted_count: int
    uncompleted_school_days: int
    original_end_date: str | None = None
    target_days: list[int]
    required_days: dict[str, int]
    strategies: dict[str, RecalibrateStrategyRead]


class RecalibrateExecuteRead(BaseModel):
    student_id: int
    strategy: str
    assignments_moved: int
    first_scheduled_date: str | None = None
    last_scheduled_date: str | None = None
    original_end_date: str | None = None
