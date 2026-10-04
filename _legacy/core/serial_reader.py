import serial
import threading
import time

class SerialReader:
    def __init__(self, port='COM3', baudrate=115200, on_motion_callback=None):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.running = False
        self.thread = None
        self.on_motion_callback = on_motion_callback

    def connect(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            return True
        except serial.SerialException as e:
            print(f"Error connecting to serial port: {e}")
            return False

    def start(self):
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

    def _read_loop(self):
        while self.running:
            try:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line.startswith("MOTION"):
                        parts = line.split(",")
                        location = parts[1] if len(parts) > 1 else "Unknown"
                        sensor_id = parts[2] if len(parts) > 2 else "Unknown"
                        if self.on_motion_callback:
                            self.on_motion_callback(location, sensor_id)
            except Exception as e:
                print(f"Serial read error: {e}")
                time.sleep(1)
            time.sleep(0.1)
