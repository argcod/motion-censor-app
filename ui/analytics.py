"""Analytics — hourly + daily range charts (Phase 6)."""
from __future__ import annotations

import datetime

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from utils.constants import Theme


class AnalyticsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.canvas = None

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_filters()

        self.chart_container = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        self.chart_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        # Default to last 7 days so charts have something to show
        today = datetime.date.today()
        self.start_entry.insert(0, (today - datetime.timedelta(days=6)).isoformat())
        self.end_entry.insert(0, today.isoformat())
        self.day_entry.insert(0, today.isoformat())

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header, text="Analytics",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            header, text="Refresh Charts", fg_color=Theme.PRIMARY, command=self.draw_charts,
        ).pack(side="right")

    def _build_filters(self):
        bar = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        ctk.CTkLabel(bar, text="Daily range From:", text_color=Theme.TEXT_SECONDARY).pack(
            side="left", padx=(16, 4), pady=12,
        )
        self.start_entry = ctk.CTkEntry(bar, width=110, placeholder_text="YYYY-MM-DD")
        self.start_entry.pack(side="left", padx=4)

        ctk.CTkLabel(bar, text="To:", text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=(8, 4))
        self.end_entry = ctk.CTkEntry(bar, width=110, placeholder_text="YYYY-MM-DD")
        self.end_entry.pack(side="left", padx=4)

        ctk.CTkButton(
            bar, text="7 Days", width=70, fg_color=Theme.PANEL_LIGHT,
            command=lambda: self._preset_days(7),
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            bar, text="30 Days", width=80, fg_color=Theme.PANEL_LIGHT,
            command=lambda: self._preset_days(30),
        ).pack(side="left", padx=4)

        ctk.CTkLabel(bar, text="Hourly day:", text_color=Theme.TEXT_SECONDARY).pack(
            side="left", padx=(20, 4),
        )
        self.day_entry = ctk.CTkEntry(bar, width=110, placeholder_text="YYYY-MM-DD")
        self.day_entry.pack(side="left", padx=4)

    def _preset_days(self, days: int):
        today = datetime.date.today()
        self.start_entry.delete(0, "end")
        self.end_entry.delete(0, "end")
        self.start_entry.insert(0, (today - datetime.timedelta(days=days - 1)).isoformat())
        self.end_entry.insert(0, today.isoformat())
        self.draw_charts()

    def _parse_date(self, raw: str):
        try:
            return datetime.date.fromisoformat(raw.strip())
        except ValueError:
            return None

    def on_show(self):
        self.draw_charts()

    def draw_charts(self):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None

        start = self._parse_date(self.start_entry.get())
        end = self._parse_date(self.end_entry.get())
        day = self._parse_date(self.day_entry.get())

        if start is None or end is None or day is None:
            self.app.notifications.show(
                "Analytics", "Use YYYY-MM-DD for all date fields.", type="warning",
            )
            return
        if start > end:
            self.app.notifications.show(
                "Analytics", "From date must be on or before To date.", type="warning",
            )
            return

        daily = self.app.db.get_daily_counts(start.isoformat(), end.isoformat())
        # Fill every day in the range so empty days show as zero bars
        labels = []
        values = []
        cursor = start
        while cursor <= end:
            key = cursor.isoformat()
            labels.append(cursor.strftime("%m-%d"))
            values.append(daily.get(key, 0))
            cursor += datetime.timedelta(days=1)

        hourly = self.app.db.get_hourly_counts_for_date(day.isoformat())
        hours = list(range(24))
        hour_counts = [hourly.get(h, 0) for h in hours]

        fig, (ax_day, ax_hour) = plt.subplots(
            1, 2, figsize=(11, 4.5), facecolor=Theme.BG_CARD,
        )

        ax_day.bar(labels, values, color=Theme.PRIMARY, alpha=0.85)
        ax_day.set_title(
            f"Daily events ({start} → {end})",
            color=Theme.TEXT_PRIMARY, fontsize=12, fontweight="bold", pad=12,
        )
        ax_day.set_xlabel("Day", color=Theme.TEXT_SECONDARY)
        ax_day.set_ylabel("Detections", color=Theme.TEXT_SECONDARY)
        ax_day.tick_params(colors=Theme.TEXT_SECONDARY, labelrotation=45)
        ax_day.set_facecolor(Theme.BG_CARD)
        for spine in ("top", "right"):
            ax_day.spines[spine].set_visible(False)
        ax_day.spines["bottom"].set_color(Theme.BORDER)
        ax_day.spines["left"].set_color(Theme.BORDER)

        ax_hour.bar(hours, hour_counts, color=Theme.CYAN_GLOW, alpha=0.8)
        ax_hour.set_title(
            f"Hourly events — {day.isoformat()}",
            color=Theme.TEXT_PRIMARY, fontsize=12, fontweight="bold", pad=12,
        )
        ax_hour.set_xlabel("Hour (0–23)", color=Theme.TEXT_SECONDARY)
        ax_hour.set_ylabel("Detections", color=Theme.TEXT_SECONDARY)
        ax_hour.tick_params(colors=Theme.TEXT_SECONDARY)
        ax_hour.set_facecolor(Theme.BG_CARD)
        for spine in ("top", "right"):
            ax_hour.spines[spine].set_visible(False)
        ax_hour.spines["bottom"].set_color(Theme.BORDER)
        ax_hour.spines["left"].set_color(Theme.BORDER)

        fig.patch.set_facecolor(Theme.BG_CARD)
        fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=16, pady=16)
        plt.close(fig)
