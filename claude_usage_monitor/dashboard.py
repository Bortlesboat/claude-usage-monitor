"""Tkinter dashboard window showing detailed usage charts and stats.

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
    COLOR_SECONDARY,
    COLOR_TEXT,
)
from .stats import UsageSnapshot, _format_tokens, load_stats


class DashboardWindow:
    """Popup dashboard with usage charts."""

    def __init__(self, snap: UsageSnapshot | None = None):
        self.snap = snap or load_stats()
        self.root: tk.Tk | None = None

    def show(self):
        """Create and display the dashboard window."""
        self.root = tk.Tk()
        self.root.title("Claude Code Usage Monitor")
        self.root.configure(bg=COLOR_BG)
        self.root.geometry("520x680")
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

        # Main scrollable frame
        canvas = tk.Canvas(root, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=COLOR_BG)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        padx = 16

        if snap.error:
            tk.Label(frame, text=f"Error: {snap.error}", fg="#e07a5f", bg=COLOR_BG,
                     font=("Segoe UI", 12)).pack(padx=padx, pady=20)
            return

        # Title
        tk.Label(frame, text="Claude Code Usage", fg=COLOR_ACCENT, bg=COLOR_BG,
                 font=("Segoe UI", 18, "bold")).pack(padx=padx, pady=(16, 4))

        # Summary cards
        summary_frame = tk.Frame(frame, bg=COLOR_BG)
        summary_frame.pack(fill="x", padx=padx, pady=(8, 4))

        cards = [
            ("Today", f"{snap.today_messages} msgs\n{_format_tokens(snap.today_tokens)} tokens"),
            ("This Week", f"{snap.week_messages} msgs\n{_format_tokens(snap.week_tokens)} tokens"),
            ("All Time", f"{snap.total_sessions} sessions\n{snap.total_messages:,} msgs"),
        ]

        for i, (title, value) in enumerate(cards):
            card = tk.Frame(summary_frame, bg="#2d2d44", padx=12, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            summary_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=title, fg=COLOR_SECONDARY, bg="#2d2d44",
                     font=("Segoe UI", 9)).pack()
            tk.Label(card, text=value, fg=COLOR_TEXT, bg="#2d2d44",
                     font=("Segoe UI", 11, "bold")).pack()

        # Model breakdown
        self._section_label(frame, "Token Usage by Model")
        if snap.models:
            max_tokens = max(m.total_tokens for m in snap.models.values())
            for model in sorted(snap.models.values(), key=lambda m: m.total_tokens, reverse=True):
                self._bar_row(frame, model.display_name, model.total_tokens, max_tokens,
                              f"{_format_tokens(model.total_tokens)}")

        # Daily activity chart (last 14 days)
        self._section_label(frame, "Daily Messages (Last 14 Days)")
        self._daily_chart(frame, snap)

        # Hour distribution
        self._section_label(frame, "Activity by Hour")
        self._hour_chart(frame, snap)

        # Stats footer
        self._section_label(frame, "Stats")
        stats_text = []
        stats_text.append(f"Days active: {snap.days_active}")
        stats_text.append(f"Avg daily messages: {snap.avg_daily_messages:.0f}")
        stats_text.append(f"Total tokens: {_format_tokens(snap.total_tokens)}")
        if snap.peak_hour is not None:
            stats_text.append(f"Peak hour: {snap.peak_hour}:00")
        if snap.longest_session_messages:
            dur_m = snap.longest_session_duration_sec // 60
            stats_text.append(f"Longest session: {snap.longest_session_messages} msgs ({dur_m // 60}h {dur_m % 60}m)")
        if snap.first_session_date:
            stats_text.append(f"First session: {snap.first_session_date[:10]}")

        for line in stats_text:
            tk.Label(frame, text=line, fg=COLOR_SECONDARY, bg=COLOR_BG,
                     font=("Segoe UI", 10), anchor="w").pack(fill="x", padx=20, pady=1)

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
        fill = tk.Frame(bar_frame, bg=color, width=int(ratio * 300))
        fill.place(x=0, y=0, relheight=1.0, width=max(int(ratio * 300), 2))

        tk.Label(row, text=display, fg=COLOR_SECONDARY, bg=COLOR_BG,
                 font=("Segoe UI", 9), width=10, anchor="e").pack(side="right")

    def _daily_chart(self, parent, snap: UsageSnapshot):
        """Draw a bar chart of daily messages for last 14 days."""
        canvas = tk.Canvas(parent, bg=COLOR_BG, height=120, highlightthickness=0)
        canvas.pack(fill="x", padx=20, pady=4)

        cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        days = [d for d in snap.daily_activity if d.date >= cutoff]

        if not days:
            canvas.create_text(200, 60, text="No recent data", fill=COLOR_SECONDARY,
                               font=("Segoe UI", 10))
            return

        canvas.update_idletasks()
        w = canvas.winfo_width() or 480
        h = 120
        margin_bottom = 25
        margin_top = 10
        chart_h = h - margin_bottom - margin_top

        max_msgs = max(d.messages for d in days) or 1
        bar_w = max((w - 40) // max(len(days), 1) - 4, 8)

        for i, day in enumerate(days):
            x = 20 + i * (bar_w + 4)
            bar_h = int((day.messages / max_msgs) * chart_h)
            y = h - margin_bottom - bar_h

            color = COLOR_BAR_HIGH if day.messages == max_msgs else COLOR_BAR_FILL
            canvas.create_rectangle(x, y, x + bar_w, h - margin_bottom, fill=color, outline="")

            label = day.date[-2:]
            canvas.create_text(x + bar_w // 2, h - 10, text=label, fill=COLOR_SECONDARY,
                               font=("Segoe UI", 7))

            if bar_h > 15:
                canvas.create_text(x + bar_w // 2, y - 8, text=str(day.messages),
                                   fill=COLOR_TEXT, font=("Segoe UI", 7))

    def _hour_chart(self, parent, snap: UsageSnapshot):
        """Draw hour distribution as a horizontal bar chart."""
        if not snap.hour_counts:
            return

        max_count = max(snap.hour_counts.values()) if snap.hour_counts else 1

        chart_frame = tk.Frame(parent, bg=COLOR_BG)
        chart_frame.pack(fill="x", padx=20, pady=4)

        for hour in range(24):
            count = snap.hour_counts.get(hour, 0)
            if count == 0:
                continue
            label = f"{hour:02d}:00"
            self._bar_row(chart_frame, label, count, max_count, str(count))


def open_dashboard():
    """Open dashboard as a separate process (avoids tkinter threading issues)."""
    subprocess.Popen(
        [sys.executable, "-m", "claude_usage_monitor.dashboard"],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


# Allow running standalone: python -m claude_usage_monitor.dashboard
if __name__ == "__main__":
    DashboardWindow().show()
