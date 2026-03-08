"""Parse and compute usage stats from Claude Code session files."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import UserConfig, get_claude_dir, get_stats_path, load_config


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
    input_tokens: int = 0
    output_tokens: int = 0
    cache_tokens: int = 0
    tokens_by_model: dict[str, int] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        if self.tokens_by_model:
            return sum(self.tokens_by_model.values())
        return self.input_tokens + self.output_tokens + self.cache_tokens


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
    def total_output_tokens(self) -> int:
        return sum(m.output_tokens for m in self.models.values())

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
    def today_output_tokens(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        for day in reversed(self.daily_tokens):
            if day.date == today:
                return day.output_tokens
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

    def period_output_tokens(self, config: UserConfig) -> int:
        """Output tokens used in the current billing period (what Anthropic meters)."""
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        return sum(d.output_tokens for d in self.daily_tokens if d.date >= cutoff)

    def period_total_tokens(self, config: UserConfig) -> int:
        """All tokens (input + output + cache) in the current billing period."""
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        return sum(d.total_tokens for d in self.daily_tokens if d.date >= cutoff)

    def period_messages(self, config: UserConfig) -> int:
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        return sum(d.messages for d in self.daily_activity if d.date >= cutoff)

    def period_sessions(self, config: UserConfig) -> int:
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        return sum(d.sessions for d in self.daily_activity if d.date >= cutoff)

    def usage_pct(self, config: UserConfig) -> float:
        """Percentage of plan output token limit used this period."""
        limit = config.output_token_limit
        if limit <= 0:
            return 0.0
        return (self.period_output_tokens(config) / limit) * 100

    def daily_budget(self, config: UserConfig) -> int:
        """Recommended daily output token budget to spread usage evenly."""
        remaining = max(config.output_token_limit - self.period_output_tokens(config), 0)
        days_left = max(config.days_until_reset, 1)
        return remaining // days_left

    def projected_usage_pct(self, config: UserConfig) -> float:
        """Projected usage % at end of period based on current pace."""
        elapsed = max(config.days_elapsed, 1)
        total_days = max(config.days_in_period, 1)
        daily_rate = self.period_output_tokens(config) / elapsed
        projected = daily_rate * total_days
        limit = config.output_token_limit
        if limit <= 0:
            return 0.0
        return (projected / limit) * 100

    def period_model_output(self, config: UserConfig) -> dict[str, int]:
        """Output tokens by model for the current period."""
        cutoff = config.current_period_start.strftime("%Y-%m-%d")
        result: dict[str, int] = {}
        for day in self.daily_tokens:
            if day.date >= cutoff:
                for model, tokens in day.tokens_by_model.items():
                    result[model] = result.get(model, 0) + tokens
        return result


def _format_tokens(n: int) -> str:
    """Format token count to human-readable string."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _scan_session_files() -> UsageSnapshot:
    """Scan all session JSONL files for real usage data."""
    claude_dir = get_claude_dir()
    projects_dir = claude_dir / "projects"

    if not projects_dir.exists():
        return UsageSnapshot(error="No projects directory found")

    # Aggregate by day
    daily_data: dict[str, dict] = defaultdict(lambda: {
        "messages": 0, "sessions": set(),
        "input_tokens": 0, "output_tokens": 0,
        "cache_read": 0, "cache_create": 0,
        "model_output": defaultdict(int),
        "model_total": defaultdict(int),
        "hours": defaultdict(int),
    })
    model_agg: dict[str, ModelStats] = {}
    total_messages = 0
    total_sessions = 0
    longest_msgs = 0
    first_date = None

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for f in project_dir.glob("*.jsonl"):
            session_id = f.stem
            session_msg_count = 0

            # Fall back to file mtime if no per-message timestamps
            try:
                fallback_mtime = datetime.fromtimestamp(f.stat().st_mtime)
            except OSError:
                fallback_mtime = datetime.now()

            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        try:
                            d = json.loads(line)
                            msg = d.get("message", {})
                            if not isinstance(msg, dict) or "usage" not in msg:
                                continue

                            # Use per-message timestamp when available
                            ts_str = d.get("timestamp")
                            if ts_str:
                                try:
                                    msg_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).astimezone()
                                except (ValueError, TypeError):
                                    msg_time = fallback_mtime
                            else:
                                msg_time = fallback_mtime

                            day_str = msg_time.strftime("%Y-%m-%d")
                            hour = msg_time.hour

                            session_msg_count += 1
                            u = msg["usage"]
                            inp = u.get("input_tokens", 0)
                            out = u.get("output_tokens", 0)
                            cr = u.get("cache_read_input_tokens", 0)
                            cc = u.get("cache_creation_input_tokens", 0)
                            model = msg.get("model", "unknown")

                            dd = daily_data[day_str]
                            dd["messages"] += 1
                            dd["sessions"].add(session_id)
                            dd["input_tokens"] += inp
                            dd["output_tokens"] += out
                            dd["cache_read"] += cr
                            dd["cache_create"] += cc
                            dd["model_output"][model] += out
                            dd["model_total"][model] += inp + out + cr + cc
                            dd["hours"][hour] += 1

                            # Aggregate model stats
                            if model not in model_agg:
                                model_agg[model] = ModelStats(name=model)
                            ms = model_agg[model]
                            ms.input_tokens += inp
                            ms.output_tokens += out
                            ms.cache_read += cr
                            ms.cache_creation += cc

                            if first_date is None or day_str < first_date:
                                first_date = day_str
                        except (json.JSONDecodeError, KeyError):
                            pass
            except OSError:
                continue

            if session_msg_count > 0:
                total_messages += session_msg_count
                total_sessions += 1
                longest_msgs = max(longest_msgs, session_msg_count)

    # Build snapshot
    snap = UsageSnapshot(
        total_sessions=total_sessions,
        total_messages=total_messages,
        first_session_date=first_date or "",
        last_computed_date=datetime.now().strftime("%Y-%m-%d"),
        models=model_agg,
        longest_session_messages=longest_msgs,
    )

    # Build daily lists
    hour_totals: dict[int, int] = defaultdict(int)
    for day_str in sorted(daily_data):
        dd = daily_data[day_str]
        snap.daily_activity.append(DailyActivity(
            date=day_str,
            messages=dd["messages"],
            sessions=len(dd["sessions"]),
        ))
        snap.daily_tokens.append(DailyActivity(
            date=day_str,
            input_tokens=dd["input_tokens"],
            output_tokens=dd["output_tokens"],
            cache_tokens=dd["cache_read"] + dd["cache_create"],
            tokens_by_model=dict(dd["model_total"]),
        ))
        for h, c in dd["hours"].items():
            hour_totals[h] += c

    snap.hour_counts = dict(hour_totals)
    return snap


def load_stats(path: Path | None = None) -> UsageSnapshot:
    """Load usage stats — scans session JSONL files for live data."""
    return _scan_session_files()
