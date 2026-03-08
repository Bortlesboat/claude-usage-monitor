"""Dashboard window. Run standalone: python -m claude_usage_monitor.dashboard"""

from __future__ import annotations

import platform
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from .api_usage import LiveUsage, UsageWindow, fetch_live_usage
from .config import (
    COLOR_ACCENT,
    COLOR_BAR_BG,
    COLOR_BG,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_TEXT,
    COLOR_YELLOW,
    UserConfig,
    load_config,
)
from .stats import UsageSnapshot, _format_tokens, load_stats

# Refined palette
CARD_BG = "#242440"
GAUGE_BG = "#1e1e36"
BORDER_COLOR = "#3a3a5c"
HEADER_FG = "#f0f0f0"
SUBTLE_TEXT = "#777799"
DIVIDER = "#2d2d4a"

# Platform-appropriate font
_system = platform.system()
if _system == "Darwin":
    FONT_FAMILY = "Helvetica Neue"
elif _system == "Windows":
    FONT_FAMILY = "Segoe UI"
else:
    FONT_FAMILY = "DejaVu Sans"


def _pct_color(pct: float) -> str:
    if pct < 50:
        return COLOR_GREEN
    if pct < 80:
        return COLOR_YELLOW
    return COLOR_RED


class DashboardWindow:

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
        self.root.geometry("520x600")
        self.root.resizable(True, True)
        self.root.minsize(400, 500)
        self._canvas = None
        self._scrollbar = None
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass
        self._build_ui()
        self.root.mainloop()

    def _refresh(self):
        import threading

        def _fetch():
            snap = load_stats()
            config = load_config()
            live = fetch_live_usage()
            if self.root:
                self.root.after(0, lambda: self._apply_refresh(snap, config, live))

        threading.Thread(target=_fetch, daemon=True).start()

    def _apply_refresh(self, snap, config, live):
        self.snap = snap
        self.config = config
        self.live = live
        if self._canvas:
            self._canvas.unbind_all("<MouseWheel>")
            self._canvas.unbind_all("<Button-4>")
            self._canvas.unbind_all("<Button-5>")
            self._canvas.destroy()
        if self._scrollbar:
            self._scrollbar.destroy()
        self._build_ui()

    def _build_ui(self):
        root = self.root
        snap = self.snap
        cfg = self.config
        live = self.live

        canvas = tk.Canvas(root, bg=COLOR_BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=COLOR_BG)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        if _system == "Linux":
            canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        elif _system == "Darwin":
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-e.delta, "units"))
        else:
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._canvas = canvas
        self._scrollbar = scrollbar

        px = 18  # Consistent horizontal padding

        # Header
        header_frame = tk.Frame(frame, bg=COLOR_BG)
        header_frame.pack(fill="x", padx=px, pady=(20, 0))
        tk.Label(header_frame, text="Claude Code", fg=HEADER_FG, bg=COLOR_BG,
                 font=(FONT_FAMILY, 20, "bold"), anchor="w").pack(side="left")

        right_frame = tk.Frame(header_frame, bg=COLOR_BG)
        right_frame.pack(side="right")
        refresh_btn = tk.Button(
            right_frame, text="Refresh", fg=COLOR_ACCENT, bg=CARD_BG,
            activeforeground=HEADER_FG, activebackground="#3a3a5c",
            font=(FONT_FAMILY, 9), bd=0, padx=10, pady=2,
            cursor="hand2", command=self._refresh,
        )
        refresh_btn.pack(side="right", padx=(8, 0))
        tk.Label(right_frame, text=cfg.plan_label, fg=COLOR_ACCENT, bg=COLOR_BG,
                 font=(FONT_FAMILY, 11)).pack(side="right")

        self._divider(frame, px)

        # Rate limits
        if live and not live.error and live.windows:
            self._section_label(frame, "RATE LIMITS", px)

            for w in sorted(live.windows, key=lambda w: w.name):
                if w.utilization == 0 and "sonnet" in w.name.lower():
                    continue  # Skip empty Sonnet window to reduce clutter
                self._usage_gauge(frame, w, snap, cfg, px)

        elif live and live.error:
            self._section_label(frame, "RATE LIMITS", px)
            err_frame = tk.Frame(frame, bg=CARD_BG, padx=14, pady=10)
            err_frame.pack(fill="x", padx=px, pady=4)
            tk.Label(err_frame, text=f"Could not fetch live data: {live.error}",
                     fg=COLOR_RED, bg=CARD_BG, font=(FONT_FAMILY, 9), wraplength=460).pack(anchor="w")

        self._divider(frame, px)

        # Stats
        self._section_label(frame, "SESSION STATS", px)

        self._stat_cards(frame, px, [
            ("Today", f"{snap.today_messages:,}", "messages"),
            ("Output", _format_tokens(snap.today_output_tokens), "tokens today"),
            ("Sessions", str(snap.today_sessions), "today"),
        ])

        used_output = snap.period_output_tokens(cfg)
        used_total = snap.period_total_tokens(cfg)
        self._stat_cards(frame, px, [
            ("This Period", f"{snap.period_messages(cfg):,}", "messages"),
            ("Output", _format_tokens(used_output), f"tokens ({_format_tokens(used_total)} total)"),
            ("Sessions", str(snap.period_sessions(cfg)), f"since {cfg.current_period_start.strftime('%b %d')}"),
        ])

        self._divider(frame, px)

        # Chart
        self._section_label(frame, "DAILY OUTPUT", px)
        self._daily_chart(frame, snap, cfg, px)

        self._divider(frame, px)

        # All time
        self._section_label(frame, "ALL TIME", px)
        all_time_frame = tk.Frame(frame, bg=CARD_BG, padx=14, pady=10)
        all_time_frame.pack(fill="x", padx=px, pady=4)

        rows = [
            ("Sessions", str(snap.total_sessions)),
            ("Messages", f"{snap.total_messages:,}"),
            ("Days active", str(snap.days_active)),
            ("Output tokens", _format_tokens(snap.total_output_tokens)),
            ("Total tokens", _format_tokens(snap.total_tokens)),
        ]
        if snap.peak_hour is not None:
            rows.append(("Peak hour", f"{snap.peak_hour:02d}:00"))
        if snap.first_session_date:
            rows.append(("First session", snap.first_session_date[:10]))

        for i, (label, value) in enumerate(rows):
            row = tk.Frame(all_time_frame, bg=CARD_BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, fg=SUBTLE_TEXT, bg=CARD_BG,
                     font=(FONT_FAMILY, 9), anchor="w", width=14).pack(side="left")
            tk.Label(row, text=value, fg=COLOR_TEXT, bg=CARD_BG,
                     font=(FONT_FAMILY, 9, "bold"), anchor="e").pack(side="right")

        # Footer
        tk.Label(frame, text="Data: ~/.claude/ | Config: ~/.claude/usage-monitor-config.json",
                 fg="#44445a", bg=COLOR_BG, font=(FONT_FAMILY, 8)).pack(padx=px, pady=(16, 12))

        tk.Frame(frame, bg=COLOR_BG, height=8).pack()

    def _usage_gauge(self, parent, w, snap, cfg, px):
        pct = w.utilization
        color = _pct_color(pct)
        remaining_pct = max(100 - pct, 0)

        gauge = tk.Frame(parent, bg=CARD_BG, padx=16, pady=12)
        gauge.pack(fill="x", padx=px, pady=3)

        top = tk.Frame(gauge, bg=CARD_BG)
        top.pack(fill="x")

        left_top = tk.Frame(top, bg=CARD_BG)
        left_top.pack(side="left", anchor="w")
        tk.Label(left_top, text=w.label, fg=HEADER_FG, bg=CARD_BG,
                 font=(FONT_FAMILY, 13, "bold")).pack(anchor="w")

        right_top = tk.Frame(top, bg=CARD_BG)
        right_top.pack(side="right", anchor="e")
        tk.Label(right_top, text=f"{pct:.0f}%", fg=color, bg=CARD_BG,
                 font=(FONT_FAMILY, 24, "bold")).pack(anchor="e")
        tk.Label(right_top, text="used", fg=SUBTLE_TEXT, bg=CARD_BG,
                 font=(FONT_FAMILY, 8)).pack(anchor="e")

        bar_outer = tk.Frame(gauge, bg=COLOR_BAR_BG, height=12)
        bar_outer.pack(fill="x", pady=(8, 6))
        bar_outer.pack_propagate(False)
        fill_w = min(pct / 100, 1.0)
        if fill_w > 0:
            bar_inner = tk.Frame(bar_outer, bg=color)
            bar_inner.place(x=0, y=0, relheight=1.0, relwidth=fill_w)

        bottom = tk.Frame(gauge, bg=CARD_BG)
        bottom.pack(fill="x")

        tk.Label(bottom, text=f"{remaining_pct:.0f}% remaining", fg=SUBTLE_TEXT, bg=CARD_BG,
                 font=(FONT_FAMILY, 9), anchor="w").pack(side="left")

        reset_text = f"Resets in {w.resets_in_display}"
        if w.resets_at and w.resets_at.tzinfo:
            local_reset = w.resets_at.astimezone()
            reset_text += f"  \u2022  {local_reset.strftime('%b %d, %I:%M %p').lstrip('0')}"
        tk.Label(bottom, text=reset_text, fg=SUBTLE_TEXT, bg=CARD_BG,
                 font=(FONT_FAMILY, 9), anchor="e").pack(side="right")

    def _stat_cards(self, parent, px, cards):
        row = tk.Frame(parent, bg=COLOR_BG)
        row.pack(fill="x", padx=px, pady=3)

        for i, (title, value, subtitle) in enumerate(cards):
            card = tk.Frame(row, bg=CARD_BG, padx=12, pady=8)
            card.grid(row=0, column=i, padx=2, sticky="nsew")
            row.columnconfigure(i, weight=1)

            tk.Label(card, text=title, fg=SUBTLE_TEXT, bg=CARD_BG,
                     font=(FONT_FAMILY, 8)).pack(anchor="w")
            tk.Label(card, text=value, fg=HEADER_FG, bg=CARD_BG,
                     font=(FONT_FAMILY, 15, "bold")).pack(anchor="w")
            tk.Label(card, text=subtitle, fg=SUBTLE_TEXT, bg=CARD_BG,
                     font=(FONT_FAMILY, 8)).pack(anchor="w")

    def _section_label(self, parent, text, px=18):
        tk.Label(parent, text=text, fg=SUBTLE_TEXT, bg=COLOR_BG,
                 font=(FONT_FAMILY, 9, "bold"), anchor="w",
                 ).pack(fill="x", padx=px, pady=(14, 4))

    def _divider(self, parent, px):
        tk.Frame(parent, bg=DIVIDER, height=1).pack(fill="x", padx=px, pady=(8, 0))

    def _daily_chart(self, parent, snap, cfg, px):
        chart_frame = tk.Frame(parent, bg=CARD_BG, padx=12, pady=10)
        chart_frame.pack(fill="x", padx=px, pady=4)

        canvas = tk.Canvas(chart_frame, bg=CARD_BG, height=120, highlightthickness=0, bd=0)
        canvas.pack(fill="x")

        cutoff = cfg.current_period_start.strftime("%Y-%m-%d")
        days = [d for d in snap.daily_tokens if d.date >= cutoff]

        if not days:
            canvas.create_text(200, 60, text="No usage data this period", fill=SUBTLE_TEXT,
                               font=(FONT_FAMILY, 10))
            return

        canvas.update_idletasks()
        w = canvas.winfo_width() or 470
        h = 120
        mb = 22  # margin bottom
        mt = 14  # margin top
        chart_h = h - mb - mt

        max_output = max(d.output_tokens for d in days) or 1
        gap = 3
        bar_w = max((w - 20) // max(len(days), 1) - gap, 12)

        for i, day in enumerate(days):
            x = 10 + i * (bar_w + gap)
            tokens = day.output_tokens
            bar_h = int((tokens / max_output) * chart_h)
            y = h - mb - bar_h

            # Bar with slight gradient feel (darker base)
            canvas.create_rectangle(x, y, x + bar_w, h - mb,
                                    fill=COLOR_ACCENT, outline="", width=0)

            # Date label
            label = day.date[5:]  # MM-DD
            canvas.create_text(x + bar_w // 2, h - 8, text=label, fill=SUBTLE_TEXT,
                               font=(FONT_FAMILY, 7))

            # Value on top
            if bar_h > 18:
                canvas.create_text(x + bar_w // 2, y - 8, text=_format_tokens(tokens),
                                   fill=HEADER_FG, font=(FONT_FAMILY, 8))


def open_dashboard():
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [sys.executable, "-m", "claude_usage_monitor.dashboard"],
        **kwargs,
    )


if __name__ == "__main__":
    DashboardWindow().show()
