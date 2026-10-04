"""Bell dropdown — lists unread motion events and jumps into event details."""
from __future__ import annotations

import customtkinter as ctk

from utils.constants import Theme


class NotificationCenter(ctk.CTkToplevel):
    """Small floating panel anchored under the top-bar bell."""

    def __init__(self, master, app, *, anchor_widget=None, on_close=None):
        super().__init__(master)
        self.app = app
        self.on_close = on_close
        self._rows = []

        self.overrideredirect(True)
        self.configure(fg_color=Theme.BG_CARD)
        self.attributes("-topmost", True)

        outer = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=12,
            border_width=1, border_color=Theme.BORDER,
        )
        outer.pack(fill="both", expand=True)

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            header, text="Notifications",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            header, text="Mark all read", width=110, height=28,
            fg_color=Theme.BORDER, hover_color=Theme.PANEL_LIGHT,
            font=ctk.CTkFont(size=11),
            command=self._mark_all_read,
        ).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(
            outer, fg_color="transparent", width=320, height=260,
        )
        self.list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(
            footer, text="Open Security Events", height=32,
            fg_color=Theme.PRIMARY, text_color=Theme.BG_PRIMARY,
            command=self._open_history,
        ).pack(fill="x")

        self.refresh()
        self.after(10, lambda: self._place_near(anchor_widget))
        # Stay open until the user picks an item, marks all read, or toggles the bell again
        self.after(50, self.focus_force)

    def _place_near(self, anchor_widget):
        try:
            self.update_idletasks()
            if anchor_widget is not None:
                ax = anchor_widget.winfo_rootx()
                ay = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 6
                width = max(self.winfo_reqwidth(), 340)
                # Keep the panel on-screen to the left of the bell
                self.geometry(f"{width}x360+{max(8, ax - width + 40)}+{ay}")
            else:
                self.geometry("340x360+100+100")
        except Exception:
            self.geometry("340x360+100+100")

    def close(self):
        if callable(self.on_close):
            self.on_close()
        try:
            self.destroy()
        except Exception:
            pass

    def refresh(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._rows = []

        logs = []
        try:
            logs = self.app.db.get_unread_logs(limit=25) or []
        except Exception:
            logs = []

        if not logs:
            empty = ctk.CTkLabel(
                self.list_frame,
                text="No unread alerts",
                text_color=Theme.TEXT_MUTED,
                font=ctk.CTkFont(size=12),
            )
            empty.pack(pady=40)
            return

        for log in logs:
            self._add_row(log)

    def _add_row(self, log: dict):
        row = ctk.CTkFrame(
            self.list_frame, fg_color=Theme.PANEL, corner_radius=8,
            border_width=1, border_color=Theme.BORDER,
        )
        row.pack(fill="x", pady=4, padx=2)

        when = str(log.get("detected_at") or "")
        if " " in when:
            when = when.split(" ")[-1]
        loc = log.get("location") or "—"
        sid = log.get("sensor_id") or "—"
        risk = log.get("risk_level") or ""

        text = f"{when}  ·  {loc}"
        sub = f"{sid}" + (f"  ·  {risk}" if risk else "")

        ctk.CTkLabel(
            row, text=text, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(
            row, text=sub, anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_SECONDARY,
        ).pack(fill="x", padx=10, pady=(0, 8))

        # Whole row is clickable so opening details is one tap
        for widget in (row, *row.winfo_children()):
            widget.bind("<Button-1>", lambda _e, item=log: self._open_details(item))

        self._rows.append(row)

    def _open_details(self, log: dict):
        self.close()
        if hasattr(self.app, "open_event_details"):
            self.app.open_event_details(log)

    def _mark_all_read(self):
        try:
            self.app.db.mark_all_motion_read()
        except Exception:
            pass
        if hasattr(self.app, "refresh_unread_badges"):
            self.app.refresh_unread_badges()
        self.refresh()

    def _open_history(self):
        self.close()
        if hasattr(self.app, "show_view"):
            self.app.show_view("Security Events", "Security Events", "❗")
