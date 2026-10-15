"""Activities: what a subject without a curriculum looks like on the record."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.reference.subjects import SUBJECTS_BY_CODE


def _link(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if not cleaned.startswith(("https://", "http://")):
        raise ValueError("Links start with https://")
    return cleaned


def _subjects(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    unknown = [code for code in value if code not in SUBJECTS_BY_CODE]
    if unknown:
        raise ValueError("Pick subjects from the list.")
    return list(dict.fromkeys(value))


def _students(value: list[int] | None) -> list[int] | None:
    return None if value is None else list(dict.fromkeys(value))


class ActivityCreate(BaseModel):
    """"5K race, PE, 40 minutes", for one child or several."""

    title: str = Field(min_length=1, max_length=255)
    on_date: date
    student_ids: list[int] = Field(min_length=1, max_length=20)
    subject_codes: list[str] = Field(default_factory=list, max_length=6)
    minutes: int | None = Field(default=None, ge=1, le=720)
    notes: str | None = Field(default=None, max_length=4000)
    link_url: str | None = Field(default=None, max_length=1024)

    _link = field_validator("link_url")(_link)
    _subjects = field_validator("subject_codes")(_subjects)
    _students = field_validator("student_ids")(_students)


class ActivityUpdate(BaseModel):
    """Only the fields sent are changed; null clears minutes, notes or the link."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    on_date: date | None = None
    student_ids: list[int] | None = Field(default=None, min_length=1, max_length=20)
    subject_codes: list[str] | None = Field(default=None, max_length=6)
    minutes: int | None = Field(default=None, ge=1, le=720)
    notes: str | None = Field(default=None, max_length=4000)
    link_url: str | None = Field(default=None, max_length=1024)

    _link = field_validator("link_url")(_link)
    _subjects = field_validator("subject_codes")(_subjects)
    _students = field_validator("student_ids")(_students)


class ActivityChild(BaseModel):
    student_id: int
    name: str


class ActivitySubject(BaseModel):
    code: str
    name: str


class ActivityEvidenceRead(BaseModel):
    id: int
    file_path: str
    captured_at: datetime


class ActivityRead(BaseModel):
    id: int
    title: str
    on_date: date
    minutes: int | None
    notes: str | None
    link_url: str | None
    subjects: list[ActivitySubject]
    students: list[ActivityChild]
    evidence: list[ActivityEvidenceRead]
