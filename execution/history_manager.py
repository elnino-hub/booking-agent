import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "history.db")

def _get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_message(user_id: str, role: str, content: str):
    """Saves a message to the history."""
    init_db() # Ensure table exists
    conn = _get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)', (user_id, role, content))
    conn.commit()
    conn.close()

def get_recent_history(user_id: str, limit: int = 10):
    """Retrieves the most recent messages for a user."""
    init_db()
    conn = _get_db_connection()
    c = conn.cursor()
    c.execute('SELECT role, content, timestamp FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?', (user_id, limit))
    rows = c.fetchall()
    conn.close()
    
    # Return reversed to show chronological order (oldest to newest)
    history = [dict(row) for row in rows]
    return history[::-1]

if __name__ == "__main__":
    # Simple test
    print("Testing History Manager...")
    init_db()
    save_message("test_user", "user", "Hello agent")
    save_message("test_user", "assistant", "Hello user")
    print(get_recent_history("test_user"))
    print("Test Complete.")
