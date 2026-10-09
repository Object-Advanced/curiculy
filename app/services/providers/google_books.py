"""Google Books provider.

Works anonymously but is rate limited hard without a key, so the key is read
from configuration and attached when present. Google reports "not found" as an
empty result set rather than HTTP 404, so both are normalized to None.
"""

from typing import Any

import httpx

from app.config import reveal_secret, settings
from app.enums import MetadataSource
from app.schemas.metadata import AuthorCredit, BookMetadataResult
from app.services.providers.base import BibliographicProvider, search_confidence
from app.utils.isbn import to_isbn13


class GoogleBooksProvider(BibliographicProvider):
    source = MetadataSource.GOOGLE_BOOKS
    base_url = "https://www.googleapis.com/books/v1"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
        max_results: int | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__(client=client, timeout=timeout, max_results=max_results)
        self._api_key = api_key if api_key is not None else settings.google_books_api_key

    async def lookup_by_isbn(self, isbn: str) -> BookMetadataResult | None:
        canonical = to_isbn13(isbn)
        if canonical is None:
            return None

        payload = await self._get_json(
            f"{self.base_url}/volumes",
            params=self._params(q=f"isbn:{canonical}", maxResults=1),
        )
        items = (payload or {}).get("items") or []
        if not items:
            return None

        return self._parse_volume(items[0], fallback_isbn13=canonical, confidence=1.0)

    async def search_by_title(
        self,
        title: str,
        author: str | None = None,
    ) -> list[BookMetadataResult]:
        query = f'intitle:"{title}"'
        if author:
            query += f' inauthor:"{author}"'

        payload = await self._get_json(
            f"{self.base_url}/volumes",
            params=self._params(q=query, maxResults=self._max_results),
        )
        items = (payload or {}).get("items") or []

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            info = item.get("volumeInfo") or {}
            authors = [str(name).strip() for name in info.get("authors") or []]
            parsed = self._parse_volume(
                item,
                confidence=search_confidence(title, info.get("title"), author, authors),
            )
            if parsed is not None:
                results.append(parsed)

        results.sort(key=lambda result: result.confidence, reverse=True)
        return results

    def _params(self, **kwargs: Any) -> dict[str, Any]:
        params = {key: value for key, value in kwargs.items() if value is not None}
        api_key = reveal_secret(self._api_key)
        if api_key:
            params["key"] = api_key
        return params

    def _parse_volume(
        self,
        item: dict[str, Any],
        fallback_isbn13: str | None = None,
        confidence: float = 1.0,
    ) -> BookMetadataResult | None:
        info = item.get("volumeInfo") or {}
        title = str(info.get("title") or "").strip()
        if not title:
            return None

        identifiers = _industry_identifiers(info)
        images = info.get("imageLinks") or {}
        cover = images.get("thumbnail") or images.get("smallThumbnail")
        page_count = info.get("pageCount")

        return BookMetadataResult(
            isbn13=identifiers.get("ISBN_13") or fallback_isbn13,
            isbn10=identifiers.get("ISBN_10"),
            title=title,
            subtitle=_clean(info.get("subtitle")),
            authors=[
                AuthorCredit(name=str(name).strip())
                for name in info.get("authors") or []
                if str(name).strip()
            ],
            publisher=_clean(info.get("publisher")),
            publication_date=_clean(info.get("publishedDate")),
            page_count=page_count if isinstance(page_count, int) and page_count > 0 else None,
            description=_clean(info.get("description")),
            cover_url=_https(cover),
            source=self.source,
            raw_payload=item,
            confidence=confidence,
        )


def _industry_identifiers(info: dict[str, Any]) -> dict[str, str]:
    identifiers: dict[str, str] = {}
    for entry in info.get("industryIdentifiers") or []:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("type") or "").upper()
        value = str(entry.get("identifier") or "").strip()
        if kind and value:
            identifiers[kind] = value
    return identifiers


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _https(url: Any) -> str | None:
    """Google returns http cover links, which browsers block on an https page."""
    text = _clean(url)
    if text is None:
        return None
    return f"https://{text[len('http://'):]}" if text.startswith("http://") else text
