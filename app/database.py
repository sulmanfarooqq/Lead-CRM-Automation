"""SQLite persistence (single-instance, low-volume)."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import get_settings


def db_path() -> str:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        raise RuntimeError("This project supports SQLite DATABASE_URL values only (sqlite:///path/to/file.db).")
    path = url.replace("sqlite:///", "", 1)
    return path if path.startswith("/") else str((Path.cwd() / path).resolve())


@contextmanager
def connect():
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass  # some network filesystems do not support WAL; the default mode still works
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Columns added after the first release. Applied with ALTER TABLE so an existing database
# keeps working after an upgrade.
_LEAD_COLUMNS = {
    "budget_value": "INTEGER",
    "follow_up_action": "TEXT",
    "crm_sync_status": "TEXT NOT NULL DEFAULT 'pending'",
    "crm_error": "TEXT",
    "crm_note_id": "TEXT",
    "crm_task_id": "TEXT",
}
_TASK_COLUMNS = {"completed_at": "TEXT"}


def _ensure_columns(db, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    for name, ddl in columns.items():
        if name not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
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
            """
        )
        _ensure_columns(db, "leads", _LEAD_COLUMNS)
        _ensure_columns(db, "follow_up_tasks", _TASK_COLUMNS)
        db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON follow_up_tasks(status, due_at)")
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('round_robin_index','0')")
