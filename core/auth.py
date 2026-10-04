import bcrypt
from utils.logger import logger

class AuthManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def authenticate(self, username, password):
        query = "SELECT id, password FROM users WHERE username = %s"
        rows = self.db.execute_query(query, (username,), fetch=True)
        if not rows:
            return False
            
        user = rows[0]
        hashed = user['password']
        
        try:
            if bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8')):
                return True
            return False
        except Exception as e:
            logger.error(f"Error during password verification: {e}")
            return False

    def update_password(self, username, new_password):
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        query = "UPDATE users SET password = %s WHERE username = %s"
        self.db.execute_query(query, (hashed, username))
        logger.info(f"Password updated for {username}")
