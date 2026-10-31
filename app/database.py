import sqlite3
from pathlib import Path
from contextlib import contextmanager
from app.config import get_settings

def db_path():
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("This starter currently supports SQLite DATABASE_URL only.")
    path = url.replace("sqlite:///", "", 1)
    return path if path.startswith("/") else str((Path.cwd() / path).resolve())

@contextmanager
def connect():
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
          id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, email TEXT, phone TEXT,
          property_type TEXT, budget_raw TEXT, preferred_location TEXT, buying_timeline TEXT,
          message TEXT, source TEXT, priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New',
          assigned_to TEXT, assigned_email TEXT, follow_up_due TEXT,
          review_reasons TEXT NOT NULL DEFAULT '[]', crm_item_id TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, raw_payload TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
        CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
        CREATE TABLE IF NOT EXISTS follow_up_tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL, title TEXT NOT NULL,
          due_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open', created_at TEXT NOT NULL,
          FOREIGN KEY(lead_id) REFERENCES leads(id)
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, event_type TEXT NOT NULL,
          detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('round_robin_index','0')")
