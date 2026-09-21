"""Tray updates must reach AppKit on the main thread.

macOS 27 traps when an NSStatusItem is touched from any other thread, so the
tray's worker threads hand their icon, menu, title and notification updates to
`_on_main_thread`. CI has no macOS runner, so these tests fake the platform and
stand in for PyObjC rather than exercising AppKit itself.
"""

import os
import sys
import threading
import types
from unittest.mock import patch

# pystray picks a GUI backend at import time, which fails on a headless runner.
os.environ.setdefault("PYSTRAY_BACKEND", "dummy")

from claude_usage_monitor import app  # noqa: E402


def _on_worker(fn):
    """Call fn on a fresh thread and wait, so it is definitely not the main one."""
    t = threading.Thread(target=fn)
    t.start()
    t.join()


class _QueueingAppHelper:
    """Stands in for PyObjCTools.AppHelper: records callAfter instead of running it."""

    def __init__(self):
        self.queued = []

    def callAfter(self, fn, *args, **kwargs):
        self.queued.append(lambda: fn(*args, **kwargs))

    def drain(self):
        while self.queued:
            self.queued.pop(0)()


def _fake_pyobjc(helper):
    tools = types.ModuleType("PyObjCTools")
    tools.AppHelper = helper
    return patch.dict(sys.modules, {"PyObjCTools": tools, "PyObjCTools.AppHelper": helper})


class TestOnMainThread:
    def test_runs_inline_off_macos_even_from_a_worker_thread(self):
        ran = []
        with patch.object(app.sys, "platform", "linux"):
            _on_worker(lambda: app._on_main_thread(lambda: ran.append(True)))
        assert ran == [True]

    def test_runs_inline_on_macos_main_thread(self):
        ran = []
        helper = _QueueingAppHelper()
        with patch.object(app.sys, "platform", "darwin"), _fake_pyobjc(helper):
            app._on_main_thread(lambda: ran.append(True))
        assert ran == [True]
        assert helper.queued == []

    def test_queues_on_macos_worker_thread_instead_of_running_inline(self):
        ran = []
        helper = _QueueingAppHelper()
        with patch.object(app.sys, "platform", "darwin"), _fake_pyobjc(helper):
            _on_worker(lambda: app._on_main_thread(lambda: ran.append(True)))
            assert ran == [], "touched AppKit from a worker thread"
            assert len(helper.queued) == 1
            helper.drain()
        assert ran == [True]


class _RecordingIcon:
    def __init__(self):
        self.assigned = []
        self.notified = []

    def __setattr__(self, name, value):
        if name in ("icon", "menu", "title"):
            self.assigned.append(name)
        object.__setattr__(self, name, value)

    def notify(self, message, title=None):
        self.notified.append((message, title))


def _bare_app(icon):
    tray = object.__new__(app.ClaudeUsageApp)
    tray.icon = icon
    return tray


class TestTrayUpdatesFromWorkerThreads:
    def test_update_icon_defers_every_assignment_to_the_main_thread(self):
        icon = _RecordingIcon()
        tray = _bare_app(icon)
        helper = _QueueingAppHelper()
        with patch.object(app.sys, "platform", "darwin"), _fake_pyobjc(helper), \
                patch.object(tray, "_icon_image", return_value="image"), \
                patch.object(tray, "_make_menu", return_value="menu", create=True), \
                patch.object(tray, "_get_title", return_value="title", create=True):
            _on_worker(tray._update_icon)
            assert icon.assigned == []
            helper.drain()
        assert icon.assigned == ["icon", "menu", "title"]
        assert (icon.icon, icon.menu, icon.title) == ("image", "menu", "title")

    def test_notify_defers_to_the_main_thread(self):
        icon = _RecordingIcon()
        tray = _bare_app(icon)
        helper = _QueueingAppHelper()
        with patch.object(app.sys, "platform", "darwin"), _fake_pyobjc(helper):
            _on_worker(lambda: tray._notify("hello", "Usage Warning"))
            assert icon.notified == []
            helper.drain()
        assert icon.notified == [("hello", "Usage Warning")]

    def test_set_title_defers_to_the_main_thread(self):
        icon = _RecordingIcon()
        tray = _bare_app(icon)
        helper = _QueueingAppHelper()
        with patch.object(app.sys, "platform", "darwin"), _fake_pyobjc(helper):
            _on_worker(lambda: tray._set_title("Checking for updates..."))
            assert icon.assigned == []
            helper.drain()
        assert icon.title == "Checking for updates..."
