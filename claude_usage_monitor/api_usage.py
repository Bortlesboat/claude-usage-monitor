"""Live usage data from Anthropic's OAuth API."""

from __future__ import annotations

import json
import time as _time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import get_claude_dir


@dataclass
class UsageWindow:
    name: str
    label: str
    utilization: float  # 0-100
    resets_at: datetime | None = None

    @property
    def resets_in_minutes(self) -> int | None:
        if not self.resets_at:
            return None
        delta = self.resets_at - datetime.now(timezone.utc)
        return max(int(delta.total_seconds() / 60), 0)

    @property
    def resets_in_display(self) -> str:
        mins = self.resets_in_minutes
        if mins is None:
            return "unknown"
        if mins < 60:
            return f"{mins}m"
        hours = mins // 60
        remaining_mins = mins % 60
        if hours < 24:
            return f"{hours}h {remaining_mins}m"
        days = hours // 24
        remaining_hours = hours % 24
        return f"{days}d {remaining_hours}h"


@dataclass
class LiveUsage:
    windows: list[UsageWindow]
    error: str | None = None
    extra_usage_enabled: bool = False
    extra_usage_utilization: float | None = None

    @property
    def primary_window(self):
        if not self.windows:
            return None
        return max(self.windows, key=lambda w: w.utilization)


def _get_oauth_token():
    creds_path = get_claude_dir() / ".credentials.json"
    if not creds_path.exists():
        return None
    try:
        with open(creds_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("claudeAiOauth", {}).get("accessToken")
    except Exception:
        return None


def _parse_reset_time(iso_str):
    if not iso_str:
        return None
    try:
        # Z suffix compat for Python 3.10
        normalized = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


WINDOW_CONFIG = {
    "five_hour": "5-Hour",
    "seven_day": "7-Day",
    "seven_day_opus": "7-Day Opus",
    "seven_day_sonnet": "7-Day Sonnet",
    "seven_day_oauth_apps": "7-Day OAuth Apps",
    "seven_day_cowork": "7-Day Cowork",
}


_cache: dict[str, tuple[float, LiveUsage]] = {}
_CACHE_TTL = 60


def _disk_cache_path():
    return get_claude_dir() / "usage-monitor-cache.json"


def _write_disk_cache(result):
    """Write to disk so the dashboard subprocess doesn't need its own API call."""
    if result.error:
        return
    try:
        path = _disk_cache_path()
        data = {
            "ts": _time.time(),
            "windows": [
                {
                    "name": w.name,
                    "label": w.label,
                    "utilization": w.utilization,
                    "resets_at": w.resets_at.isoformat() if w.resets_at else None,
                }
                for w in result.windows
            ],
            "extra_usage_enabled": result.extra_usage_enabled,
            "extra_usage_utilization": result.extra_usage_utilization,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _read_disk_cache():
    try:
        path = _disk_cache_path()
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        # Only use if fresh (< 60s old)
        if _time.time() - data.get("ts", 0) > 60:
            return None
        windows = []
        for w in data.get("windows", []):
            windows.append(UsageWindow(
                name=w["name"],
                label=w["label"],
                utilization=float(w["utilization"]),
                resets_at=_parse_reset_time(w.get("resets_at")),
            ))
        return LiveUsage(
            windows=windows,
            extra_usage_enabled=data.get("extra_usage_enabled", False),
            extra_usage_utilization=data.get("extra_usage_utilization"),
        )
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def fetch_live_usage():
    now = _time.monotonic()
    if "last" in _cache:
        ts, cached = _cache["last"]
        ttl = _CACHE_TTL if not cached.error else _CACHE_TTL // 2
        if now - ts < ttl:
            return cached

    # Try disk cache first (shared with dashboard subprocess)
    disk = _read_disk_cache()
    if disk:
        _cache["last"] = (now, disk)
        return disk

    result = _fetch_live_usage_uncached()
    _cache["last"] = (now, result)
    _write_disk_cache(result)
    return result


def _fetch_live_usage_uncached():
    token = _get_oauth_token()
    if not token:
        return LiveUsage(windows=[], error="Sign in to Claude Code first (run 'claude' in terminal)")

    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://api.anthropic.com/api/oauth/usage")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")
            req.add_header("anthropic-version", "2023-06-01")
            req.add_header("anthropic-beta", "oauth-2025-04-20")

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break  # Success
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited — back off and retry
                retry_after = int(e.headers.get("Retry-After", 2 ** (attempt + 1)))
                if attempt < 2:
                    _time.sleep(min(retry_after, 10))
                    last_err = e
                    continue
                return LiveUsage(windows=[], error="API rate limited — will retry next refresh")
            if e.code == 401:
                msg = "Session expired — run 'claude' in terminal to re-authenticate"
            elif e.code == 403:
                msg = "Token doesn't have required permissions — re-authenticate Claude Code"
            else:
                msg = f"Anthropic API error (HTTP {e.code})"
            return LiveUsage(windows=[], error=msg)
        except (urllib.error.URLError, TimeoutError, OSError):
            return LiveUsage(windows=[], error="Can't reach Anthropic — local stats still work")
        except Exception:
            return LiveUsage(windows=[], error="Unexpected error fetching usage data")

    windows = []
    for key, label in WINDOW_CONFIG.items():
        window_data = data.get(key)
        if window_data is None:
            continue
        util = window_data.get("utilization")
        if util is None:
            continue
        windows.append(UsageWindow(
            name=key,
            label=label,
            utilization=float(util),
            resets_at=_parse_reset_time(window_data.get("resets_at")),
        ))

    # Extra usage
    extra = data.get("extra_usage", {})
    extra_enabled = extra.get("is_enabled", False) if extra else False
    extra_util = extra.get("utilization") if extra else None

    return LiveUsage(
        windows=windows,
        extra_usage_enabled=extra_enabled,
        extra_usage_utilization=float(extra_util) if extra_util is not None else None,
    )
