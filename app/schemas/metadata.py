"""Normalized bibliographic metadata.

Every external provider returns a different shape, so each one maps its payload
onto :class:`BookMetadataResult`. Downstream code (barcode scan, catalog import,
future AI parsing) only ever sees this model, which mirrors the fields on
``Work`` / ``BookEdition`` so persisting a result is a direct field copy.
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import ContributorRole, MetadataSource
from app.utils.isbn import to_isbn10, to_isbn13

_YEAR = re.compile(r"(\d{4})")


class AuthorCredit(BaseModel):
    """A contributor plus the role they played, matching ``WorkAuthor.role``."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=255)
    role: ContributorRole = ContributorRole.AUTHOR


class BookMetadataResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    isbn10: str | None = None
    isbn13: str | None = None
    title: str = Field(min_length=1)
    subtitle: str | None = None
    authors: list[AuthorCredit] = Field(default_factory=list)
    publisher: str | None = None
    # Providers report anything from "2004" to "2004-05-17"; the raw precision is
    # preserved here rather than fabricating a full date.
    publication_date: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    description: str | None = None
    cover_url: str | None = None
    source: MetadataSource
    raw_payload: dict[str, Any] | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _canonicalize_isbns(self) -> "BookMetadataResult":
        """Drop unparseable identifiers and fill in whichever form is missing."""
        isbn13 = to_isbn13(self.isbn13) or to_isbn13(self.isbn10)
        isbn10 = to_isbn10(self.isbn10) or to_isbn10(isbn13)
        self.isbn13 = isbn13
        self.isbn10 = isbn10
        return self

    @property
    def publication_year(self) -> int | None:
        """The year alone, which is what ``BookEdition.publication_year`` stores."""
        if not self.publication_date:
            return None
        match = _YEAR.search(self.publication_date)
        return int(match.group(1)) if match else None

    @property
    def author_names(self) -> list[str]:
        return [credit.name for credit in self.authors]
