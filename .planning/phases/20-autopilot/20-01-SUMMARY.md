---
phase: 20
plan: 01
subsystem: autopilot
tags: [service, agent-integration, i18n, tests]
dependency_graph:
  requires: []
  provides: [autopilot-audit-wiring, change-detection, morning-brief]
  affects: [autopilot_service.py, readiness-workflow]
tech_stack:
  added: []
  patterns: [SHA256-hashing, agent-registry-invocation, workspace-file-generation]
key_files:
  created:
    - tests/test_autopilot_service.py
  modified:
    - src/services/autopilot_service.py
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - Invoke ComplianceAuditAgent directly via AgentRegistry.create for autopilot audits
  - Use SHA256 for document change detection (content_hash column)
  - Generate markdown briefs in workspace/{institution_id}/briefs/ directory
metrics:
  duration: 4.5 minutes
  completed: "2026-03-21T23:47:45Z"
  tasks_completed: 5
  tests_added: 13
---

# Phase 20 Plan 01: AutopilotService Enhancement Summary

Wired autopilot run_audit=True to ComplianceAuditAgent via registry pattern, added SHA256 document change detection, implemented morning brief generation with readiness delta tracking.

## Completed Tasks

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Wire autopilot audit to ComplianceAuditAgent | 930f104 |
| 2 | Add document change detection via SHA256 | 930f104 |
| 3 | Verify readiness snapshot persistence | 930f104 |
| 4 | Add morning brief generation | 930f104 |
| 5 | Add i18n keys for autopilot brief | 14499aa |
| - | Add unit tests (13 tests) | fdee113 |

## Implementation Details

### Autopilot Audit Wiring

Replaced the `NotImplementedError` guard with actual agent invocation:

```python
def _run_compliance_audit(institution_id, workspace_manager, conn):
    session = AgentSession(
        institution_id=institution_id,
        agent_type=AgentType.COMPLIANCE_AUDIT.value,
        status=SessionStatus.RUNNING,
    )
    agent = AgentRegistry.create(AgentType.COMPLIANCE_AUDIT, session, workspace_manager)
    # Initialize and run completeness pass for each indexed document
```

### Document Change Detection

SHA256-based change detection for identifying modified documents:

```python
def _compute_file_hash(file_path: str) -> Optional[str]:
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def _detect_changed_documents(institution_id, conn) -> List[Dict]:
    """Compare content_hash column with current file hash."""
```

### Morning Brief Generation

Generates daily markdown brief in workspace:

```
workspace/{institution_id}/briefs/YYYY-MM-DD.md
```

Content includes:
- Readiness score with delta from yesterday
- Top 5 blockers
- Next 5 best actions
- Autopilot run summary (docs indexed, issues found, duration)

### i18n Support

Added `autopilot.brief.*` keys (13 strings) for both en-US and es-PR locales.

## Test Coverage

13 unit tests added:

- **TestFileHash** (4 tests): Hash computation, missing files, consistency
- **TestChangeDetection** (3 tests): New files, unchanged files, changed files
- **TestUpdateDocumentHash** (1 test): Hash persistence
- **TestAutopilotConfig** (2 tests): Config save/load, updates
- **TestMorningBrief** (3 tests): Content generation, blockers, delta calculation

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] src/services/autopilot_service.py modified with new functions
- [x] src/i18n/en-US.json includes autopilot.brief.* keys
- [x] src/i18n/es-PR.json includes autopilot.brief.* keys
- [x] tests/test_autopilot_service.py created with 13 tests
- [x] All commits exist: 930f104, 14499aa, fdee113
