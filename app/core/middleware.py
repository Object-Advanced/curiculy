"""HTTP middleware: security headers, request size cap, and selective gzip.

Plain ASGI classes (not BaseHTTPMiddleware) so streamed responses such as
file downloads pass through untouched.
"""

from __future__ import annotations

from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The SPA loads only same-origin scripts (theme-boot.js, the vendored
# Chart.js, app.js). Inline style attributes are used throughout the
# templates, hence 'unsafe-inline' for styles only. blob: covers evidence
# thumbnails and the weekly-checklist PDF the SPA opens in a new tab; object-src
# allows blob: so the browser's PDF viewer can render it.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "worker-src 'self'",
        "manifest-src 'self'",
        "object-src 'self' blob:",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

SECURITY_HEADERS: dict[bytes, bytes] = {
    b"content-security-policy": CONTENT_SECURITY_POLICY.encode(),
    b"x-content-type-options": b"nosniff",
    b"referrer-policy": b"strict-origin-when-cross-origin",
    b"x-frame-options": b"DENY",
    b"permissions-policy": b"camera=(self), microphone=(), geolocation=(), payment=()",
}


class SecurityHeadersMiddleware:
    """Adds the headers above unless the route already set its own."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend(
                    (name, value) for name, value in SECURITY_HEADERS.items() if name not in present
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Refuses requests that declare a body larger than ``max_bytes`` (413).

    Browsers send Content-Length with uploads, so this stops an oversized
    upload before it is spooled to disk. Per-file limits (evidence photos)
    are checked again where the file is stored.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for name, value in scope.get("headers", []):
                if name == b"content-length":
                    try:
                        declared = int(value)
                    except ValueError:
                        declared = 0
                    if declared > self.max_bytes:
                        megabytes = self.max_bytes // (1024 * 1024)
                        response = JSONResponse(
                            {"detail": f"That upload is too large (the limit is {megabytes} MB)."},
                            status_code=413,
                        )
                        await response(scope, receive, send)
                        return
                    break
        await self.app(scope, receive, send)


# Already-compressed formats gain nothing from gzip and only cost CPU.
_INCOMPRESSIBLE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".pdf", ".woff2", ".zip")
_INCOMPRESSIBLE_PREFIXES = (
    "/api/evidence/files/",
    "/api/reports/weekly-manifest",
    "/api/curriculum/paper-template",
)


class SelectiveGZipMiddleware:
    """Gzip text (HTML, JS, CSS, JSON); skip photos, PDFs, and evidence files."""

    def __init__(self, app: ASGIApp, minimum_size: int = 1024) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size, compresslevel=6)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path", "").lower()
            if not path.endswith(_INCOMPRESSIBLE_SUFFIXES) and not path.startswith(
                _INCOMPRESSIBLE_PREFIXES
            ):
                await self.gzip(scope, receive, send)
                return
        await self.app(scope, receive, send)
