import sqlite3
import time
import logging
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

def safe_db_operation_with_retry(func, *args, retries=3, delay=1, **kwargs):
    """Ma'lumotlar bazasi operatsiyalarini xavfsiz bajarish uchun qayta urinish."""
    for attempt in range(retries):
        try:
            conn = sqlite3.connect(DATABASE_PATH, timeout=10)
            cur = conn.cursor()
            result = func(cur, *args, **kwargs)
            conn.commit()
            logger.info(f"Ma'lumotlar bazasi operatsiyasi {func.__name__} muvaffaqiyatli")
            return result
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                logger.warning(f"Ma'lumotlar bazasi qulflangan, qayta urinish {attempt + 1}/{retries}")
                time.sleep(delay)
                continue
            logger.error(f"{func.__name__} da ma'lumotlar bazasi xatosi: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"{func.__name__} da xato: {str(e)}")
            return None
        finally:
            cur.close()
            conn.close()
    return None

def init_db():
    """Ma'lumotlar bazasini ishga tushirish va kerakli jadvallarni yaratish."""
    def _init_db(cur):
        # Users jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                banned BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Eski jadvallarga banned ustuni qo'shish
        try:
            cur.execute("ALTER TABLE users ADD COLUMN banned BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Agar ustun allaqachon mavjud bo'lsa, o'tkazib yuborish
        # Channels jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL
            )
        """)
        # Ads jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Admins jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT UNIQUE NOT NULL
            )
        """)
    safe_db_operation_with_retry(_init_db)

def register_user(telegram_id, first_name, last_name, phone_number):
    """Yangi foydalanuvchini ro'yxatdan o'tkazish."""
    def _register(cur, telegram_id, first_name, last_name, phone_number):
        cur.execute("""
            INSERT OR IGNORE INTO users (telegram_id, first_name, last_name, phone_number)
            VALUES (?, ?, ?, ?)
        """, (str(telegram_id), first_name, last_name, phone_number))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_register, telegram_id, first_name, last_name, phone_number) or False

def is_user_registered(telegram_id):
    """Foydalanuvchi ro'yxatdan o'tganligini tekshirish."""
    def _check_registered(cur, telegram_id):
        cur.execute("SELECT 1 FROM users WHERE telegram_id = ?", (str(telegram_id),))
        return cur.fetchone() is not None
    return safe_db_operation_with_retry(_check_registered, telegram_id) or False

def get_user(telegram_id):
    """Foydalanuvchi ma'lumotlarini olish."""
    def _get_user(cur, telegram_id):
        cur.execute("SELECT telegram_id, first_name, last_name, phone_number, banned, created_at FROM users WHERE telegram_id = ?", (str(telegram_id),))
        return cur.fetchone()
    return safe_db_operation_with_retry(_get_user, telegram_id)

def is_user_banned(telegram_id):
    """Foydalanuvchi banlanganligini tekshirish."""
    def _check_banned(cur, telegram_id):
        cur.execute("SELECT banned FROM users WHERE telegram_id = ?", (str(telegram_id),))
        result = cur.fetchone()
        return result[0] if result else False
    return safe_db_operation_with_retry(_check_banned, telegram_id) or False

def ban_user(telegram_id):
    """Foydalanuvchini ban qilish."""
    def _ban_user(cur, telegram_id):
        cur.execute("UPDATE users SET banned = 1 WHERE telegram_id = ?", (str(telegram_id),))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_ban_user, telegram_id) or False

def unban_user(telegram_id):
    """Foydalanuvchi bandan chiqarish."""
    def _unban_user(cur, telegram_id):
        cur.execute("UPDATE users SET banned = 0 WHERE telegram_id = ?", (str(telegram_id),))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_unban_user, telegram_id) or False

def update_user(telegram_id, field, value):
    """Foydalanuvchi ma'lumotlarini yangilash."""
    def _update_user(cur, telegram_id, field, value):
        query = f"UPDATE users SET {field} = ? WHERE telegram_id = ?"
        cur.execute(query, (value, str(telegram_id)))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_update_user, telegram_id, field, value) or False

def get_all_users():
    """Barcha foydalanuvchilarni olish."""
    def _get_all_users(cur):
        cur.execute("SELECT telegram_id, first_name, last_name, phone_number, banned FROM users")
        return cur.fetchall()
    return safe_db_operation_with_retry(_get_all_users) or []

def get_user_count():
    """Foydalanuvchilar sonini olish."""
    def _get_user_count(cur):
        cur.execute("SELECT COUNT(*) FROM users")
        return cur.fetchone()[0]
    return safe_db_operation_with_retry(_get_user_count) or 0

def get_users_today():
    """Bugun ro'yxatdan o'tgan foydalanuvchilar sonini olish."""
    def _get_users_today(cur):
        cur.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
        return cur.fetchone()[0]
    return safe_db_operation_with_retry(_get_users_today) or 0

def add_channel(channel_id):
    """Yangi majburiy kanal qo'shish."""
    def _add_channel(cur, channel_id):
        cur.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (str(channel_id),))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_add_channel, channel_id) or False

def remove_channel(channel_id):
    """Kanalni o'chirish."""
    def _remove_channel(cur, channel_id):
        cur.execute("DELETE FROM channels WHERE channel_id = ?", (str(channel_id),))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_remove_channel, channel_id) or False

def get_channels():
    """Barcha majburiy kanallarni olish."""
    def _get_channels(cur):
        cur.execute("SELECT channel_id FROM channels")
        return [row[0] for row in cur.fetchall()]
    return safe_db_operation_with_retry(_get_channels) or []

def save_ad(message):
    """Reklama xabarini saqlash."""
    def _save_ad(cur, message):
        cur.execute("INSERT INTO ads (message) VALUES (?)", (message,))
        return True
    return safe_db_operation_with_retry(_save_ad, message) or False

def get_ad_history():
    """Reklama tarixini olish."""
    def _get_ad_history(cur):
        cur.execute("SELECT id, message, sent_at FROM ads ORDER BY sent_at DESC")
        return cur.fetchall()
    return safe_db_operation_with_retry(_get_ad_history) or []

def add_admin(admin_id):
    """Yangi admin qo'shish."""
    def _add_admin(cur, admin_id):
        cur.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (str(admin_id),))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_add_admin, admin_id) or False

def remove_admin(admin_id):
    """Adminni o'chirish."""
    def _remove_admin(cur, admin_id):
        cur.execute("DELETE FROM admins WHERE admin_id = ?", (str(admin_id),))
        return cur.rowcount > 0
    return safe_db_operation_with_retry(_remove_admin, admin_id) or False

def get_admins():
    """Barcha adminlarni olish."""
    def _get_admins(cur):
        cur.execute("SELECT admin_id FROM admins")
        return [row[0] for row in cur.fetchall()]
    return safe_db_operation_with_retry(_get_admins) or []