import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'tracker.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            min_price REAL,
            max_price REAL,
            category_id TEXT,
            buying_option TEXT,
            active INTEGER DEFAULT 1
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS seen_items (
            item_id TEXT PRIMARY KEY,
            search_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_search(keyword, min_price, max_price, category_id, buying_option):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO searches (keyword, min_price, max_price, category_id, buying_option)
        VALUES (?, ?, ?, ?, ?)
    ''', (keyword, min_price, max_price, category_id, buying_option))
    conn.commit()
    conn.close()

def get_active_searches():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM searches WHERE active = 1')
    rows = c.fetchall()
    conn.close()
    return rows

def delete_search(search_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM searches WHERE id = ?', (search_id,))
    conn.commit()
    conn.close()

def item_seen(item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM seen_items WHERE item_id = ?', (item_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_item_seen(item_id, search_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO seen_items (item_id, search_id) VALUES (?, ?)', (item_id, search_id))
    conn.commit()
    conn.close()

def get_total_seen_count():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM seen_items')
    count = c.fetchone()[0]
    conn.close()
    return count