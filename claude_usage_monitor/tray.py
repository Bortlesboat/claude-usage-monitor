"""System tray icon and menu for Claude Usage Monitor."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .api_usage import LiveUsage
from .autostart import is_autostart_enabled
from .config import UserConfig, load_config
from .predictions import generate_predictions
from .stats import UsageSnapshot, _format_tokens


def create_icon_image(text: str = "CC", bg_color: str = "#1a1a2e",
                      text_color: str = "#d4a574") -> Image.Image:
    """Create a tray icon with text and optional color-coded background."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([2, 2, size - 2, size - 2], radius=12, fill=bg_color)

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        try:
            # macOS
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        except OSError:
            try:
                # Linux
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            except OSError:
                font = ImageFont.load_default()

    c = text_color.lstrip("#")
    rgb = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - 2
    draw.text((x, y), text, fill=rgb, font=font)

    return img


def get_icon_for_usage(pct: float) -> Image.Image:
    """Create icon with color reflecting usage level."""
    if pct >= 80:
        bg = "#3d1f1f"
        color = "#e07a5f"
    elif pct >= 50:
        bg = "#3d351f"
        color = "#f2cc8f"
    else:
        bg = "#1a1a2e"
        color = "#d4a574"

    if pct >= 100:
        text = "!!"
    elif pct >= 10:
        text = f"{pct:.0f}"
    else:
        text = f"{pct:.0f}%"

    return create_icon_image(text, bg_color=bg, text_color=color)


def build_menu_items(snap: UsageSnapshot, config: UserConfig | None = None,
                     live: LiveUsage | None = None) -> list[tuple]:
    """Build menu items. Returns list of (label, action_or_None)."""
    cfg = config or load_config()
    items = []

    if snap.error:
        items.append((f"Error: {snap.error}", None))
        items.append(("---", None))
        items.append(("Quit", "quit"))
        return items

    # ── Live rate limits ──
    if live and not live.error and live.windows:
        for w in sorted(live.windows, key=lambda w: w.name):
            if w.utilization == 0 and "sonnet" in w.name.lower():
                continue
            remaining = max(100 - w.utilization, 0)
            reset = w.resets_in_display
            items.append((f"{w.label}:  {w.utilization:.0f}% used  ({remaining:.0f}% left)  \u2022  resets in {reset}", None))
        # Pace prediction summary
        preds = generate_predictions(live)
        if preds.primary:
            items.append((preds.tray_summary, None))
        items.append(("---", None))
    elif live and live.error:
        items.append((f"{live.error}", None))
        items.append(("---", None))

    # ── Today ──
    items.append((f"Today:  {snap.today_messages:,} msgs  \u2022  {_format_tokens(snap.today_output_tokens)} output  \u2022  {snap.today_sessions} sessions", None))

    # ── This billing cycle ──
    used = snap.period_output_tokens(cfg)
    total = snap.period_total_tokens(cfg)
    since = cfg.current_period_start.strftime("%b %d")
    items.append((f"Since {since}:  {_format_tokens(used)} output  ({_format_tokens(total)} total)  \u2022  {snap.period_messages(cfg):,} msgs", None))
    items.append(("---", None))

    # ── Actions ──
    items.append(("Open Dashboard", "dashboard"))
    items.append(("---", None))

    # Autostart toggle
    autostart_label = "Start on Login  (on)" if is_autostart_enabled() else "Start on Login  (off)"
    items.append((autostart_label, "toggle_autostart"))
    items.append(("Create Desktop Shortcut", "create_shortcut"))
    items.append(("---", None))

    items.append(("Check for Updates", "update"))
    items.append(("GitHub / Help", "github"))
    items.append(("Refresh", "refresh"))
    items.append(("---", None))
    items.append((f"v{__version__}", None))
    items.append(("Quit", "quit"))

    return items
