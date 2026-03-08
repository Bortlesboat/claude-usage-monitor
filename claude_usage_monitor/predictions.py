"""Usage predictions — projected time to limit, pace indicators, safe budgets.

Pure math on live usage windows + historical daily token data. No ML libraries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .api_usage import LiveUsage, UsageWindow
from .stats import UsageSnapshot, _format_tokens


@dataclass
class WindowPrediction:
    """Prediction data for a single rate limit window."""

    window: UsageWindow
    pace: str  # "well under" | "on track" | "burning fast"
    pace_color: str  # "green" | "yellow" | "red"
    hours_to_limit: float | None  # None if won't hit limit before reset
    safe_hourly_budget: int  # output tokens/hr to stay under limit until reset
    current_hourly_rate: int  # estimated tokens/hr being consumed now
    projected_at_reset: float  # projected utilization % at reset time

    @property
    def safe_budget_display(self) -> str:
        return _format_tokens(self.safe_hourly_budget) + "/hr"

    @property
    def hours_to_limit_display(self) -> str:
        if self.hours_to_limit is None:
            return "won't hit"
        h = self.hours_to_limit
        if h < 1:
            return f"{max(int(h * 60), 1)}m"
        if h < 24:
            return f"{h:.1f}h"
        d = int(h // 24)
        remaining_h = h % 24
        return f"{d}d {remaining_h:.0f}h"

    @property
    def pace_summary(self) -> str:
        """One-line summary for tray menu."""
        if self.pace == "burning fast":
            return f"burning fast — ~{self.hours_to_limit_display} to limit"
        if self.pace == "on track":
            return f"on track — {self.safe_budget_display} budget"
        return f"comfortable — {self.safe_budget_display} budget"


@dataclass
class UsagePredictions:
    """Predictions for all active rate windows."""

    predictions: list[WindowPrediction]

    @property
    def primary(self) -> WindowPrediction | None:
        """The most concerning prediction (highest projected usage)."""
        if not self.predictions:
            return None
        return max(self.predictions, key=lambda p: p.projected_at_reset)

    @property
    def tray_summary(self) -> str:
        """One-line summary for system tray."""
        p = self.primary
        if not p:
            return "Pace: no data"
        return f"Pace: {p.pace_summary}"


def _estimate_window_duration_hours(window: UsageWindow) -> float:
    """Estimate total window duration based on window name."""
    name = window.name.lower()
    if "five_hour" in name:
        return 5.0
    if "seven_day" in name:
        return 7 * 24.0
    # Fallback: guess from reset time
    if window.resets_at:
        mins = window.resets_in_minutes
        if mins is not None:
            # Rough heuristic: if 80% used and 1hr left, window is probably ~5hrs
            # But we can't know for sure, so just use remaining time as lower bound
            return max(mins / 60, 1.0)
    return 5.0  # default assumption


def _estimate_current_rate(window: UsageWindow) -> float:
    """Estimate current utilization rate as %/hour.

    Uses the utilization already consumed and the elapsed time in the window.
    """
    total_hours = _estimate_window_duration_hours(window)

    if window.resets_at:
        remaining_mins = window.resets_in_minutes
        if remaining_mins is not None:
            remaining_hours = remaining_mins / 60
            elapsed_hours = max(total_hours - remaining_hours, 0.1)
            return window.utilization / elapsed_hours

    # No reset time — assume halfway through window
    elapsed_hours = max(total_hours / 2, 0.1)
    return window.utilization / elapsed_hours


def predict_window(window: UsageWindow) -> WindowPrediction:
    """Generate predictions for a single usage window."""
    pct = window.utilization
    remaining_pct = max(100.0 - pct, 0.0)
    total_hours = _estimate_window_duration_hours(window)

    # Time remaining in window
    if window.resets_at:
        remaining_mins = window.resets_in_minutes or 0
        remaining_hours = remaining_mins / 60
    else:
        remaining_hours = total_hours / 2  # assume halfway

    # Current consumption rate (% per hour)
    rate_pct_per_hour = _estimate_current_rate(window)

    # Projected utilization at reset
    if rate_pct_per_hour > 0:
        projected_at_reset = pct + rate_pct_per_hour * remaining_hours
    else:
        projected_at_reset = pct

    # Hours until hitting 100%
    if rate_pct_per_hour > 0 and remaining_pct > 0:
        hours_to_limit = remaining_pct / rate_pct_per_hour
        # If we'd hit it after the window resets, we won't actually hit it
        if hours_to_limit > remaining_hours:
            hours_to_limit = None
    else:
        hours_to_limit = None

    # Safe hourly budget: spread remaining capacity evenly over remaining time
    # Express as tokens/hr (approximate: assume 100% = window's token limit)
    # Since we don't know absolute token limits, express as % budget and convert
    # to a rough token estimate using typical limits:
    #   5-hour window: ~2M output tokens, 7-day: ~50M output tokens
    token_limit = _estimate_token_limit(window)

    if remaining_hours > 0:
        remaining_tokens = int((remaining_pct / 100) * token_limit)
        safe_hourly_budget = int(remaining_tokens / remaining_hours)
    else:
        safe_hourly_budget = 0

    # Current hourly rate in tokens
    current_hourly_rate = int((rate_pct_per_hour / 100) * token_limit)

    # Pace classification
    if projected_at_reset >= 95:
        pace = "burning fast"
        pace_color = "red"
    elif projected_at_reset >= 70:
        pace = "on track"
        pace_color = "yellow"
    else:
        pace = "well under"
        pace_color = "green"

    return WindowPrediction(
        window=window,
        pace=pace,
        pace_color=pace_color,
        hours_to_limit=hours_to_limit,
        safe_hourly_budget=max(safe_hourly_budget, 0),
        current_hourly_rate=max(current_hourly_rate, 0),
        projected_at_reset=projected_at_reset,
    )


def _estimate_token_limit(window: UsageWindow) -> int:
    """Rough token limit estimate per window type.

    These are approximate — Anthropic doesn't publish exact numbers.
    Used only for displaying safe budgets in human-readable token counts.
    """
    name = window.name.lower()
    if "five_hour" in name:
        # ~2M output tokens per 5-hour window (Max 20x estimate)
        return 2_000_000
    if "opus" in name:
        # 7-day Opus limit tends to be lower
        return 20_000_000
    if "seven_day" in name:
        # ~50M output tokens per 7-day window
        return 50_000_000
    return 5_000_000  # conservative default


def generate_predictions(live: LiveUsage | None = None) -> UsagePredictions:
    """Generate predictions for all active rate limit windows."""
    if not live or live.error or not live.windows:
        return UsagePredictions(predictions=[])

    predictions = []
    for w in live.windows:
        if w.utilization == 0 and "sonnet" in w.name.lower():
            continue  # Skip empty Sonnet windows (matches dashboard filtering)
        predictions.append(predict_window(w))

    return UsagePredictions(predictions=predictions)
