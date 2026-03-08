"""CLI mode — print usage stats to stdout and exit."""

from __future__ import annotations

import sys
from datetime import date

from . import __version__
from .api_usage import LiveUsage, fetch_live_usage
from .config import load_config
from .stats import UsageSnapshot, format_tokens, load_stats


def _fmt_number(n: int) -> str:
    """Format integer with comma separators."""
    return f"{n:,}"


def cli_report() -> int:
    """Fetch stats, print summary, return exit code (0=ok, 1=error)."""
    config = load_config()
    snap: UsageSnapshot = load_stats()

    # Attempt live usage fetch (non-fatal if it fails)
    live: LiveUsage | None = None
    try:
        live = fetch_live_usage()
        if live.error:
            live = None
    except Exception:
        live = None

    lines: list[str] = []
    lines.append(f"Claude Code Usage Monitor v{__version__}")
    lines.append("")

    # --- Rate limits (live API) ---
    if live and live.windows:
        lines.append("Rate Limits:")
        # Determine label width for alignment
        max_label = max(len(w.label) for w in live.windows)
        for w in sorted(live.windows, key=lambda w: w.name):
            remaining = max(100 - w.utilization, 0)
            reset_str = f"resets in {w.resets_in_display}" if w.resets_in_display != "unknown" else ""
            label = f"{w.label}:".ljust(max_label + 1)
            lines.append(
                f"  {label}  {w.utilization:5.1f}% used ({remaining:5.1f}% remaining)  {reset_str}"
            )
        if live.extra_usage_enabled and live.extra_usage_utilization is not None:
            lines.append(f"  Extra Usage: {live.extra_usage_utilization:.1f}% used")
        lines.append("")
    else:
        lines.append("Rate Limits: unavailable (sign in to Claude Code first)")
        lines.append("")

    # --- Session stats ---
    if snap.error:
        lines.append(f"Session Stats: {snap.error}")
    else:
        today_msgs = snap.today_messages
        today_out = snap.today_output_tokens
        today_sess = snap.today_sessions

        lines.append(
            f"Today: {_fmt_number(today_msgs)} messages | "
            f"{format_tokens(today_out)} output tokens | "
            f"{today_sess} sessions"
        )

        period_start = config.current_period_start
        period_label = period_start.strftime("%b %d")
        period_msgs = snap.period_messages(config)
        period_out = snap.period_output_tokens(config)
        period_sess = snap.period_sessions(config)

        lines.append(
            f"This Period (since {period_label}): "
            f"{_fmt_number(period_msgs)} messages | "
            f"{format_tokens(period_out)} output tokens | "
            f"{period_sess} sessions"
        )

        # Budget line
        limit = config.output_token_limit
        if limit > 0:
            pct = snap.usage_pct(config)
            daily_budget = snap.daily_budget(config)
            days_left = config.days_until_reset
            lines.append(
                f"Budget: {pct:.1f}% of {format_tokens(limit)} limit used | "
                f"{format_tokens(daily_budget)}/day for {days_left} days remaining"
            )

        lines.append("")

        # All-time one-liner
        lines.append(
            f"All Time: {_fmt_number(snap.total_messages)} messages | "
            f"{format_tokens(snap.total_output_tokens)} output tokens | "
            f"{snap.total_sessions} sessions | "
            f"{snap.days_active} days active"
        )

    # Print everything
    output = "\n".join(lines)
    print(output)
    return 0
