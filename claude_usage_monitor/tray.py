"""System tray icon and menu for Claude Usage Monitor."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .config import UserConfig, load_config
from .stats import UsageSnapshot, _format_tokens


def create_icon_image(text: str = "CC", color: str = "#d4a574") -> Image.Image:
    """Create a simple tray icon with text overlay."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([2, 2, size - 2, size - 2], radius=12, fill="#1a1a2e")

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except OSError:
            font = ImageFont.load_default()

    c = color.lstrip("#")
    rgb = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - 2
    draw.text((x, y), text, fill=rgb, font=font)

    return img


def build_menu_items(snap: UsageSnapshot, config: UserConfig | None = None) -> list[tuple]:
    """Build menu items from usage snapshot. Returns list of (label, callback_or_None)."""
    cfg = config or load_config()
    items = []

    if snap.error:
        items.append((f"Error: {snap.error}", None))
        items.append(("---", None))
        items.append(("Quit", "quit"))
        return items

    # Plan usage header
    pct = snap.usage_pct(cfg)
    used = snap.period_tokens(cfg)
    limit = cfg.output_token_limit
    remaining = max(limit - used, 0)

    items.append((f"{cfg.plan_label}  —  {pct:.1f}% used", None))
    items.append((f"{_format_tokens(used)} / {_format_tokens(limit)} tokens", None))
    items.append(("---", None))

    # Reset
    days_left = cfg.days_until_reset
    items.append((f"Resets in {days_left} day{'s' if days_left != 1 else ''} ({cfg.next_reset.strftime('%b %d')})", None))
    items.append((f"Tokens remaining: {_format_tokens(remaining)}", None))
    items.append((f"Daily budget: {_format_tokens(snap.daily_budget(cfg))}/day", None))
    items.append(("---", None))

    # Today
    items.append((f"Today: {snap.today_messages} msgs, {_format_tokens(snap.today_tokens)} tokens", None))
    items.append(("---", None))

    # Projected
    proj = snap.projected_usage_pct(cfg)
    if proj > 100:
        items.append((f"Projected: {proj:.0f}% (over limit!)", None))
    else:
        items.append((f"Projected: {proj:.0f}% at end of period", None))
    items.append(("---", None))

    # All time (compact)
    items.append((f"All time: {snap.total_sessions} sessions, {snap.total_messages:,} msgs", None))
    items.append(("---", None))

    items.append(("Open Dashboard", "dashboard"))
    items.append(("Check for Updates", "update"))
    items.append(("Refresh", "refresh"))
    items.append(("Quit", "quit"))

    return items
