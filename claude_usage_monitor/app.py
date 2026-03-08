"""Main application - system tray icon with usage monitoring."""

from __future__ import annotations

import os
import sys
import subprocess
import threading
import time
import webbrowser

import pystray
from pystray import MenuItem, Menu

from . import __version__
from .api_usage import LiveUsage, fetch_live_usage
from .autostart import create_desktop_shortcut, toggle_autostart
from .config import get_claude_dir, load_config
from .dashboard import open_dashboard
from .stats import UsageSnapshot, _format_tokens, load_stats
from .tray import build_menu_items, get_icon_for_usage
from .updater import check_update, do_update

GITHUB_URL = "https://github.com/Bortlesboat/claude-usage-monitor"


class ClaudeUsageApp:
    """System tray application for monitoring Claude Code usage."""

    def __init__(self):
        self.config = load_config()
        self.snap: UsageSnapshot = load_stats()
        self.live: LiveUsage = LiveUsage(windows=[])  # Populated async
        self.icon: pystray.Icon | None = None
        self._running = True
        self._first_launch = not (get_claude_dir() / "usage-monitor-config.json").exists()

    def _make_menu(self) -> Menu:
        items = build_menu_items(self.snap, self.config, self.live)
        menu_items = []

        for label, action in items:
            if label == "---":
                menu_items.append(Menu.SEPARATOR)
            elif action == "quit":
                menu_items.append(MenuItem("Quit", self._quit))
            elif action == "refresh":
                menu_items.append(MenuItem("Refresh", self._refresh))
            elif action == "dashboard":
                menu_items.append(MenuItem("Open Dashboard", self._open_dashboard))
            elif action == "update":
                menu_items.append(MenuItem("Check for Updates", self._check_update))
            elif action == "toggle_autostart":
                menu_items.append(MenuItem(label, self._toggle_autostart))
            elif action == "create_shortcut":
                menu_items.append(MenuItem(label, self._create_shortcut))
            elif action == "github":
                menu_items.append(MenuItem(label, self._open_github))
            else:
                menu_items.append(MenuItem(label, None, enabled=False))

        return Menu(*menu_items)

    def _get_primary_pct(self) -> float:
        """Get the primary usage % for icon display."""
        if self.live and self.live.primary_window:
            return self.live.primary_window.utilization
        return self.snap.usage_pct(self.config)

    def _get_title(self) -> str:
        if self.live and not self.live.error and self.live.windows:
            parts = []
            for w in sorted(self.live.windows, key=lambda w: w.name):
                if w.utilization == 0 and "sonnet" in w.name.lower():
                    continue
                parts.append(f"{w.label}: {w.utilization:.0f}%")
            return " | ".join(parts)
        return f"Claude Usage Monitor v{__version__}"

    def _update_icon(self):
        """Update icon image, menu, and title."""
        if not self.icon:
            return
        pct = self._get_primary_pct()
        self.icon.icon = get_icon_for_usage(pct)
        self.icon.menu = self._make_menu()
        self.icon.title = self._get_title()

    def _refresh(self, icon=None, item=None):
        """Reload everything."""
        self.config = load_config()
        self.snap = load_stats()
        try:
            self.live = fetch_live_usage()
        except Exception:
            pass
        self._update_icon()

    def _open_dashboard(self, icon=None, item=None):
        self._refresh()
        open_dashboard()

    def _toggle_autostart(self, icon=None, item=None):
        success, message = toggle_autostart()
        if self.icon:
            self.icon.notify(message, "Claude Usage Monitor")
            self._update_icon()

    def _create_shortcut(self, icon=None, item=None):
        success, message = create_desktop_shortcut()
        if self.icon:
            self.icon.notify(message, "Claude Usage Monitor")

    def _open_github(self, icon=None, item=None):
        webbrowser.open(GITHUB_URL)

    def _check_update(self, icon=None, item=None):
        def _run():
            if self.icon:
                self.icon.title = "Checking for updates..."

            available, current, remote = check_update()

            if not available:
                if self.icon:
                    self.icon.notify(
                        f"You're on the latest version (v{current})",
                        "Claude Usage Monitor",
                    )
                    self.icon.title = self._get_title()
                return

            if self.icon:
                self.icon.notify(f"Updating v{current} \u2192 v{remote}...", "Claude Usage Monitor")

            success, message = do_update()

            if self.icon:
                self.icon.notify(message, "Claude Usage Monitor")
                self.icon.title = self._get_title()

        threading.Thread(target=_run, daemon=True).start()

    def _quit(self, icon=None, item=None):
        self._running = False
        if self.icon:
            self.icon.stop()

    def _initial_api_fetch(self):
        """Fetch API data in background so the icon appears instantly."""
        try:
            self.live = fetch_live_usage()
            self._update_icon()
        except Exception:
            pass

        # First-launch notification
        if self._first_launch and self.icon:
            self.icon.notify(
                "Right-click the tray icon to see your Claude usage stats.",
                "Claude Usage Monitor",
            )

    def _auto_refresh_loop(self):
        """Background thread that refreshes periodically."""
        while self._running:
            time.sleep(60)
            if self._running:
                try:
                    self._refresh()
                except Exception:
                    pass

    def run(self):
        """Start the system tray application."""
        pct = self._get_primary_pct()
        self.icon = pystray.Icon(
            name="claude-usage",
            icon=get_icon_for_usage(pct),
            title=f"Claude Usage Monitor v{__version__} — loading...",
            menu=self._make_menu(),
        )

        # Fetch API data in background (don't block startup)
        threading.Thread(target=self._initial_api_fetch, daemon=True).start()

        # Periodic refresh
        threading.Thread(target=self._auto_refresh_loop, daemon=True).start()

        self.icon.run()


def main():
    """Entry point."""
    app = ClaudeUsageApp()
    app.run()


if __name__ == "__main__":
    main()
