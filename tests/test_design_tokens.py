"""Design-token guardrails: raw colors and type sizes live only in tokens.css."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS_CSS = ROOT / "static" / "css" / "tokens.css"
APP_CSS = ROOT / "static" / "css" / "app.css"

HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b(?![\w-])")
FONT_SIZE_RE = re.compile(r"font-size:\s*([^;]+);")
FONT_URL_RE = re.compile(r'url\("(/static/fonts/[^"?]+)')


def test_app_css_uses_tokens_for_every_color() -> None:
    assert HEX_COLOR_RE.findall(APP_CSS.read_text(encoding="utf-8")) == []


def test_app_css_font_sizes_come_from_the_type_scale() -> None:
    allowed = re.compile(r"^(inherit|var\(--text-[\w-]+\)|clamp\(var\(--text-[\w-]+\), [\d.]+vw, var\(--text-[\w-]+\)\))$")
    sizes = {value.strip() for value in FONT_SIZE_RE.findall(APP_CSS.read_text(encoding="utf-8"))}
    assert {size for size in sizes if not allowed.match(size)} == set()


def test_every_font_face_file_ships() -> None:
    paths = FONT_URL_RE.findall(TOKENS_CSS.read_text(encoding="utf-8"))
    assert len(paths) == 5
    for path in paths:
        font = ROOT / path.lstrip("/")
        assert font.is_file(), path
        assert font.read_bytes()[:4] == b"wOF2", path
