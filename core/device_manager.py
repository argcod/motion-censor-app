"""Device CRUD — single source of truth for PIR/camera markers on the floor plan."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from utils.logger import logger
from utils.paths import asset_path, ensure_dir, path_str


class DeviceManager:
    def __init__(self, db_manager, settings_manager):
        self.db = db_manager
        self.settings = settings_manager
        # Pages register here so Sensors/Cameras stay in sync after place/edit/delete
        self._change_listeners = []

    def register_change_listener(self, callback):
        if callback not in self._change_listeners:
            self._change_listeners.append(callback)

    def unregister_change_listener(self, callback):
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_changed(self):
        for cb in list(self._change_listeners):
            try:
                cb()
            except Exception as e:
                logger.error(f"Device change listener failed: {e}")

    def get_active_floor_plan_id(self):
        raw = self.settings.get("active_floor_plan_id", "")
        try:
            return int(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def list_floor_plans(self):
        return self.db.get_floor_plans()

    def set_active_floor_plan(self, floor_plan_id):
        # Remember the plan the viewport should show after restart
        self.settings.set("active_floor_plan_id", str(floor_plan_id))

    def get_active_floor_plan(self):
        fp_id = self.get_active_floor_plan_id()
        if fp_id is None:
            plans = self.db.get_floor_plans()
            return plans[0] if plans else None
        plan = self.db.get_floor_plan(fp_id)
        if plan is None:
            plans = self.db.get_floor_plans()
            return plans[0] if plans else None
        return plan

    def replace_floor_plan_image(self, floor_plan_id, source_path):
        # Phase 6 — copy the chosen file into assets/ and remember the path in MySQL
        src = Path(source_path)
        if not src.is_file():
            logger.warning(f"Floor plan image not found: {source_path}")
            return None

        ensure_dir(asset_path())
        ext = src.suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            ext = ".jpg"
        dest = asset_path(f"floor_plan_{floor_plan_id}{ext}")
        try:
            shutil.copy2(src, dest)
        except OSError as e:
            logger.error(f"Failed to copy floor plan image: {e}")
            return None

        # Store a project-relative path so the app still finds it after moving folders
        stored = f"assets/{dest.name}"
        self.db.update_floor_plan(floor_plan_id, image_path=stored)
        plan = self.db.get_floor_plan(floor_plan_id)
        self._notify_changed()
        logger.info(f"Floor plan {floor_plan_id} image replaced → {path_str(dest)}")
        return plan

    def list_devices(self, device_type=None, floor_plan_id=None):
        # Prefer the active floor so markers match what the viewport shows
        if floor_plan_id is None:
            floor_plan_id = self.get_active_floor_plan_id()
        return self.db.get_devices(floor_plan_id=floor_plan_id, device_type=device_type)

    def list_all_devices(self, device_type=None):
        # Sensors/Cameras pages show every device, not only the active floor
        return self.db.get_devices(floor_plan_id=None, device_type=device_type)

    def get_device(self, device_uid):
        return self.db.get_device_by_uid(device_uid)

    def list_rooms(self, floor_plan_id=None):
        if floor_plan_id is None:
            floor_plan_id = self.get_active_floor_plan_id()
        if floor_plan_id is None:
            return []
        return self.db.get_rooms(floor_plan_id)

    def get_room(self, room_id):
        return self.db.get_room(room_id)

    def suggest_uid(self, device_type: str) -> str:
        # Auto-fill a free Sensor/Camera id so place clicks are one less typing step
        prefix = "Sensor" if device_type == "pir" else "Camera"
        existing = {
            (d.get("device_uid") or "")
            for d in self.list_all_devices(device_type=device_type)
        }
        for i in range(1, 1000):
            candidate = f"{prefix}{i:02d}"
            if candidate not in existing:
                return candidate
        return f"{prefix}{len(existing) + 1:02d}"

    def create_device(
        self,
        device_type,
        device_uid,
        name=None,
        floor_plan_id=None,
        room_id=None,
        x_norm=None,
        y_norm=None,
        linked_camera_uid=None,
        enabled=True,
        meta_json=None,
    ):
        device_type = "camera" if device_type == "camera" else "pir"
        device_uid = (device_uid or "").strip()
        if not device_uid:
            logger.warning("create_device requires a device_uid")
            return None
        if self.get_device(device_uid):
            logger.warning(f"Device uid already exists: {device_uid}")
            return None

        if floor_plan_id is None:
            floor_plan_id = self.get_active_floor_plan_id()
        if name is None or not str(name).strip():
            name = device_uid

        # Cameras default to OpenCV index 0 until the user edits meta
        if device_type == "camera" and meta_json is None:
            meta_json = json.dumps({"device_index": 0})

        row_id = self.db.insert_device(
            device_type=device_type,
            device_uid=device_uid,
            name=name,
            floor_plan_id=floor_plan_id,
            room_id=room_id,
            x_norm=x_norm,
            y_norm=y_norm,
            linked_camera_uid=linked_camera_uid,
            enabled=enabled,
            meta_json=meta_json,
        )
        if row_id is None:
            return None
        self._notify_changed()
        return self.get_device(device_uid)

    def update_device(self, device_uid, **kwargs):
        if not self.get_device(device_uid):
            logger.warning(f"update_device: unknown uid {device_uid}")
            return None
        # Renaming uid must stay unique
        new_uid = kwargs.get("device_uid")
        if new_uid and new_uid != device_uid:
            clash = self.get_device(new_uid)
            if clash:
                logger.warning(f"Cannot rename to existing uid {new_uid}")
                return None
        result = self.db.update_device(device_uid, **kwargs)
        if result is None:
            return None
        lookup = new_uid or device_uid
        self._notify_changed()
        return self.get_device(lookup)

    def delete_device(self, device_uid):
        if not self.get_device(device_uid):
            return False
        self.db.delete_device(device_uid)
        self._notify_changed()
        return True

    def move_device(self, device_uid, x_norm, y_norm):
        # Save normalized coords so zoom/pan never shift the marker in the DB
        x_norm = max(0.0, min(1.0, float(x_norm)))
        y_norm = max(0.0, min(1.0, float(y_norm)))
        result = self.db.update_device(device_uid, x_norm=x_norm, y_norm=y_norm)
        if result is None:
            return None
        self._notify_changed()
        return self.get_device(device_uid)

    def create_room(self, name, polygon_points, floor_plan_id=None):
        if floor_plan_id is None:
            floor_plan_id = self.get_active_floor_plan_id()
        if floor_plan_id is None:
            logger.warning("create_room needs an active floor plan")
            return None
        name = (name or "").strip() or "Room"
        # Normalize points as [[x,y],...] JSON for later room highlight animation
        clean = [[float(x), float(y)] for x, y in (polygon_points or [])]
        if len(clean) < 3:
            logger.warning("Room polygon needs at least 3 points")
            return None
        polygon_json = json.dumps(clean)
        room_id = self.db.insert_room(floor_plan_id, name, polygon_json)
        if room_id is None:
            return None
        self._notify_changed()
        return self.db.get_room(room_id)

    def update_room(self, room_id, name=None, polygon_points=None):
        polygon_json = None
        if polygon_points is not None:
            clean = [[float(x), float(y)] for x, y in polygon_points]
            polygon_json = json.dumps(clean)
        result = self.db.update_room(room_id, name=name, polygon_json=polygon_json)
        if result is None:
            return None
        self._notify_changed()
        return self.db.get_room(room_id)

    def delete_room(self, room_id):
        self.db.delete_room(room_id)
        self._notify_changed()
        return True

    def parse_room_polygon(self, room) -> list:
        raw = (room or {}).get("polygon_json")
        if not raw:
            return []
        try:
            pts = json.loads(raw)
            return [(float(p[0]), float(p[1])) for p in pts if len(p) >= 2]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
