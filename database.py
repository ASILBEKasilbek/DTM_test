import sqlite3
import logging
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

def init_db():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                banned BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT UNIQUE NOT NULL
            )
        """)
        conn.commit()
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        cur.close()
        conn.close()

def register_user(telegram_id, first_name, last_name, phone_number):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO users (telegram_id, first_name, last_name, phone_number)
            VALUES (?, ?, ?, ?)
        """, (telegram_id, first_name, last_name, phone_number))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in register_user: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def is_user_registered(telegram_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,))
        exists = cur.fetchone() is not None
        return exists
    except Exception as e:
        logger.error(f"Error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_user(telegram_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT telegram_id, first_name, last_name, phone_number, banned, created_at FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cur.fetchone()
        return user
    except Exception as e:
        logger.error(f"Error in get_user: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def is_user_banned(telegram_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT banned FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cur.fetchone()
        return result[0] if result else False
    except Exception as e:
        logger.error(f"Error in is_user_banned: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def ban_user(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE users SET banned = 1 WHERE telegram_id = ?", (user_id,))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in ban_user: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def unban_user(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE users SET banned = 0 WHERE telegram_id = ?", (user_id,))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in unban_user: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def update_user(telegram_id, field, value):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        query = f"UPDATE users SET {field} = ? WHERE telegram_id = ?"
        cur.execute(query, (value, telegram_id))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in update_user: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_all_users():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT telegram_id, first_name, last_name, phone_number, banned FROM users")
        users = cur.fetchall()
        return users
    except Exception as e:
        logger.error(f"Error in get_all_users: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_user_count():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error in get_user_count: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def get_users_today():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
        count = cur.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error in get_users_today: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def add_channel(channel_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (channel_id,))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in add_channel: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def remove_channel(channel_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in remove_channel: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_channels():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT channel_id FROM channels")
        channels = [row[0] for row in cur.fetchall()]
        return channels
    except Exception as e:
        logger.error(f"Error in get_channels: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def save_ad(message):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO ads (message) VALUES (?)", (message,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error in save_ad: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_ad_history():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, message, sent_at FROM ads ORDER BY sent_at DESC")
        ads = cur.fetchall()
        return ads
    except Exception as e:
        logger.error(f"Error in get_ad_history: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def add_admin(admin_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (admin_id,))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in add_admin: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def remove_admin(admin_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM admins WHERE admin_id = ?", (admin_id,))
        result = cur.rowcount > 0
        conn.commit()
        return result
    except Exception as e:
        logger.error(f"Error in remove_admin: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_admins():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT admin_id FROM admins")
        admins = [row[0] for row in cur.fetchall()]
        return admins
    except Exception as e:
        logger.error(f"Error in get_admins: {e}")
        return []
    finally:
        cur.close()
        conn.close()