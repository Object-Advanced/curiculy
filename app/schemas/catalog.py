"""Read models for the book catalog.

An edition is returned with its work, contributors, and publisher inlined: a
barcode scan is a single user gesture, so the client should not have to follow
three more links to render what was scanned.
"""

from pydantic import BaseModel, Field

from app.enums import BookFormat, ContributorRole, CurriculumSource
from app.schemas.core import ORMModel


class PublisherRead(ORMModel):
    id: int
    name: str
    website: str | None = None


class WorkAuthorRead(ORMModel):
    author_id: int
    author_name: str
    role: ContributorRole
    sort_order: int


class WorkRead(ORMModel):
    id: int
    title: str
    subtitle: str | None
    subject: str | None
    language: str | None
    description: str | None
    publisher: PublisherRead | None
    authors: list[WorkAuthorRead]


class BookEditionRead(ORMModel):
    id: int
    work_id: int
    publisher_id: int | None
    edition_label: str | None
    isbn10: str | None
    isbn13: str | None
    barcode: str | None
    publication_year: int | None
    printing: str | None
    book_format: BookFormat
    page_count: int | None
    page_offset: int | None
    cover_image_path: str | None
    work: WorkRead
    publisher: PublisherRead | None


class BookResolveRequest(BaseModel):
    """A scanned barcode or a typed ISBN, in any punctuation."""

    isbn: str = Field(min_length=1, max_length=64)


class ISBNLookupRequest(BookResolveRequest):
    """Same identifier the scanner posts; named for the catalog form."""


class ISBNLookupRead(BaseModel):
    """The fields the Add curriculum form fills after an ISBN lookup."""

    isbn13: str
    isbn10: str | None = None
    barcode: str | None = None
    title: str
    subtitle: str | None = None
    publisher: str | None = None
    description: str | None = None
    page_count: int | None = None
    publication_year: int | None = None
    authors: list[str] = Field(default_factory=list)


class CurriculumFromISBNRequest(BaseModel):
    """Create a curriculum edition linked to the book this ISBN identifies."""

    isbn: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    subject: str | None = None
    description: str | None = None


class CurriculumFromISBNRead(ORMModel):
    id: int
    title: str
    publisher_id: int | None
    publisher_name: str | None
    subject: str | None
    description: str | None
    source_type: CurriculumSource
    curriculum_edition_id: int
    edition_label: str
    book_edition: BookEditionRead
