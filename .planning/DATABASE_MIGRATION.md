# SQLite Migration Plan for AccreditAI

## Overview

This plan implements a lightweight SQLite migration system that:
- Stores ordered SQL files in `src/db/migrations/`
- Tracks applied migrations in `schema_migrations` table
- Is invoked by `flask db upgrade` (with `flask init-db` calling it)
- Stores DB at `WORKSPACE_DIR/_system/accreditai.db`

## Why SQLite + Migration System

- SPEC requires SQLite storage + sqlite-vss for chunks/embeddings
- App is single-user localhost (no need for heavy ORM migrations)
- "Workspace is truth" - DB file lives inside workspace
- Coexists with file-based WorkspaceManager during transition

---

## Directory Structure

```text
src/db/
├── __init__.py
├── connection.py      # get_db_path(), get_conn(), execute_script()
├── migrate.py         # apply_migrations(), schema_migrations table
└── migrations/
    ├── 0001_core.sql
    ├── 0002_docs.sql
    ├── 0003_vectors.sql
    ├── 0004_standards.sql
    ├── 0005_audits.sql
    ├── 0006_remediation.sql
    ├── 0007_submissions.sql
    └── 0008_i18n.sql
```

---

## Implementation Files

### src/db/connection.py

```python
"""Database connection utilities."""
import sqlite3
from pathlib import Path
from src.config import Config


def get_db_path() -> Path:
    """Get path to SQLite database file."""
    workspace = Path(Config.WORKSPACE_DIR)
    system_dir = workspace / "_system"
    system_dir.mkdir(parents=True, exist_ok=True)
    return system_dir / "accreditai.db"


def get_conn() -> sqlite3.Connection:
    """Get SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def execute_script(conn: sqlite3.Connection, script_path: Path) -> None:
    """Execute a SQL script file."""
    with open(script_path, 'r') as f:
        conn.executescript(f.read())
```

### src/db/migrate.py

```python
"""Database migration runner."""
import sqlite3
from pathlib import Path
from typing import List
from src.db.connection import get_conn


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_applied_migrations(conn: sqlite3.Connection) -> List[str]:
    """Get list of applied migration versions."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')
    cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    return [row[0] for row in cursor.fetchall()]


def apply_migrations(migrations_dir: Path = None) -> List[str]:
    """Apply all pending migrations."""
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
            with open(migration_file, 'r') as f:
                conn.executescript(f.read())
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,)
            )
            conn.commit()
            newly_applied.append(version)

    conn.close()
    return newly_applied


def get_migration_status() -> dict:
    """Get status of all migrations."""
    conn = get_conn()
    applied = get_applied_migrations(conn)

    all_migrations = sorted(
        f.name for f in MIGRATIONS_DIR.glob("*.sql")
    )

    conn.close()
    return {
        "applied": applied,
        "pending": [m for m in all_migrations if m not in applied],
        "total": len(all_migrations),
    }
```

### Flask CLI Commands (in app.py)

```python
import click
from flask.cli import with_appcontext

@app.cli.command("db")
@click.argument("action")
@with_appcontext
def db_command(action):
    """Database management commands."""
    from src.db.migrate import apply_migrations, get_migration_status

    if action == "upgrade":
        applied = apply_migrations()
        if applied:
            click.echo(f"Applied {len(applied)} migrations: {', '.join(applied)}")
        else:
            click.echo("No pending migrations.")

    elif action == "status":
        status = get_migration_status()
        click.echo(f"Applied: {len(status['applied'])} / {status['total']}")
        if status['pending']:
            click.echo(f"Pending: {', '.join(status['pending'])}")

    else:
        click.echo(f"Unknown action: {action}. Use 'upgrade' or 'status'.")
```

---

## Migration DDL Files

### 0001_core.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT,
  locale TEXT NOT NULL DEFAULT 'en-US',
  theme_preference TEXT NOT NULL DEFAULT 'system',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS institutions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  legal_name TEXT,
  accreditor_primary TEXT,
  timezone TEXT NOT NULL DEFAULT 'America/New_York',
  default_locale TEXT NOT NULL DEFAULT 'en-US',
  supported_locales TEXT NOT NULL DEFAULT '["en-US"]',
  theme_preference TEXT NOT NULL DEFAULT 'system',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS programs (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  name TEXT NOT NULL,
  credential_level TEXT,
  delivery_modes TEXT NOT NULL DEFAULT '[]',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS institution_memberships (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_programs_institution_id ON programs(institution_id);
CREATE INDEX IF NOT EXISTS idx_memberships_institution_id ON institution_memberships(institution_id);
```

### 0002_docs.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  program_id TEXT,
  doc_type TEXT NOT NULL,
  title TEXT NOT NULL,
  source_language TEXT NOT NULL DEFAULT 'en-US',
  status TEXT NOT NULL DEFAULT 'uploaded',
  original_file_path TEXT NOT NULL,
  file_sha256 TEXT NOT NULL,
  page_count INTEGER,
  created_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
  FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  version_type TEXT NOT NULL,
  label TEXT,
  file_path TEXT NOT NULL,
  file_sha256 TEXT NOT NULL,
  created_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS document_parses (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  extracted_text_path TEXT NOT NULL,
  structured_json_path TEXT,
  pii_redacted_text_path TEXT NOT NULL,
  parse_warnings TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_institution_id ON documents(institution_id);
CREATE INDEX IF NOT EXISTS idx_documents_program_id ON documents(program_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_document_parses_document_id ON document_parses(document_id);
```

### 0003_vectors.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS document_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  page_start INTEGER,
  page_end INTEGER,
  section_header TEXT,
  language TEXT NOT NULL DEFAULT 'en-US',
  redacted_text_path TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_language ON document_chunks(language);

-- Vector store tables depend on sqlite-vss installation specifics.
-- Create a plain embeddings table as a stable interface.
CREATE TABLE IF NOT EXISTS chunk_embeddings (
  chunk_id TEXT PRIMARY KEY,
  embedding BLOB NOT NULL,
  model TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE
);
```

### 0004_standards.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accreditors (
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  default_language TEXT NOT NULL DEFAULT 'en-US'
);

CREATE TABLE IF NOT EXISTS standards (
  id TEXT PRIMARY KEY,
  accreditor_id TEXT NOT NULL,
  standard_code TEXT NOT NULL,
  title TEXT NOT NULL,
  body_path TEXT,
  parent_id TEXT,
  source_language TEXT NOT NULL DEFAULT 'en-US',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (accreditor_id) REFERENCES accreditors(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_id) REFERENCES standards(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS standard_translations (
  id TEXT PRIMARY KEY,
  standard_id TEXT NOT NULL,
  target_language TEXT NOT NULL,
  title_translated TEXT,
  body_translated_path TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (standard_id) REFERENCES standards(id) ON DELETE CASCADE,
  UNIQUE (standard_id, target_language)
);

CREATE INDEX IF NOT EXISTS idx_standards_accreditor_id ON standards(accreditor_id);
CREATE INDEX IF NOT EXISTS idx_standards_parent_id ON standards(parent_id);
```

### 0005_audits.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS audit_runs (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  program_id TEXT,
  checklist_id TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  started_at TEXT,
  completed_at TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
  FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_findings (
  id TEXT PRIMARY KEY,
  audit_run_id TEXT NOT NULL,
  document_id TEXT,
  checklist_item_id TEXT,
  status TEXT NOT NULL,
  severity TEXT NOT NULL,
  summary TEXT NOT NULL,
  recommendation TEXT,
  confidence REAL NOT NULL,
  human_review_required INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evidence_refs (
  id TEXT PRIMARY KEY,
  finding_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  document_version_id TEXT,
  page INTEGER,
  locator TEXT NOT NULL DEFAULT '{}',
  snippet_hash TEXT NOT NULL,
  snippet_text_path TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'en-US',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS finding_standard_refs (
  id TEXT PRIMARY KEY,
  finding_id TEXT NOT NULL,
  standard_id TEXT NOT NULL,
  FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,
  FOREIGN KEY (standard_id) REFERENCES standards(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS human_checkpoints (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  session_id TEXT,
  finding_id TEXT,
  checkpoint_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  requested_by TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  resolved_at TEXT,
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
  FOREIGN KEY (finding_id) REFERENCES audit_findings(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_runs_institution_id ON audit_runs(institution_id);
CREATE INDEX IF NOT EXISTS idx_findings_audit_run_id ON audit_findings(audit_run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_finding_id ON evidence_refs(finding_id);
```

### 0006_remediation.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS truth_index (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  source_document_id TEXT,
  source_page INTEGER,
  source_locator TEXT,
  confidence REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
  FOREIGN KEY (source_document_id) REFERENCES documents(id) ON DELETE SET NULL,
  UNIQUE (institution_id, key)
);

CREATE TABLE IF NOT EXISTS consistency_checks (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  started_at TEXT,
  completed_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS consistency_issues (
  id TEXT PRIMARY KEY,
  check_id TEXT NOT NULL,
  key TEXT NOT NULL,
  found_values TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'warning',
  resolved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (check_id) REFERENCES consistency_checks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS remediation_jobs (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  audit_run_id TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  redline_path TEXT,
  final_path TEXT,
  crossref_path TEXT,
  started_at TEXT,
  completed_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_truth_index_institution ON truth_index(institution_id);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_check ON consistency_issues(check_id);
```

### 0007_submissions.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS submission_packets (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  program_id TEXT,
  packet_type TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  docx_path TEXT,
  pdf_path TEXT,
  zip_path TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
  FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS packet_items (
  id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  item_type TEXT NOT NULL,
  title TEXT,
  ref TEXT NOT NULL DEFAULT '{}',
  order_index INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (packet_id) REFERENCES submission_packets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_packets_institution ON submission_packets(institution_id);
CREATE INDEX IF NOT EXISTS idx_packet_items_packet ON packet_items(packet_id);
```

### 0008_i18n.sql

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS terminology_glossaries (
  id TEXT PRIMARY KEY,
  institution_id TEXT NOT NULL,
  locale TEXT NOT NULL,
  entries TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (institution_id) REFERENCES institutions(id) ON DELETE CASCADE,
  UNIQUE (institution_id, locale)
);

CREATE TABLE IF NOT EXISTS document_translations (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  source_language TEXT NOT NULL,
  target_language TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  translated_text_path TEXT,
  translated_structured_json_path TEXT,
  quality_flags TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  UNIQUE (document_id, target_language)
);

CREATE TABLE IF NOT EXISTS document_chunk_translations (
  id TEXT PRIMARY KEY,
  document_chunk_id TEXT NOT NULL,
  target_language TEXT NOT NULL,
  translated_text_path TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE,
  UNIQUE (document_chunk_id, target_language)
);

CREATE INDEX IF NOT EXISTS idx_doc_translations_doc_id ON document_translations(document_id);
CREATE INDEX IF NOT EXISTS idx_chunk_translations_lang ON document_chunk_translations(target_language);
```

---

## Claude Code Prompt

```text
Implement a lightweight SQLite migration system for AccreditAI.

Context:
- app.py initializes WorkspaceManager, AIClient (optional), and a task queue, then registers blueprints
- SPEC requires SQLite storage for chunking + embeddings and language filters for retrieval
- Workspace-based: DB at WORKSPACE_DIR/_system/accreditai.db

Requirements:
1) Create src/db/connection.py:
   - get_db_path() uses WORKSPACE_DIR and stores db at WORKSPACE_DIR/_system/accreditai.db
   - get_conn() returns sqlite3 connection with foreign_keys ON and row_factory=sqlite3.Row
   - execute_script(conn, path) helper

2) Create src/db/migrate.py:
   - apply_migrations(migrations_dir) - applies all *.sql in sorted order
   - get_applied_migrations(conn) - creates schema_migrations table, returns applied versions
   - get_migration_status() - returns {applied, pending, total}

3) Add Flask CLI commands to app.py:
   - flask db upgrade - apply pending migrations
   - flask db status - show migration status
   - Keep flask init-db but have it call db upgrade internally

4) Create src/db/migrations/ with DDL files:
   - 0001_core.sql: users, institutions, programs, memberships
   - 0002_docs.sql: documents, versions, parses
   - 0003_vectors.sql: document_chunks, chunk_embeddings
   - 0004_standards.sql: accreditors, standards, translations
   - 0005_audits.sql: audit_runs, findings, evidence_refs, checkpoints
   - 0006_remediation.sql: truth_index, consistency_checks, remediation_jobs
   - 0007_submissions.sql: submission_packets, packet_items
   - 0008_i18n.sql: glossaries, document_translations, chunk_translations

5) Coexistence:
   - WorkspaceManager keeps file-based artifacts (originals, redlines, finals)
   - DB tables used for indexing, search, and UI queries
   - Do NOT remove file-based persistence

6) Tests (tests/test_db_migrations.py):
   - Apply migrations on temp workspace creates expected tables
   - Re-running db upgrade is idempotent (no errors, no changes)
   - Foreign key constraints work

Start by implementing connection.py + migrate.py + 0001_core.sql, then add the CLI commands and a test.
```

---

## Verification

1. **Apply migrations**: `flask db upgrade`
2. **Check status**: `flask db status`
3. **Verify tables**: `sqlite3 workspace/_system/accreditai.db ".tables"`
4. **Test FK constraints**: Insert with invalid foreign key should fail
5. **Test idempotency**: Running `flask db upgrade` twice should be safe

---

## Notes

- All timestamps use SQLite `datetime('now')` for UTC
- JSON arrays stored as TEXT (SQLite has no native array type)
- Indexes on foreign keys for join performance
- `ON DELETE CASCADE` for child records, `ON DELETE SET NULL` for optional refs
