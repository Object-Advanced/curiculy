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
_PDF_CONTENT_TYPE = "application/pdf"


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


def _media_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _compress_to_webp(data: bytes) -> bytes | None:
    """Resize to 1600px and encode WebP, or return None if this is not an image."""
    try:
        with Image.open(BytesIO(data)) as image:
            rgb = image.convert("RGB")
            rgb.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
            buffer = BytesIO()
            rgb.save(buffer, format="WEBP", quality=WEBP_QUALITY)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def store_capture(
    source: BinaryIO,
    original_name: str | None = None,
    *,
    tenant_uuid: str,
    content_type: str | None = None,
) -> str:
    """Write a capture under the tenant's evidence folder and return its relative path.

    Images are converted to RGB, resized to a 1600×1600 box, and stored as WebP.
    PDFs and other non-image documents are written unchanged. The stored name is
    a UUID so two uploads of the same worksheet cannot collide.
    """
    data = source.read()
    media = _media_type(content_type)
    compressed = None if media == _PDF_CONTENT_TYPE else _compress_to_webp(data)

    if compressed is not None:
        filename = f"{uuid4()}.webp"
        payload = compressed
    else:
        filename = f"{uuid4()}{Path(original_name or '').suffix}"
        payload = data

    relative_path = f"{tenant_uuid}/{filename}"
    destination = _tenant_dir(tenant_uuid) / filename
    destination.write_bytes(payload)
    return relative_path
