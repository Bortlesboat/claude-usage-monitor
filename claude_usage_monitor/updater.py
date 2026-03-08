"""Self-update from GitHub."""

from __future__ import annotations

import subprocess
import sys
import urllib.request

from . import __version__

REPO = "Bortlesboat/claude-usage-monitor"
PYPI_PACKAGE = "claude-usage-tray"
PYPROJECT_URL = f"https://raw.githubusercontent.com/{REPO}/master/pyproject.toml"


def get_remote_version() -> str | None:
    """Fetch the version from the remote pyproject.toml."""
    try:
        req = urllib.request.Request(PYPROJECT_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode("utf-8")
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


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse version string to comparable tuple."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0,)


def check_update() -> tuple[bool, str, str]:
    """Check if an update is available. Returns (available, current, remote)."""
    remote = get_remote_version()
    if remote is None:
        return False, __version__, "unknown"
    available = _parse_version(remote) > _parse_version(__version__)
    return available, __version__, remote


def do_update() -> tuple[bool, str]:
    """Run pip install to update from PyPI. Returns (success, message)."""
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
