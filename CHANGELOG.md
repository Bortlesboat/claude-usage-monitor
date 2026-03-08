# Changelog

## 3.0.0

- Simplified: removed speculative predictions and plan comparison features
- Added disk cache shared between tray and dashboard (fixes 429 rate limit errors)
- Added thread safety for background refresh
- Added PID sentinel to single-instance lock (prevents false lockouts from PID recycling)
- Added stats caching (30s TTL) to reduce filesystem scanning overhead
- Fixed `subprocess.CREATE_NO_WINDOW` crash on macOS/Linux
- Fixed scroll binding accumulation on dashboard refresh
- Fixed platform-specific font handling (Segoe UI / Helvetica Neue / DejaVu Sans)
- Fixed `astimezone()` crash on naive datetimes
- Cleaned up codebase for readability

## 2.4.0

- Published to PyPI as `claude-usage-tray`
- Added usage predictions (pace indicator, projected %, safe budgets)

## 2.3.0

- UX overhaul: autostart toggle, desktop shortcuts, async launch
- Rewrote README for current features
- Fixed version comparison in self-updater

## 2.2.0

- Added plan comparison (see usage on Pro/5x/20x side by side)

## 2.1.0

- UI overhaul: polished dark theme, remaining %, reset times with local timezone

## 2.0.0

- Live usage from Anthropic's OAuth API — real rate limit windows (5-hour, 7-day)
- Color-coded tray icon based on utilization
- Dashboard with gauges, stats cards, daily chart

## 1.x

- Initial release: session JSONL scanning, basic tray menu, plan tracking
- Self-update feature
- Dashboard window with token stats
