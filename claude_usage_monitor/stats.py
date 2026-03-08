"""Parse and compute usage stats from Claude Code's stats-cache.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import UserConfig, get_stats_path, load_config


@dataclass
class ModelStats:
    """Token usage for a single model."""
    name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read + self.cache_creation

    @property
    def display_name(self) -> str:
        """Shorten model ID to human-readable name."""
        name = self.name
        replacements = {
            "claude-opus-4-6": "Opus 4.6",
            "claude-opus-4-5": "Opus 4.5",
            "claude-sonnet-4-6": "Sonnet 4.6",
            "claude-sonnet-4-5": "Sonnet 4.5",
            "claude-haiku-4-5": "Haiku 4.5",
            "claude-3-5-sonnet": "Sonnet 3.5",
            "claude-3-5-haiku": "Haiku 3.5",
        }
        for pattern, replacement in replacements.items():
            if pattern in name:
                return replacement
        return name


@dataclass
class DailyActivity:
    """Activity stats for a single day."""
    date: str
    messages: int = 0
    sessions: int = 0
    tool_calls: int = 0
    tokens_by_model: dict[str, int] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens_by_model.values())


@dataclass
class UsageSnapshot:
    """Complete usage snapshot."""
    total_sessions: int = 0
    total_messages: int = 0
    first_session_date: str = ""
    last_computed_date: str = ""
    models: dict[str, ModelStats] = field(default_factory=dict)
    daily_activity: list[DailyActivity] = field(default_factory=list)
    daily_tokens: list[DailyActivity] = field(default_factory=list)
    hour_counts: dict[int, int] = field(default_factory=dict)
    longest_session_messages: int = 0
    longest_session_duration_sec: int = 0
    error: str | None = None

    @property
    def total_tokens(self) -> int:
        return sum(m.total_tokens for m in self.models.values())

    @property
    def today_messages(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        for day in reversed(self.daily_activity):
            if day.date == today:
                return day.messages
        return 0

    @property
    def today_tokens(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        for day in reversed(self.daily_tokens):
            if day.date == today:
                return day.total_tokens
        return 0

    @property
    def today_sessions(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        for day in reversed(self.daily_activity):
            if day.date == today:
                return day.sessions
        return 0

    @property
    def week_messages(self) -> int:
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        return sum(d.messages for d in self.daily_activity if d.date >= cutoff)

    @property
    def week_tokens(self) -> int:
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        return sum(d.total_tokens for d in self.daily_tokens if d.date >= cutoff)

    @property
    def avg_daily_messages(self) -> float:
        if not self.daily_activity:
            return 0
        return self.total_messages / len(self.daily_activity)

    @property
    def peak_hour(self) -> int | None:
        if not self.hour_counts:
            return None
        return max(self.hour_counts, key=self.hour_counts.get)

    @property
    def days_active(self) -> int:
        return len(self.daily_activity)

    def period_tokens(self, config: UserConfig) -> int:
        """Total output tokens used in the current billing period."""
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        return sum(d.total_tokens for d in self.daily_tokens if d.date >= cutoff)

    def period_messages(self, config: UserConfig) -> int:
        """Messages sent in the current billing period."""
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        return sum(d.messages for d in self.daily_activity if d.date >= cutoff)

    def period_sessions(self, config: UserConfig) -> int:
        """Sessions in the current billing period."""
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        return sum(d.sessions for d in self.daily_activity if d.date >= cutoff)

    def usage_pct(self, config: UserConfig) -> float:
        """Percentage of plan limit used this period (0-100+)."""
        limit = config.output_token_limit
        if limit <= 0:
            return 0.0
        return (self.period_tokens(config) / limit) * 100

    def daily_budget(self, config: UserConfig) -> int:
        """Recommended daily token budget to spread usage evenly."""
        remaining = max(config.output_token_limit - self.period_tokens(config), 0)
        days_left = max(config.days_until_reset, 1)
        return remaining // days_left

    def projected_usage_pct(self, config: UserConfig) -> float:
        """Projected usage % at end of period based on current pace."""
        elapsed = max(config.days_elapsed, 1)
        total_days = max(config.days_in_period, 1)
        daily_rate = self.period_tokens(config) / elapsed
        projected = daily_rate * total_days
        limit = config.output_token_limit
        if limit <= 0:
            return 0.0
        return (projected / limit) * 100


def _format_tokens(n: int) -> str:
    """Format token count to human-readable string."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def load_stats(path: Path | None = None) -> UsageSnapshot:
    """Load and parse stats-cache.json into a UsageSnapshot."""
    path = path or get_stats_path()

    if not path.exists():
        return UsageSnapshot(error=f"Stats file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return UsageSnapshot(error=f"Failed to read stats: {e}")

    snap = UsageSnapshot(
        total_sessions=data.get("totalSessions", 0),
        total_messages=data.get("totalMessages", 0),
        first_session_date=data.get("firstSessionDate", ""),
        last_computed_date=data.get("lastComputedDate", ""),
    )

    # Parse model usage
    for model_id, usage in data.get("modelUsage", {}).items():
        snap.models[model_id] = ModelStats(
            name=model_id,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            cache_read=usage.get("cacheReadInputTokens", 0),
            cache_creation=usage.get("cacheCreationInputTokens", 0),
        )

    # Parse daily activity
    for day in data.get("dailyActivity", []):
        snap.daily_activity.append(DailyActivity(
            date=day.get("date", ""),
            messages=day.get("messageCount", 0),
            sessions=day.get("sessionCount", 0),
            tool_calls=day.get("toolCallCount", 0),
        ))

    # Parse daily model tokens
    for day in data.get("dailyModelTokens", []):
        snap.daily_tokens.append(DailyActivity(
            date=day.get("date", ""),
            tokens_by_model=day.get("tokensByModel", {}),
        ))

    # Parse hour counts
    snap.hour_counts = {int(k): v for k, v in data.get("hourCounts", {}).items()}

    # Parse longest session
    longest = data.get("longestSession", {})
    snap.longest_session_messages = longest.get("messageCount", 0)
    snap.longest_session_duration_sec = longest.get("duration", 0) // 1000

    return snap
