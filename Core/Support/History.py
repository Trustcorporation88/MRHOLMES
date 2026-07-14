"""Histórico de buscas com SQLite para Mr.Holmes"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "Logs" / "history.db"

def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            query TEXT NOT NULL,
            country TEXT,
            area TEXT,
            carrier TEXT,
            sites_found INTEGER DEFAULT 0,
            report_path TEXT,
            searched_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_searches_type ON searches(type);
        CREATE INDEX IF NOT EXISTS idx_searches_date ON searches(searched_at);
    """)
    conn.commit()
    conn.close()

def save_search(
    search_type: str,
    query: str,
    country: str = "",
    area: str = "",
    carrier: str = "",
    sites_found: int = 0,
    report_path: str = "",
):
    init_db()
    conn = _get_conn()
    conn.execute("""
        INSERT INTO searches (type, query, country, area, carrier, sites_found, report_path, searched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (search_type, query, country, area, carrier, sites_found, report_path, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_history(search_type: str = "", limit: int = 20) -> list:
    init_db()
    conn = _get_conn()
    if search_type:
        rows = conn.execute(
            "SELECT * FROM searches WHERE type = ? ORDER BY searched_at DESC LIMIT ?",
            (search_type, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM searches ORDER BY searched_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats() -> dict:
    init_db()
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM searches").fetchone()
    by_type = conn.execute(
        "SELECT type, COUNT(*) as c FROM searches GROUP BY type"
    ).fetchall()
    today = conn.execute(
        "SELECT COUNT(*) as c FROM searches WHERE date(searched_at) = date('now')"
    ).fetchone()
    conn.close()
    return {
        "total": total["c"] if total else 0,
        "today": today["c"] if today else 0,
        "by_type": {r["type"]: r["c"] for r in by_type},
    }
