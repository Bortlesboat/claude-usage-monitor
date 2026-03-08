# Claude Code Usage Monitor

A system tray app that shows your **real-time Claude Code usage** — rate limits, reset timers, plan comparison, and token stats — all from a single icon.

[![PyPI](https://img.shields.io/pypi/v/claude-usage-tray.svg)](https://pypi.org/project/claude-usage-tray/)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

## Why?

Claude Code doesn't show you how much of your rate limit you've used or when it resets. This app lives in your system tray and gives you that info at a glance — so you never get surprised by a rate limit wall.

## Features

- **Color-coded tray icon** — green/yellow/red based on usage level, shows current % number
- **Live rate limits** from Anthropic's API — 5-hour and 7-day windows with reset countdowns
- **Usage predictions** — pace indicator (well under / on track / burning fast), projected % at reset, safe hourly token budget
- **Plan comparison** — see what your usage would look like on Pro ($20), Max 5x ($100), or Max 20x ($200)
- **Dashboard** with gauges, predictions, stats cards, daily output chart, and plan verdict
- **Auto-detect your plan** from Claude Code credentials (Pro, Max 5x, Max 20x)
- **Start on Login** toggle — runs silently in the background
- **Desktop shortcut** creation (one click)
- **Self-update** — check for updates and install from the tray menu
- **Cross-platform** — Windows, macOS, Linux
- **No API key required** — uses your existing Claude Code OAuth session
- **Auto-refresh** every 60 seconds

## What You See

### System Tray

The icon shows your current usage percentage with color coding:
- **Green** (< 50%) — plenty of headroom
- **Yellow** (50-80%) — moderate usage
- **Red** (> 80%) — approaching limit

Right-click for quick stats:

```
5-Hour:  42% used  (58% left)  • resets in 2h 14m
7-Day:   38% used  (62% left)  • resets in 4d 11h
Pace: comfortable — 297.6K/hr budget
──────────────────────────────────────────
Today:  89 msgs  • 1.2M output  • 4 sessions
Since Mar 01:  3.8M output (12.4M total)  • 412 msgs
──────────────────────────────────────────
Open Dashboard
──────────────────────────────────────────
Start on Login  (off)
Create Desktop Shortcut
──────────────────────────────────────────
Check for Updates
GitHub / Help
Refresh
Quit
```

### Dashboard

Click "Open Dashboard" for a detailed breakdown:

- **Rate limit gauges** — big percentage with progress bar, remaining %, reset time (with local time)
- **Predictions** — pace status per window, projected usage at reset, time to limit warning, safe hourly budget vs current rate
- **Session stats** — today and billing period messages, output tokens, sessions
- **Daily output chart** — bar chart for the current billing period
- **Plan comparison** — simulates your usage on each plan tier with progress bars and a verdict on whether your current plan is worth it
- **All-time stats** — sessions, messages, days active, peak hour

## Quick Start

### Option 1: pip from PyPI (recommended)

```bash
pip install claude-usage-tray
claude-usage
```

### Option 2: pipx (isolated environment)

```bash
pipx install claude-usage-tray
claude-usage
```

### Option 3: pip from GitHub (latest dev)

```bash
pip install git+https://github.com/Bortlesboat/claude-usage-monitor.git
python -m claude_usage_monitor
```

### Option 4: Clone and run

```bash
git clone https://github.com/Bortlesboat/claude-usage-monitor.git
cd claude-usage-monitor
pip install .
python -m claude_usage_monitor
```

### First Launch

1. Make sure you've signed in to [Claude Code](https://docs.anthropic.com/en/docs/claude-code) at least once (`claude` in terminal)
2. Run the monitor — the icon appears in your system tray
3. Right-click the icon to see your stats
4. Use "Start on Login" to run it automatically at startup

## How It Works

The app uses two data sources:

| Source | What it provides |
|--------|-----------------|
| **Anthropic OAuth API** | Real-time rate limit windows (5-hour, 7-day), utilization %, reset times |
| **Session JSONL files** (`~/.claude/projects/`) | Token counts by model, daily activity, session history |

Your OAuth token is read from `~/.claude/.credentials.json` (created when you sign in to Claude Code). No API keys or extra configuration needed.

### Configuration

On first run, the app auto-detects your plan from Claude Code's credentials. Config is saved at `~/.claude/usage-monitor-config.json`:

```json
{
  "plan": "max_20x",
  "billing_day": 1
}
```

- `plan`: `free`, `pro`, `max_5x`, or `max_20x`
- `billing_day`: day of month your billing cycle resets (1-28)

## Requirements

- Python 3.10+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and signed in
- Works on **Windows**, **macOS**, and **Linux**

### Linux dependencies

```bash
# Ubuntu/Debian
sudo apt install python3-tk libappindicator3-1

# Fedora
sudo dnf install python3-tkinter libappindicator-gtk3
```

## Troubleshooting

### `claude-usage` command not found (Windows)

Windows Store Python installs scripts to a directory not on PATH. Use `python -m claude_usage_monitor` instead, or install with `pipx` which handles PATH automatically.

### "Sign in to Claude Code first"

Run `claude` in your terminal and complete the sign-in flow. The monitor needs the OAuth token created during sign-in.

### "Session expired"

Your Claude Code session has expired. Run `claude` in terminal to re-authenticate.

### No data showing

Make sure you've used Claude Code at least once — session files are created in `~/.claude/projects/` after your first conversation.

### Tray icon not visible (Linux)

You may need a system tray / app indicator extension. On GNOME, install the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/).

## Updating

Click "Check for Updates" in the tray menu, or manually:

```bash
pip install --upgrade claude-usage-tray
```

## License

MIT
