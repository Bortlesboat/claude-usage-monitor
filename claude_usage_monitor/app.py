"""Main application - system tray icon with usage monitoring."""

from __future__ import annotations

import sys
import threading
import time

import pystray
from pystray import MenuItem, Menu

from .dashboard import open_dashboard
from .stats import UsageSnapshot, _format_tokens, load_stats
from .tray import build_menu_items, create_icon_image


class ClaudeUsageApp:
    """System tray application for monitoring Claude Code usage."""

    def __init__(self):
        self.snap: UsageSnapshot = load_stats()
        self.icon: pystray.Icon | None = None
        self._running = True

    def _make_menu(self) -> Menu:
        """Build the pystray menu from current snapshot."""
        items = build_menu_items(self.snap)
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
            else:
                menu_items.append(MenuItem(label, None, enabled=False))

        return Menu(*menu_items)

    def _get_icon_text(self) -> str:
        """Get short text for the icon based on today's usage."""
        msgs = self.snap.today_messages
        if msgs >= 1000:
            return f"{msgs // 1000}K"
        if msgs > 0:
            return str(msgs)
        return "CC"

    def _refresh(self, icon=None, item=None):
        """Reload stats from disk."""
        self.snap = load_stats()
        if self.icon:
            self.icon.icon = create_icon_image(self._get_icon_text())
            self.icon.menu = self._make_menu()
            title = f"Claude Code - {self.snap.today_messages} msgs today"
            self.icon.title = title

    def _open_dashboard(self, icon=None, item=None):
        """Open the dashboard window."""
        self._refresh()
        open_dashboard(self.snap)

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
            title=f"Claude Code - {self.snap.today_messages} msgs today",
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
