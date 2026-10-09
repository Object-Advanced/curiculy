"""Store worksheet photos on the evidence volume; DB rows hold paths."""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from app.config import settings

MAX_IMAGE_DIMENSION = 1600
WEBP_QUALITY = 80
MAX_EVIDENCE_BYTES = 20 * 1024 * 1024
_PDF_MAGIC = b"%PDF-"
# Served inline; anything else on disk (from before uploads were checked) is
# sent as a download so a browser never renders it as a page.
INLINE_MEDIA_TYPES = frozenset(
    {"image/webp", "image/png", "image/jpeg", "image/gif", "application/pdf"}
)


class EvidenceRejected(ValueError):
    """An upload that cannot be kept as a work sample."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
_MEDIA_TYPES = {
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".avif": "image/avif",
    ".pdf": "application/pdf",
}


def evidence_root() -> Path:
    path = Path(settings.evidence_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _tenant_dir(tenant_uuid: str) -> Path:
    """``/data/evidence/{tenant_uuid}/``, created on first upload."""
    name = Path(tenant_uuid).name
    if not name or name != tenant_uuid:
        raise ValueError("Invalid tenant")
    path = evidence_root() / name
    os.makedirs(path, exist_ok=True)
    return path


def _compress_to_webp(data: bytes) -> bytes | None:
    """Resize to 1600px and encode WebP, or return None if this is not an image."""
    try:
        with Image.open(BytesIO(data)) as image:
            rgb = image.convert("RGB")
            rgb.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
            buffer = BytesIO()
            rgb.save(buffer, format="WEBP", quality=WEBP_QUALITY)
            return buffer.getvalue()
    except Image.DecompressionBombError as error:
        raise EvidenceRejected(413, "That image is too large to store.") from error
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def store_capture(source: BinaryIO, *, tenant_uuid: str) -> str:
    """Keep a photo or PDF under the tenant's evidence folder; return its relative path.

    The type comes from the bytes, not the uploader's claimed type or file
    name. Photos are converted to RGB, resized to a 1600×1600 box, and stored
    as WebP. PDFs are stored as they are. Anything else (SVG, HTML, documents)
    is refused, as is anything over MAX_EVIDENCE_BYTES. Stored names are UUIDs,
    so two uploads of the same worksheet cannot collide.
    """
    data = source.read(MAX_EVIDENCE_BYTES + 1)
    if len(data) > MAX_EVIDENCE_BYTES:
        raise EvidenceRejected(413, "Work samples can be up to 20 MB.")
    if data.startswith(_PDF_MAGIC):
        filename, payload = f"{uuid4()}.pdf", data
    else:
        compressed = _compress_to_webp(data)
        if compressed is None:
            raise EvidenceRejected(415, "Work samples must be a photo or a PDF.")
        filename, payload = f"{uuid4()}.webp", compressed

    relative_path = f"{tenant_uuid}/{filename}"
    destination = _tenant_dir(tenant_uuid) / filename
    destination.write_bytes(payload)
    return relative_path


def stored_relative_path(file_path: str | None) -> str | None:
    """Turn a DB file_path into ``tenant/filename`` under the evidence volume.

    Rejects traversal and anything that is not exactly one tenant folder plus a
    file name. Does not touch the disk.
    """
    if not file_path or not str(file_path).strip():
        return None
    relative = Path(str(file_path).replace("\\", "/").lstrip("/"))
    parts = relative.parts
    if len(parts) >= 2 and parts[0] == "data" and parts[1] == "evidence":
        relative = Path(*parts[2:])
        parts = relative.parts
    if len(parts) != 2 or ".." in parts:
        return None
    tenant, filename = parts
    if not tenant or tenant in {".", ".."}:
        return None
    if not filename or filename in {".", ".."} or Path(filename).name != filename:
        return None
    if Path(tenant).name != tenant:
        return None
    return f"{tenant}/{filename}"


def resolve_evidence_file(
    file_path: str | None,
    *,
    tenant_uuid: str | None = None,
) -> Path | None:
    """Absolute file on the evidence volume, or None if it is missing/unsafe.

    When ``tenant_uuid`` is set, the path must live in that household's folder.
    """
    relative = stored_relative_path(file_path)
    if relative is None:
        return None
    tenant, filename = relative.split("/", 1)
    if tenant_uuid is not None and tenant != tenant_uuid:
        return None
    root = evidence_root().resolve()
    candidate = (root / tenant / filename).resolve()
    try:
        candidate.relative_to(root / tenant)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def evidence_media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
