"""Tkinter dashboard window showing usage vs plan limits.

Can be run standalone: python -m claude_usage_monitor.dashboard
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

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
    """Green < 60%, yellow 60-85%, red > 85%."""
    if pct < 60:
        return COLOR_GREEN
    if pct < 85:
        return COLOR_YELLOW
    return COLOR_RED


class DashboardWindow:
    """Popup dashboard focused on usage vs plan allowance."""

    def __init__(self, snap: UsageSnapshot | None = None, config: UserConfig | None = None):
        self.snap = snap or load_stats()
        self.config = config or load_config()
        self.root: tk.Tk | None = None

    def show(self):
        """Create and display the dashboard window."""
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

        if snap.error:
            tk.Label(frame, text=f"Error: {snap.error}", fg=COLOR_RED, bg=COLOR_BG,
                     font=("Segoe UI", 12)).pack(padx=padx, pady=20)
            return

        # ── Title + Plan ──
        tk.Label(frame, text="Claude Code Usage", fg=COLOR_ACCENT, bg=COLOR_BG,
                 font=("Segoe UI", 18, "bold")).pack(padx=padx, pady=(16, 2))
        tk.Label(frame, text=f"Plan: {cfg.plan_label}", fg=COLOR_SECONDARY, bg=COLOR_BG,
                 font=("Segoe UI", 10)).pack(padx=padx, pady=(0, 8))

        # ── Big Usage Gauge ──
        pct = snap.usage_pct(cfg)
        used = snap.period_tokens(cfg)
        limit = cfg.output_token_limit
        color = _pct_color(pct)

        gauge_frame = tk.Frame(frame, bg="#2d2d44", padx=20, pady=16)
        gauge_frame.pack(fill="x", padx=padx, pady=(4, 8))

        tk.Label(gauge_frame, text=f"{pct:.1f}%", fg=color, bg="#2d2d44",
                 font=("Segoe UI", 36, "bold")).pack()
        tk.Label(gauge_frame, text="of plan used this period", fg=COLOR_SECONDARY, bg="#2d2d44",
                 font=("Segoe UI", 10)).pack()
        tk.Label(gauge_frame, text=f"{_format_tokens(used)} / {_format_tokens(limit)} tokens",
                 fg=COLOR_TEXT, bg="#2d2d44", font=("Segoe UI", 12)).pack(pady=(4, 0))

        # Usage bar
        bar_outer = tk.Frame(gauge_frame, bg=COLOR_BAR_BG, height=20)
        bar_outer.pack(fill="x", pady=(8, 0))
        bar_outer.pack_propagate(False)
        fill_w = min(pct / 100, 1.0)
        bar_inner = tk.Frame(bar_outer, bg=color)
        bar_inner.place(x=0, y=0, relheight=1.0, relwidth=fill_w)

        # ── Reset & Budget Info ──
        info_frame = tk.Frame(frame, bg=COLOR_BG)
        info_frame.pack(fill="x", padx=padx, pady=(8, 4))

        left = tk.Frame(info_frame, bg="#2d2d44", padx=12, pady=8)
        left.grid(row=0, column=0, padx=(0, 4), sticky="nsew")
        right = tk.Frame(info_frame, bg="#2d2d44", padx=12, pady=8)
        right.grid(row=0, column=1, padx=(4, 0), sticky="nsew")
        info_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)

        # Reset info
        tk.Label(left, text="Resets in", fg=COLOR_SECONDARY, bg="#2d2d44",
                 font=("Segoe UI", 9)).pack()
        days_left = cfg.days_until_reset
        reset_text = f"{days_left} day{'s' if days_left != 1 else ''}"
        tk.Label(left, text=reset_text, fg=COLOR_TEXT, bg="#2d2d44",
                 font=("Segoe UI", 16, "bold")).pack()
        tk.Label(left, text=cfg.next_reset.strftime("%b %d, %Y"), fg=COLOR_SECONDARY, bg="#2d2d44",
                 font=("Segoe UI", 9)).pack()

        # Daily budget
        budget = snap.daily_budget(cfg)
        tk.Label(right, text="Daily budget", fg=COLOR_SECONDARY, bg="#2d2d44",
                 font=("Segoe UI", 9)).pack()
        tk.Label(right, text=_format_tokens(budget), fg=COLOR_TEXT, bg="#2d2d44",
                 font=("Segoe UI", 16, "bold")).pack()
        tk.Label(right, text="tokens/day remaining", fg=COLOR_SECONDARY, bg="#2d2d44",
                 font=("Segoe UI", 9)).pack()

        # ── Projected Usage ──
        proj = snap.projected_usage_pct(cfg)
        proj_color = _pct_color(proj)
        proj_frame = tk.Frame(frame, bg="#2d2d44", padx=16, pady=10)
        proj_frame.pack(fill="x", padx=padx, pady=(8, 4))

        proj_row = tk.Frame(proj_frame, bg="#2d2d44")
        proj_row.pack(fill="x")
        tk.Label(proj_row, text="Projected end-of-period usage:", fg=COLOR_SECONDARY, bg="#2d2d44",
                 font=("Segoe UI", 10), anchor="w").pack(side="left")
        tk.Label(proj_row, text=f"{proj:.0f}%", fg=proj_color, bg="#2d2d44",
                 font=("Segoe UI", 14, "bold"), anchor="e").pack(side="right")

        if proj > 100:
            tk.Label(proj_frame, text="At this pace you'll exceed your plan limit",
                     fg=COLOR_RED, bg="#2d2d44", font=("Segoe UI", 9)).pack(anchor="w")
        elif proj > 85:
            tk.Label(proj_frame, text="On track to use most of your allowance",
                     fg=COLOR_YELLOW, bg="#2d2d44", font=("Segoe UI", 9)).pack(anchor="w")
        else:
            tk.Label(proj_frame, text="Usage is well within your plan limits",
                     fg=COLOR_GREEN, bg="#2d2d44", font=("Segoe UI", 9)).pack(anchor="w")

        # ── Period Summary Cards ──
        self._section_label(frame, "This Period")
        period_frame = tk.Frame(frame, bg=COLOR_BG)
        period_frame.pack(fill="x", padx=padx, pady=(4, 4))

        period_msgs = snap.period_messages(cfg)
        period_sessions = snap.period_sessions(cfg)
        remaining = max(limit - used, 0)

        cards = [
            ("Messages", f"{period_msgs:,}"),
            ("Sessions", str(period_sessions)),
            ("Tokens left", _format_tokens(remaining)),
        ]
        for i, (title, value) in enumerate(cards):
            card = tk.Frame(period_frame, bg="#2d2d44", padx=12, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            period_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=title, fg=COLOR_SECONDARY, bg="#2d2d44",
                     font=("Segoe UI", 9)).pack()
            tk.Label(card, text=value, fg=COLOR_TEXT, bg="#2d2d44",
                     font=("Segoe UI", 13, "bold")).pack()

        # ── Token Usage by Model (this period) ──
        self._section_label(frame, "Tokens by Model (This Period)")
        cutoff = cfg.current_period_start.strftime("%Y-%m-%d")
        model_period: dict[str, int] = {}
        for day in snap.daily_tokens:
            if day.date >= cutoff:
                for model, tokens in day.tokens_by_model.items():
                    model_period[model] = model_period.get(model, 0) + tokens

        if model_period:
            max_t = max(model_period.values())
            from .stats import ModelStats
            for model_id in sorted(model_period, key=model_period.get, reverse=True):
                ms = ModelStats(name=model_id)
                tokens = model_period[model_id]
                pct_of_limit = (tokens / limit * 100) if limit else 0
                self._bar_row(frame, ms.display_name, tokens, max_t,
                              f"{_format_tokens(tokens)} ({pct_of_limit:.1f}%)")
        else:
            tk.Label(frame, text="No usage this period", fg=COLOR_SECONDARY, bg=COLOR_BG,
                     font=("Segoe UI", 10)).pack(padx=20, pady=4)

        # ── Daily Usage Chart ──
        self._section_label(frame, "Daily Tokens (This Period)")
        self._daily_chart(frame, snap, cfg)

        # ── All Time Stats ──
        self._section_label(frame, "All Time")
        stats = [
            f"Sessions: {snap.total_sessions}  |  Messages: {snap.total_messages:,}  |  Days: {snap.days_active}",
            f"Total tokens: {_format_tokens(snap.total_tokens)}",
        ]
        if snap.peak_hour is not None:
            stats.append(f"Peak hour: {snap.peak_hour:02d}:00")
        if snap.longest_session_messages:
            dur_m = snap.longest_session_duration_sec // 60
            stats.append(f"Longest session: {snap.longest_session_messages} msgs ({dur_m // 60}h {dur_m % 60}m)")

        for line in stats:
            tk.Label(frame, text=line, fg=COLOR_SECONDARY, bg=COLOR_BG,
                     font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=20, pady=1)

        # ── Config note ──
        tk.Label(frame, text=f"Config: ~/.claude/usage-monitor-config.json  |  Billing day: {cfg.billing_day}",
                 fg="#555577", bg=COLOR_BG, font=("Segoe UI", 8)).pack(padx=padx, pady=(16, 8))

        # Bottom padding
        tk.Frame(frame, bg=COLOR_BG, height=20).pack()

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, fg=COLOR_ACCENT, bg=COLOR_BG,
                 font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x", padx=16, pady=(12, 4))

    def _bar_row(self, parent, label, value, max_val, display):
        row = tk.Frame(parent, bg=COLOR_BG)
        row.pack(fill="x", padx=20, pady=2)

        tk.Label(row, text=label, fg=COLOR_TEXT, bg=COLOR_BG, font=("Segoe UI", 10),
                 width=12, anchor="w").pack(side="left")

        bar_frame = tk.Frame(row, bg=COLOR_BAR_BG, height=18)
        bar_frame.pack(side="left", fill="x", expand=True, padx=(4, 8))
        bar_frame.pack_propagate(False)

        ratio = value / max_val if max_val else 0
        color = COLOR_BAR_HIGH if ratio > 0.8 else COLOR_BAR_FILL
        bar_inner = tk.Frame(bar_frame, bg=color)
        bar_inner.place(x=0, y=0, relheight=1.0, width=max(int(ratio * 300), 2))

        tk.Label(row, text=display, fg=COLOR_SECONDARY, bg=COLOR_BG,
                 font=("Segoe UI", 9), width=16, anchor="e").pack(side="right")

    def _daily_chart(self, parent, snap: UsageSnapshot, cfg: UserConfig):
        """Bar chart of daily token usage for the current billing period."""
        canvas = tk.Canvas(parent, bg=COLOR_BG, height=130, highlightthickness=0)
        canvas.pack(fill="x", padx=20, pady=4)

        cutoff = cfg.current_period_start.strftime("%Y-%m-%d")
        days = [d for d in snap.daily_tokens if d.date >= cutoff]

        if not days:
            canvas.create_text(200, 65, text="No usage data this period", fill=COLOR_SECONDARY,
                               font=("Segoe UI", 10))
            return

        # Draw budget line
        budget = snap.daily_budget(cfg)

        canvas.update_idletasks()
        w = canvas.winfo_width() or 490
        h = 130
        margin_bottom = 25
        margin_top = 15
        chart_h = h - margin_bottom - margin_top

        max_tokens = max(max(d.total_tokens for d in days), budget) or 1
        bar_w = max((w - 40) // max(len(days), 1) - 4, 8)

        # Budget line
        budget_y = h - margin_bottom - int((budget / max_tokens) * chart_h)
        canvas.create_line(10, budget_y, w - 10, budget_y, fill=COLOR_GREEN, dash=(4, 4))
        canvas.create_text(w - 10, budget_y - 8, text="budget", fill=COLOR_GREEN,
                           font=("Segoe UI", 7), anchor="e")

        for i, day in enumerate(days):
            x = 20 + i * (bar_w + 4)
            tokens = day.total_tokens
            bar_h = int((tokens / max_tokens) * chart_h)
            y = h - margin_bottom - bar_h

            color = COLOR_RED if tokens > budget * 1.5 else (COLOR_YELLOW if tokens > budget else COLOR_BAR_FILL)
            canvas.create_rectangle(x, y, x + bar_w, h - margin_bottom, fill=color, outline="")

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
