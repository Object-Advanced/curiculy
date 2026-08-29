"""ISBN normalization, validation, and conversion.

Identifiers reach Curiculy in three shapes: a barcode scan yields an EAN-13,
sometimes followed by a 2- or 5-digit price add-on; printed copyright pages and
catalog imports use ISBN-10 or ISBN-13 with arbitrary punctuation. Because
``BookEdition.isbn13`` is the unique catalog key, every inbound identifier is
funnelled through :func:`to_isbn13` so the same physical book cannot be stored
twice under two spellings.

Invalid input returns ``None`` rather than raising, so callers can map a failed
scan to a 400 response without exception handling.
"""

import re

BOOKLAND_PREFIXES = ("978", "979")

_ISBN10_LENGTH = 10
_ISBN13_LENGTH = 13
_ADD_ON_LENGTHS = (15, 18)  # EAN-13 plus a 2- or 5-digit supplement

# Matches labels such as "ISBN", "ISBN-13:", "ISBN10 " so the 10/13 in the label
# is not mistaken for part of the number.
_LABEL = re.compile(r"^\s*ISBN(?:[-\s]?1[03])?\s*[:\-]?\s*")


def _clean(value: str | None) -> str:
    """Strip labels and punctuation, keeping only digits and a trailing X."""
    if value is None:
        return ""
    text = _LABEL.sub("", str(value).strip().upper())
    return "".join(char for char in text if char.isdigit() or char == "X")


def isbn10_check_digit(body: str) -> str | None:
    """Return the ISBN-10 check character for the first 9 digits."""
    digits = _clean(body)
    if len(digits) != _ISBN10_LENGTH - 1 or not digits.isdigit():
        return None
    total = sum((10 - index) * int(digit) for index, digit in enumerate(digits))
    remainder = (11 - total % 11) % 11
    return "X" if remainder == 10 else str(remainder)


def isbn13_check_digit(body: str) -> str | None:
    """Return the ISBN-13 check digit for the first 12 digits."""
    digits = _clean(body)
    if len(digits) != _ISBN13_LENGTH - 1 or not digits.isdigit():
        return None
    total = sum(
        int(digit) * (3 if index % 2 else 1) for index, digit in enumerate(digits)
    )
    return str((10 - total % 10) % 10)


def is_valid_isbn10(value: str | None) -> bool:
    digits = _clean(value)
    if len(digits) != _ISBN10_LENGTH or not digits[:9].isdigit():
        return False
    return isbn10_check_digit(digits[:9]) == digits[9]


def is_valid_isbn13(value: str | None) -> bool:
    digits = _clean(value)
    if len(digits) != _ISBN13_LENGTH or not digits.isdigit():
        return False
    if not digits.startswith(BOOKLAND_PREFIXES):
        return False
    return isbn13_check_digit(digits[:12]) == digits[12]


def is_valid_isbn(value: str | None) -> bool:
    return is_valid_isbn10(value) or is_valid_isbn13(value)


def normalize_isbn(value: str | None) -> str | None:
    """Return the identifier stripped of punctuation, or None if it is not an ISBN."""
    digits = _clean(value)
    return digits if is_valid_isbn(digits) else None


def isbn10_to_isbn13(value: str | None) -> str | None:
    if not is_valid_isbn10(value):
        return None
    body = "978" + _clean(value)[:9]
    check = isbn13_check_digit(body)
    return None if check is None else body + check


def isbn13_to_isbn10(value: str | None) -> str | None:
    """Convert back to ISBN-10, which only exists for the 978 prefix."""
    if not is_valid_isbn13(value):
        return None
    digits = _clean(value)
    if not digits.startswith("978"):
        return None
    body = digits[3:12]
    check = isbn10_check_digit(body)
    return None if check is None else body + check


def to_isbn13(value: str | None) -> str | None:
    """Canonical catalog form for any valid ISBN-10 or ISBN-13."""
    digits = _clean(value)
    if is_valid_isbn13(digits):
        return digits
    return isbn10_to_isbn13(digits)


def to_isbn10(value: str | None) -> str | None:
    digits = _clean(value)
    if is_valid_isbn10(digits):
        return digits
    return isbn13_to_isbn10(digits)


def barcode_to_isbn13(value: str | None) -> str | None:
    """Resolve a scanned barcode to a catalog ISBN-13.

    Handles Bookland EAN-13 with an optional 2- or 5-digit price add-on, and
    rejects non-book barcodes such as retail UPCs.
    """
    digits = _clean(value)
    if not digits:
        return None
    if len(digits) in _ADD_ON_LENGTHS and digits.isdigit():
        digits = digits[:_ISBN13_LENGTH]
    if len(digits) == _ISBN13_LENGTH:
        return digits if is_valid_isbn13(digits) else None
    if len(digits) == _ISBN10_LENGTH:
        return to_isbn13(digits)
    return None


def isbns_equal(left: str | None, right: str | None) -> bool:
    """Compare identifiers across formats so 10- and 13-digit forms match."""
    left_canonical = to_isbn13(left)
    right_canonical = to_isbn13(right)
    return left_canonical is not None and left_canonical == right_canonical
