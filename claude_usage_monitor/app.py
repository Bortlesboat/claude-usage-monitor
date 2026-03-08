"""Main application - system tray icon with usage monitoring."""

from __future__ import annotations

import os
import sys
import subprocess
import threading
import time

import pystray
from pystray import MenuItem, Menu

from . import __version__
from .config import load_config
from .dashboard import open_dashboard
from .stats import UsageSnapshot, _format_tokens, load_stats
from .tray import build_menu_items, create_icon_image
from .updater import check_update, do_update


class ClaudeUsageApp:
    """System tray application for monitoring Claude Code usage."""

    def __init__(self):
        self.config = load_config()
        self.snap: UsageSnapshot = load_stats()
        self.icon: pystray.Icon | None = None
        self._running = True

    def _make_menu(self) -> Menu:
        """Build the pystray menu from current snapshot."""
        items = build_menu_items(self.snap, self.config)
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
            else:
                menu_items.append(MenuItem(label, None, enabled=False))

        return Menu(*menu_items)

    def _get_icon_text(self) -> str:
        """Get usage % for the icon."""
        pct = self.snap.usage_pct(self.config)
        if pct >= 100:
            return "!!"
        if pct >= 10:
            return f"{pct:.0f}"
        if pct > 0:
            return f"{pct:.0f}%"
        return "CC"

    def _refresh(self, icon=None, item=None):
        """Reload stats from disk."""
        self.config = load_config()
        self.snap = load_stats()
        if self.icon:
            pct = self.snap.usage_pct(self.config)
            self.icon.icon = create_icon_image(self._get_icon_text())
            self.icon.menu = self._make_menu()
            self.icon.title = f"Claude Code - {pct:.1f}% of plan used"

    def _open_dashboard(self, icon=None, item=None):
        """Open the dashboard window as a separate process."""
        self._refresh()
        open_dashboard()

    def _check_update(self, icon=None, item=None):
        """Check for updates and apply if available."""
        def _run():
            if self.icon:
                self.icon.title = "Claude Code - Checking for updates..."

            available, current, remote = check_update()

            if not available:
                if self.icon:
                    self.icon.title = f"Claude Code v{current} - Up to date!"
                    # Show notification
                    self.icon.notify(
                        f"You're on the latest version (v{current})",
                        "Claude Usage Monitor",
                    )
                return

            # Update available — apply it
            if self.icon:
                self.icon.title = f"Claude Code - Updating v{current} -> v{remote}..."
                self.icon.notify(
                    f"Updating v{current} -> v{remote}...",
                    "Claude Usage Monitor",
                )

            success, message = do_update()

            if self.icon:
                self.icon.notify(message, "Claude Usage Monitor")
                if success:
                    self.icon.title = f"Claude Code - Updated to v{remote}! Restart to apply."
                else:
                    self.icon.title = f"Claude Code v{current} - Update failed"

        threading.Thread(target=_run, daemon=True).start()

    def _quit(self, icon=None, item=None):
        """Stop the tray icon."""
        self._running = False
        if self.icon:
            self.icon.stop()

    def _auto_refresh_loop(self):
        """Background thread that refreshes stats periodically."""
        while self._running:
            time.sleep(30)
            if self._running:
                try:
                    self._refresh()
                except Exception:
                    pass

    def run(self):
        """Start the system tray application."""
        self.icon = pystray.Icon(
            name="claude-usage",
            icon=create_icon_image(self._get_icon_text()),
            title=f"Claude Code v{__version__} - {self.snap.usage_pct(self.config):.1f}% of plan used",
            menu=self._make_menu(),
        )

        # Start auto-refresh thread
        refresh_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        refresh_thread.start()

        self.icon.run()


def main():
    """Entry point."""
    app = ClaudeUsageApp()
    app.run()


if __name__ == "__main__":
    main()
