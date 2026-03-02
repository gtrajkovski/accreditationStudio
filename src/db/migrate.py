"""Database migration runner for AccreditAI.

Provides a lightweight migration system that:
- Stores ordered SQL files in src/db/migrations/
- Tracks applied migrations in schema_migrations table
- Applies migrations idempotently
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.db.connection import get_conn, get_db_path


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Create schema_migrations table if it doesn't exist.

    Args:
        conn: SQLite connection
    """
    conn.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection) -> List[str]:
    """Get list of applied migration versions.

    Args:
        conn: SQLite connection

    Returns:
        List of version strings (filenames) that have been applied
    """
    ensure_migrations_table(conn)
    cursor = conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    )
    return [row[0] for row in cursor.fetchall()]


def get_pending_migrations(migrations_dir: Optional[Path] = None) -> List[Path]:
    """Get list of migration files not yet applied.

    Args:
        migrations_dir: Directory containing migration files

    Returns:
        List of Path objects for pending migration files
    """
    if migrations_dir is None:
        migrations_dir = MIGRATIONS_DIR

    conn = get_conn()
    applied = get_applied_migrations(conn)
    conn.close()

    # Get all migration files sorted
    all_migrations = sorted(migrations_dir.glob("*.sql"))

    return [m for m in all_migrations if m.name not in applied]


def apply_migration(conn: sqlite3.Connection, migration_file: Path) -> None:
    """Apply a single migration file.

    Args:
        conn: SQLite connection
        migration_file: Path to .sql migration file
    """
    version = migration_file.name

    # Read and execute the migration
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    conn.executescript(sql)

    # Record the migration
    conn.execute(
        "INSERT INTO schema_migrations (version) VALUES (?)",
        (version,)
    )
    conn.commit()


def apply_migrations(migrations_dir: Optional[Path] = None) -> List[str]:
    """Apply all pending migrations.

    Args:
        migrations_dir: Directory containing migration files.
                        Defaults to src/db/migrations/

    Returns:
        List of version strings that were applied
    """
    if migrations_dir is None:
        migrations_dir = MIGRATIONS_DIR

    conn = get_conn()
    applied = get_applied_migrations(conn)
    newly_applied = []

    # Get all migration files sorted
    migration_files = sorted(migrations_dir.glob("*.sql"))

    for migration_file in migration_files:
        version = migration_file.name
        if version not in applied:
            print(f"Applying migration: {version}")
            try:
                apply_migration(conn, migration_file)
                newly_applied.append(version)
                print(f"  [OK] {version}")
            except Exception as e:
                print(f"  [FAIL] {version}: {e}")
                conn.rollback()
                raise

    conn.close()
    return newly_applied


def get_migration_status(migrations_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Get status of all migrations.

    Args:
        migrations_dir: Directory containing migration files

    Returns:
        Dictionary with applied, pending, and total counts
    """
    if migrations_dir is None:
        migrations_dir = MIGRATIONS_DIR

    conn = get_conn()
    applied = get_applied_migrations(conn)
    conn.close()

    all_migrations = sorted(
        f.name for f in migrations_dir.glob("*.sql")
    )

    return {
        "applied": applied,
        "pending": [m for m in all_migrations if m not in applied],
        "total": len(all_migrations),
        "db_path": str(get_db_path()),
    }


def rollback_migration(version: str) -> bool:
    """Remove a migration from the applied list.

    Note: This does NOT undo the schema changes.
    Use only for testing or recovery.

    Args:
        version: Version string (filename) to remove

    Returns:
        True if removed, False if not found
    """
    conn = get_conn()
    cursor = conn.execute(
        "DELETE FROM schema_migrations WHERE version = ?",
        (version,)
    )
    conn.commit()
    removed = cursor.rowcount > 0
    conn.close()
    return removed
