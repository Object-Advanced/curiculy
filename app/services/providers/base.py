"""Provider contract shared by every external bibliographic source.

Providers are thin, stateless adapters: they issue one HTTP request, map the
response onto :class:`~app.schemas.metadata.BookMetadataResult`, and translate
transport failures into the small exception vocabulary below so callers can
choose a fallback provider without knowing which service failed.

Error handling is deliberately uniform:

* a missing record (HTTP 404, or an empty result set) returns ``None`` / ``[]``
  because "this book is not in that catalog" is an answer, not a failure;
* HTTP 429 raises :class:`ProviderRateLimited`, carrying ``Retry-After``;
* timeouts raise :class:`ProviderTimeout`;
* anything else raises :class:`ProviderUnavailable` or :class:`ProviderError`.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from types import TracebackType
from typing import Any, ClassVar, Self

import httpx

from app.config import settings
from app.enums import MetadataSource
from app.schemas.metadata import BookMetadataResult


class ProviderError(RuntimeError):
    """A provider could not answer the question."""

    def __init__(self, source: MetadataSource, message: str) -> None:
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message


class ProviderTimeout(ProviderError):
    """The provider did not respond within the configured timeout."""


class ProviderRateLimited(ProviderError):
    """The provider rejected the request with HTTP 429."""

    def __init__(
        self,
        source: MetadataSource,
        message: str,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(source, message)
        self.retry_after = retry_after


class ProviderUnavailable(ProviderError):
    """The provider is reachable but failing, or returned an unusable body."""


class BibliographicProvider(ABC):
    source: ClassVar[MetadataSource]
    base_url: ClassVar[str]

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
        max_results: int | None = None,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._timeout = (
            timeout if timeout is not None else settings.provider_timeout_seconds
        )
        self._max_results = (
            max_results if max_results is not None else settings.provider_max_results
        )

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> Any | None:
        """GET and decode JSON, or None when the record simply does not exist."""
        try:
            response = await self.client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(self.source, f"request to {url} timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(self.source, f"request to {url} failed: {exc}") from exc

        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            raise ProviderRateLimited(
                self.source,
                "rate limited",
                retry_after=_retry_after_seconds(response),
            )
        if response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
            raise ProviderUnavailable(self.source, f"HTTP {response.status_code}")
        if not response.is_success:
            raise ProviderError(self.source, f"HTTP {response.status_code}")

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderUnavailable(self.source, "response was not valid JSON") from exc

    @abstractmethod
    async def lookup_by_isbn(self, isbn: str) -> BookMetadataResult | None:
        """Return metadata for an exact ISBN, or None when the book is unknown."""

    @abstractmethod
    async def search_by_title(
        self,
        title: str,
        author: str | None = None,
    ) -> list[BookMetadataResult]:
        """Return candidate matches, most confident first."""


def search_confidence(
    query_title: str,
    result_title: str | None,
    query_author: str | None = None,
    result_authors: Sequence[str] = (),
) -> float:
    """Score a title-search hit.

    Title search is a guess, so results never claim the certainty of an exact
    ISBN match: the ceiling is 0.95 and a bare title hit starts at 0.5.
    """
    score = 0.5
    query = _normalize_text(query_title)
    found = _normalize_text(result_title)
    if query and found:
        if query == found:
            score += 0.3
        elif query in found or found in query:
            score += 0.15
    if query_author:
        wanted = _normalize_text(query_author)
        candidates = [_normalize_text(name) for name in result_authors if name]
        if wanted and any(wanted in name or name in wanted for name in candidates):
            score += 0.2
    return round(min(score, 0.95), 2)


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    stripped = "".join(char if char.isalnum() else " " for char in value.lower())
    return " ".join(stripped.split())


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
