import sqlite3
import os
from datetime import datetime

# Store in the standard ~/.gemini folder
DB_PATH = os.path.join(os.path.expanduser("~"), ".gemini", "context_history.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_history (
            date TEXT PRIMARY KEY,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cached_tokens INTEGER,
            sessions INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def log_daily_usage(input_tokens, output_tokens, cached_tokens, sessions):
    init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO usage_history (date, input_tokens, output_tokens, cached_tokens, sessions)
        VALUES (?, ?, ?, ?, ?)
    ''', (today, input_tokens, output_tokens, cached_tokens, sessions))
    conn.commit()
    conn.close()

def get_history(limit=7):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date, input_tokens, output_tokens, cached_tokens, sessions
        FROM usage_history
        ORDER BY date DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows
