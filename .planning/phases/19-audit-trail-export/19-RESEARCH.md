# Phase 19: Audit Trail Export - Research

**Researched:** 2026-03-21
**Domain:** Audit trail export, compliance reporting, regulatory evidence packaging
**Confidence:** HIGH

## Summary

Phase 19 requires implementing audit trail export functionality for regulatory compliance and evidence preservation. The system must export agent session logs as structured JSON, support date range filtering, package exports with compliance reports as ZIP files, and provide filtering by agent type and operation.

AccreditAI already persists agent sessions to `workspace/{institution_id}/agent_sessions/{session_id}.json` files. These sessions contain complete audit trails including tool calls, agent decisions, confidence scores, and timestamps. The implementation will leverage existing workspace structure, add service and API layers for querying and packaging, and provide UI controls for export operations.

**Primary recommendation:** Build a dedicated AuditTrailService that queries workspace session files, applies filters (date range, agent type, operation), aggregates results, and exports as JSON or ZIP packages. Use Python's standard library `zipfile` for packaging, Flask's `send_file` for downloads, and maintain full backwards compatibility with existing session storage.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUD-01 | User can export agent session logs as JSON | Workspace already stores sessions as JSON; add aggregation endpoint |
| AUD-02 | User can export activity history for date range | ISO8601 timestamps present; use datetime.fromisoformat() for filtering |
| AUD-03 | User can package audit trail with compliance report | Standard library zipfile supports multi-file packaging |
| AUD-04 | Exported logs include tool calls, decisions, and timestamps | AgentSession model already captures all required fields |
| AUD-05 | User can filter export by agent type or operation | Session metadata includes agent_type; add query filtering |

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| zipfile | stdlib | ZIP archive creation | Built-in, no dependencies, reliable for packaging multiple files |
| json | stdlib | JSON serialization | Already used throughout codebase, native Python support |
| datetime | stdlib | Date range filtering | ISO8601 parsing with fromisoformat(), timezone-aware |
| Flask send_file | 3.0.0+ | File downloads | Project standard for PDF/DOCX downloads, handles mimetype and streaming |
| pathlib | stdlib | File system traversal | Already used in WorkspaceManager, cross-platform path handling |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 7.4.0+ | Testing | Already project standard for service tests |
| io.BytesIO | stdlib | In-memory file buffers | Building ZIP archives without disk writes |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| zipfile (stdlib) | py7zr (7-Zip) | Better compression but adds dependency; stdlib sufficient for audit trails |
| datetime.fromisoformat() | python-dateutil | More flexible parsing but adds dependency; ISO8601 is project standard |
| File system queries | SQLite FTS5 | Faster search but requires migration; file-based storage is existing pattern |

**Installation:**
```bash
# No new dependencies required - all stdlib
# Existing requirements already include Flask 3.0.0+
```

**Version verification:** All libraries are Python standard library (ships with Python 3.11+). Flask already pinned at >=3.0.0 in requirements.txt.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── services/
│   └── audit_trail_service.py    # Core export logic
├── api/
│   └── audit_trails.py            # REST endpoints
└── exporters/
    └── audit_trail_exporter.py    # ZIP packaging (optional - can merge into service)

templates/
└── audit_trails/
    └── audit_trails.html          # UI page

static/
└── js/
    └── audit_trails.js            # Frontend logic
```

### Pattern 1: Service Layer with File System Queries

**What:** Service class that reads JSON files from workspace, filters by criteria, aggregates results

**When to use:** For audit trail export where session data already persists to disk as JSON

**Example:**
```python
# src/services/audit_trail_service.py
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

class AuditTrailService:
    """Service for querying and exporting audit trail data."""

    @staticmethod
    def query_sessions(
        institution_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        agent_type: Optional[str] = None,
        operation: Optional[str] = None,
        workspace_dir: Path = Path("./workspace")
    ) -> List[Dict[str, Any]]:
        """Query sessions with filters.

        Args:
            institution_id: Institution ID
            start_date: ISO8601 start date (inclusive)
            end_date: ISO8601 end date (inclusive)
            agent_type: Filter by agent type (e.g., "compliance_audit")
            operation: Filter by operation in metadata
            workspace_dir: Workspace root directory

        Returns:
            List of session dictionaries matching criteria
        """
        sessions_dir = workspace_dir / institution_id / "agent_sessions"
        if not sessions_dir.exists():
            return []

        results = []
        for session_file in sessions_dir.glob("*.json"):
            with open(session_file, "r", encoding="utf-8") as f:
                session = json.load(f)

            # Date range filter
            if start_date:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                session_dt = datetime.fromisoformat(
                    session.get("created_at", "").replace("Z", "+00:00")
                )
                if session_dt < start_dt:
                    continue

            if end_date:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                session_dt = datetime.fromisoformat(
                    session.get("created_at", "").replace("Z", "+00:00")
                )
                if session_dt > end_dt:
                    continue

            # Agent type filter
            if agent_type and session.get("agent_type") != agent_type:
                continue

            # Operation filter (from metadata)
            if operation:
                session_op = session.get("metadata", {}).get("operation")
                if session_op != operation:
                    continue

            results.append(session)

        # Sort by created_at descending
        results.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return results
```

### Pattern 2: ZIP Packaging with Multiple Files

**What:** Package multiple JSON files and PDFs into a single ZIP archive for download

**When to use:** AUD-03 requirement - packaging audit trail with compliance report

**Example:**
```python
# src/services/audit_trail_service.py (continued)
import zipfile
from io import BytesIO

class AuditTrailService:
    @staticmethod
    def create_audit_package(
        institution_id: str,
        session_ids: List[str],
        include_report: bool = False,
        report_id: Optional[str] = None,
        workspace_dir: Path = Path("./workspace")
    ) -> BytesIO:
        """Create ZIP package with audit trails and optional report.

        Args:
            institution_id: Institution ID
            session_ids: List of session IDs to include
            include_report: Whether to include compliance report
            report_id: Report ID if including report
            workspace_dir: Workspace root directory

        Returns:
            BytesIO buffer containing ZIP archive
        """
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add session logs
            sessions_dir = workspace_dir / institution_id / "agent_sessions"
            for session_id in session_ids:
                session_file = sessions_dir / f"{session_id}.json"
                if session_file.exists():
                    zf.write(
                        session_file,
                        arcname=f"audit_logs/{session_id}.json"
                    )

            # Add compliance report if requested
            if include_report and report_id:
                report_path = workspace_dir / institution_id / "reports" / f"{report_id}.pdf"
                if report_path.exists():
                    zf.write(report_path, arcname="compliance_report.pdf")

            # Add manifest with export metadata
            manifest = {
                "exported_at": datetime.now().isoformat(),
                "institution_id": institution_id,
                "session_count": len(session_ids),
                "includes_report": include_report,
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        buffer.seek(0)
        return buffer
```

### Pattern 3: Flask Download Endpoint with send_file

**What:** REST endpoint that generates export and streams to client

**When to use:** All export endpoints (JSON, ZIP)

**Example:**
```python
# src/api/audit_trails.py
from flask import Blueprint, request, jsonify, send_file
from datetime import datetime

audit_trails_bp = Blueprint("audit_trails", __name__, url_prefix="/api/audit-trails")

@audit_trails_bp.route("/institutions/<institution_id>/export", methods=["POST"])
def export_audit_trail(institution_id: str):
    """Export audit trail as JSON or ZIP.

    Request Body:
        format: "json" or "zip" (default: "json")
        start_date: ISO8601 start date (optional)
        end_date: ISO8601 end date (optional)
        agent_type: Filter by agent type (optional)
        include_report: Include compliance report (ZIP only, optional)
        report_id: Report ID to include (optional)

    Returns:
        File download (JSON or ZIP)
    """
    data = request.get_json() or {}

    format_type = data.get("format", "json")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    agent_type = data.get("agent_type")

    # Query sessions
    sessions = AuditTrailService.query_sessions(
        institution_id=institution_id,
        start_date=start_date,
        end_date=end_date,
        agent_type=agent_type,
    )

    if format_type == "zip":
        # Package as ZIP
        session_ids = [s["id"] for s in sessions]
        buffer = AuditTrailService.create_audit_package(
            institution_id=institution_id,
            session_ids=session_ids,
            include_report=data.get("include_report", False),
            report_id=data.get("report_id"),
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_trail_{institution_id}_{timestamp}.zip"

        return send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )
    else:
        # Return as JSON
        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "exported_at": datetime.now().isoformat(),
            "session_count": len(sessions),
            "sessions": sessions,
        })
```

### Pattern 4: UI with Date Range Picker and Filter Chips

**What:** Frontend interface with date inputs, agent type dropdown, format toggle

**When to use:** User-facing audit trail export page

**Example:**
```javascript
// static/js/audit_trails.js
class AuditTrailManager {
    constructor() {
        this.institutionId = this.getCurrentInstitutionId();
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.getElementById("export-btn").addEventListener("click", () => {
            this.exportAuditTrail();
        });

        document.getElementById("preview-btn").addEventListener("click", () => {
            this.previewSessions();
        });
    }

    async exportAuditTrail() {
        const format = document.getElementById("export-format").value;
        const startDate = document.getElementById("start-date").value;
        const endDate = document.getElementById("end-date").value;
        const agentType = document.getElementById("agent-type").value;
        const includeReport = document.getElementById("include-report").checked;
        const reportId = document.getElementById("report-id").value;

        const payload = {
            format,
            start_date: startDate ? new Date(startDate).toISOString() : null,
            end_date: endDate ? new Date(endDate).toISOString() : null,
            agent_type: agentType || null,
            include_report: includeReport,
            report_id: reportId || null,
        };

        if (format === "zip") {
            // Trigger download
            const form = document.createElement("form");
            form.method = "POST";
            form.action = `/api/audit-trails/institutions/${this.institutionId}/export`;
            form.innerHTML = `<input type="hidden" name="data" value='${JSON.stringify(payload)}'>`;
            document.body.appendChild(form);
            form.submit();
            document.body.removeChild(form);
        } else {
            // Fetch JSON
            const response = await fetch(
                `/api/audit-trails/institutions/${this.institutionId}/export`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                }
            );
            const data = await response.json();
            this.displaySessions(data.sessions);
        }
    }

    async previewSessions() {
        // Show preview modal with session count and metadata
        const startDate = document.getElementById("start-date").value;
        const endDate = document.getElementById("end-date").value;
        const agentType = document.getElementById("agent-type").value;

        const response = await fetch(
            `/api/audit-trails/institutions/${this.institutionId}/sessions?` +
            new URLSearchParams({
                start_date: startDate || "",
                end_date: endDate || "",
                agent_type: agentType || "",
            })
        );
        const data = await response.json();

        document.getElementById("preview-count").textContent = data.count;
        document.getElementById("preview-date-range").textContent =
            `${startDate || "All"} → ${endDate || "All"}`;
    }
}
```

### Anti-Patterns to Avoid

- **Storing duplicate data in database:** Agent sessions already persist to workspace files - don't duplicate to SQL tables for querying (adds complexity, sync issues)
- **Loading all sessions into memory:** For institutions with thousands of sessions, use generators or pagination instead of loading all JSON files
- **Mutable session files:** Never modify session files during export - preserve original audit trail integrity
- **Client-side filtering for large datasets:** Apply filters server-side to reduce payload size
- **Exposing raw file paths in API:** Use session IDs for lookups, not file system paths

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ZIP archive creation | Custom binary file writer | Python stdlib `zipfile` | Edge cases (compression levels, file permissions, unicode filenames, streaming) |
| ISO8601 date parsing | Regex-based date parser | `datetime.fromisoformat()` | Timezone handling, leap seconds, edge cases (T separator, Z suffix) |
| File downloads | Custom streaming response | Flask `send_file` | Handles content-disposition, mimetype, range requests, error handling |
| JSON schema validation | Manual dictionary checks | Existing `AgentSession.to_dict()` | Already handles serialization, maintains consistency |
| Date range filtering | Manual string comparison | Timezone-aware datetime objects | Daylight saving time, UTC conversion, comparison edge cases |

**Key insight:** Compliance audit trails have regulatory requirements (immutability, chain of custody, retention). Using stdlib ensures long-term compatibility and reduces risk of bugs in custom implementations. The existing workspace structure already provides audit trail persistence - export is just aggregation and packaging.

## Common Pitfalls

### Pitfall 1: Timezone Naive Date Filtering

**What goes wrong:** Comparing ISO8601 strings or naive datetime objects across timezones produces incorrect results

**Why it happens:** Sessions use UTC timestamps (`2026-03-21T14:30:00Z`), user input may be local time

**How to avoid:** Always parse with timezone awareness using `.replace("Z", "+00:00")` before `datetime.fromisoformat()`

**Warning signs:** Sessions missing from exports despite being in date range, off-by-N-hours errors

**Example:**
```python
# WRONG - naive datetime comparison
session_dt = datetime.fromisoformat(session["created_at"].replace("Z", ""))  # Naive
filter_dt = datetime.fromisoformat(start_date)  # May be naive

# RIGHT - timezone-aware comparison
session_dt = datetime.fromisoformat(session["created_at"].replace("Z", "+00:00"))
filter_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
```

### Pitfall 2: Missing Session Files During Iteration

**What goes wrong:** FileNotFoundError or missing sessions if files deleted during export

**Why it happens:** Long-running exports may span file system changes (cleanup jobs, concurrent operations)

**How to avoid:** Collect file list first, then read files with try/except per file

**Warning signs:** Intermittent export failures, different session counts on retry

**Example:**
```python
# WRONG - iterating and reading in same loop
for session_file in sessions_dir.glob("*.json"):
    session = json.load(open(session_file))  # May fail if file deleted

# RIGHT - defensive iteration
session_files = list(sessions_dir.glob("*.json"))  # Snapshot file list
for session_file in session_files:
    try:
        with open(session_file, "r") as f:
            session = json.load(f)
        results.append(session)
    except (FileNotFoundError, json.JSONDecodeError):
        continue  # Skip corrupted or deleted files
```

### Pitfall 3: Large ZIP Archives Exhaust Memory

**What goes wrong:** Creating 500MB+ ZIP files in BytesIO causes MemoryError

**Why it happens:** BytesIO stores entire archive in RAM before sending

**How to avoid:** For large exports, write to temp file and stream with `send_file(path, as_attachment=True)`

**Warning signs:** Memory usage spikes during export, server OOM errors for large date ranges

**Example:**
```python
# WRONG - large archive in memory
buffer = BytesIO()
with zipfile.ZipFile(buffer, "w") as zf:
    for session_file in large_session_list:  # 1000+ files
        zf.write(session_file)  # All in RAM
return send_file(buffer, ...)  # May OOM

# RIGHT - temp file for large exports
import tempfile
with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for session_file in large_session_list:
            zf.write(session_file)
    tmp.flush()
    return send_file(tmp.name, as_attachment=True, download_name="audit.zip")
```

### Pitfall 4: Including PII in Audit Logs

**What goes wrong:** Audit trail exports contain student names, SSNs, or sensitive data

**Why it happens:** Tool calls may reference PII in arguments (e.g., `search_student(ssn="123-45-6789")`)

**How to avoid:** Add PII redaction pass before export, or document that exports contain sensitive data

**Warning signs:** Compliance violations, data breach risk, failed audits

**Example:**
```python
# Add redaction before export
def redact_pii_from_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Redact PII from session tool calls."""
    redacted = session.copy()
    for tool_call in redacted.get("tool_calls", []):
        # Redact tool input arguments
        if "input" in tool_call:
            tool_call["input"] = "[REDACTED]"
    return redacted
```

### Pitfall 5: Missing Manifest or Metadata

**What goes wrong:** Exported ZIP files lack context (export date, filters applied, session count)

**Why it happens:** Focus on session data, forget to document export parameters

**How to avoid:** Always include `manifest.json` with export metadata

**Warning signs:** Cannot reconstruct export parameters, audit questions like "when was this exported?"

**Example:**
```python
# Include manifest in every ZIP export
manifest = {
    "exported_at": datetime.now(timezone.utc).isoformat(),
    "institution_id": institution_id,
    "filters": {
        "start_date": start_date,
        "end_date": end_date,
        "agent_type": agent_type,
    },
    "session_count": len(session_ids),
    "includes_report": include_report,
    "export_version": "1.0",  # Schema version
}
zf.writestr("manifest.json", json.dumps(manifest, indent=2))
```

## Code Examples

Verified patterns from research and existing codebase:

### Query Sessions with Date Range Filter

```python
# Source: Research + existing workspace.py patterns
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

def query_sessions(
    institution_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    agent_type: Optional[str] = None,
    workspace_dir: Path = Path("./workspace")
) -> List[Dict[str, Any]]:
    """Query agent sessions with filters."""
    sessions_dir = workspace_dir / institution_id / "agent_sessions"
    if not sessions_dir.exists():
        return []

    results = []
    session_files = list(sessions_dir.glob("*.json"))

    for session_file in session_files:
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                session = json.load(f)

            # Date range filtering
            if start_date or end_date:
                session_dt = datetime.fromisoformat(
                    session.get("created_at", "").replace("Z", "+00:00")
                )

                if start_date:
                    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    if session_dt < start_dt:
                        continue

                if end_date:
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    if session_dt > end_dt:
                        continue

            # Agent type filtering
            if agent_type and session.get("agent_type") != agent_type:
                continue

            results.append(session)

        except (FileNotFoundError, json.JSONDecodeError):
            continue  # Skip corrupted or deleted files

    results.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return results
```

### Create ZIP Package with Audit Trail + Report

```python
# Source: Research + existing PDFExporter patterns
import zipfile
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path

def create_audit_package(
    institution_id: str,
    session_ids: List[str],
    include_report: bool = False,
    report_id: Optional[str] = None,
    workspace_dir: Path = Path("./workspace")
) -> BytesIO:
    """Create ZIP package with audit trail and optional compliance report."""
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add session logs
        sessions_dir = workspace_dir / institution_id / "agent_sessions"
        for session_id in session_ids:
            session_file = sessions_dir / f"{session_id}.json"
            if session_file.exists():
                zf.write(session_file, arcname=f"audit_logs/{session_id}.json")

        # Add compliance report
        if include_report and report_id:
            report_path = workspace_dir / institution_id / "reports" / f"{report_id}.pdf"
            if report_path.exists():
                zf.write(report_path, arcname="compliance_report.pdf")

        # Add manifest
        manifest = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "institution_id": institution_id,
            "session_count": len(session_ids),
            "includes_report": include_report,
            "export_version": "1.0",
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    buffer.seek(0)
    return buffer
```

### Flask Export Endpoint

```python
# Source: Research + existing reports.py patterns
from flask import Blueprint, request, jsonify, send_file
from datetime import datetime

@audit_trails_bp.route("/institutions/<institution_id>/export", methods=["POST"])
def export_audit_trail(institution_id: str):
    """Export audit trail as JSON or ZIP."""
    data = request.get_json() or {}

    # Query sessions
    sessions = AuditTrailService.query_sessions(
        institution_id=institution_id,
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        agent_type=data.get("agent_type"),
    )

    if data.get("format") == "zip":
        # Package as ZIP
        session_ids = [s["id"] for s in sessions]
        buffer = AuditTrailService.create_audit_package(
            institution_id=institution_id,
            session_ids=session_ids,
            include_report=data.get("include_report", False),
            report_id=data.get("report_id"),
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_trail_{institution_id}_{timestamp}.zip"

        return send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )
    else:
        # Return JSON
        return jsonify({
            "success": True,
            "institution_id": institution_id,
            "exported_at": datetime.now().isoformat(),
            "session_count": len(sessions),
            "sessions": sessions,
        })
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CSV exports for logs | Structured JSON with nested data | 2024+ | Preserves full session structure, tool calls, metadata |
| Manual date filtering | ISO8601 with fromisoformat() | Python 3.7+ | Timezone-aware, reliable parsing |
| Custom compression | stdlib zipfile with ZIP_DEFLATED | Always standard | Cross-platform, no dependencies |
| Database audit logs | File-based session storage | AccreditAI design | Simpler, no migration, matches workspace model |
| Static retention | Configurable retention policies | 2026 compliance | GDPR (6 years), HIPAA (6 years), SOC2 (1+ year) |

**Deprecated/outdated:**
- **CSV format for audit logs:** Loses nested structure (tool calls, checkpoints), difficult to parse
- **Naive datetime objects:** Python 3.7+ recommends timezone-aware datetime throughout
- **Global file locks for reading:** Workspace uses per-file locks, read-only operations don't need locks

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.0+ |
| Config file | pytest.ini (existing) |
| Quick run command | `pytest tests/test_audit_trail_service.py -x` |
| Full suite command | `pytest tests/ --cov=src/services/audit_trail_service` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUD-01 | Export sessions as JSON | unit | `pytest tests/test_audit_trail_service.py::test_export_json -x` | ❌ Wave 0 |
| AUD-02 | Date range filtering | unit | `pytest tests/test_audit_trail_service.py::test_date_range_filter -x` | ❌ Wave 0 |
| AUD-03 | ZIP packaging with report | unit | `pytest tests/test_audit_trail_service.py::test_create_zip_package -x` | ❌ Wave 0 |
| AUD-04 | Complete session data export | unit | `pytest tests/test_audit_trail_service.py::test_session_completeness -x` | ❌ Wave 0 |
| AUD-05 | Agent type and operation filtering | unit | `pytest tests/test_audit_trail_service.py::test_filter_by_agent_type -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_audit_trail_service.py -x` (< 5s)
- **Per wave merge:** `pytest tests/test_audit_trail_service.py --cov` (coverage check)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_audit_trail_service.py` — covers AUD-01 through AUD-05
  - Test query_sessions with date range
  - Test query_sessions with agent_type filter
  - Test create_audit_package with sessions only
  - Test create_audit_package with report
  - Test session completeness (tool_calls, timestamps, confidence)
  - Test timezone-aware date filtering
  - Test large export (1000+ sessions) memory usage
- [ ] `tests/test_audit_trails_api.py` — covers API endpoints
  - Test POST /export with format=json
  - Test POST /export with format=zip
  - Test GET /sessions with filters
  - Test send_file download headers

## Sources

### Primary (HIGH confidence)

- Python zipfile documentation - https://docs.python.org/3/library/zipfile.html - confirmed ZIP_DEFLATED, writestr, arcname patterns
- Python datetime documentation - https://docs.python.org/3/library/datetime.html - fromisoformat() for ISO8601 parsing
- AccreditAI workspace.py - existing patterns for save_agent_session, load_agent_session, file locking
- AccreditAI models.py - AgentSession dataclass structure with tool_calls, timestamps, metadata
- AccreditAI reports.py - existing send_file patterns for PDF downloads

### Secondary (MEDIUM confidence)

- [Flask send_file best practices 2026](https://copyprogramming.com/howto/python-flask-return-json-from-file-code-example) - send_file with mimetype, download_name, as_attachment
- [Audit log retention policies](https://learn.microsoft.com/en-us/purview/audit-log-retention-policies) - 180-day default, 1-year standard, compliance requirements
- [Compliance audit trail requirements](https://sftptogo.com/blog/data-compliancee-news-2026-file-transfer/) - GDPR, SOC2, HIPAA log export requirements
- [Log management best practices](https://mev.com/blog/log-management-for-compliance-faqs-best-practices) - immutable records, chain of custody, encryption

### Tertiary (LOW confidence)

- [Writing JSON into ZIP files](https://bbengfort.github.io/2020/08/zipfiles-json/) - Blog post with BytesIO patterns
- [ISO8601 parsing libraries](https://pyiso8601.readthedocs.io/) - Alternative to fromisoformat (not needed)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All stdlib, existing Flask patterns, verified in requirements.txt
- Architecture: HIGH - Extends existing workspace/service/API patterns, matches project conventions
- Pitfalls: HIGH - Based on datetime timezone issues, file system race conditions, memory limits (common patterns)

**Research date:** 2026-03-21
**Valid until:** 90 days (stable domain - stdlib APIs don't change rapidly, compliance requirements stable)
