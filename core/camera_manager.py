import cv2
import threading
import time
import datetime
from utils.logger import logger
from utils.paths import ensure_dir, path_str, snapshot_path


class CameraManager:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.running = False
        self.thread = None
        self.current_frame = None
        self.lock = threading.Lock()

        # Snapshots always live under project/snapshots, not the cwd
        ensure_dir(snapshot_path())

    def start(self, camera_index=None):
        if camera_index is not None:
            self.camera_index = camera_index

        if self.running:
            return True

        try:
            # Avoid blocking indefinitely if camera is unavailable
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                # Fallback to default backend
                self.cap = cv2.VideoCapture(self.camera_index)

            if not self.cap.isOpened():
                logger.error(f"Failed to open camera index {self.camera_index}")
                return False

            self.running = True
            self.thread = threading.Thread(target=self._update_loop, daemon=True)
            self.thread.start()
            logger.info(f"Camera {self.camera_index} started.")
            return True
        except Exception as e:
            logger.error(f"Error starting camera: {e}")
            return False

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        self.cap = None
        logger.info("Camera stopped.")

    def _update_loop(self):
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    # Convert BGR to RGB for Tkinter/Pillow
                    self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                time.sleep(0.1)
            time.sleep(0.03)  # Cap at roughly 30 FPS

    def get_frame(self):
        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None

    def capture_snapshot(self, prefix="motion"):
        frame = self.get_frame()
        if frame is None:
            return None

        # Convert back to BGR for saving with cv2
        save_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        date_folder = datetime.datetime.now().strftime("%Y-%m-%d")

        folder_path = ensure_dir(snapshot_path(date_folder))
        filename = f"{prefix}_{timestamp}.jpg"
        filepath = folder_path / filename

        try:
            cv2.imwrite(path_str(filepath), save_frame)
            logger.info(f"Snapshot saved: {filepath}")
            # Store a project-relative path so DB rows stay portable
            return f"snapshots/{date_folder}/{filename}"
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return None
