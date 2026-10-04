"""Shared Place Mode wiring for 3D Environment and Floor Plan pages."""
from __future__ import annotations

import customtkinter as ctk

from components.device_edit_dialog import DeviceEditDialog, RoomNameDialog
from components.floorplan_canvas import FloorPlanCanvas
from utils.constants import Theme


class PlacementController:
    """Toolbar + DeviceManager hooks so both viewports share the same place/edit flow."""

    def __init__(self, app, floorplan: FloorPlanCanvas, toolbar_parent, status_label=None):
        self.app = app
        self.floorplan = floorplan
        self.status_label = status_label
        self._pending_room_points = None
        self._suppress_notify = False

        # Canvas talks back here instead of each page reimplementing place logic
        self.floorplan.on_place = self._on_place
        self.floorplan.on_device_moved = self._on_device_moved
        self.floorplan.on_device_selected = self._on_device_selected
        self.floorplan.on_room_complete = self._on_room_complete
        self.floorplan.on_mode_changed = self._on_mode_changed

        self._build_toolbar(toolbar_parent)

        dm = getattr(app, "device_manager", None)
        if dm is not None:
            dm.register_change_listener(self.refresh_from_db)

    def _dm(self):
        return getattr(self.app, "device_manager", None)

    def _build_toolbar(self, parent):
        self.bar = ctk.CTkFrame(parent, fg_color="transparent")
        self.bar.pack(side="left", padx=(12, 0))

        self.btn_pir = ctk.CTkButton(
            self.bar, text="+ PIR", width=78, height=30,
            fg_color=Theme.BG_CARD, hover_color=Theme.SUCCESS,
            border_width=1, border_color=Theme.BORDER,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self.set_mode(FloorPlanCanvas.MODE_PLACE_PIR),
        )
        self.btn_pir.pack(side="left", padx=3)

        self.btn_cam = ctk.CTkButton(
            self.bar, text="+ Camera", width=92, height=30,
            fg_color=Theme.BG_CARD, hover_color=Theme.PRIMARY,
            border_width=1, border_color=Theme.BORDER,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self.set_mode(FloorPlanCanvas.MODE_PLACE_CAMERA),
        )
        self.btn_cam.pack(side="left", padx=3)

        self.btn_room = ctk.CTkButton(
            self.bar, text="Draw Room", width=96, height=30,
            fg_color=Theme.BG_CARD, hover_color=Theme.WARNING,
            border_width=1, border_color=Theme.BORDER,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self.set_mode(FloorPlanCanvas.MODE_EDIT_ROOM),
        )
        self.btn_room.pack(side="left", padx=3)

        self.btn_done_room = ctk.CTkButton(
            self.bar, text="Finish Room", width=96, height=30,
            fg_color=Theme.WARNING, hover_color=Theme.PRIMARY_LIGHT,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._finish_room,
        )
        # Shown only while drawing a room outline
        self.btn_done_room.pack_forget()

        self.btn_cancel = ctk.CTkButton(
            self.bar, text="Cancel", width=72, height=30,
            fg_color=Theme.BG_CARD, hover_color=Theme.PANEL_LIGHT,
            border_width=1, border_color=Theme.BORDER,
            font=ctk.CTkFont(size=11),
            command=lambda: self.set_mode(FloorPlanCanvas.MODE_VIEW),
        )
        self.btn_cancel.pack(side="left", padx=3)

        self._highlight_mode(FloorPlanCanvas.MODE_VIEW)

    def set_mode(self, mode: str):
        self.floorplan.set_mode(mode)

    def _on_mode_changed(self, mode: str):
        self._highlight_mode(mode)
        hints = {
            FloorPlanCanvas.MODE_VIEW: "Drag plan to pan · Drag marker to move · Click marker to edit",
            FloorPlanCanvas.MODE_PLACE_PIR: "Click the plan to place a PIR sensor · Right-click cancels",
            FloorPlanCanvas.MODE_PLACE_CAMERA: "Click the plan to place a camera · Right-click cancels",
            FloorPlanCanvas.MODE_EDIT_ROOM: "Click corners · Double-click or Finish Room to close · Right-click clears",
        }
        if self.status_label is not None:
            self.status_label.configure(text=hints.get(mode, ""))
        if mode == FloorPlanCanvas.MODE_EDIT_ROOM:
            self.btn_done_room.pack(side="left", padx=3, after=self.btn_room)
        else:
            self.btn_done_room.pack_forget()

    def _highlight_mode(self, mode: str):
        def style(btn, active, active_color):
            btn.configure(
                fg_color=active_color if active else Theme.BG_CARD,
                border_color=active_color if active else Theme.BORDER,
            )

        style(self.btn_pir, mode == FloorPlanCanvas.MODE_PLACE_PIR, Theme.SUCCESS)
        style(self.btn_cam, mode == FloorPlanCanvas.MODE_PLACE_CAMERA, Theme.PRIMARY)
        style(self.btn_room, mode == FloorPlanCanvas.MODE_EDIT_ROOM, Theme.WARNING)

    def refresh_from_db(self):
        if self._suppress_notify:
            return
        dm = self._dm()
        if dm is None:
            self.floorplan.set_devices([])
            self.floorplan.set_rooms([])
            return

        devices = dm.list_devices() or []
        rooms_raw = dm.list_rooms() or []
        rooms = []
        for r in rooms_raw:
            entry = dict(r)
            entry["_points"] = dm.parse_room_polygon(r)
            rooms.append(entry)
        self.floorplan.set_devices(devices)
        self.floorplan.set_rooms(rooms)

    def _toast(self, title, message, type_="info"):
        notes = getattr(self.app, "notifications", None)
        if notes is not None:
            notes.show(title, message, type=type_)

    def _on_place(self, device_type: str, x_norm: float, y_norm: float):
        dm = self._dm()
        if dm is None:
            return
        floor_id = dm.get_active_floor_plan_id()

        def after_save(_device):
            self.set_mode(FloorPlanCanvas.MODE_VIEW)
            self.refresh_from_db()
            self._toast("Device placed", "Marker saved — it will stay after restart.", type_="success")

        DeviceEditDialog(
            self.app,
            dm,
            device=None,
            device_type=device_type,
            x_norm=x_norm,
            y_norm=y_norm,
            floor_plan_id=floor_id,
            on_saved=after_save,
        )

    def _on_device_moved(self, device_uid: str, x_norm: float, y_norm: float):
        dm = self._dm()
        if dm is None:
            return
        # Quiet refresh — listener would redraw while we're already showing the new spot
        self._suppress_notify = True
        try:
            dm.move_device(device_uid, x_norm, y_norm)
        finally:
            self._suppress_notify = False
        self.refresh_from_db()

    def _on_device_selected(self, device_uid: str):
        dm = self._dm()
        if dm is None:
            return
        device = dm.get_device(device_uid)
        if not device:
            return

        def after_save(_d):
            self.refresh_from_db()
            self._toast("Device updated", f"{device_uid} saved.", type_="success")

        def after_delete(_uid):
            self.floorplan.set_selected_uid(None)
            self.refresh_from_db()
            self._toast("Device removed", f"{device_uid} deleted.", type_="warning")

        DeviceEditDialog(
            self.app,
            dm,
            device=device,
            on_saved=after_save,
            on_deleted=after_delete,
        )

    def _on_room_complete(self, points: list):
        self._pending_room_points = points
        RoomNameDialog(self.app, default_name="Room", on_confirm=self._save_room)

    def _finish_room(self):
        self.floorplan.finish_room_draft()

    def _save_room(self, name: str):
        dm = self._dm()
        points = self._pending_room_points or []
        self._pending_room_points = None
        if dm is None or len(points) < 3:
            return
        room = dm.create_room(name, points)
        if room:
            self.set_mode(FloorPlanCanvas.MODE_VIEW)
            self.refresh_from_db()
            self._toast("Room saved", f"“{name}” outline stored on this floor.", type_="success")
        else:
            self._toast("Room not saved", "Need at least 3 points.", type_="warning")

    def prompt_place_unknown_sensor(self, sensor_uid: str, location: str = ""):
        # Motion arrived from a UID that is not on the plan yet
        dm = self._dm()
        if dm is None:
            return
        if dm.get_device(sensor_uid):
            return

        def after_save(_d):
            self.refresh_from_db()
            self._toast("Sensor placed", f"{sensor_uid} is now on the floor plan.", type_="success")

        DeviceEditDialog(
            self.app,
            dm,
            device=None,
            device_type="pir",
            x_norm=0.5,
            y_norm=0.5,
            floor_plan_id=dm.get_active_floor_plan_id(),
            initial_uid=sensor_uid,
            initial_name=location or sensor_uid,
            title=f"Place unknown sensor — {sensor_uid}",
            on_saved=after_save,
        )
