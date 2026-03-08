"""Tests for pure logic functions in claude_usage_monitor."""

from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from claude_usage_monitor.stats import format_tokens
from claude_usage_monitor.api_usage import _parse_reset_time, UsageWindow
from claude_usage_monitor.updater import _parse_version
from claude_usage_monitor.config import UserConfig


# ---------------------------------------------------------------------------
# stats.format_tokens
# ---------------------------------------------------------------------------

class TestFormatTokens:
    def test_zero(self):
        assert format_tokens(0) == "0"

    def test_small(self):
        assert format_tokens(500) == "500"

    def test_just_under_1k(self):
        assert format_tokens(999) == "999"

    def test_1k(self):
        assert format_tokens(1000) == "1.0K"

    def test_thousands(self):
        assert format_tokens(1500) == "1.5K"

    def test_tens_of_thousands(self):
        assert format_tokens(50000) == "50.0K"

    def test_just_under_1m(self):
        assert format_tokens(999_999) == "1000.0K"

    def test_millions(self):
        assert format_tokens(1_500_000) == "1.5M"

    def test_billions(self):
        assert format_tokens(2_500_000_000) == "2.5B"

    def test_exact_million(self):
        assert format_tokens(1_000_000) == "1.0M"

    def test_exact_billion(self):
        assert format_tokens(1_000_000_000) == "1.0B"


# ---------------------------------------------------------------------------
# api_usage._parse_reset_time
# ---------------------------------------------------------------------------

class TestParseResetTime:
    def test_z_suffix(self):
        result = _parse_reset_time("2026-03-08T12:00:00Z")
        assert result is not None
        assert result.tzinfo is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 8
        assert result.hour == 12

    def test_plus_utc_offset(self):
        result = _parse_reset_time("2026-03-08T12:00:00+00:00")
        assert result is not None
        assert result.tzinfo is not None
        assert result.hour == 12

    def test_none_input(self):
        assert _parse_reset_time(None) is None

    def test_empty_string(self):
        assert _parse_reset_time("") is None

    def test_invalid_string(self):
        assert _parse_reset_time("not-a-date") is None

    def test_naive_datetime_gets_utc(self):
        # A datetime string without timezone info should get UTC assigned
        result = _parse_reset_time("2026-03-08T12:00:00")
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_non_utc_offset(self):
        result = _parse_reset_time("2026-03-08T12:00:00+05:30")
        assert result is not None
        assert result.hour == 12
        assert result.utcoffset() == timedelta(hours=5, minutes=30)


# ---------------------------------------------------------------------------
# api_usage.UsageWindow.resets_in_display
# ---------------------------------------------------------------------------

class TestUsageWindowResetsInDisplay:
    def test_no_reset_time(self):
        w = UsageWindow(name="test", label="Test", utilization=50.0, resets_at=None)
        assert w.resets_in_display == "unknown"

    def test_minutes_only(self):
        future = datetime.now(timezone.utc) + timedelta(minutes=45)
        w = UsageWindow(name="test", label="Test", utilization=50.0, resets_at=future)
        display = w.resets_in_display
        assert display.endswith("m")
        assert "h" not in display
        assert "d" not in display

    def test_hours_and_minutes(self):
        future = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
        w = UsageWindow(name="test", label="Test", utilization=50.0, resets_at=future)
        display = w.resets_in_display
        assert "h" in display
        assert "m" in display
        assert "d" not in display

    def test_days_and_hours(self):
        future = datetime.now(timezone.utc) + timedelta(days=2, hours=5)
        w = UsageWindow(name="test", label="Test", utilization=50.0, resets_at=future)
        display = w.resets_in_display
        assert display.startswith("2d")
        assert "h" in display

    def test_past_time_shows_zero(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        w = UsageWindow(name="test", label="Test", utilization=50.0, resets_at=past)
        assert w.resets_in_display == "0m"

    def test_exactly_one_hour(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1, seconds=30)
        w = UsageWindow(name="test", label="Test", utilization=50.0, resets_at=future)
        display = w.resets_in_display
        assert "1h" in display


# ---------------------------------------------------------------------------
# updater._parse_version
# ---------------------------------------------------------------------------

class TestParseVersion:
    def test_normal_version(self):
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_two_part_version(self):
        assert _parse_version("3.0") == (3, 0)

    def test_single_digit(self):
        assert _parse_version("5") == (5,)

    def test_version_with_whitespace(self):
        assert _parse_version("  1.2.3  ") == (1, 2, 3)

    def test_empty_string(self):
        assert _parse_version("") == (0,)

    def test_invalid_string(self):
        assert _parse_version("abc") == (0,)

    def test_none_input(self):
        assert _parse_version(None) == (0,)

    def test_comparison(self):
        assert _parse_version("2.0.0") > _parse_version("1.9.9")
        assert _parse_version("1.0.1") > _parse_version("1.0.0")
        assert _parse_version("3.0.0") == _parse_version("3.0.0")


# ---------------------------------------------------------------------------
# config.UserConfig date properties
# ---------------------------------------------------------------------------

class TestUserConfigDateProperties:
    """Test date-dependent properties using unittest.mock.patch on date.today()."""

    def _make_config(self, billing_day=15):
        return UserConfig(plan="pro", billing_day=billing_day)

    def test_current_period_start_after_billing_day(self):
        # Today is the 20th, billing day 15 -> period started on the 15th this month
        fake_today = date(2026, 3, 20)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            result = cfg.current_period_start
            assert result == date(2026, 3, 15)

    def test_current_period_start_before_billing_day(self):
        # Today is the 5th, billing day 15 -> period started on the 15th last month
        fake_today = date(2026, 3, 5)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            result = cfg.current_period_start
            assert result == date(2026, 2, 15)

    def test_current_period_start_on_billing_day(self):
        # Today IS the billing day -> period started today
        fake_today = date(2026, 3, 15)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            result = cfg.current_period_start
            assert result == date(2026, 3, 15)

    def test_current_period_start_january_rollback(self):
        # Today is Jan 5, billing day 15 -> should roll back to Dec 15 previous year
        fake_today = date(2026, 1, 5)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            result = cfg.current_period_start
            assert result == date(2025, 12, 15)

    def test_next_reset_before_billing_day(self):
        # Today is 5th, billing day 15 -> next reset is the 15th this month
        fake_today = date(2026, 3, 5)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            result = cfg.next_reset
            assert result == date(2026, 3, 15)

    def test_next_reset_after_billing_day(self):
        # Today is 20th, billing day 15 -> next reset is 15th next month
        fake_today = date(2026, 3, 20)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            result = cfg.next_reset
            assert result == date(2026, 4, 15)

    def test_next_reset_december_rollover(self):
        # Today is Dec 20, billing day 15 -> next reset Jan 15 next year
        fake_today = date(2026, 12, 20)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            result = cfg.next_reset
            assert result == date(2027, 1, 15)

    def test_days_until_reset(self):
        fake_today = date(2026, 3, 10)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            assert cfg.days_until_reset == 5

    def test_days_until_reset_on_billing_day(self):
        # On billing day, next reset is next month
        fake_today = date(2026, 3, 15)
        with patch("claude_usage_monitor.config.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            cfg = self._make_config(billing_day=15)
            # On billing day, today.day >= day, so next_reset = next month
            assert cfg.days_until_reset == 31  # March 15 -> April 15

    def test_billing_day_clamped_to_28(self):
        cfg = UserConfig(billing_day=31)
        assert cfg.billing_day == 28

    def test_billing_day_clamped_to_1(self):
        cfg = UserConfig(billing_day=0)
        assert cfg.billing_day == 1

    def test_output_token_limit_default_pro(self):
        cfg = UserConfig(plan="pro")
        assert cfg.output_token_limit == 5_000_000

    def test_output_token_limit_custom_override(self):
        cfg = UserConfig(plan="pro", custom_output_limit=10_000_000)
        assert cfg.output_token_limit == 10_000_000

    def test_plan_label(self):
        cfg = UserConfig(plan="max_5x")
        assert cfg.plan_label == "Max 5x ($100/mo)"

    def test_unknown_plan_defaults_to_pro(self):
        cfg = UserConfig(plan="nonexistent")
        assert cfg.plan_info == {"label": "Pro ($20/mo)", "output_tokens": 5_000_000}
