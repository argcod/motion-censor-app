"""Popup that shows one motion event — snapshot, risk, and mobile-alert fields."""
from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from PIL import Image

from utils.constants import Theme
from utils.paths import resolve_snapshot_file


class EventDetailsModal(ctk.CTkToplevel):
    """Read-only event inspector used by Active Alert, History, and the bell list."""

    def __init__(self, master, event: dict, *, app=None, on_changed=None):
        super().__init__(master)
        self.app = app
        self.event = dict(event or {})
        self.on_changed = on_changed
        self._thumb_image = None

        self.title("Event Details")
        self.geometry("480x620")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_SECONDARY)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self._build()
        self.after(40, self._center_on_parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Opening the modal counts as reviewing the alert
        self._mark_read_if_needed()

    def _center_on_parent(self):
        try:
            self.update_idletasks()
            parent = self.master.winfo_toplevel()
            px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

    def _build(self):
        pad = {"padx": 20, "pady": 4}

        ctk.CTkLabel(
            self, text="Security Event",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(18, 6))

        # Snapshot area — file thumb when we have one, otherwise a clear empty state
        snap_frame = ctk.CTkFrame(
            self, height=180, fg_color="#050A10", corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        snap_frame.pack(fill="x", padx=20, pady=(4, 12))
        snap_frame.pack_propagate(False)

        snap_path = resolve_snapshot_file(self.event.get("snapshot_path"))
        if snap_path is not None:
            try:
                img = Image.open(snap_path).convert("RGB")
                img.thumbnail((440, 170))
                self._thumb_image = ctk.CTkImage(
                    light_image=img, dark_image=img, size=img.size,
                )
                ctk.CTkLabel(snap_frame, image=self._thumb_image, text="").pack(expand=True)
            except Exception:
                ctk.CTkLabel(
                    snap_frame, text="Could not load snapshot",
                    text_color=Theme.TEXT_MUTED, font=ctk.CTkFont(size=12),
                ).pack(expand=True)
        else:
            ctk.CTkLabel(
                snap_frame, text="No snapshot for this event",
                text_color=Theme.TEXT_MUTED, font=ctk.CTkFont(size=12),
            ).pack(expand=True)

        fields = [
            ("Time", self.event.get("detected_at") or "—"),
            ("Location", self.event.get("location") or "—"),
            ("Sensor", self.event.get("sensor_id") or "—"),
            ("Camera", self.event.get("camera_uid") or "—"),
            ("Status", self.event.get("status") or "Motion Detected"),
            ("Risk Level", self.event.get("risk_level") or "—"),
            ("AI Detection", self.event.get("ai_label") or "Disabled (v1)"),
            ("Snapshot", self._short_path(self.event.get("snapshot_path"))),
            ("Mobile Sent", self._yes_no(self.event.get("mobile_alert_sent"))),
            ("Mobile Channels", self.event.get("mobile_alert_channels") or "—"),
            ("Mobile Error", self.event.get("mobile_alert_error") or "—"),
            ("Read", self._yes_no(self.event.get("is_read"))),
        ]

        body = ctk.CTkScrollableFrame(self, fg_color="transparent", height=280)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        for label, value in fields:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", **pad)
            ctk.CTkLabel(
                row, text=label, width=120, anchor="w",
                text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12),
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=str(value), anchor="w", wraplength=280, justify="left",
                text_color=Theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12, weight="bold"),
            ).pack(side="left", fill="x", expand=True)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(4, 18))

        is_read = bool(self.event.get("is_read"))
        toggle_text = "Mark Unread" if is_read else "Mark Read"
        ctk.CTkButton(
            actions, text=toggle_text, height=34,
            fg_color=Theme.BORDER, hover_color=Theme.PANEL_LIGHT,
            command=self._toggle_read,
        ).pack(side="left")

        ctk.CTkButton(
            actions, text="Close", height=34, width=100,
            fg_color=Theme.PRIMARY, text_color=Theme.BG_PRIMARY,
            command=self.destroy,
        ).pack(side="right")

    def _short_path(self, stored) -> str:
        if not stored:
            return "—"
        path = Path(str(stored))
        return path.name if path.name else str(stored)

    def _yes_no(self, value) -> str:
        if value is None:
            return "No"
        if isinstance(value, (bytes, bytearray)):
            return "Yes" if value and value[0] else "No"
        return "Yes" if value in (True, 1, "1", "true", "True") else "No"

    def _event_id(self):
        return self.event.get("id") or self.event.get("event_id")

    def _mark_read_if_needed(self):
        # Auto-clear unread when the user opens details from the bell or Active Alert
        event_id = self._event_id()
        if not event_id or not self.app or not getattr(self.app, "db", None):
            return
        if self.event.get("is_read") in (True, 1, "1"):
            return
        try:
            self.app.db.mark_motion_read(event_id, True)
            self.event["is_read"] = True
            if callable(self.on_changed):
                self.on_changed()
            elif hasattr(self.app, "refresh_unread_badges"):
                self.app.refresh_unread_badges()
        except Exception:
            pass

    def _toggle_read(self):
        event_id = self._event_id()
        if not event_id or not self.app or not getattr(self.app, "db", None):
            return
        currently_read = self._yes_no(self.event.get("is_read")) == "Yes"
        new_state = not currently_read
        self.app.db.mark_motion_read(event_id, new_state)
        self.event["is_read"] = new_state
        if callable(self.on_changed):
            self.on_changed()
        elif hasattr(self.app, "refresh_unread_badges"):
            self.app.refresh_unread_badges()
        self.destroy()
