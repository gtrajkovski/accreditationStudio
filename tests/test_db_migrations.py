"""Tests for database migration system."""

import sqlite3
import tempfile
from pathlib import Path
import pytest

from src.db.connection import get_conn, get_db_path, dict_from_row
from src.db.migrate import (
    apply_migrations,
    get_migration_status,
    get_applied_migrations,
    ensure_migrations_table,
    MIGRATIONS_DIR,
)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create a temporary database for testing."""
    # Patch WORKSPACE_DIR to use temp directory
    monkeypatch.setattr('src.config.Config.WORKSPACE_DIR', tmp_path)

    # Also patch the migrate module's get_conn import
    from src.db import connection
    original_workspace = connection.Config.WORKSPACE_DIR
    connection.Config.WORKSPACE_DIR = tmp_path

    yield tmp_path

    # Restore
    connection.Config.WORKSPACE_DIR = original_workspace


class TestConnection:
    """Tests for connection module."""

    def test_get_db_path_creates_system_dir(self, temp_db):
        """Test that get_db_path creates _system directory."""
        db_path = get_db_path()
        assert db_path.parent.name == "_system"
        assert db_path.parent.exists()
        assert db_path.name == "accreditai.db"

    def test_get_conn_returns_connection(self, temp_db):
        """Test that get_conn returns a valid connection."""
        conn = get_conn()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

        # Verify foreign keys are enabled
        cursor = conn.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1

        conn.close()

    def test_get_conn_uses_row_factory(self, temp_db):
        """Test that connection uses Row factory."""
        conn = get_conn()
        conn.execute("CREATE TABLE test (id TEXT, name TEXT)")
        conn.execute("INSERT INTO test VALUES ('1', 'Test')")

        cursor = conn.execute("SELECT * FROM test")
        row = cursor.fetchone()

        # Row factory allows column access by name
        assert row['id'] == '1'
        assert row['name'] == 'Test'

        conn.close()

    def test_dict_from_row(self, temp_db):
        """Test converting Row to dict."""
        conn = get_conn()
        conn.execute("CREATE TABLE test (id TEXT, name TEXT)")
        conn.execute("INSERT INTO test VALUES ('1', 'Test')")

        cursor = conn.execute("SELECT * FROM test")
        row = cursor.fetchone()

        result = dict_from_row(row)
        assert result == {'id': '1', 'name': 'Test'}

        conn.close()

    def test_dict_from_row_handles_none(self):
        """Test that dict_from_row handles None."""
        assert dict_from_row(None) is None


class TestMigrations:
    """Tests for migration system."""

    def test_ensure_migrations_table(self, temp_db):
        """Test that migrations table is created."""
        conn = get_conn()
        ensure_migrations_table(conn)

        # Check table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_apply_migrations_creates_tables(self, temp_db):
        """Test that applying migrations creates expected tables."""
        applied = apply_migrations()

        # Should apply all 8 migrations
        assert len(applied) >= 1

        # Verify core tables exist
        conn = get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        # Core tables from 0001_core.sql
        assert 'users' in tables
        assert 'institutions' in tables
        assert 'programs' in tables
        assert 'institution_memberships' in tables

        # Document tables from 0002_docs.sql
        assert 'documents' in tables
        assert 'document_versions' in tables
        assert 'document_parses' in tables

        conn.close()

    def test_apply_migrations_is_idempotent(self, temp_db):
        """Test that running migrations twice is safe."""
        # First run
        applied1 = apply_migrations()
        assert len(applied1) > 0

        # Second run should apply nothing
        applied2 = apply_migrations()
        assert len(applied2) == 0

    def test_get_migration_status(self, temp_db):
        """Test migration status reporting."""
        # Before any migrations
        status = get_migration_status()
        assert status['total'] > 0
        assert len(status['pending']) == status['total']
        assert len(status['applied']) == 0

        # After migrations
        apply_migrations()
        status = get_migration_status()
        assert len(status['applied']) > 0
        assert len(status['pending']) == 0

    def test_foreign_key_constraints(self, temp_db):
        """Test that foreign key constraints are enforced."""
        apply_migrations()
        conn = get_conn()

        # Insert a valid institution
        conn.execute(
            "INSERT INTO institutions (id, name) VALUES ('inst_1', 'Test Institution')"
        )
        conn.commit()

        # Insert a program with valid foreign key
        conn.execute(
            "INSERT INTO programs (id, institution_id, name) VALUES ('prog_1', 'inst_1', 'Test Program')"
        )
        conn.commit()

        # Try to insert a program with invalid foreign key
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO programs (id, institution_id, name) VALUES ('prog_2', 'invalid_inst', 'Bad Program')"
            )

        conn.close()

    def test_cascade_delete(self, temp_db):
        """Test that cascade delete works."""
        apply_migrations()
        conn = get_conn()

        # Insert institution and program
        conn.execute(
            "INSERT INTO institutions (id, name) VALUES ('inst_1', 'Test Institution')"
        )
        conn.execute(
            "INSERT INTO programs (id, institution_id, name) VALUES ('prog_1', 'inst_1', 'Test Program')"
        )
        conn.commit()

        # Delete institution
        conn.execute("DELETE FROM institutions WHERE id = 'inst_1'")
        conn.commit()

        # Program should be deleted too
        cursor = conn.execute("SELECT * FROM programs WHERE id = 'prog_1'")
        assert cursor.fetchone() is None

        conn.close()


class TestMigrationFiles:
    """Tests for migration file content."""

    def test_all_migrations_exist(self):
        """Test that expected migration files exist."""
        expected = [
            '0001_core.sql',
            '0002_docs.sql',
            '0003_vectors.sql',
            '0004_standards.sql',
            '0005_audits.sql',
            '0006_remediation.sql',
            '0007_submissions.sql',
            '0008_i18n.sql',
        ]

        for filename in expected:
            path = MIGRATIONS_DIR / filename
            assert path.exists(), f"Migration file missing: {filename}"

    def test_migrations_have_valid_sql(self):
        """Test that all migration files contain valid SQL."""
        for migration_file in MIGRATIONS_DIR.glob("*.sql"):
            with open(migration_file, 'r') as f:
                sql = f.read()

            # Basic validation - should have CREATE TABLE statements
            assert 'CREATE TABLE' in sql or 'CREATE INDEX' in sql, \
                f"Migration {migration_file.name} has no CREATE statements"

    def test_migration_order(self):
        """Test that migrations are numbered correctly."""
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        numbers = [int(f.name.split('_')[0]) for f in files]

        # Should be sequential starting from 1
        expected = list(range(1, len(numbers) + 1))
        assert numbers == expected, "Migration numbers should be sequential"
