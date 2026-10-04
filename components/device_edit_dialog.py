"""Modal to create/edit a PIR or camera device on the floor plan."""
from __future__ import annotations

import customtkinter as ctk

from utils.constants import Theme


class DeviceEditDialog(ctk.CTkToplevel):
    """Collect uid / name / room / linked camera / enabled before saving to DB."""

    def __init__(
        self,
        master,
        device_manager,
        *,
        device=None,
        device_type="pir",
        x_norm=None,
        y_norm=None,
        floor_plan_id=None,
        initial_uid=None,
        initial_name=None,
        title=None,
        on_saved=None,
        on_deleted=None,
    ):
        super().__init__(master)
        self.dm = device_manager
        self.device = device
        self.device_type = (device or {}).get("device_type") or device_type
        self.x_norm = x_norm if x_norm is not None else (device or {}).get("x_norm")
        self.y_norm = y_norm if y_norm is not None else (device or {}).get("y_norm")
        self.floor_plan_id = floor_plan_id or (device or {}).get("floor_plan_id")
        # Used when placing an unknown serial sensor so the UID matches the ESP32
        self.initial_uid = initial_uid
        self.initial_name = initial_name
        self.on_saved = on_saved
        self.on_deleted = on_deleted
        self.result = None

        is_edit = device is not None
        self.title(title or ("Edit Device" if is_edit else "Place Device"))
        self.geometry("420x460")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_SECONDARY)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self._build_form(is_edit)
        self.after(40, self._center_on_parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _center_on_parent(self):
        try:
            self.update_idletasks()
            parent = self.master.winfo_toplevel()
            px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

    def _build_form(self, is_edit: bool):
        pad = {"padx": 24, "pady": 4}
        kind = "Camera" if self.device_type == "camera" else "PIR Sensor"

        ctk.CTkLabel(
            self, text=f"{'Edit' if is_edit else 'Place'} {kind}",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(20, 8))

        ctk.CTkLabel(self, text="Device UID", text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12)).pack(anchor="w", **pad)
        default_uid = (
            (self.device or {}).get("device_uid")
            or self.initial_uid
            or self.dm.suggest_uid(self.device_type)
        )
        self.uid_entry = ctk.CTkEntry(self, height=36, fg_color=Theme.BG_CARD, border_color=Theme.BORDER)
        self.uid_entry.pack(fill="x", padx=24, pady=(0, 8))
        self.uid_entry.insert(0, default_uid)

        ctk.CTkLabel(self, text="Display name", text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12)).pack(anchor="w", **pad)
        self.name_entry = ctk.CTkEntry(self, height=36, fg_color=Theme.BG_CARD, border_color=Theme.BORDER)
        self.name_entry.pack(fill="x", padx=24, pady=(0, 8))
        self.name_entry.insert(
            0,
            (self.device or {}).get("name") or self.initial_name or default_uid,
        )

        # Room dropdown — optional link for later Stage 4 highlight
        rooms = self.dm.list_rooms(self.floor_plan_id) if self.dm else []
        self._room_map = {"(none)": None}
        room_labels = ["(none)"]
        for r in rooms:
            label = r.get("name") or f"Room {r.get('id')}"
            # Keep labels unique in the menu
            base = label
            n = 2
            while label in self._room_map:
                label = f"{base} ({n})"
                n += 1
            self._room_map[label] = r.get("id")
            room_labels.append(label)

        ctk.CTkLabel(self, text="Room", text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12)).pack(anchor="w", **pad)
        self.room_menu = ctk.CTkOptionMenu(
            self, values=room_labels, height=34,
            fg_color=Theme.BG_CARD, button_color=Theme.PANEL_LIGHT,
            button_hover_color=Theme.PRIMARY, dropdown_fg_color=Theme.BG_CARD,
        )
        self.room_menu.pack(fill="x", padx=24, pady=(0, 8))
        current_room = (self.device or {}).get("room_id")
        chosen = "(none)"
        for label, rid in self._room_map.items():
            if rid == current_room:
                chosen = label
                break
        self.room_menu.set(chosen)

        # PIR sensors can point at a camera for snapshots
        cameras = self.dm.list_all_devices(device_type="camera") if self.dm else []
        cam_values = ["(none)"] + [c.get("device_uid") for c in cameras if c.get("device_uid")]
        ctk.CTkLabel(self, text="Linked camera", text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12)).pack(anchor="w", **pad)
        self.camera_menu = ctk.CTkOptionMenu(
            self, values=cam_values or ["(none)"], height=34,
            fg_color=Theme.BG_CARD, button_color=Theme.PANEL_LIGHT,
            button_hover_color=Theme.PRIMARY, dropdown_fg_color=Theme.BG_CARD,
        )
        self.camera_menu.pack(fill="x", padx=24, pady=(0, 8))
        linked = (self.device or {}).get("linked_camera_uid") or "(none)"
        if linked not in cam_values:
            linked = "(none)"
        self.camera_menu.set(linked)
        if self.device_type == "camera":
            self.camera_menu.configure(state="disabled")

        self.enabled_var = ctk.BooleanVar(value=bool((self.device or {}).get("enabled", True)))
        ctk.CTkCheckBox(
            self, text="Enabled on floor plan", variable=self.enabled_var,
            text_color=Theme.TEXT_PRIMARY, fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_LIGHT,
        ).pack(anchor="w", padx=24, pady=(4, 8))

        self.error_lbl = ctk.CTkLabel(self, text="", text_color=Theme.DANGER, font=ctk.CTkFont(size=11))
        self.error_lbl.pack(anchor="w", padx=24)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(8, 20), side="bottom")

        ctk.CTkButton(
            btns, text="Cancel", width=90, height=34,
            fg_color=Theme.BG_CARD, hover_color=Theme.PANEL_LIGHT,
            border_width=1, border_color=Theme.BORDER,
            command=self._cancel,
        ).pack(side="left")

        if is_edit:
            ctk.CTkButton(
                btns, text="Delete", width=90, height=34,
                fg_color=Theme.DANGER, hover_color=Theme.DANGER_LIGHT,
                command=self._delete,
            ).pack(side="left", padx=8)

        ctk.CTkButton(
            btns, text="Save", width=110, height=34,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_LIGHT,
            font=ctk.CTkFont(weight="bold"),
            command=self._save,
        ).pack(side="right")

    def _save(self):
        uid = self.uid_entry.get().strip()
        name = self.name_entry.get().strip() or uid
        if not uid:
            self.error_lbl.configure(text="Device UID is required.")
            return

        room_id = self._room_map.get(self.room_menu.get())
        linked = self.camera_menu.get()
        linked_camera_uid = None if linked in (None, "", "(none)") else linked
        enabled = bool(self.enabled_var.get())

        if self.device is None:
            created = self.dm.create_device(
                device_type=self.device_type,
                device_uid=uid,
                name=name,
                floor_plan_id=self.floor_plan_id,
                room_id=room_id,
                x_norm=self.x_norm,
                y_norm=self.y_norm,
                linked_camera_uid=linked_camera_uid,
                enabled=enabled,
            )
            if created is None:
                self.error_lbl.configure(text="Could not create — UID may already exist.")
                return
            self.result = created
        else:
            old_uid = self.device.get("device_uid")
            updated = self.dm.update_device(
                old_uid,
                device_uid=uid,
                name=name,
                room_id=room_id,
                linked_camera_uid=linked_camera_uid,
                enabled=enabled,
                x_norm=self.x_norm if self.x_norm is not None else self.device.get("x_norm"),
                y_norm=self.y_norm if self.y_norm is not None else self.device.get("y_norm"),
            )
            if updated is None:
                self.error_lbl.configure(text="Could not save — check UID is unique.")
                return
            self.result = updated

        if self.on_saved:
            self.on_saved(self.result)
        self.destroy()

    def _delete(self):
        if not self.device:
            return
        uid = self.device.get("device_uid")
        self.dm.delete_device(uid)
        if self.on_deleted:
            self.on_deleted(uid)
        self.result = None
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class RoomNameDialog(ctk.CTkToplevel):
    """Ask for a room name after the polygon is closed on the canvas."""

    def __init__(self, master, default_name="Room", on_confirm=None):
        super().__init__(master)
        self.on_confirm = on_confirm
        self.result = None
        self.title("Name Room")
        self.geometry("360x180")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG_SECONDARY)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        ctk.CTkLabel(
            self, text="Room name",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(24, 8))

        self.entry = ctk.CTkEntry(self, height=36, fg_color=Theme.BG_CARD, border_color=Theme.BORDER)
        self.entry.pack(fill="x", padx=24)
        self.entry.insert(0, default_name)
        self.entry.focus_set()

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=20)
        ctk.CTkButton(
            btns, text="Cancel", width=90, height=32,
            fg_color=Theme.BG_CARD, border_width=1, border_color=Theme.BORDER,
            command=self.destroy,
        ).pack(side="left")
        ctk.CTkButton(
            btns, text="Save Room", width=110, height=32,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_LIGHT,
            command=self._ok,
        ).pack(side="right")
        self.bind("<Return>", lambda e: self._ok())

    def _ok(self):
        name = self.entry.get().strip() or "Room"
        self.result = name
        if self.on_confirm:
            self.on_confirm(name)
        self.destroy()
