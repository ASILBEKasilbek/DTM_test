import sqlite3
from config import DATABASE_PATH

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
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
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False