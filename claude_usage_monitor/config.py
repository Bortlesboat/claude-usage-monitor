"""Configuration and path resolution."""

import os
import platform
from pathlib import Path


def get_claude_dir() -> Path:
    """Get the Claude Code config directory (~/.claude/)."""
    if platform.system() == "Windows":
        return Path(os.environ.get("USERPROFILE", "~")) / ".claude"
    return Path.home() / ".claude"


def get_stats_path() -> Path:
    """Get the path to stats-cache.json."""
    return get_claude_dir() / "stats-cache.json"


# Refresh interval in milliseconds
REFRESH_INTERVAL_MS = 30_000

# Colors
COLOR_BG = "#1a1a2e"
COLOR_TEXT = "#e0e0e0"
COLOR_ACCENT = "#d4a574"
COLOR_BAR_BG = "#2d2d44"
COLOR_BAR_FILL = "#d4a574"
COLOR_BAR_HIGH = "#e07a5f"
COLOR_SECONDARY = "#8888aa"
