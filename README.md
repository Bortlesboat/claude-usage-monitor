# Claude Code Usage Monitor

A lightweight system tray app that displays your [Claude Code](https://docs.anthropic.com/en/docs/claude-code) usage statistics at a glance.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

## Features

- **System tray icon** showing today's message count
- **Right-click menu** with quick stats (today, this week, all time)
- **Dashboard window** with visual charts:
  - Token usage by model (bar chart)
  - Daily message activity (last 14 days)
  - Hourly activity distribution
  - Session and token totals
- **Auto-refresh** every 30 seconds
- Reads directly from Claude Code's local `~/.claude/stats-cache.json` — no API keys needed

## Screenshots

**System Tray Menu:**
```
Claude Code Usage Monitor
─────────────────────────
Today: 142 messages, 3 sessions
Today tokens: 45.2K
─────────────────────────
This week: 1,204 messages, 2.1M tokens
─────────────────────────
All time: 66 sessions, 21,740 messages
Total tokens: 551.2M
Days active: 19
Avg daily: 1,144 messages
─────────────────────────
Models:
  Opus 4.6: 285.3M tokens
  Opus 4.5: 242.9M tokens
  Sonnet 4.5: 24.8M tokens
─────────────────────────
Open Dashboard
Refresh
Quit
```

## Quick Start

### Option 1: pipx (recommended)

[pipx](https://pipx.pypa.io/) installs Python CLI tools in isolated environments and handles PATH automatically.

```bash
# Install pipx if you don't have it
pip install pipx
pipx ensurepath

# Install claude-usage-monitor
pipx install git+https://github.com/Bortlesboat/claude-usage-monitor.git

# Run it
claude-usage
```

### Option 2: pip + python module

```bash
pip install git+https://github.com/Bortlesboat/claude-usage-monitor.git

# Run as a module (works even if scripts aren't on PATH)
python -m claude_usage_monitor
```

### Option 3: Clone and run

```bash
git clone https://github.com/Bortlesboat/claude-usage-monitor.git
cd claude-usage-monitor
pip install .
python -m claude_usage_monitor
```

## Usage

The icon appears in your system tray (bottom-right on Windows, menu bar on macOS).

- **Right-click** the icon to see quick stats
- **Click "Open Dashboard"** for the full visual breakdown with charts
- **Click "Quit"** to close

The app auto-refreshes every 30 seconds.

## Requirements

- Python 3.10+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed (reads `~/.claude/stats-cache.json`)
- Works on **Windows**, **macOS**, and **Linux** (requires a system tray / notification area)

### Linux dependencies

On Linux, you may need:

```bash
# Ubuntu/Debian
sudo apt install python3-tk libappindicator3-1

# Fedora
sudo dnf install python3-tkinter libappindicator-gtk3
```

## How it works

Claude Code stores usage statistics in `~/.claude/stats-cache.json`. This app reads that file and displays the data in a system tray icon and optional dashboard window. No network requests, no API keys — everything is local.

### Data shown

| Metric | Source |
|--------|--------|
| Messages per day/week/all-time | `dailyActivity` |
| Token usage by model | `modelUsage` |
| Daily token breakdown | `dailyModelTokens` |
| Session counts | `totalSessions` |
| Peak usage hours | `hourCounts` |
| Longest session | `longestSession` |

## Troubleshooting

### `claude-usage` command not found (Windows)

Windows Store Python installs scripts to a directory not on PATH. Use `python -m claude_usage_monitor` instead, or install with `pipx` which handles PATH automatically.

### No data showing

Make sure you've used Claude Code at least once — it creates `~/.claude/stats-cache.json` after your first session.

### Tray icon not visible (Linux)

You may need a system tray / app indicator extension. On GNOME, install the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/).

## License

MIT
