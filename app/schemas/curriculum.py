"""Curriculum import payloads and structure read models.

JSON and CSV describe a program with the same vocabulary — ``curriculum_name``,
``edition``, ``unit_title`` — so a spreadsheet typed by hand and a generated
document are interchangeable.

Page numbers are plain integers rather than constrained fields on purpose. The
importer validates them for both formats, which lets a bad range be reported as
"row 12: end_page 4 precedes start_page 40" instead of as a schema path that
means nothing to someone looking at a spreadsheet.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.enums import MappingSource, ResourceKind, UnitKind
from app.schemas.catalog import BookEditionRead
from app.schemas.core import ORMModel

DEFAULT_EDITION_LABEL = "1st edition"


class ImportResource(BaseModel):
    """A book or component the units are paged against."""

    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(
        default=None,
        description="Name units use to reference this resource; the ISBN, title, "
        "or kind also work.",
    )
    kind: ResourceKind = ResourceKind.STUDENT_TEXT
    title: str | None = None
    isbn13: str | None = Field(
        default=None,
        description="Links the resource to an already resolved book. Unknown ISBNs "
        "are reported as warnings rather than failing the import.",
    )
    is_required: bool = True
    is_consumable: bool = False
    sort_order: int | None = None
    notes: str | None = None


class ImportUnit(BaseModel):
    """One teachable node, with the page range it occupies in a resource."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    kind: UnitKind = UnitKind.LESSON
    label: str | None = Field(default=None, max_length=64)
    sequence: int | None = Field(
        default=None,
        description="Order among siblings; defaults to the order given.",
    )
    estimated_minutes: int | None = None
    estimated_sessions: int | None = None
    is_optional: bool = False
    notes: str | None = None
    resource: str | None = Field(
        default=None,
        description="Which resource the pages refer to. Optional when the import "
        "declares exactly one resource.",
    )
    page_start: int | None = None
    page_end: int | None = Field(
        default=None,
        description="Defaults to page_start, so a single-page lesson needs one number.",
    )
    printed_page_start: str | None = None
    printed_page_end: str | None = None
    source_ref: str | None = Field(
        default=None,
        description="Where this unit came from, such as a CSV row number. Used only "
        "to make error messages locatable.",
    )
    children: list["ImportUnit"] = Field(default_factory=list)


class CurriculumImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_name: str = Field(min_length=1, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=128)
    description: str | None = None
    edition: str = Field(default=DEFAULT_EDITION_LABEL, min_length=1, max_length=128)
    copyright_year: int | None = None
    grade_level: str | None = Field(default=None, max_length=64)
    is_current: bool = True
    resources: list[ImportResource] = Field(default_factory=list)
    units: list[ImportUnit] = Field(default_factory=list)


class ImportSummary(BaseModel):
    """What the import changed.

    Created and updated counts are reported separately so re-running a corrected
    file shows as updates rather than looking like a duplicate import.
    """

    curriculum_id: int
    curriculum_title: str
    curriculum_edition_id: int
    edition_label: str
    curriculum_created: bool
    edition_created: bool
    resources_created: int
    units_created: int
    units_updated: int
    page_mappings_created: int
    page_mappings_updated: int
    errors: list[str] = Field(default_factory=list)


class PageMappingRead(ORMModel):
    id: int
    curriculum_resource_id: int
    resource_title: str
    page_start: int
    page_end: int
    page_count: int
    printed_page_start: str | None
    printed_page_end: str | None
    is_primary: bool
    source: MappingSource
    confidence: float | None


class CurriculumUnitNode(ORMModel):
    id: int
    parent_id: int | None
    kind: UnitKind
    label: str | None
    title: str
    sort_order: int
    depth: int
    estimated_minutes: int | None
    estimated_sessions: int | None
    is_optional: bool
    notes: str | None
    page_mappings: list[PageMappingRead] = Field(default_factory=list)
    children: list["CurriculumUnitNode"] = Field(default_factory=list)


class CurriculumTreeRead(BaseModel):
    curriculum_id: int
    curriculum_title: str
    curriculum_edition_id: int
    edition_label: str
    units: list[CurriculumUnitNode]


class CurriculumResourceRead(ORMModel):
    id: int
    curriculum_edition_id: int
    kind: ResourceKind
    title: str
    is_required: bool
    is_consumable: bool
    sort_order: int
    notes: str | None
    book_edition: BookEditionRead | None


class CurriculumResourcesRead(BaseModel):
    curriculum_id: int
    curriculum_title: str
    curriculum_edition_id: int
    edition_label: str
    resources: list[CurriculumResourceRead]


ImportUnit.model_rebuild()
CurriculumUnitNode.model_rebuild()
