"""
GovCon database schema and query helpers.
All agents in this app use get_db("govcon.db") from core.db.
"""
from core.db import get_db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    notice_id              TEXT PRIMARY KEY,
    title                  TEXT NOT NULL,
    solicitation_number    TEXT,
    agency                 TEXT,
    naics_code             TEXT,
    type_of_set_aside      TEXT,
    type_of_set_aside_desc TEXT,
    response_deadline      TEXT,
    posted_date            TEXT,
    notice_type            TEXT,
    ui_link                TEXT,
    description            TEXT,
    state_code             TEXT,
    state_name             TEXT,
    status                 TEXT NOT NULL DEFAULT 'new'
                               CHECK(status IN ('new','reviewing','bid','no_bid','archived')),
    relevance_score        REAL,
    notes                  TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_opp_naics    ON opportunities(naics_code);
CREATE INDEX IF NOT EXISTS idx_opp_status   ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opp_posted   ON opportunities(posted_date);
CREATE INDEX IF NOT EXISTS idx_opp_deadline ON opportunities(response_deadline);

CREATE TABLE IF NOT EXISTS company_profile (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SEED_PROFILE = [
    ("company_name",    "My Company LLC"),
    ("naics_codes",     '["541511", "541512", "541519"]'),
    ("keywords",        '["software development", "cloud", "cybersecurity"]'),
    ("set_aside_types", '["SBA"]'),
    ("min_value",       "50000"),
    ("max_value",       ""),
]


def init_db() -> None:
    """Create tables, run migrations, and seed default company profile. Idempotent."""
    with get_db("govcon.db") as conn:
        conn.executescript(_SCHEMA)
        # Migrations: add columns introduced after initial release
        for col, definition in [
            ("state_code", "TEXT"),
            ("state_name", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE opportunities ADD COLUMN {col} {definition}")
            except Exception:
                pass  # Column already exists
        conn.executemany(
            "INSERT OR IGNORE INTO company_profile (key, value) VALUES (?, ?)",
            _SEED_PROFILE,
        )
