"""System tray icon and menu for Claude Usage Monitor."""

from __future__ import annotations

import threading
import webbrowser

from PIL import Image, ImageDraw, ImageFont

from .stats import UsageSnapshot, _format_tokens, load_stats


def create_icon_image(text: str = "CC", color: str = "#d4a574") -> Image.Image:
    """Create a simple tray icon with text overlay."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded background
    draw.rounded_rectangle([2, 2, size - 2, size - 2], radius=12, fill="#1a1a2e")

    # Draw text
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except OSError:
            font = ImageFont.load_default()

    # Parse hex color
    c = color.lstrip("#")
    rgb = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - 2
    draw.text((x, y), text, fill=rgb, font=font)

    return img


def build_menu_items(snap: UsageSnapshot) -> list[tuple]:
    """Build menu items from usage snapshot. Returns list of (label, callback_or_None)."""
    items = []

    if snap.error:
        items.append((f"Error: {snap.error}", None))
        items.append(("---", None))
        items.append(("Quit", "quit"))
        return items

    # Header
    items.append(("Claude Code Usage Monitor", None))
    items.append(("---", None))

    # Today
    items.append((f"Today: {snap.today_messages} messages, {snap.today_sessions} sessions", None))
    items.append((f"Today tokens: {_format_tokens(snap.today_tokens)}", None))
    items.append(("---", None))

    # This week
    items.append((f"This week: {snap.week_messages} messages, {_format_tokens(snap.week_tokens)} tokens", None))
    items.append(("---", None))

    # All time
    items.append((f"All time: {snap.total_sessions} sessions, {snap.total_messages:,} messages", None))
    items.append((f"Total tokens: {_format_tokens(snap.total_tokens)}", None))
    items.append((f"Days active: {snap.days_active}", None))
    items.append((f"Avg daily: {snap.avg_daily_messages:.0f} messages", None))
    items.append(("---", None))

    # Model breakdown
    items.append(("Models:", None))
    for model in sorted(snap.models.values(), key=lambda m: m.total_tokens, reverse=True):
        items.append((f"  {model.display_name}: {_format_tokens(model.total_tokens)} tokens", None))
    items.append(("---", None))

    # Peak hour
    if snap.peak_hour is not None:
        h = snap.peak_hour
        label = f"{h}:00" if h >= 10 else f"0{h}:00"
        items.append((f"Peak hour: {label}", None))

    # Longest session
    if snap.longest_session_messages:
        dur_min = snap.longest_session_duration_sec // 60
        dur_h = dur_min // 60
        dur_m = dur_min % 60
        items.append((f"Longest session: {snap.longest_session_messages} msgs ({dur_h}h {dur_m}m)", None))

    items.append(("---", None))
    items.append(("Open Dashboard", "dashboard"))
    items.append(("Check for Updates", "update"))
    items.append(("Refresh", "refresh"))
    items.append(("Quit", "quit"))

    return items
