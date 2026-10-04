import mysql.connector
from mysql.connector import Error
import datetime
import bcrypt
from utils.logger import logger
from utils.paths import asset_path, path_str


class DatabaseManager:
    def __init__(self, host='localhost', database='motion_db', user='root', password='root'):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.conn = None
        self.setup_database()

    def connect(self):
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                connection_timeout=3
            )
            return self.conn.is_connected()
        except Error as e:
            logger.error(f"Error connecting to MySQL: {e}")
            return False

    def get_connection(self):
        if not self.conn or not self.conn.is_connected():
            self.connect()
            if self.conn and self.conn.is_connected():
                self.conn.cursor().execute(f"USE {self.database}")
        return self.conn

    def setup_database(self):
        if not self.connect():
            logger.error("Failed to connect to MySQL for setup.")
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            cursor.execute(f"USE {self.database}")

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL
                )
            """)

            # Legacy sensors/cameras kept for now — DeviceManager is the source of truth going forward
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensors (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sensor_id VARCHAR(50) NOT NULL UNIQUE,
                    location VARCHAR(100),
                    enabled BOOLEAN DEFAULT TRUE,
                    last_detection DATETIME
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    device_index INT NOT NULL,
                    location VARCHAR(100),
                    enabled BOOLEAN DEFAULT TRUE,
                    resolution_w INT DEFAULT 1280,
                    resolution_h INT DEFAULT 720
                )
            """)

            # motion_log without camera FK — camera_uid is a free string, not a fragile cameras.id
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS motion_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    detected_at DATETIME NOT NULL,
                    location VARCHAR(255) NOT NULL,
                    sensor_id VARCHAR(50),
                    camera_uid VARCHAR(100) NULL,
                    snapshot_path VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'Motion Detected',
                    risk_level VARCHAR(50) NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    mobile_alert_sent BOOLEAN DEFAULT FALSE,
                    mobile_alert_channels TEXT NULL,
                    mobile_alert_error TEXT NULL,
                    ai_label VARCHAR(100) NULL,
                    ai_confidence FLOAT NULL,
                    bbox_json TEXT NULL
                )
            """)

            # TEXT so webhook URLs and tokens are not truncated at 255
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key VARCHAR(50) PRIMARY KEY,
                    setting_value TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS floor_plans (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    image_path VARCHAR(500) NOT NULL,
                    floor_number INT DEFAULT 1,
                    property_name VARCHAR(100) DEFAULT 'Home',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    floor_plan_id INT NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    polygon_json TEXT NULL,
                    FOREIGN KEY (floor_plan_id) REFERENCES floor_plans(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    device_type ENUM('pir', 'camera') NOT NULL,
                    device_uid VARCHAR(100) NOT NULL UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    floor_plan_id INT NULL,
                    room_id INT NULL,
                    x_norm FLOAT NULL,
                    y_norm FLOAT NULL,
                    linked_camera_uid VARCHAR(100) NULL,
                    enabled BOOLEAN DEFAULT TRUE,
                    meta_json TEXT NULL,
                    last_seen DATETIME NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (floor_plan_id) REFERENCES floor_plans(id) ON DELETE SET NULL,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL
                )
            """)

            self._migrate_schema(cursor)
            self._seed_admin(cursor)
            self._seed_floor_plan_and_devices(cursor)

            self.conn.commit()
            cursor.close()
            logger.info("Database setup complete.")
        except Error as e:
            logger.error(f"Error setting up database: {e}")

    def _column_exists(self, cursor, table, column):
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """,
            (self.database, table, column),
        )
        return cursor.fetchone()[0] > 0

    def _add_column_if_missing(self, cursor, table, column, definition):
        # Additive migration so older installs pick up new fields without a wipe
        if not self._column_exists(cursor, table, column):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            logger.info(f"Added column {table}.{column}")

    def _migrate_schema(self, cursor):
        # Expand setting_value for long tokens/webhooks if this DB was created earlier
        try:
            cursor.execute(
                """
                SELECT DATA_TYPE FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'system_settings'
                  AND COLUMN_NAME = 'setting_value'
                """,
                (self.database,),
            )
            row = cursor.fetchone()
            if row and row[0] and row[0].lower() in ("varchar", "char"):
                cursor.execute("ALTER TABLE system_settings MODIFY setting_value TEXT")
                logger.info("Migrated system_settings.setting_value to TEXT")
        except Error as e:
            logger.warning(f"Could not alter system_settings.setting_value: {e}")

        # Older motion_log had camera_id FK — drop it so inserts no longer fail on empty cameras
        try:
            cursor.execute(
                """
                SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'motion_log'
                  AND COLUMN_NAME = 'camera_id' AND REFERENCED_TABLE_NAME IS NOT NULL
                """,
                (self.database,),
            )
            for (constraint_name,) in cursor.fetchall() or []:
                cursor.execute(f"ALTER TABLE motion_log DROP FOREIGN KEY `{constraint_name}`")
                logger.info(f"Dropped motion_log FK {constraint_name}")
        except Error as e:
            logger.warning(f"Could not drop motion_log camera_id FK: {e}")

        # Older DBs used `timestamp` — rename so inserts match the canonical column name
        if self._column_exists(cursor, "motion_log", "timestamp") and not self._column_exists(
            cursor, "motion_log", "detected_at"
        ):
            try:
                cursor.execute("ALTER TABLE motion_log CHANGE COLUMN timestamp detected_at DATETIME NOT NULL")
                logger.info("Renamed motion_log.timestamp -> detected_at")
            except Error as e:
                logger.warning(f"Could not rename motion_log.timestamp: {e}")

        self._add_column_if_missing(cursor, "motion_log", "detected_at", "DATETIME NULL")
        self._add_column_if_missing(cursor, "motion_log", "snapshot_path", "VARCHAR(255) NULL")
        self._add_column_if_missing(cursor, "motion_log", "status", "VARCHAR(50) DEFAULT 'Motion Detected'")
        self._add_column_if_missing(cursor, "motion_log", "camera_uid", "VARCHAR(100) NULL")
        self._add_column_if_missing(cursor, "motion_log", "risk_level", "VARCHAR(50) NULL")
        self._add_column_if_missing(cursor, "motion_log", "is_read", "BOOLEAN DEFAULT FALSE")
        self._add_column_if_missing(cursor, "motion_log", "mobile_alert_sent", "BOOLEAN DEFAULT FALSE")
        self._add_column_if_missing(cursor, "motion_log", "mobile_alert_channels", "TEXT NULL")
        self._add_column_if_missing(cursor, "motion_log", "mobile_alert_error", "TEXT NULL")
        self._add_column_if_missing(cursor, "motion_log", "ai_label", "VARCHAR(100) NULL")
        self._add_column_if_missing(cursor, "motion_log", "ai_confidence", "FLOAT NULL")
        self._add_column_if_missing(cursor, "motion_log", "bbox_json", "TEXT NULL")

        # Copy legacy camera_id into camera_uid text so old rows stay readable
        if self._column_exists(cursor, "motion_log", "camera_id"):
            try:
                cursor.execute(
                    """
                    UPDATE motion_log
                    SET camera_uid = CAST(camera_id AS CHAR)
                    WHERE camera_uid IS NULL AND camera_id IS NOT NULL
                    """
                )
            except Error as e:
                logger.warning(f"Could not backfill camera_uid from camera_id: {e}")

    def _seed_admin(self, cursor):
        cursor.execute("SELECT password FROM users WHERE username = 'admin'")
        row = cursor.fetchone()
        if not row:
            hashed = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                ('admin', hashed),
            )
        else:
            existing_pw = row[0]
            if not existing_pw.startswith('$2b$'):
                logger.info("Migrating plain-text admin password to bcrypt...")
                hashed = bcrypt.hashpw(existing_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute(
                    "UPDATE users SET password = %s WHERE username = 'admin'",
                    (hashed,),
                )

    def _seed_floor_plan_and_devices(self, cursor):
        # One default isometric plan so 3D Environment has something to show after login
        cursor.execute("SELECT id FROM floor_plans LIMIT 1")
        row = cursor.fetchone()
        if row:
            floor_plan_id = row[0]
        else:
            image = path_str(asset_path("isometric_base.jpg")).replace("\\", "/")
            cursor.execute(
                """
                INSERT INTO floor_plans (name, image_path, floor_number, property_name)
                VALUES (%s, %s, %s, %s)
                """,
                ("Main Floor", image, 1, "Home"),
            )
            floor_plan_id = cursor.lastrowid
            logger.info(f"Seeded default floor plan id={floor_plan_id}")

        # Remember which floor plan is active for later placement phases
        cursor.execute(
            """
            INSERT INTO system_settings (setting_key, setting_value)
            VALUES ('active_floor_plan_id', %s)
            ON DUPLICATE KEY UPDATE setting_value = IF(setting_value = '' OR setting_value IS NULL, VALUES(setting_value), setting_value)
            """,
            (str(floor_plan_id),),
        )

        # Optional starter devices so Sensors/Cameras are not empty on first run
        cursor.execute("SELECT COUNT(*) FROM devices")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute(
                """
                INSERT INTO devices
                    (device_type, device_uid, name, floor_plan_id, x_norm, y_norm, linked_camera_uid, enabled, meta_json)
                VALUES
                    ('pir', 'Sensor01', 'PIR Sensor 01', %s, 0.35, 0.45, 'Camera01', TRUE, NULL),
                    ('camera', 'Camera01', 'Camera 01', %s, 0.55, 0.40, NULL, TRUE, '{"device_index": 0}')
                """,
                (floor_plan_id, floor_plan_id),
            )
            logger.info("Seeded default Sensor01 and Camera01 devices")

    def execute_query(self, query, params=None, fetch=False):
        conn = self.get_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())

            if fetch:
                result = cursor.fetchall()
            else:
                conn.commit()
                result = cursor.lastrowid

            cursor.close()
            return result
        except Error as e:
            logger.error(f"Database query error: {e}")
            return None

    def log_motion(
        self,
        location,
        sensor_id,
        camera_uid=None,
        snapshot_path=None,
        status="Motion Detected",
        risk_level=None,
        is_read=False,
    ):
        # Write camera_uid (string) instead of the old cameras.id FK
        query = """
            INSERT INTO motion_log
                (detected_at, location, sensor_id, camera_uid, snapshot_path, status, risk_level, is_read)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        params = (
            timestamp,
            location,
            sensor_id,
            camera_uid,
            snapshot_path,
            status,
            risk_level,
            bool(is_read),
        )
        return self.execute_query(query, params)

    def get_motion_logs(self, limit=100):
        query = "SELECT * FROM motion_log ORDER BY detected_at DESC LIMIT %s"
        return self.execute_query(query, (limit,), fetch=True)

    def get_motion_logs_in_range(self, start_date, end_date, limit=5000):
        # Phase 6 — Reports/Analytics need events between two calendar dates
        query = """
            SELECT * FROM motion_log
            WHERE DATE(detected_at) BETWEEN %s AND %s
            ORDER BY detected_at DESC
            LIMIT %s
        """
        return self.execute_query(query, (start_date, end_date, limit), fetch=True) or []

    def get_motion_summary(self, start_date, end_date):
        # Phase 6 — roll up totals for the Reports summary cards
        rows = self.execute_query(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN risk_level = 'High' THEN 1 ELSE 0 END) AS high_risk,
                SUM(CASE WHEN risk_level = 'Medium' THEN 1 ELSE 0 END) AS medium_risk,
                SUM(CASE WHEN risk_level = 'Low' THEN 1 ELSE 0 END) AS low_risk,
                COUNT(DISTINCT sensor_id) AS sensors,
                COUNT(DISTINCT location) AS locations
            FROM motion_log
            WHERE DATE(detected_at) BETWEEN %s AND %s
            """,
            (start_date, end_date),
            fetch=True,
        )
        if not rows:
            return {
                "total": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0,
                "sensors": 0, "locations": 0,
            }
        row = rows[0]
        return {
            "total": int(row.get("total") or 0),
            "high_risk": int(row.get("high_risk") or 0),
            "medium_risk": int(row.get("medium_risk") or 0),
            "low_risk": int(row.get("low_risk") or 0),
            "sensors": int(row.get("sensors") or 0),
            "locations": int(row.get("locations") or 0),
        }

    def get_daily_counts(self, start_date, end_date):
        # Phase 6 — one bar per day for the Analytics range chart
        rows = self.execute_query(
            """
            SELECT DATE(detected_at) AS day, COUNT(*) AS count
            FROM motion_log
            WHERE DATE(detected_at) BETWEEN %s AND %s
            GROUP BY DATE(detected_at)
            ORDER BY day
            """,
            (start_date, end_date),
            fetch=True,
        ) or []
        result = {}
        for row in rows:
            day = row.get("day")
            if day is None:
                continue
            key = day.strftime("%Y-%m-%d") if hasattr(day, "strftime") else str(day)
            result[key] = int(row.get("count") or 0)
        return result

    def get_hourly_counts_for_date(self, day):
        # Phase 6 — hourly breakdown for a single selected day
        rows = self.execute_query(
            """
            SELECT HOUR(detected_at) AS hour, COUNT(*) AS count
            FROM motion_log
            WHERE DATE(detected_at) = %s
            GROUP BY HOUR(detected_at)
            """,
            (day,),
            fetch=True,
        ) or []
        hourly = {i: 0 for i in range(24)}
        for row in rows:
            try:
                hourly[int(row.get("hour"))] = int(row.get("count") or 0)
            except (TypeError, ValueError):
                continue
        return hourly

    def update_floor_plan(self, floor_plan_id, **fields):
        # Phase 6 — mainly used to point a floor at a newly chosen image
        allowed = {"name", "image_path", "floor_number", "property_name"}
        sets = []
        params = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            sets.append(f"{key} = %s")
            params.append(value)
        if not sets:
            return None
        params.append(floor_plan_id)
        return self.execute_query(
            f"UPDATE floor_plans SET {', '.join(sets)} WHERE id = %s",
            tuple(params),
        )

    def ping(self):
        # Phase 6 — Command Center health widget needs a cheap DB alive check
        try:
            rows = self.execute_query("SELECT 1 AS ok", fetch=True)
            return bool(rows)
        except Exception:
            return False

    def get_today_count(self):
        query = "SELECT COUNT(*) as count FROM motion_log WHERE DATE(detected_at) = CURDATE()"
        result = self.execute_query(query, fetch=True)
        return result[0]['count'] if result else 0

    def get_unread_count(self):
        query = "SELECT COUNT(*) as count FROM motion_log WHERE is_read = FALSE OR is_read IS NULL"
        result = self.execute_query(query, fetch=True)
        return result[0]['count'] if result else 0

    def get_motion_log(self, log_id):
        # Single event for the details modal / mark-read actions
        rows = self.execute_query(
            "SELECT * FROM motion_log WHERE id = %s",
            (log_id,),
            fetch=True,
        )
        return rows[0] if rows else None

    def get_unread_logs(self, limit=20):
        # Bell dropdown only needs recent unread rows
        return self.execute_query(
            """
            SELECT * FROM motion_log
            WHERE is_read = FALSE OR is_read IS NULL
            ORDER BY detected_at DESC
            LIMIT %s
            """,
            (limit,),
            fetch=True,
        ) or []

    def mark_motion_read(self, log_id, is_read=True):
        # Clears (or restores) unread so sidebar/bell badges stay accurate
        return self.execute_query(
            "UPDATE motion_log SET is_read = %s WHERE id = %s",
            (bool(is_read), log_id),
        )

    def mark_all_motion_read(self):
        # One-click clear from the notification center
        return self.execute_query(
            "UPDATE motion_log SET is_read = TRUE WHERE is_read = FALSE OR is_read IS NULL"
        )

    def update_mobile_alert_status(self, log_id, sent=False, channels=None, error=None):
        # Phase 5 — store which mobile channels fired (or why they were skipped)
        return self.execute_query(
            """
            UPDATE motion_log
            SET mobile_alert_sent = %s,
                mobile_alert_channels = %s,
                mobile_alert_error = %s
            WHERE id = %s
            """,
            (bool(sent), channels, error, log_id),
        )

    def update_sensor_activity(self, sensor_id, location):
        query = """
            INSERT INTO sensors (sensor_id, location, last_detection, enabled)
            VALUES (%s, %s, NOW(), TRUE)
            ON DUPLICATE KEY UPDATE last_detection=NOW(), location=%s
        """
        self.execute_query(query, (sensor_id, location, location))

    def get_settings(self):
        query = "SELECT setting_key, setting_value FROM system_settings"
        rows = self.execute_query(query, fetch=True)
        return {r['setting_key']: r['setting_value'] for r in rows} if rows else {}

    def save_setting(self, key, value):
        query = """
            INSERT INTO system_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE setting_value=%s
        """
        self.execute_query(query, (key, value, value))

    # --- Floor plan / device helpers used by DeviceManager ---

    def get_floor_plans(self):
        return self.execute_query(
            "SELECT * FROM floor_plans ORDER BY floor_number, id",
            fetch=True,
        ) or []

    def get_floor_plan(self, floor_plan_id):
        rows = self.execute_query(
            "SELECT * FROM floor_plans WHERE id = %s",
            (floor_plan_id,),
            fetch=True,
        )
        return rows[0] if rows else None

    def get_devices(self, floor_plan_id=None, device_type=None):
        clauses = []
        params = []
        if floor_plan_id is not None:
            clauses.append("floor_plan_id = %s")
            params.append(floor_plan_id)
        if device_type is not None:
            clauses.append("device_type = %s")
            params.append(device_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.execute_query(
            f"SELECT * FROM devices {where} ORDER BY device_type, name",
            tuple(params) if params else None,
            fetch=True,
        ) or []

    def get_device_by_uid(self, device_uid):
        rows = self.execute_query(
            "SELECT * FROM devices WHERE device_uid = %s",
            (device_uid,),
            fetch=True,
        )
        return rows[0] if rows else None

    def get_rooms(self, floor_plan_id):
        return self.execute_query(
            "SELECT * FROM rooms WHERE floor_plan_id = %s ORDER BY name",
            (floor_plan_id,),
            fetch=True,
        ) or []

    def get_room(self, room_id):
        rows = self.execute_query(
            "SELECT * FROM rooms WHERE id = %s",
            (room_id,),
            fetch=True,
        )
        return rows[0] if rows else None

    def insert_device(
        self,
        device_type,
        device_uid,
        name,
        floor_plan_id=None,
        room_id=None,
        x_norm=None,
        y_norm=None,
        linked_camera_uid=None,
        enabled=True,
        meta_json=None,
    ):
        # Persist a new PIR/camera so Place Mode markers survive restart
        return self.execute_query(
            """
            INSERT INTO devices
                (device_type, device_uid, name, floor_plan_id, room_id,
                 x_norm, y_norm, linked_camera_uid, enabled, meta_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                device_type,
                device_uid,
                name,
                floor_plan_id,
                room_id,
                x_norm,
                y_norm,
                linked_camera_uid,
                bool(enabled),
                meta_json,
            ),
        )

    def update_device(self, device_uid, **fields):
        # Only update columns the caller passed so partial edits stay safe
        allowed = {
            "device_type", "device_uid", "name", "floor_plan_id", "room_id",
            "x_norm", "y_norm", "linked_camera_uid", "enabled", "meta_json", "last_seen",
        }
        sets = []
        params = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            sets.append(f"{key} = %s")
            params.append(value)
        if not sets:
            return None
        params.append(device_uid)
        return self.execute_query(
            f"UPDATE devices SET {', '.join(sets)} WHERE device_uid = %s",
            tuple(params),
        )

    def delete_device(self, device_uid):
        return self.execute_query(
            "DELETE FROM devices WHERE device_uid = %s",
            (device_uid,),
        )

    def insert_room(self, floor_plan_id, name, polygon_json=None):
        # Store room outline as normalized JSON so Stage 4 can tint the zone later
        return self.execute_query(
            """
            INSERT INTO rooms (floor_plan_id, name, polygon_json)
            VALUES (%s, %s, %s)
            """,
            (floor_plan_id, name, polygon_json),
        )

    def update_room(self, room_id, name=None, polygon_json=None):
        fields = {}
        if name is not None:
            fields["name"] = name
        if polygon_json is not None:
            fields["polygon_json"] = polygon_json
        if not fields:
            return None
        sets = ", ".join(f"{k} = %s" for k in fields)
        params = list(fields.values()) + [room_id]
        return self.execute_query(
            f"UPDATE rooms SET {sets} WHERE id = %s",
            tuple(params),
        )

    def delete_room(self, room_id):
        return self.execute_query(
            "DELETE FROM rooms WHERE id = %s",
            (room_id,),
        )
