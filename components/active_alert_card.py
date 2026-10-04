"""Right-panel Active Alert card — fields + snapshot/live thumb update on each motion event."""
from __future__ import annotations

import customtkinter as ctk
from PIL import Image

from utils.constants import Theme
from utils.paths import resolve_snapshot_file


class ActiveAlertCard(ctk.CTkFrame):
    def __init__(self, master, on_details=None, app=None, **kwargs):
        super().__init__(
            master,
            fg_color=Theme.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=Theme.DANGER,
            **kwargs,
        )
        self.on_details = on_details
        self.app = app
        self._last_event = None
        self._thumb_image = None

        header = ctk.CTkFrame(self, fg_color="#2A1218", corner_radius=10)
        header.pack(fill="x", padx=2, pady=2)

        ctk.CTkLabel(
            header, text="●  Motion Detected",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.DANGER_LIGHT,
        ).pack(anchor="w", padx=14, pady=(10, 0))

        self.time_lbl = ctk.CTkLabel(
            header, text="Waiting for event…",
            font=ctk.CTkFont(size=11), text_color=Theme.TEXT_SECONDARY,
        )
        self.time_lbl.pack(anchor="w", padx=14, pady=(2, 10))

        self.feed_frame = ctk.CTkFrame(
            self, height=140, fg_color="#050A10", corner_radius=8,
        )
        self.feed_frame.pack(fill="x", padx=12, pady=(8, 8))
        self.feed_frame.pack_propagate(False)

        feed_top = ctk.CTkFrame(self.feed_frame, fg_color="transparent")
        feed_top.pack(fill="x", padx=8, pady=6)
        self.camera_title = ctk.CTkLabel(
            feed_top, text="Camera", font=ctk.CTkFont(size=10, weight="bold"),
            text_color=Theme.TEXT_SECONDARY,
        )
        self.camera_title.pack(side="left")
        self.live_badge = ctk.CTkLabel(
            feed_top, text="● LIVE", font=ctk.CTkFont(size=10, weight="bold"),
            text_color=Theme.DANGER,
        )
        self.live_badge.pack(side="right")

        self.feed_placeholder = ctk.CTkLabel(
            self.feed_frame,
            text="Waiting for camera snapshot…",
            text_color=Theme.TEXT_MUTED, font=ctk.CTkFont(size=11),
        )
        self.feed_placeholder.pack(expand=True)

        self.feed_image_lbl = ctk.CTkLabel(self.feed_frame, text="")
        # Packed only when we have a thumb to show

        details = ctk.CTkFrame(self, fg_color="transparent")
        details.pack(fill="x", padx=14, pady=(0, 4))

        self.fields = {}
        for key, default in (
            ("Location", "—"),
            ("Sensor", "—"),
            ("Camera", "—"),
            ("AI Detection", "Disabled (v1)"),
            ("Risk Level", "—"),
        ):
            row = ctk.CTkFrame(details, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=key, width=100, anchor="w",
                text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=11),
            ).pack(side="left")
            val = ctk.CTkLabel(
                row, text=default, anchor="w",
                text_color=Theme.TEXT_PRIMARY, font=ctk.CTkFont(size=11, weight="bold"),
            )
            val.pack(side="left")
            self.fields[key] = val

        self.btn_details = ctk.CTkButton(
            self, text="View Details  →", height=32,
            fg_color="transparent", border_width=1, border_color=Theme.BORDER,
            hover_color=Theme.PANEL_LIGHT, font=ctk.CTkFont(size=12),
            command=self._on_details_clicked,
        )
        self.btn_details.pack(fill="x", padx=12, pady=(8, 12))

    def _on_details_clicked(self):
        if callable(self.on_details):
            self.on_details(self._last_event)

    def _clear_thumb(self):
        self._thumb_image = None
        self.feed_image_lbl.pack_forget()
        self.feed_image_lbl.configure(image=None, text="")
        self.feed_placeholder.pack(expand=True)
        self.live_badge.configure(text="● LIVE", text_color=Theme.DANGER)

    def _show_pil_thumb(self, pil_image: Image.Image, *, from_live: bool):
        # Fit the thumb into the feed box without stretching odd aspect ratios
        img = pil_image.convert("RGB")
        img.thumbnail((320, 110))
        self._thumb_image = ctk.CTkImage(
            light_image=img, dark_image=img, size=img.size,
        )
        self.feed_placeholder.pack_forget()
        self.feed_image_lbl.configure(image=self._thumb_image, text="")
        self.feed_image_lbl.pack(expand=True, pady=(0, 8))
        if from_live:
            self.live_badge.configure(text="● LIVE", text_color=Theme.DANGER)
        else:
            self.live_badge.configure(text="SNAPSHOT", text_color=Theme.WARNING)

    def _update_thumb(self, event: dict):
        # Prefer the saved snapshot; fall back to one live frame if capture was off
        snap = resolve_snapshot_file(event.get("snapshot_path"))
        if snap is not None:
            try:
                self._show_pil_thumb(Image.open(snap), from_live=False)
                return
            except Exception:
                pass

        camera = getattr(self.app, "camera_manager", None) if self.app else None
        if camera is not None and getattr(camera, "running", False):
            frame = camera.get_frame()
            if frame is not None:
                try:
                    self._show_pil_thumb(Image.fromarray(frame), from_live=True)
                    return
                except Exception:
                    pass

        self._clear_thumb()
        self.feed_placeholder.configure(text="No snapshot available")

    def update_event(self, event: dict | None):
        """Fill Location / Sensor / Camera / Risk and refresh the camera thumb."""
        self._last_event = event
        if not event:
            self.time_lbl.configure(text="Waiting for event…")
            for key in ("Location", "Sensor", "Camera", "Risk Level"):
                self.fields[key].configure(text="—")
            self.fields["AI Detection"].configure(text="Disabled (v1)")
            self.camera_title.configure(text="Camera")
            self._clear_thumb()
            self.feed_placeholder.configure(text="Waiting for camera snapshot…")
            return

        when = event.get("detected_at") or event.get("timestamp") or "Just now"
        self.time_lbl.configure(text=str(when))
        self.fields["Location"].configure(text=str(event.get("location") or "—"))
        self.fields["Sensor"].configure(text=str(event.get("sensor_id") or "—"))
        cam = event.get("camera_uid") or "—"
        self.fields["Camera"].configure(text=str(cam))
        self.camera_title.configure(text=str(cam) if cam != "—" else "Camera")
        self.fields["AI Detection"].configure(text="Disabled (v1)")
        risk = event.get("risk_level") or "—"
        risk_color = Theme.TEXT_PRIMARY
        if risk == "High" or risk == "Critical":
            risk_color = Theme.DANGER_LIGHT
        elif risk == "Medium":
            risk_color = Theme.WARNING
        elif risk == "Low":
            risk_color = Theme.SUCCESS
        self.fields["Risk Level"].configure(text=str(risk), text_color=risk_color)
        self._update_thumb(event)
