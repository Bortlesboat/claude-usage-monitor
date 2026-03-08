"""System tray app."""

from __future__ import annotations

import atexit
import os
import sys
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

    def __init__(self):
        self._first_launch = not (get_claude_dir() / "usage-monitor-config.json").exists()
        self.config = load_config()
        self.snap: UsageSnapshot = load_stats()
        self.live: LiveUsage = LiveUsage(windows=[])
        self.icon: pystray.Icon | None = None
        self._running = True
        self._notified_thresholds: set[str] = set()

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
                menu_items.append(MenuItem("Open Dashboard", self._open_dashboard, default=True))
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

    def _get_primary_pct(self):
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
            from datetime import datetime
            updated = datetime.now().strftime("%I:%M %p").lstrip("0")
            return " | ".join(parts) + f" (updated {updated})"
        return f"Claude Usage Monitor v{__version__}"

    def _update_icon(self):
        if not self.icon:
            return
        pct = self._get_primary_pct()
        self.icon.icon = get_icon_for_usage(pct)
        self.icon.menu = self._make_menu()
        self.icon.title = self._get_title()

    def _refresh(self, icon=None, item=None):
        self.config = load_config()
        self.snap = load_stats()
        try:
            self.live = fetch_live_usage()
        except Exception:
            pass
        self._update_icon()
        self._check_thresholds()

    def _notify(self, message, title="Claude Usage Monitor"):
        if not self.icon:
            return
        try:
            self.icon.notify(message, title)
        except Exception:
            pass  # some pystray backends don't support this

    def _check_thresholds(self):
        if not self.icon or not self.live or self.live.error or not self.live.windows:
            return
        for w in self.live.windows:
            for threshold in (80, 90):
                key = f"{w.name}_{threshold}"
                if w.utilization >= threshold and key not in self._notified_thresholds:
                    self._notified_thresholds.add(key)
                    self._notify(
                        f"{w.label} at {w.utilization:.0f}% — resets in {w.resets_in_display}",
                        "Usage Warning",
                    )
                elif w.utilization < threshold and key in self._notified_thresholds:
                    self._notified_thresholds.discard(key)  # Reset after window resets

    def _open_dashboard(self, icon=None, item=None):
        self._refresh()
        open_dashboard()

    def _toggle_autostart(self, icon=None, item=None):
        success, message = toggle_autostart()
        self._notify(message)
        self._update_icon()

    def _create_shortcut(self, icon=None, item=None):
        success, message = create_desktop_shortcut()
        self._notify(message)

    def _open_github(self, icon=None, item=None):
        webbrowser.open(GITHUB_URL)

    def _check_update(self, icon=None, item=None):
        def _run():
            if self.icon:
                self.icon.title = "Checking for updates..."

            available, current, remote = check_update()

            if not available:
                self._notify(f"You're on the latest version (v{current})")
                if self.icon:
                    self.icon.title = self._get_title()
                return

            self._notify(f"Updating v{current} \u2192 v{remote}...")

            success, message = do_update()

            self._notify(message)
            if self.icon:
                self.icon.title = self._get_title()

        threading.Thread(target=_run, daemon=True).start()

    def _quit(self, icon=None, item=None):
        self._running = False
        if self.icon:
            self.icon.stop()

    def _initial_api_fetch(self):
        try:
            self.live = fetch_live_usage()
            self._update_icon()
        except Exception:
            pass

        if self._first_launch:
            self._notify("Right-click the tray icon to see your Claude usage stats.")

    def _auto_refresh_loop(self):
        while self._running:
            time.sleep(60)
            if self._running:
                try:
                    self._refresh()
                except Exception:
                    pass

    def run(self):
        pct = self._get_primary_pct()
        self.icon = pystray.Icon(
            name="claude-usage",
            icon=get_icon_for_usage(pct),
            title=f"Claude Usage Monitor v{__version__} — loading...",
            menu=self._make_menu(),
        )

        threading.Thread(target=self._initial_api_fetch, daemon=True).start()
        threading.Thread(target=self._auto_refresh_loop, daemon=True).start()

        self.icon.run()


def _check_single_instance():
    lock_path = get_claude_dir() / "usage-monitor.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_path.exists():
            try:
                old_pid = int(lock_path.read_text().strip())
                if sys.platform == "win32":
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.OpenProcess(0x1000, False, old_pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                        return False
                else:
                    os.kill(old_pid, 0)
                    return False
            except (ValueError, OSError, ProcessLookupError):
                pass
        lock_path.write_text(str(os.getpid()))
        atexit.register(lambda: lock_path.unlink(missing_ok=True))
        return True
    except OSError:
        return True


def main():
    if not _check_single_instance():
        print("Claude Usage Monitor is already running.", file=sys.stderr)
        sys.exit(0)
    app = ClaudeUsageApp()
    app.run()


if __name__ == "__main__":
    main()
