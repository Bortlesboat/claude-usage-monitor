"""Which icon the tray shows.

With no live reading the icon used to fall back to a percentage estimated from
local logs against the configured plan. That estimate routinely runs past 100,
and anything over 100 draws as the red "!!" tile, so an expired session looked
exactly like genuinely running out of quota.
"""

import os

import pytest

# pystray picks a GUI backend at import time, which fails on a headless runner.
os.environ.setdefault("PYSTRAY_BACKEND", "dummy")

from claude_usage_monitor import app, tray  # noqa: E402
from claude_usage_monitor.api_usage import LiveUsage, UsageWindow  # noqa: E402


class _LocalEstimateOverLimit:
    """A snapshot whose local-log estimate is well past the plan. Real machines
    reach this easily; the one this was found on reported 129.8%."""

    error = None

    def usage_pct(self, config):
        return 129.8


def _tray(live):
    instance = object.__new__(app.ClaudeUsageApp)
    instance.live = live
    instance.snap = _LocalEstimateOverLimit()
    instance.config = None
    return instance


@pytest.fixture
def icons(monkeypatch):
    """Record which icon builder was asked for, without drawing anything."""
    calls = {"usage": [], "plain": []}
    monkeypatch.setattr(app, "get_icon_for_usage",
                        lambda pct: calls["usage"].append(pct) or "usage")
    monkeypatch.setattr(app, "create_icon_image",
                        lambda text, **kw: calls["plain"].append((text, kw)) or "plain")
    return calls


class TestIconState:

    def test_live_reading_uses_the_busiest_window(self, icons):
        live = LiveUsage(windows=[UsageWindow("five_hour", "5-Hour", 13.0),
                                  UsageWindow("seven_day", "7-Day", 6.0)])
        assert _tray(live)._icon_image() == "usage"
        assert icons["usage"] == [13.0]
        assert icons["plain"] == []

    def test_failed_fetch_does_not_fall_back_to_the_local_estimate(self, icons):
        live = LiveUsage(windows=[], error="Session expired — run 'claude' in terminal to re-authenticate")
        _tray(live)._icon_image()
        # The bug: this used to be get_icon_for_usage(129.8), drawn as "!!".
        assert icons["usage"] == []
        assert icons["plain"] == [(app.ICON_ERROR,
                                   {"bg_color": app.NO_DATA_BG, "text_color": app.NO_DATA_FG})]

    def test_rate_limit_is_an_error_too(self, icons):
        _tray(LiveUsage(windows=[], error="API rate limited — will retry next refresh"))._icon_image()
        assert icons["usage"] == []
        assert icons["plain"][0][0] == app.ICON_ERROR

    def test_before_the_first_fetch_is_pending_not_an_error(self, icons):
        _tray(None)._icon_image()
        assert icons["usage"] == []
        assert icons["plain"][0][0] == app.ICON_PENDING

    def test_a_response_with_no_windows_is_not_a_reading(self, icons):
        _tray(LiveUsage(windows=[]))._icon_image()
        assert icons["usage"] == []
        assert icons["plain"][0][0] == app.ICON_ERROR

    def test_pending_and_error_look_different(self):
        assert app.ICON_ERROR != app.ICON_PENDING


class TestNoDataTileColour:

    @pytest.mark.parametrize("pct", [5, 60, 95, 130])
    def test_grey_tile_matches_no_threshold_tile(self, pct):
        """If it borrowed a threshold colour it would read as a usage level."""
        no_data = app.create_icon_image(app.ICON_ERROR, bg_color=app.NO_DATA_BG,
                                        text_color=app.NO_DATA_FG).convert("RGB")
        spot = (32, 10)  # inside the rounded tile, above the glyph
        assert no_data.getpixel(spot) != tray.get_icon_for_usage(pct).convert("RGB").getpixel(spot)
