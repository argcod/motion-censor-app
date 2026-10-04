import datetime
import threading
from utils.logger import logger
from core.risk_engine import RiskEngine


class MotionManager:
    def __init__(self, db_manager, camera_manager, settings_manager, device_manager=None, notifier_manager=None):
        self.db = db_manager
        self.camera = camera_manager
        self.settings = settings_manager
        self.devices = device_manager
        self.notifier = notifier_manager
        self.risk = RiskEngine()

        self.ui_callbacks = []
        self.last_event_time = 0
        self.cooldown_seconds = 2  # Desktop debounce only — mobile cooldown lives in AlertPolicy

    def set_notifier(self, notifier_manager):
        # Allows main.py to attach NotifierManager after both objects exist
        self.notifier = notifier_manager

    def register_ui_callback(self, callback):
        self.ui_callbacks.append(callback)

    def simulate(self, sensor_uid: str):
        """Same pipeline as serial MOTION, but started from the UI Simulate button."""
        sensor_uid = (sensor_uid or "").strip() or "Sensor01"
        location = "Unknown"
        if self.devices is not None:
            device = self.devices.get_device(sensor_uid)
            if device:
                location = device.get("name") or sensor_uid
                room = None
                if device.get("room_id"):
                    room = self.devices.get_room(device["room_id"])
                if room and room.get("name"):
                    location = room["name"]
        logger.info(f"Simulate motion for {sensor_uid} at {location}")
        self.on_motion_detected(location, sensor_uid)

    def on_motion_detected(self, location, sensor_id):
        current_time = datetime.datetime.now().timestamp()

        # Debounce to prevent duplicate events from same physical motion
        if current_time - self.last_event_time < self.cooldown_seconds:
            logger.debug("Motion event ignored due to cooldown.")
            return

        self.last_event_time = current_time

        logger.info(f"Processing motion event from {sensor_id} at {location}")

        snapshot_path = None
        camera_uid = None
        device = None
        x_norm, y_norm = 0.5, 0.5
        room_name = None
        room_points = []
        sensor_known = False

        # Prefer linked camera / coords from devices table when DeviceManager is available
        if self.devices is not None:
            device = self.devices.get_device(sensor_id)
            if device:
                sensor_known = True
                camera_uid = device.get("linked_camera_uid")
                if device.get("x_norm") is not None:
                    x_norm = float(device["x_norm"])
                if device.get("y_norm") is not None:
                    y_norm = float(device["y_norm"])
                if device.get("name") and location in (None, "", "Unknown"):
                    location = device.get("name")
                if device.get("room_id"):
                    room = self.devices.get_room(device["room_id"])
                    if room:
                        room_name = room.get("name")
                        room_points = self.devices.parse_room_polygon(room)
                        if location in (None, "", "Unknown", device.get("name")):
                            location = room_name or location

        armed = self.settings.get("mobile_alerts_armed", "false").lower() == "true"
        risk_level = self.risk.compute(armed=armed, sensor_known=sensor_known)

        capture_enabled = self.settings.get("camera_capture_enabled", "true").lower() == "true"
        if capture_enabled and self.camera.running:
            if not camera_uid:
                camera_uid = "Camera01"
            snapshot_path = self.camera.capture_snapshot(prefix=f"motion_{sensor_id}")

        detected_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event = {
            "location": location,
            "sensor_id": sensor_id,
            "camera_uid": camera_uid,
            "snapshot_path": snapshot_path,
            "risk_level": risk_level,
            "x_norm": x_norm,
            "y_norm": y_norm,
            "room_name": room_name,
            "room_points": room_points,
            "sensor_known": sensor_known,
            "detected_at": detected_at,
            "armed": armed,
        }

        # Run DB insert off the serial thread so the reader stays responsive
        threading.Thread(
            target=self._log_and_notify,
            args=(event,),
            daemon=True,
        ).start()

    def _log_and_notify(self, event: dict):
        try:
            sensor_id = event["sensor_id"]
            location = event["location"]
            self.db.update_sensor_activity(sensor_id, location)
            # camera_uid string — never the old cameras.id FK that broke inserts
            log_id = self.db.log_motion(
                location,
                sensor_id,
                camera_uid=event.get("camera_uid"),
                snapshot_path=event.get("snapshot_path"),
                risk_level=event.get("risk_level"),
                is_read=False,
            )
            # Keep the new row id on the event so Active Alert / bell can open details
            if log_id:
                event["id"] = log_id

            for cb in self.ui_callbacks:
                cb(event)

            # Phase 5 — fan-out to Telegram/Discord/WhatsApp on a worker queue (not UI thread)
            if self.notifier is not None:
                self.notifier.enqueue_motion(event)
        except Exception as e:
            logger.error(f"Failed to process motion workflow: {e}")
