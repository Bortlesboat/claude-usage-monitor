"""System tray icon and menu for Claude Usage Monitor."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .api_usage import LiveUsage, fetch_live_usage
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


def build_menu_items(snap: UsageSnapshot, config: UserConfig | None = None,
                     live: LiveUsage | None = None) -> list[tuple]:
    """Build menu items from usage snapshot. Returns list of (label, callback_or_None)."""
    cfg = config or load_config()
    items = []

    if snap.error:
        items.append((f"Error: {snap.error}", None))
        items.append(("---", None))
        items.append(("Quit", "quit"))
        return items

    # ── Live API Usage (primary focus) ──
    if live and not live.error and live.windows:
        for w in sorted(live.windows, key=lambda w: w.name):
            pct = w.utilization
            reset = w.resets_in_display
            bar = _usage_bar(pct)
            items.append((f"{w.label}: {bar} {pct:.0f}%  (resets {reset})", None))
        items.append(("---", None))
    elif live and live.error:
        items.append((f"API: {live.error[:60]}", None))
        items.append(("---", None))

    # Today
    items.append((f"Today: {snap.today_messages} msgs, {_format_tokens(snap.today_output_tokens)} output", None))
    items.append(("---", None))

    # Period stats
    used_output = snap.period_output_tokens(cfg)
    items.append((f"Period: {_format_tokens(used_output)} output, {snap.period_messages(cfg):,} msgs", None))
    items.append(("---", None))

    items.append(("Open Dashboard", "dashboard"))
    items.append(("Check for Updates", "update"))
    items.append(("Refresh", "refresh"))
    items.append(("Quit", "quit"))

    return items


def _usage_bar(pct: float, width: int = 10) -> str:
    """Create a text-based usage bar like [████░░░░░░]."""
    filled = int(pct / 100 * width)
    filled = min(filled, width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"
