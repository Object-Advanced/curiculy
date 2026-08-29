"""Tests for the normalized BookMetadataResult contract."""

import pytest
from pydantic import ValidationError

from app.enums import ContributorRole, MetadataSource
from app.schemas.metadata import AuthorCredit, BookMetadataResult

ISBN10 = "0306406152"
ISBN13 = "9780306406157"


def build(**overrides) -> BookMetadataResult:
    payload = {"title": "Saxon Math 3", "source": MetadataSource.MANUAL} | overrides
    return BookMetadataResult(**payload)


class TestIdentifierNormalization:
    def test_isbn13_is_derived_from_isbn10(self) -> None:
        result = build(isbn10=ISBN10)
        assert result.isbn13 == ISBN13

    def test_isbn10_is_derived_from_isbn13(self) -> None:
        result = build(isbn13=ISBN13)
        assert result.isbn10 == ISBN10

    def test_punctuation_is_stripped(self) -> None:
        result = build(isbn13="978-0-306-40615-7")
        assert result.isbn13 == ISBN13

    def test_unparseable_identifiers_are_dropped(self) -> None:
        result = build(isbn10="junk", isbn13="also-junk")
        assert result.isbn10 is None
        assert result.isbn13 is None

    def test_bad_checksum_is_dropped(self) -> None:
        assert build(isbn13="9780306406158").isbn13 is None

    def test_979_has_no_isbn10(self) -> None:
        result = build(isbn13="9791234567896")
        assert result.isbn13 == "9791234567896"
        assert result.isbn10 is None


class TestPublicationYear:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2004", 2004),
            ("2004-05-17", 2004),
            ("May 2004", 2004),
            ("c1997", 1997),
            (None, None),
            ("undated", None),
        ],
    )
    def test_year_extraction(self, value: str | None, expected: int | None) -> None:
        assert build(publication_date=value).publication_year == expected


class TestValidation:
    def test_title_is_required(self) -> None:
        with pytest.raises(ValidationError):
            BookMetadataResult(source=MetadataSource.MANUAL)

    def test_empty_title_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            build(title="")

    def test_source_is_required(self) -> None:
        with pytest.raises(ValidationError):
            BookMetadataResult(title="Saxon Math 3")

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_confidence_bounds(self, confidence: float) -> None:
        with pytest.raises(ValidationError):
            build(confidence=confidence)

    def test_negative_page_count_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            build(page_count=-1)

    def test_defaults(self) -> None:
        result = build()
        assert result.authors == []
        assert result.confidence == 1.0
        assert result.raw_payload is None


class TestAuthorCredit:
    def test_role_defaults_to_author(self) -> None:
        assert AuthorCredit(name="Nancy Larson").role is ContributorRole.AUTHOR

    def test_role_can_be_overridden(self) -> None:
        credit = AuthorCredit(name="Someone", role=ContributorRole.ILLUSTRATOR)
        assert credit.role is ContributorRole.ILLUSTRATOR

    def test_author_names_helper(self) -> None:
        result = build(authors=[{"name": "A"}, {"name": "B", "role": "editor"}])
        assert result.author_names == ["A", "B"]
        assert result.authors[1].role is ContributorRole.EDITOR
