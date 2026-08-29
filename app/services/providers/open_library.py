"""Open Library provider.

Open Library needs no credentials, so it is the default lookup. Its Books API
keys responses by the bibkey that was requested, and its search endpoint returns
a flatter document shape, so the two responses are parsed separately.
"""

from typing import Any

from app.enums import MetadataSource
from app.schemas.metadata import AuthorCredit, BookMetadataResult
from app.services.providers.base import BibliographicProvider, search_confidence
from app.utils.isbn import to_isbn13

COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

_SEARCH_FIELDS = ",".join(
    [
        "key",
        "title",
        "subtitle",
        "author_name",
        "publisher",
        "publish_date",
        "first_publish_year",
        "isbn",
        "number_of_pages_median",
        "cover_i",
    ]
)


class OpenLibraryProvider(BibliographicProvider):
    source = MetadataSource.OPEN_LIBRARY
    base_url = "https://openlibrary.org"

    async def lookup_by_isbn(self, isbn: str) -> BookMetadataResult | None:
        canonical = to_isbn13(isbn)
        if canonical is None:
            return None

        bibkey = f"ISBN:{canonical}"
        payload = await self._get_json(
            f"{self.base_url}/api/books",
            params={"bibkeys": bibkey, "format": "json", "jscmd": "data"},
        )
        if not isinstance(payload, dict) or not payload:
            return None

        record = payload.get(bibkey)
        if record is None and len(payload) == 1:
            record = next(iter(payload.values()))
        if not isinstance(record, dict):
            return None

        return self._parse_book(record, fallback_isbn13=canonical)

    async def search_by_title(
        self,
        title: str,
        author: str | None = None,
    ) -> list[BookMetadataResult]:
        params: dict[str, Any] = {
            "title": title,
            "limit": self._max_results,
            "fields": _SEARCH_FIELDS,
        }
        if author:
            params["author"] = author

        payload = await self._get_json(f"{self.base_url}/search.json", params=params)
        docs = (payload or {}).get("docs") or []

        results = [
            parsed
            for doc in docs
            if isinstance(doc, dict)
            and (parsed := self._parse_search_doc(doc, title, author)) is not None
        ]
        results.sort(key=lambda result: result.confidence, reverse=True)
        return results

    def _parse_book(
        self,
        record: dict[str, Any],
        fallback_isbn13: str | None = None,
    ) -> BookMetadataResult | None:
        title = str(record.get("title") or "").strip()
        if not title:
            return None

        identifiers = record.get("identifiers") or {}
        cover = record.get("cover") or {}
        publishers = [
            str(entry.get("name")).strip()
            for entry in record.get("publishers") or []
            if isinstance(entry, dict) and entry.get("name")
        ]

        return BookMetadataResult(
            isbn13=_first(identifiers.get("isbn_13")) or fallback_isbn13,
            isbn10=_first(identifiers.get("isbn_10")),
            title=title,
            subtitle=_clean(record.get("subtitle")),
            authors=[
                AuthorCredit(name=str(entry["name"]).strip())
                for entry in record.get("authors") or []
                if isinstance(entry, dict) and entry.get("name")
            ],
            publisher=publishers[0] if publishers else None,
            publication_date=_clean(record.get("publish_date")),
            page_count=_positive_int(record.get("number_of_pages")),
            description=_description(record),
            cover_url=_clean(cover.get("large") or cover.get("medium") or cover.get("small")),
            source=self.source,
            raw_payload=record,
            confidence=1.0,
        )

    def _parse_search_doc(
        self,
        doc: dict[str, Any],
        query_title: str,
        query_author: str | None,
    ) -> BookMetadataResult | None:
        title = str(doc.get("title") or "").strip()
        if not title:
            return None

        author_names = [
            str(name).strip() for name in doc.get("author_name") or [] if str(name).strip()
        ]
        publishers = [
            str(name).strip() for name in doc.get("publisher") or [] if str(name).strip()
        ]
        cover_id = doc.get("cover_i")
        publish_year = doc.get("first_publish_year")

        return BookMetadataResult(
            isbn13=_best_isbn13(doc.get("isbn")),
            title=title,
            subtitle=_clean(doc.get("subtitle")),
            authors=[AuthorCredit(name=name) for name in author_names],
            publisher=publishers[0] if publishers else None,
            publication_date=str(publish_year) if publish_year else None,
            page_count=_positive_int(doc.get("number_of_pages_median")),
            cover_url=COVER_URL.format(cover_id=cover_id) if cover_id else None,
            source=self.source,
            raw_payload=doc,
            confidence=search_confidence(query_title, title, query_author, author_names),
        )


def _first(values: Any) -> str | None:
    if isinstance(values, list) and values:
        return str(values[0]).strip() or None
    if isinstance(values, str):
        return values.strip() or None
    return None


def _best_isbn13(values: Any) -> str | None:
    """Open Library mixes 10- and 13-digit ISBNs; take the first usable one."""
    if not isinstance(values, list):
        return None
    for value in values:
        canonical = to_isbn13(str(value))
        if canonical:
            return canonical
    return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _description(record: dict[str, Any]) -> str | None:
    """Notes may be a string or a typed object; excerpts are the fallback."""
    notes = record.get("notes")
    if isinstance(notes, dict):
        notes = notes.get("value")
    if isinstance(notes, str) and notes.strip():
        return notes.strip()

    for excerpt in record.get("excerpts") or []:
        if isinstance(excerpt, dict) and str(excerpt.get("text") or "").strip():
            return str(excerpt["text"]).strip()
    return None
