import mysql.connector
from mysql.connector import Error
import datetime

class DatabaseHandler:
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
                password=self.password
            )
            return self.conn.is_connected()
        except Error as e:
            print(f"Error connecting to MySQL Platform: {e}")
            return False

    def setup_database(self):
        if not self.connect():
            return
        cursor = self.conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
        cursor.execute(f"USE {self.database}")

        # Create motion log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS motion_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                location VARCHAR(255) NOT NULL,
                sensor_id VARCHAR(50)
            )
        """)
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL
            )
        """)
        
        # Insert admin user if not exists
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password) VALUES ('admin', 'admin123')")

        self.conn.commit()
        cursor.close()

    def log_motion(self, location="Main Entrance", sensor_id="ESP32_01"):
        if not self.conn or not self.conn.is_connected():
            self.connect()
            self.conn.cursor().execute(f"USE {self.database}")
            
        cursor = self.conn.cursor()
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = "INSERT INTO motion_log (timestamp, location, sensor_id) VALUES (%s, %s, %s)"
        cursor.execute(query, (timestamp, location, sensor_id))
        self.conn.commit()
        cursor.close()

    def get_motion_logs(self, limit=100):
        if not self.conn or not self.conn.is_connected():
            self.connect()
            self.conn.cursor().execute(f"USE {self.database}")
            
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM motion_log ORDER BY timestamp DESC LIMIT %s", (limit,))
        result = cursor.fetchall()
        cursor.close()
        return result

    def get_today_count(self):
        if not self.conn or not self.conn.is_connected():
            self.connect()
            self.conn.cursor().execute(f"USE {self.database}")
            
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM motion_log WHERE DATE(timestamp) = CURDATE()")
        count = cursor.fetchone()[0]
        cursor.close()
        return count
