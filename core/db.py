import os
import sqlite3
from contextlib import contextmanager

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def db_path(name: str = "platform.db") -> str:
    """Return the absolute path for a named database, creating the data/ dir if needed."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    return os.path.abspath(os.path.join(_DATA_DIR, name))


@contextmanager
def get_db(name: str = "platform.db"):
    """
    Context manager yielding a sqlite3 connection.

    - row_factory=sqlite3.Row so rows behave like dicts
    - WAL mode for safe concurrent reads
    - Auto-commits on clean exit, rolls back on exception
    """
    conn = sqlite3.connect(db_path(name))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
