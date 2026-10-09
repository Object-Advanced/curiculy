"""The app imports cleanly no matter which module is imported first.

conftest imports app.models (and so app.db) before anything else, which hid
a circular import between app.db and app.core.security: uvicorn imports
app.main, whose routers reach app.core.security first, and the app failed to
start. Each case runs in a fresh interpreter so pytest's import order can't
mask it.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "first",
    ["app.main", "app.core.security", "app.core.deps", "app.db", "app.routers.admin", "app.models"],
)
def test_app_imports_with_any_module_first(first: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {first}; import app.main"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "JWT_SECRET": "x" * 40, "DEV_MODE": "false"},
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-2000:]
