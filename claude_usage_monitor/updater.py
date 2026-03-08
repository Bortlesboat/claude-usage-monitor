"""Check for updates and install from PyPI."""

from __future__ import annotations

import subprocess
import sys
import urllib.request

from . import __version__

REPO = "Bortlesboat/claude-usage-monitor"
PYPI_PACKAGE = "claude-usage-tray"
_PYPROJECT_URLS = [
    f"https://raw.githubusercontent.com/{REPO}/master/pyproject.toml",
    f"https://raw.githubusercontent.com/{REPO}/main/pyproject.toml",
]


def get_remote_version():
    text = None
    for url in _PYPROJECT_URLS:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                text = resp.read().decode("utf-8")
            break
        except Exception:
            continue
    if text is None:
        return None
    try:
        in_project = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "[project]":
                in_project = True
            elif stripped.startswith("[") and in_project:
                break  # Entered a different section
            elif in_project and stripped.startswith("version"):
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None


def _parse_version(v):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0,)


def check_update():
    remote = get_remote_version()
    if remote is None:
        return False, __version__, "unknown"
    available = _parse_version(remote) > _parse_version(__version__)
    return available, __version__, remote


def do_update():
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", PYPI_PACKAGE],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return True, "Updated successfully. Restart the app to use the new version."
        return False, "Update failed. Try manually: pip install --upgrade claude-usage-tray"
    except Exception:
        return False, "Update failed. Try manually: pip install --upgrade claude-usage-tray"
