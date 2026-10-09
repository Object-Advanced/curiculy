"""App shell, service-worker cache lockstep, and referenced brand assets."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "index.html"
SW_JS = ROOT / "sw.js"
APP_CSS = ROOT / "static" / "css" / "app.css"
EXTENSION_DIR = ROOT / "extension"
MANIFEST = EXTENSION_DIR / "manifest.json"
OPTIONS_HTML = EXTENSION_DIR / "options.html"

SHELL_VERSION_RE = re.compile(
    r'const SHELL_VERSION\s*=\s*["\']([^"\']+)["\']'
)
STATIC_VERSION_RE = re.compile(r"/static/[^\"')\s?]+[?&]v=([\w.-]+)")
STATIC_PATH_RE = re.compile(r"/static/([^\"')\s?]+)")
ICON_SRC_RE = re.compile(r"""src=["'](icons/[^"']+)["']""")
SHELL_URL_RE = re.compile(r"""[`"'](/[^`"']*)[`"']""")


def _shell_version() -> str:
    text = SW_JS.read_text(encoding="utf-8")
    match = SHELL_VERSION_RE.search(text)
    assert match, "sw.js must declare const SHELL_VERSION"
    return match.group(1)


def _static_versions(text: str) -> set[str]:
    return set(STATIC_VERSION_RE.findall(text))


def _static_files(text: str) -> set[str]:
    return set(STATIC_PATH_RE.findall(text))


def test_service_worker_script(client: TestClient) -> None:
    response = client.get("/sw.js")
    assert response.status_code == 200
    body = response.text
    assert "curiculy-sync" in body
    assert "outbox" in body
    assert "sync-outbox" in body
    assert "SHELL_VERSION" in body
    assert response.headers.get("service-worker-allowed") == "/"
    assert "javascript" in response.headers.get("content-type", "")


def test_shell_cache_version_matches_html_and_css() -> None:
    version = _shell_version()
    sw_text = SW_JS.read_text(encoding="utf-8")
    resolved_sw = sw_text.replace("${SHELL_VERSION}", version)
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = APP_CSS.read_text(encoding="utf-8")

    assert "curiculy-shell-${SHELL_VERSION}" in sw_text
    html_versions = _static_versions(html)
    css_versions = _static_versions(css)
    sw_versions = _static_versions(resolved_sw)
    assert html_versions == {version}, html_versions
    assert css_versions == {version}, css_versions
    assert sw_versions == {version}, sw_versions
    for path in (
        f"/static/js/app.js?v={version}",
        f"/static/css/app.css?v={version}",
        f"/static/curiculy-logo.png?v={version}",
        f"/static/night-mountains.jpg?v={version}",
    ):
        assert path in html or path in css
        assert path in resolved_sw


def test_index_html_references_existing_static_files() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    missing = [name for name in _static_files(html) if not (ROOT / "static" / name).is_file()]
    assert missing == []


def test_readme_covers_bootstrap() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "JWT_SECRET" in text
    assert "localhost:3040" in text
    assert "docker compose --profile dev run --rm tests pytest" in text


def test_github_actions_runs_the_compose_suite() -> None:
    text = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "docker compose --profile dev run --rm -T tests pytest -q --tb=line" in text


def test_shell_urls_are_existing_files() -> None:
    version = _shell_version()
    sw_text = SW_JS.read_text(encoding="utf-8").replace("${SHELL_VERSION}", version)
    urls = SHELL_URL_RE.findall(sw_text)
    static_urls = [url.split("?", 1)[0] for url in urls if url.startswith("/static/")]
    assert static_urls
    missing = [
        path
        for path in static_urls
        if not (ROOT / path.lstrip("/")).is_file()
    ]
    assert missing == []


def test_school_year_editor_lives_in_settings_menu() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    action = 'data-action="open-school-year-settings"'
    assert action in html
    nav_start = html.index('<nav class="nav"')
    nav_end = html.index("</nav>", nav_start)
    menu_start = html.index('id="user-menu"')
    menu_end = html.index("</div>", menu_start)
    assert action not in html[nav_start:nav_end]
    assert action in html[menu_start:menu_end]


def test_application_shell_loads(client: TestClient) -> None:
    version = _shell_version()
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert f"/static/js/app.js?v={version}" in body
    assert f"/static/css/app.css?v={version}" in body
    assert f"/static/curiculy-logo.png?v={version}" in body
    assert response.headers.get("cache-control") == "no-cache"


def test_shell_static_assets_are_served(client: TestClient) -> None:
    version = _shell_version()
    checks = [
        (f"/static/js/app.js?v={version}", "javascript"),
        (f"/static/css/app.css?v={version}", "css"),
        (f"/static/curiculy-logo.png?v={version}", "png"),
        (f"/static/night-mountains.jpg?v={version}", "jpeg"),
    ]
    for path, kind in checks:
        response = client.get(path)
        assert response.status_code == 200, path
        content_type = response.headers.get("content-type", "")
        assert kind in content_type, (path, content_type)
        assert response.content


def test_logo_is_a_png() -> None:
    path = ROOT / "static" / "curiculy-logo.png"
    assert path.is_file()
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.size[0] >= 40 and image.size[1] >= 40


def test_extension_manifest_icons_exist() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected_sizes = {
        "16": (16, 16),
        "32": (32, 32),
        "48": (48, 48),
        "128": (128, 128),
    }
    referenced = []
    for collection in (manifest.get("icons") or {}, (manifest.get("action") or {}).get("default_icon") or {}):
        referenced.extend(collection.items())
    assert referenced
    for size, relative in referenced:
        path = EXTENSION_DIR / relative
        assert path.is_file(), relative
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == expected_sizes[str(size)], (relative, image.size)


def test_extension_options_logo_exists() -> None:
    html = OPTIONS_HTML.read_text(encoding="utf-8")
    srcs = ICON_SRC_RE.findall(html)
    assert srcs
    for relative in srcs:
        path = EXTENSION_DIR / relative
        assert path.is_file(), relative
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size[0] >= 16 and image.size[1] >= 16
