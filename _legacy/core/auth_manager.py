class AuthManager:
    def __init__(self, db_handler):
        self.db = db_handler

    def authenticate(self, username, password):
        if not self.db.conn or not self.db.conn.is_connected():
            self.db.connect()
            self.db.conn.cursor().execute(f"USE {self.db.database}")

        cursor = self.db.conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        
        return user is not None
