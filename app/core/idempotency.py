"""Idempotency keys, so a retried write is not applied twice.

The SPA sends ``Idempotency-Key`` with every write. If the network drops
after the server applied the change but before the reply arrived, the SPA
queues the change offline and later replays it with the same key; the
server answers that replay from the stored response instead of applying it
again (no duplicate evidence, no second copy of a 180-lesson plan apply).

Keys are scoped to the signed-in principal (household, user, and kid; each
demo household separately). Responses below 500 are stored; a 500 can be
retried. Writes without a key, or without a valid bearer token, are not
affected. Records older than two days are purged at startup and as new ones
are written.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import timedelta

from anyio import to_thread
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.security import DEMO_TENANT_UUID, decode_access_token
from app.db import open_admin_session
from app.models.admin import IdempotencyRecord
from app.models.mixins import utcnow

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
RETENTION = timedelta(days=2)
MAX_STORED_BODY = 256 * 1024
PURGE_EVERY = 500


@dataclass(frozen=True)
class StoredResponse:
    method: str
    path: str
    status_code: int
    content_type: str | None
    body: bytes


def principal_for(authorization: str | None) -> str | None:
    """Who is writing, from a verified bearer token; None if unsigned or invalid."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        payload = decode_access_token(authorization[7:].strip())
    except HTTPException:
        return None
    tenant, subject = payload.get("tenant_uuid"), payload.get("sub")
    if not tenant or not subject:
        return None
    # Every demo household is its own database, keyed by the token's jti.
    household = f"{tenant}/{payload.get('jti')}" if tenant == DEMO_TENANT_UUID else tenant
    return f"{household}:{subject}:{payload.get('student_id') or ''}"


def find_response(principal: str, key: str) -> StoredResponse | None:
    session = open_admin_session()
    try:
        row = (
            session.query(IdempotencyRecord)
            .filter(IdempotencyRecord.principal == principal, IdempotencyRecord.key == key)
            .one_or_none()
        )
        if row is None:
            return None
        return StoredResponse(row.method, row.path, row.status_code, row.content_type, row.body)
    finally:
        session.close()


def store_response(principal: str, key: str, response: StoredResponse) -> None:
    session = open_admin_session()
    try:
        session.add(
            IdempotencyRecord(
                principal=principal,
                key=key,
                method=response.method,
                path=response.path,
                status_code=response.status_code,
                content_type=response.content_type,
                body=response.body,
            )
        )
        session.commit()
    except IntegrityError:
        session.rollback()  # stored by a concurrent request already
    finally:
        session.close()


def purge_expired_records() -> int:
    session = open_admin_session()
    try:
        removed = (
            session.query(IdempotencyRecord)
            .filter(IdempotencyRecord.created_at < utcnow() - RETENTION)
            .delete(synchronize_session=False)
        )
        session.commit()
        return removed
    finally:
        session.close()


class IdempotencyMiddleware:
    """Answers a repeated (principal, Idempotency-Key) write from the stored response.

    Must sit inside the gzip middleware so stored bodies are uncompressed.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._stored = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in WRITE_METHODS
            or not scope["path"].startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return
        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        raw_key = headers.get(b"idempotency-key")
        if raw_key is None:
            await self.app(scope, receive, send)
            return
        key = raw_key.decode("latin-1")
        if not KEY_PATTERN.fullmatch(key):
            await JSONResponse(
                {"detail": "Idempotency-Key must be 8-128 letters, digits, '-' or '_'."},
                status_code=400,
            )(scope, receive, send)
            return
        authorization = headers.get(b"authorization")
        principal = principal_for(authorization.decode("latin-1") if authorization else None)
        if principal is None:
            await self.app(scope, receive, send)
            return

        slot = (principal, key)
        lock = self._locks.setdefault(slot, asyncio.Lock())
        try:
            async with lock:
                stored = await to_thread.run_sync(find_response, principal, key)
                if stored is not None:
                    await self._replay(stored, scope, receive, send)
                    return
                response = await self._run(scope, receive, send)
                if response.status_code < 500 and len(response.body) <= MAX_STORED_BODY:
                    await to_thread.run_sync(store_response, principal, key, response)
                    self._stored += 1
                    if self._stored % PURGE_EVERY == 0:
                        await to_thread.run_sync(purge_expired_records)
        finally:
            # Safe once released: the response is already stored, so a request
            # that makes a new lock for this slot will find it.
            if not lock.locked():
                self._locks.pop(slot, None)

    async def _replay(self, stored: StoredResponse, scope: Scope, receive: Receive, send: Send) -> None:
        if stored.method != scope["method"] or stored.path != scope["path"]:
            await JSONResponse(
                {"detail": "This Idempotency-Key was already used for a different request."},
                status_code=422,
            )(scope, receive, send)
            return
        await Response(
            content=stored.body,
            status_code=stored.status_code,
            media_type=stored.content_type,
            headers={"Idempotent-Replayed": "true"},
        )(scope, receive, send)

    async def _run(self, scope: Scope, receive: Receive, send: Send) -> StoredResponse:
        status_code = 500
        content_type: str | None = None
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal status_code, content_type
            if message["type"] == "http.response.start":
                status_code = message["status"]
                for name, value in message.get("headers", []):
                    if name.lower() == b"content-type":
                        content_type = value.decode("latin-1")
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        return StoredResponse(scope["method"], scope["path"], status_code, content_type, b"".join(chunks))
