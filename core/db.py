import sqlite3
import os
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'tracker.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_names(conn: sqlite3.Connection, table: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _migrate_seen_items_if_needed(conn: sqlite3.Connection):
    """
    Old schema: seen_items(item_id TEXT PRIMARY KEY, search_id INTEGER, timestamp ...)
    New schema: seen_items(search_id INTEGER, item_id TEXT, timestamp ..., PRIMARY KEY(search_id, item_id))
    """
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='seen_items'")
    exists = cur.fetchone() is not None
    if not exists:
        return

    cols = _column_names(conn, "seen_items")
    if "item_id" not in cols:
        return

    # Create new table with correct PK if current PK is item_id-only.
    # We check sqlite_master sql definition for PRIMARY KEY.
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='seen_items'")
    row = cur.fetchone()
    if not row:
        return
    create_sql = (row[0] or "").upper()
    if "PRIMARY KEY (SEARCH_ID, ITEM_ID)" in create_sql or "PRIMARY KEY(SEARCH_ID, ITEM_ID)" in create_sql:
        return  # already migrated

    cur.execute("""
        CREATE TABLE IF NOT EXISTS seen_items_new (
            search_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (search_id, item_id)
        )
    """)
    # Best-effort copy. Note: old schema may have duplicates across searches suppressed already.
    cur.execute("""
        INSERT OR IGNORE INTO seen_items_new (search_id, item_id, timestamp)
        SELECT COALESCE(search_id, -1) AS search_id, item_id, timestamp
        FROM seen_items
    """)
    cur.execute("DROP TABLE seen_items")
    cur.execute("ALTER TABLE seen_items_new RENAME TO seen_items")
    conn.commit()

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
    # Create the new schema. If an old schema exists, migrate it.
    c.execute('''
        CREATE TABLE IF NOT EXISTS seen_items (
            search_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (search_id, item_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            title TEXT,
            price_value REAL,
            price_currency TEXT,
            url TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (search_id, item_id)
        )
    ''')
    conn.commit()
    _migrate_seen_items_if_needed(conn)
    c = conn.cursor()
    c.execute('CREATE INDEX IF NOT EXISTS idx_seen_items_item_id ON seen_items (item_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_alerts_search_id_ts ON alerts (search_id, timestamp DESC)')
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

def item_seen(search_id, item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM seen_items WHERE search_id = ? AND item_id = ?', (search_id, item_id))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_item_seen(item_id, search_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO seen_items (search_id, item_id) VALUES (?, ?)', (search_id, item_id))
    conn.commit()
    conn.close()

def record_alerts(search_id: int, items: List[Dict[str, Any]]):
    if not items:
        return
    conn = get_connection()
    c = conn.cursor()
    for item in items:
        item_id = item.get("itemId")
        if not item_id:
            continue
        price = item.get("price") or {}
        price_value: Optional[float] = None
        try:
            if "value" in price and price["value"] is not None:
                price_value = float(price["value"])
        except Exception:
            price_value = None

        c.execute(
            '''
            INSERT OR IGNORE INTO alerts (search_id, item_id, title, price_value, price_currency, url)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                search_id,
                item_id,
                item.get("title"),
                price_value,
                price.get("currency"),
                item.get("itemWebUrl"),
            ),
        )
    conn.commit()
    conn.close()


def get_alert_count_by_search(search_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM alerts WHERE search_id = ?', (search_id,))
    count = int(c.fetchone()[0])
    conn.close()
    return count


def get_alerts_for_search(search_id: int, limit: int = 500):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        '''
        SELECT id, search_id, item_id, title, price_value, price_currency, url, timestamp
        FROM alerts
        WHERE search_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        ''',
        (search_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_total_seen_count():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM seen_items')
    count = c.fetchone()[0]
    conn.close()
    return count