"""Unit tests for app.utils.isbn.

Fixtures use identifiers whose check digits were computed by hand so the tests
do not simply re-derive their expectations from the code under test:

* ``0306406152`` <-> ``9780306406157`` (plain ISBN-10)
* ``080442957X`` <-> ``9780804429573`` (ISBN-10 with an X check character)
* ``9791234567896`` (979 prefix, so it has no ISBN-10 equivalent)
"""

import pytest

from app.utils.isbn import (
    barcode_to_isbn13,
    is_valid_isbn,
    is_valid_isbn10,
    is_valid_isbn13,
    isbn10_check_digit,
    isbn10_to_isbn13,
    isbn13_check_digit,
    isbn13_to_isbn10,
    isbns_equal,
    normalize_isbn,
    to_isbn10,
    to_isbn13,
)

ISBN10 = "0306406152"
ISBN13 = "9780306406157"
ISBN10_WITH_X = "080442957X"
ISBN13_OF_X = "9780804429573"
ISBN13_979 = "9791234567896"


class TestCheckDigits:
    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ("030640615", "2"),
            ("080442957", "X"),
            ("043935806", "X"),
            ("000000000", "0"),
        ],
    )
    def test_isbn10_check_digit(self, body: str, expected: str) -> None:
        assert isbn10_check_digit(body) == expected

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ("978030640615", "7"),
            ("978080442957", "3"),
            ("979123456789", "6"),
        ],
    )
    def test_isbn13_check_digit(self, body: str, expected: str) -> None:
        assert isbn13_check_digit(body) == expected

    @pytest.mark.parametrize("body", ["", None, "12345", "0306406152", "12345678901234"])
    def test_check_digits_reject_wrong_length(self, body: str | None) -> None:
        assert isbn10_check_digit(body) is None
        assert isbn13_check_digit(body) is None

    def test_check_digit_rejects_letters_in_body(self) -> None:
        assert isbn10_check_digit("03064061X") is None
        assert isbn13_check_digit("97803064061X") is None


class TestValidation:
    @pytest.mark.parametrize(
        "value",
        [
            ISBN10,
            ISBN10_WITH_X,
            "080442957x",
            "0-306-40615-2",
            "0 306 40615 2",
            "ISBN 0-306-40615-2",
            "isbn: 0306406152",
        ],
    )
    def test_valid_isbn10(self, value: str) -> None:
        assert is_valid_isbn10(value) is True
        assert is_valid_isbn(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            ISBN13,
            ISBN13_979,
            "978-0-306-40615-7",
            "978 0 306 40615 7",
            "ISBN-13: 978-0-306-40615-7",
        ],
    )
    def test_valid_isbn13(self, value: str) -> None:
        assert is_valid_isbn13(value) is True
        assert is_valid_isbn(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "   ",
            "not-an-isbn",
            "0306406153",  # ISBN-10 checksum off by one
            "9780306406158",  # ISBN-13 checksum off by one
            "030640615",  # too short
            "03064061521",  # too long
            "03064X6152",  # X outside the check position
            "1234567890123",  # valid length, non-Bookland prefix
        ],
    )
    def test_invalid_identifiers(self, value: str | None) -> None:
        assert is_valid_isbn10(value) is False
        assert is_valid_isbn13(value) is False
        assert is_valid_isbn(value) is False

    def test_isbn13_requires_bookland_prefix(self) -> None:
        assert is_valid_isbn13("9770306406154") is False


class TestNormalize:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("978-0-306-40615-7", ISBN13),
            ("0-306-40615-2", ISBN10),
            ("  978 0 306 40615 7  ", ISBN13),
            ("080442957x", ISBN10_WITH_X),
        ],
    )
    def test_normalize_strips_punctuation(self, value: str, expected: str) -> None:
        assert normalize_isbn(value) == expected

    @pytest.mark.parametrize("value", [None, "", "junk", "9780306406158"])
    def test_normalize_rejects_invalid(self, value: str | None) -> None:
        assert normalize_isbn(value) is None


class TestConversion:
    def test_isbn10_to_isbn13(self) -> None:
        assert isbn10_to_isbn13(ISBN10) == ISBN13
        assert isbn10_to_isbn13("0-306-40615-2") == ISBN13

    def test_isbn10_with_x_to_isbn13(self) -> None:
        assert isbn10_to_isbn13(ISBN10_WITH_X) == ISBN13_OF_X

    def test_isbn13_to_isbn10(self) -> None:
        assert isbn13_to_isbn10(ISBN13) == ISBN10
        assert isbn13_to_isbn10(ISBN13_OF_X) == ISBN10_WITH_X

    def test_979_has_no_isbn10(self) -> None:
        assert isbn13_to_isbn10(ISBN13_979) is None
        assert to_isbn10(ISBN13_979) is None

    @pytest.mark.parametrize("value", [None, "", "junk", "9780306406158"])
    def test_conversion_rejects_invalid(self, value: str | None) -> None:
        assert isbn10_to_isbn13(value) is None
        assert isbn13_to_isbn10(value) is None
        assert to_isbn13(value) is None
        assert to_isbn10(value) is None

    @pytest.mark.parametrize("value", [ISBN10, ISBN13, "978-0-306-40615-7"])
    def test_to_isbn13_is_canonical(self, value: str) -> None:
        assert to_isbn13(value) == ISBN13

    @pytest.mark.parametrize("value", [ISBN10, ISBN13])
    def test_round_trip(self, value: str) -> None:
        assert to_isbn13(to_isbn10(value)) == ISBN13
        assert to_isbn10(to_isbn13(value)) == ISBN10

    def test_to_isbn10_passes_through_valid_isbn10(self) -> None:
        assert to_isbn10(ISBN10_WITH_X) == ISBN10_WITH_X


class TestBarcodes:
    def test_plain_ean13_scan(self) -> None:
        assert barcode_to_isbn13(ISBN13) == ISBN13

    def test_strips_five_digit_price_add_on(self) -> None:
        assert barcode_to_isbn13(ISBN13 + "90000") == ISBN13

    def test_strips_two_digit_add_on(self) -> None:
        assert barcode_to_isbn13(ISBN13 + "12") == ISBN13

    def test_accepts_hyphenated_scan(self) -> None:
        assert barcode_to_isbn13("978-0-306-40615-7") == ISBN13

    def test_upgrades_ten_digit_scan(self) -> None:
        assert barcode_to_isbn13(ISBN10) == ISBN13

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "012345678905",  # 12-digit retail UPC
            "1234567890123",  # non-Bookland EAN-13
            "9780306406158",  # bad check digit
            "97803064061",  # truncated scan
        ],
    )
    def test_rejects_non_book_barcodes(self, value: str | None) -> None:
        assert barcode_to_isbn13(value) is None


class TestEquality:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            (ISBN10, ISBN13),
            (ISBN13, ISBN10),
            ("0-306-40615-2", "978 0 306 40615 7"),
            (ISBN10_WITH_X, ISBN13_OF_X),
            (ISBN13, ISBN13),
        ],
    )
    def test_equal_across_formats(self, left: str, right: str) -> None:
        assert isbns_equal(left, right) is True

    @pytest.mark.parametrize(
        ("left", "right"),
        [
            (ISBN10, ISBN13_979),
            (ISBN13, ISBN13_OF_X),
            (None, None),
            ("junk", "junk"),
            (ISBN13, None),
        ],
    )
    def test_unequal_or_unparseable(self, left: str | None, right: str | None) -> None:
        assert isbns_equal(left, right) is False
