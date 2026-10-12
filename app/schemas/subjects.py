"""Reference lists, state subject requirements, and each child's subjects."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from app.reference.subjects import SUBJECTS_BY_CODE


class StateOption(BaseModel):
    code: str
    name: str


class GradeOption(BaseModel):
    code: str
    label: str


class SubjectOption(BaseModel):
    code: str
    name: str
    group: str
    covers: str = ""


class ReferenceRead(BaseModel):
    """The fixed lists every screen picks from."""

    states: list[StateOption]
    grades: list[GradeOption]
    subjects: list[SubjectOption]


class RequiredSubject(BaseModel):
    code: str
    name: str
    state_label: str
    every_year: bool = False


class StateSubjectsRead(BaseModel):
    """What a state requires for a grade. ``supported`` is False until a state's rules are reviewed."""

    state_code: str
    state_name: str
    grade: str | None
    supported: bool
    band: str | None = None
    rule: str | None = None
    subjects: list[RequiredSubject] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class StudentSubjectRead(BaseModel):
    id: int
    subject_code: str | None
    name: str
    kind: str  # required, common, own
    counts_toward: str | None
    counts_toward_name: str | None
    active: bool
    objective: str | None
    # Taught in an earlier school year (shown as checked when setting up a new year).
    covered_before: bool = False
    # The state expects it every year (Pennsylvania: fire safety).
    every_year: bool = False
    state_label: str | None = None
    warning: str | None = None


class StudentSubjectsRead(BaseModel):
    student_id: int
    school_year_id: int
    state_code: str | None
    supported: bool
    band: str | None = None
    rule: str | None = None
    subjects: list[StudentSubjectRead]


def _check_code(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip()
    if code not in SUBJECTS_BY_CODE:
        raise ValueError("Pick a subject from the list.")
    return code


class StudentSubjectCreate(BaseModel):
    """Add a listed subject (``subject_code``) or the family's own (``name``, counting toward one or none)."""

    school_year_id: int | None = None
    subject_code: str | None = None
    name: str | None = Field(default=None, max_length=128)
    counts_toward: str | None = None

    _code = field_validator("subject_code", "counts_toward")(_check_code)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def _one_of(self) -> StudentSubjectCreate:
        if (self.subject_code is None) == (self.name is None):
            raise ValueError("Give either a subject from the list or your own subject's name.")
        return self


class StudentSubjectUpdate(BaseModel):
    active: bool | None = None
    objective: str | None = Field(default=None, max_length=500)
    # Own subjects only:
    name: str | None = Field(default=None, min_length=1, max_length=128)
    counts_toward: str | None = None
    clear_counts_toward: bool = False

    _code = field_validator("counts_toward")(_check_code)
