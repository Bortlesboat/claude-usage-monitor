"""Tkinter dashboard window showing live usage vs plan limits.

Can be run standalone: python -m claude_usage_monitor.dashboard
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from .api_usage import LiveUsage, UsageWindow, fetch_live_usage
from .config import (
    COLOR_ACCENT,
    COLOR_BAR_BG,
    COLOR_BAR_FILL,
    COLOR_BAR_HIGH,
    COLOR_BG,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_SECONDARY,
    COLOR_TEXT,
    COLOR_YELLOW,
    UserConfig,
    load_config,
)
from .stats import UsageSnapshot, _format_tokens, load_stats


def _pct_color(pct: float) -> str:
    if pct < 60:
        return COLOR_GREEN
    if pct < 85:
        return COLOR_YELLOW
    return COLOR_RED


class DashboardWindow:
    """Dashboard focused on live usage windows and plan allowance."""

    def __init__(self, snap: UsageSnapshot | None = None, config: UserConfig | None = None,
                 live: LiveUsage | None = None):
        self.snap = snap or load_stats()
        self.config = config or load_config()
        self.live = live or fetch_live_usage()
        self.root: tk.Tk | None = None

    def show(self):
        self.root = tk.Tk()
        self.root.title("Claude Code Usage Monitor")
        self.root.configure(bg=COLOR_BG)
        self.root.geometry("540x720")
        self.root.resizable(True, True)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass
        self._build_ui()
        self.root.mainloop()

    def _build_ui(self):
        root = self.root
        snap = self.snap
        cfg = self.config
        live = self.live

        # Scrollable frame
        canvas = tk.Canvas(root, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=COLOR_BG)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        padx = 16

        # ── Title ──
        tk.Label(frame, text="Claude Code Usage", fg=COLOR_ACCENT, bg=COLOR_BG,
                 font=("Segoe UI", 18, "bold")).pack(padx=padx, pady=(16, 2))
        tk.Label(frame, text=f"Plan: {cfg.plan_label}", fg=COLOR_SECONDARY, bg=COLOR_BG,
                 font=("Segoe UI", 10)).pack(padx=padx, pady=(0, 8))

        # ── Live Usage Windows (PRIMARY SECTION) ──
        if live and not live.error and live.windows:
            self._section_label(frame, "Usage Limits (Live)")

            for w in sorted(live.windows, key=lambda w: w.name):
                self._usage_gauge(frame, w)
        elif live and live.error:
            self._section_label(frame, "Usage Limits")
            tk.Label(frame, text=f"Could not fetch: {live.error}", fg=COLOR_RED, bg=COLOR_BG,
                     font=("Segoe UI", 10)).pack(padx=20, pady=4)

        # ── Today ──
        self._section_label(frame, "Today")
        today_frame = tk.Frame(frame, bg=COLOR_BG)
        today_frame.pack(fill="x", padx=padx, pady=(4, 4))

        cards = [
            ("Messages", f"{snap.today_messages:,}"),
            ("Output tokens", _format_tokens(snap.today_output_tokens)),
            ("Sessions", str(snap.today_sessions)),
        ]
        for i, (title, value) in enumerate(cards):
            card = tk.Frame(today_frame, bg="#2d2d44", padx=12, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            today_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=title, fg=COLOR_SECONDARY, bg="#2d2d44",
                     font=("Segoe UI", 9)).pack()
            tk.Label(card, text=value, fg=COLOR_TEXT, bg="#2d2d44",
                     font=("Segoe UI", 13, "bold")).pack()

        # ── Period Summary ──
        self._section_label(frame, "This Billing Period")
        period_frame = tk.Frame(frame, bg=COLOR_BG)
        period_frame.pack(fill="x", padx=padx, pady=(4, 4))

        used_output = snap.period_output_tokens(cfg)
        period_cards = [
            ("Output used", _format_tokens(used_output)),
            ("Messages", f"{snap.period_messages(cfg):,}"),
            ("Sessions", str(snap.period_sessions(cfg))),
        ]
        for i, (title, value) in enumerate(period_cards):
            card = tk.Frame(period_frame, bg="#2d2d44", padx=12, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            period_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=title, fg=COLOR_SECONDARY, bg="#2d2d44",
                     font=("Segoe UI", 9)).pack()
            tk.Label(card, text=value, fg=COLOR_TEXT, bg="#2d2d44",
                     font=("Segoe UI", 13, "bold")).pack()

        # ── Daily Output Chart ──
        self._section_label(frame, "Daily Output Tokens (This Period)")
        self._daily_chart(frame, snap, cfg)

        # ── All Time ──
        self._section_label(frame, "All Time")
        stats = [
            f"Sessions: {snap.total_sessions}  |  Messages: {snap.total_messages:,}  |  Days active: {snap.days_active}",
            f"Total output: {_format_tokens(snap.total_output_tokens)}  |  Total all: {_format_tokens(snap.total_tokens)}",
        ]
        if snap.peak_hour is not None:
            stats.append(f"Peak hour: {snap.peak_hour:02d}:00")

        for line in stats:
            tk.Label(frame, text=line, fg=COLOR_SECONDARY, bg=COLOR_BG,
                     font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=20, pady=1)

        # Footer
        tk.Label(frame, text=f"Config: ~/.claude/usage-monitor-config.json",
                 fg="#555577", bg=COLOR_BG, font=("Segoe UI", 8)).pack(padx=padx, pady=(16, 8))
        tk.Frame(frame, bg=COLOR_BG, height=20).pack()

    def _usage_gauge(self, parent, w: UsageWindow):
        """Draw a usage gauge for a single rate limit window."""
        pct = w.utilization
        color = _pct_color(pct)

        gauge = tk.Frame(parent, bg="#2d2d44", padx=16, pady=10)
        gauge.pack(fill="x", padx=20, pady=4)

        # Header row: label + percentage
        header = tk.Frame(gauge, bg="#2d2d44")
        header.pack(fill="x")
        tk.Label(header, text=w.label, fg=COLOR_TEXT, bg="#2d2d44",
                 font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
        tk.Label(header, text=f"{pct:.0f}%", fg=color, bg="#2d2d44",
                 font=("Segoe UI", 20, "bold"), anchor="e").pack(side="right")

        # Progress bar
        bar_outer = tk.Frame(gauge, bg=COLOR_BAR_BG, height=16)
        bar_outer.pack(fill="x", pady=(6, 4))
        bar_outer.pack_propagate(False)
        fill_w = min(pct / 100, 1.0)
        bar_inner = tk.Frame(bar_outer, bg=color)
        bar_inner.place(x=0, y=0, relheight=1.0, relwidth=fill_w)

        # Reset info
        reset_text = f"Resets in {w.resets_in_display}"
        if w.resets_at:
            local_reset = w.resets_at.astimezone()
            reset_text += f"  ({local_reset.strftime('%b %d, %I:%M %p')})"
        tk.Label(gauge, text=reset_text, fg=COLOR_SECONDARY, bg="#2d2d44",
                 font=("Segoe UI", 9), anchor="w").pack(anchor="w")

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, fg=COLOR_ACCENT, bg=COLOR_BG,
                 font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x", padx=16, pady=(12, 4))

    def _daily_chart(self, parent, snap: UsageSnapshot, cfg: UserConfig):
        """Bar chart of daily output token usage for the current billing period."""
        canvas = tk.Canvas(parent, bg=COLOR_BG, height=130, highlightthickness=0)
        canvas.pack(fill="x", padx=20, pady=4)

        cutoff = cfg.current_period_start.strftime("%Y-%m-%d")
        days = [d for d in snap.daily_tokens if d.date >= cutoff]

        if not days:
            canvas.create_text(200, 65, text="No usage data this period", fill=COLOR_SECONDARY,
                               font=("Segoe UI", 10))
            return

        canvas.update_idletasks()
        w = canvas.winfo_width() or 490
        h = 130
        margin_bottom = 25
        margin_top = 15
        chart_h = h - margin_bottom - margin_top

        max_output = max(d.output_tokens for d in days) or 1
        bar_w = max((w - 40) // max(len(days), 1) - 4, 8)

        for i, day in enumerate(days):
            x = 20 + i * (bar_w + 4)
            tokens = day.output_tokens
            bar_h = int((tokens / max_output) * chart_h)
            y = h - margin_bottom - bar_h

            canvas.create_rectangle(x, y, x + bar_w, h - margin_bottom, fill=COLOR_BAR_FILL, outline="")

            label = day.date[-2:]
            canvas.create_text(x + bar_w // 2, h - 10, text=label, fill=COLOR_SECONDARY,
                               font=("Segoe UI", 7))

            if bar_h > 15:
                canvas.create_text(x + bar_w // 2, y - 8, text=_format_tokens(tokens),
                                   fill=COLOR_TEXT, font=("Segoe UI", 7))


def open_dashboard():
    """Open dashboard as a separate process."""
    subprocess.Popen(
        [sys.executable, "-m", "claude_usage_monitor.dashboard"],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


if __name__ == "__main__":
    DashboardWindow().show()
