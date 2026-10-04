import serial
import serial.tools.list_ports
import threading
import time
from utils.logger import logger

class SerialManager:
    def __init__(self, port=None, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.running = False
        self.thread = None
        self.callbacks = []
        self.connection_callbacks = []

    def register_callback(self, callback):
        self.callbacks.append(callback)

    def register_connection_callback(self, callback):
        self.connection_callbacks.append(callback)

    def _notify_connection_status(self, is_connected):
        for cb in self.connection_callbacks:
            try:
                cb(is_connected)
            except Exception as e:
                logger.error(f"Connection callback error: {e}")

    @staticmethod
    def get_available_ports():
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self):
        if not self.port:
            ports = self.get_available_ports()
            if ports:
                self.port = ports[0]
                logger.info(f"Auto-selected port {self.port}")
            else:
                logger.warning("No COM ports available.")
                return False

        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self._notify_connection_status(True)
            return True
        except serial.SerialException as e:
            logger.error(f"Error connecting to serial port {self.port}: {e}")
            self._notify_connection_status(False)
            return False

    def start(self):
        if self.running:
            return True
            
        if self.connect():
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            return True
        return False

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.serial_conn = None
        self._notify_connection_status(False)

    @property
    def is_connected(self):
        # Phase 6 — Settings/health widgets need a simple online check
        return bool(self.serial_conn and self.serial_conn.is_open)

    def restart(self, port=None, baudrate=None):
        # Settings Save calls this so a new COM/baud takes effect without restarting the app
        if port is not None:
            self.port = port
        if baudrate is not None:
            try:
                self.baudrate = int(baudrate)
            except (TypeError, ValueError):
                logger.warning(f"Invalid baudrate '{baudrate}', keeping {self.baudrate}")
        self.stop()
        ok = self.start()
        logger.info(
            f"Serial restart → port={self.port} baud={self.baudrate} connected={ok}"
        )
        return ok

    def _read_loop(self):
        while self.running:
            try:
                if self.serial_conn and self.serial_conn.is_open:
                    if self.serial_conn.in_waiting > 0:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            logger.debug(f"Serial received: {line}")
                            self._process_line(line)
                else:
                    # Connection lost, try to reconnect
                    self._notify_connection_status(False)
                    time.sleep(2)
                    self.connect()
            except Exception as e:
                logger.error(f"Serial read error: {e}")
                self._notify_connection_status(False)
                if self.serial_conn:
                    self.serial_conn.close()
                time.sleep(2)
                self.connect()
            time.sleep(0.05)

    def _process_line(self, line):
        # Boot heartbeat from firmware — treat as connected, do not invent a motion event
        if line.startswith("SYSTEM_READY"):
            logger.info("ESP32 reported SYSTEM_READY")
            self._notify_connection_status(True)
            return

        if line.startswith("MOTION"):
            parts = line.split(",")
            location = parts[1].strip() if len(parts) > 1 else "Unknown"
            sensor_id = parts[2].strip() if len(parts) > 2 else "Unknown"

            for cb in self.callbacks:
                try:
                    cb(location, sensor_id)
                except Exception as e:
                    logger.error(f"Error in motion callback: {e}")
