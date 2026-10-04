"""Sensors page — PIR devices from the unified devices table."""
from __future__ import annotations

import customtkinter as ctk

from components.device_edit_dialog import DeviceEditDialog
from utils.constants import Theme


class SensorsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            header, text="Sensor Management",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="PIR devices from the floor plan. Same records as markers in 3D Environment.",
            text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=13),
        ).pack(anchor="w", pady=(4, 0))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkButton(
            actions, text="Refresh", width=100, height=32,
            fg_color=Theme.BG_CARD, border_width=1, border_color=Theme.BORDER,
            hover_color=Theme.PANEL_LIGHT, command=self.load_sensors,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions, text="+ Add Sensor", width=120, height=32,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_LIGHT,
            font=ctk.CTkFont(weight="bold"), command=self._add_sensor,
        ).pack(side="left")

        self.empty_lbl = ctk.CTkLabel(
            self, text="", text_color=Theme.TEXT_MUTED, font=ctk.CTkFont(size=12),
        )
        self.empty_lbl.pack(anchor="w", padx=20)

        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=12, pady=8)

        dm = getattr(app, "device_manager", None)
        if dm is not None:
            dm.register_change_listener(self.load_sensors)

        self.after(60, self.load_sensors)

    def on_show(self):
        self.load_sensors()

    def _dm(self):
        return getattr(self.app, "device_manager", None)

    def load_sensors(self):
        for w in self.container.winfo_children():
            w.destroy()

        dm = self._dm()
        if dm is None:
            self.empty_lbl.configure(text="Device manager unavailable.")
            return

        # List every PIR so multi-floor installs still show up here
        sensors = dm.list_all_devices(device_type="pir") or []
        if not sensors:
            self.empty_lbl.configure(text="No PIR sensors yet — place one on the floor plan or click Add Sensor.")
            return

        self.empty_lbl.configure(text=f"{len(sensors)} sensor(s)")
        for device in sensors:
            self._build_card(device)

    def _build_card(self, device: dict):
        card = ctk.CTkFrame(
            self.container, fg_color=Theme.BG_CARD, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        card.pack(fill="x", pady=6, padx=8)

        uid = device.get("device_uid") or "—"
        name = device.get("name") or uid
        enabled = bool(device.get("enabled", True))
        status_color = Theme.SUCCESS if enabled else Theme.TEXT_MUTED
        status_text = "Enabled" if enabled else "Disabled"

        room_name = "—"
        dm = self._dm()
        if dm and device.get("room_id"):
            room = dm.get_room(device["room_id"])
            if room:
                room_name = room.get("name") or "—"

        linked = device.get("linked_camera_uid") or "—"
        pos = "Not placed"
        if device.get("x_norm") is not None and device.get("y_norm") is not None:
            pos = f"({float(device['x_norm']):.2f}, {float(device['y_norm']):.2f})"

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(
            top, text=f"●  {uid}", text_color=status_color,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            top, text=status_text, text_color=Theme.TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(side="right")

        ctk.CTkLabel(
            card,
            text=f"{name}\nRoom: {room_name}  ·  Linked camera: {linked}\nPlan position: {pos}",
            text_color=Theme.TEXT_SECONDARY, justify="left", font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(0, 8))

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(anchor="w", padx=18, pady=(0, 14))
        ctk.CTkButton(
            btns, text="Edit", width=80, height=30,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_LIGHT,
            command=lambda d=device: self._edit(d),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btns, text="Delete", width=80, height=30,
            fg_color=Theme.BG_CARD, border_width=1, border_color=Theme.DANGER,
            hover_color=Theme.PANEL_LIGHT, text_color=Theme.DANGER,
            command=lambda d=device: self._delete(d),
        ).pack(side="left", padx=(0, 8))
        # Simulate uses this sensor uid so the 3D animation lands on its marker
        ctk.CTkButton(
            btns, text="Simulate", width=90, height=30,
            fg_color=Theme.DANGER, hover_color=Theme.DANGER_LIGHT,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda u=uid: self._simulate(u),
        ).pack(side="left")

    def _simulate(self, sensor_uid: str):
        if hasattr(self.app, "motion_manager"):
            self.app.motion_manager.simulate(sensor_uid)

    def _add_sensor(self):
        dm = self._dm()
        if dm is None:
            return

        def after_save(_d):
            self.load_sensors()
            notes = getattr(self.app, "notifications", None)
            if notes:
                notes.show("Sensor added", "Saved to devices — place it on the plan if needed.", type="success")

        DeviceEditDialog(
            self.app, dm, device=None, device_type="pir",
            floor_plan_id=dm.get_active_floor_plan_id(),
            x_norm=0.5, y_norm=0.5,
            on_saved=after_save,
        )

    def _edit(self, device: dict):
        dm = self._dm()
        if dm is None:
            return
        DeviceEditDialog(
            self.app, dm, device=device,
            on_saved=lambda _d: self.load_sensors(),
            on_deleted=lambda _u: self.load_sensors(),
        )

    def _delete(self, device: dict):
        dm = self._dm()
        if dm is None:
            return
        uid = device.get("device_uid")
        dm.delete_device(uid)
        self.load_sensors()
        notes = getattr(self.app, "notifications", None)
        if notes:
            notes.show("Sensor removed", f"{uid} deleted.", type="warning")
