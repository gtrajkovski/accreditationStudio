"""Database connection utilities for AccreditAI.

Provides SQLite connection management with workspace-based database storage.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from src.config import Config


def get_db_path() -> Path:
    """Get path to SQLite database file.

    Database is stored at WORKSPACE_DIR/_system/accreditai.db
    to maintain workspace-as-truth principle.

    Returns:
        Path to the database file
    """
    workspace = Config.WORKSPACE_DIR
    system_dir = workspace / "_system"
    system_dir.mkdir(parents=True, exist_ok=True)
    return system_dir / "accreditai.db"


def get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get SQLite connection with foreign keys enabled.

    Args:
        db_path: Optional path to database file. If None, uses default.

    Returns:
        SQLite connection with foreign_keys ON and Row factory
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def execute_script(conn: sqlite3.Connection, script_path: Path) -> None:
    """Execute a SQL script file.

    Args:
        conn: SQLite connection
        script_path: Path to .sql file
    """
    with open(script_path, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())


def dict_from_row(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a dictionary.

    Args:
        row: SQLite Row object

    Returns:
        Dictionary with column names as keys
    """
    if row is None:
        return None
    return dict(zip(row.keys(), row))
