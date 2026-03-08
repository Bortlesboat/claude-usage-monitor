"""Configuration and path resolution."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path


def get_claude_dir() -> Path:
    """Get the Claude Code config directory (~/.claude/)."""
    if platform.system() == "Windows":
        return Path(os.environ.get("USERPROFILE", "~")) / ".claude"
    return Path.home() / ".claude"


def get_stats_path() -> Path:
    """Get the path to stats-cache.json."""
    return get_claude_dir() / "stats-cache.json"


def get_config_path() -> Path:
    """Get path to our config file."""
    return get_claude_dir() / "usage-monitor-config.json"


# Refresh interval in milliseconds
REFRESH_INTERVAL_MS = 30_000

# Colors
COLOR_BG = "#1a1a2e"
COLOR_TEXT = "#e0e0e0"
COLOR_ACCENT = "#d4a574"
COLOR_BAR_BG = "#2d2d44"
COLOR_BAR_FILL = "#d4a574"
COLOR_BAR_HIGH = "#e07a5f"
COLOR_GREEN = "#81b29a"
COLOR_YELLOW = "#f2cc8f"
COLOR_RED = "#e07a5f"
COLOR_SECONDARY = "#8888aa"

# Plan definitions — token limits per billing period
# These are community-estimated values; Anthropic doesn't publish exact numbers.
# Users can override with custom limits in config.
PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "label": "Free",
        "output_tokens": 500_000,
    },
    "pro": {
        "label": "Pro ($20/mo)",
        "output_tokens": 5_000_000,
    },
    "max_5x": {
        "label": "Max 5x ($100/mo)",
        "output_tokens": 25_000_000,
    },
    "max_20x": {
        "label": "Max 20x ($200/mo)",
        "output_tokens": 100_000_000,
    },
}


@dataclass
class UserConfig:
    """User's plan configuration."""
    plan: str = "pro"  # free, pro, max_5x, max_20x
    billing_day: int = 1  # Day of month billing resets (1-28)
    custom_output_limit: int | None = None  # Override plan default

    def __post_init__(self):
        # Clamp billing_day to valid range
        self.billing_day = max(1, min(self.billing_day, 28))

    @property
    def plan_info(self) -> dict:
        return PLAN_LIMITS.get(self.plan, PLAN_LIMITS["pro"])

    @property
    def output_token_limit(self) -> int:
        if self.custom_output_limit is not None:
            return self.custom_output_limit
        return self.plan_info["output_tokens"]

    @property
    def plan_label(self) -> str:
        return self.plan_info["label"]

    @property
    def current_period_start(self) -> date:
        """Get the start of the current billing period."""
        today = date.today()
        day = min(self.billing_day, 28)
        if today.day >= day:
            return today.replace(day=day)
        # Roll back to previous month
        if today.month == 1:
            return today.replace(year=today.year - 1, month=12, day=day)
        return today.replace(month=today.month - 1, day=day)

    @property
    def next_reset(self) -> date:
        """Get the next billing reset date."""
        today = date.today()
        day = min(self.billing_day, 28)
        if today.day < day:
            return today.replace(day=day)
        # Roll forward to next month
        if today.month == 12:
            return today.replace(year=today.year + 1, month=1, day=day)
        return today.replace(month=today.month + 1, day=day)

    @property
    def days_until_reset(self) -> int:
        return (self.next_reset - date.today()).days

    @property
    def days_in_period(self) -> int:
        return (self.next_reset - self.current_period_start).days

    @property
    def days_elapsed(self) -> int:
        return (date.today() - self.current_period_start).days


def detect_plan_from_credentials() -> str | None:
    """Try to detect plan from Claude's .credentials.json."""
    creds_path = get_claude_dir() / ".credentials.json"
    if not creds_path.exists():
        return None
    try:
        with open(creds_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        oauth = data.get("claudeAiOauth", {})
        tier = oauth.get("rateLimitTier", "")
        if "20x" in tier:
            return "max_20x"
        if "5x" in tier:
            return "max_5x"
        sub_type = oauth.get("subscriptionType", "")
        if sub_type == "max":
            return "max_20x"  # Default max to 20x
        if sub_type == "pro":
            return "pro"
        return None
    except Exception:
        return None


def load_config() -> UserConfig:
    """Load user config, auto-detecting plan if no config exists."""
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return UserConfig(
                plan=data.get("plan", "pro"),
                billing_day=data.get("billing_day", 1),
                custom_output_limit=data.get("custom_output_limit"),
            )
        except Exception:
            pass

    # Auto-detect from credentials
    detected = detect_plan_from_credentials()
    config = UserConfig(plan=detected or "pro")

    # Save detected config so user can edit it
    save_config(config)
    return config


def save_config(config: UserConfig):
    """Save user config to disk."""
    config_path = get_config_path()
    data = {
        "plan": config.plan,
        "billing_day": config.billing_day,
    }
    if config.custom_output_limit:
        data["custom_output_limit"] = config.custom_output_limit
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
