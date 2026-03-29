---
phase: 36
plan: 01
subsystem: accreditors
tags: [architecture, modular-design, standards, regulatory]
dependency_graph:
  requires: [standards-library, database-migrations]
  provides: [accreditor-registry, modular-accreditors, crosswalk-seeds]
  affects: [standards-harvester, compliance-audit]
tech_stack:
  added: [accreditor-packages-table]
  patterns: [registry-pattern, plugin-architecture, manifest-discovery]
key_files:
  created:
    - src/db/migrations/0043_accreditor_packages.sql
    - src/accreditors/accsc/mappings.py
    - src/accreditors/sacscoc/manifest.json
    - src/accreditors/hlc/manifest.json
    - src/accreditors/abhes/manifest.json
    - src/api/accreditors.py
    - tests/test_accreditor_packages.py
  modified:
    - app.py
decisions:
  - Leveraged existing AccreditorRegistry with manifest-based discovery
  - Added crosswalk seeds only to ACCSC (reference implementation)
  - Used existing base_package.py structure (already implemented)
  - Registered accreditors_bp alongside 32 other blueprints
metrics:
  duration_minutes: 8
  tasks_completed: 1
  tests_added: 8
  tests_passing: 8
  files_created: 7
  lines_added: 206
  completed_at: "2026-03-29T01:23:46Z"
---

# Phase 36 Plan 01: Accreditor Package System Summary

**One-liner:** Modular accreditor package system with registry discovery, ACCSC crosswalk seeds, and API endpoints for 5 accreditors (ACCSC, SACSCOC, HLC, ABHES, COE).

## What Was Built

Created repeatable onboarding structure for accreditor packages:

1. **Database Migration** - `0043_accreditor_packages.sql` with table for tracking package metadata
2. **Crosswalk Mappings** - ACCSC mappings to federal (34 CFR) and state requirements
3. **Manifest Stubs** - Complete manifests for SACSCOC (regional), HLC (regional), ABHES (programmatic)
4. **API Blueprint** - 3 endpoints: list accreditors, get details, trigger fetch
5. **Blueprint Registration** - Integrated with app.py (33 total blueprints now)
6. **Test Coverage** - 8 tests validating registry, manifests, sources

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Leveraged Existing Infrastructure**
- **Found during:** Task 1 (Directory creation)
- **Issue:** Discovered `src/accreditors/` already existed with base_package.py, registry.py, and 2 accreditor packages (ACCSC, COE)
- **Fix:** Reused existing architecture instead of creating duplicate structure. Only added missing manifests (SACSCOC, HLC, ABHES) and new files (mappings.py, accreditors.py API)
- **Files modified:** None (avoided duplication)
- **Commit:** Same commit (integrated approach)

**Rationale:** The existing implementation already provided AccreditorRegistry with manifest-based discovery, AccreditorManifest dataclass, and dynamic module loading. Creating a parallel structure would violate DRY and create conflicts. Instead, I extended the existing system with the missing pieces.

## Technical Decisions

| Decision | Context | Outcome |
|----------|---------|---------|
| Reuse existing registry | AccreditorRegistry already had manifest discovery + dynamic imports | Avoided code duplication, maintained consistency |
| Crosswalk seeds only for ACCSC | Plan showed ACCSC as reference implementation | Other accreditors can add mappings later |
| Manifest-only stubs | SACSCOC/HLC/ABHES don't need parsers yet | Allows registry to discover them without implementation |
| API blueprint without DI | Simple read-only endpoints | No dependencies needed on WorkspaceManager/AIClient |

## Validation

**Tests:** 8/8 passing

```
✓ test_registry_discovers_packages (finds all 5 accreditors)
✓ test_accsc_manifest_valid (code, type, name)
✓ test_accsc_package_has_sources (sources module exists)
✓ test_unknown_accreditor_returns_none (error handling)
✓ test_all_required_accreditors_present (ACCSC, SACSCOC, HLC, ABHES, COE)
✓ test_sacscoc_manifest (institutional, regional)
✓ test_hlc_manifest (institutional, regional)
✓ test_abhes_manifest (programmatic, national)
```

**Database:** Migration 0043 applied successfully

**API:** Blueprint registered at `/api/accreditors`

## Known Stubs

None - Plan was intentionally creating manifest-only stubs for SACSCOC, HLC, ABHES. These are complete for discovery purposes. Future plans will add sources.py and parser.py as needed.

## Integration Points

- **Standards Harvester** (Phase 37) will call `/api/accreditors/<code>/fetch` to trigger downloads
- **Compliance Audit Agent** can query crosswalk seeds via AccreditorRegistry
- **Regulatory Stack Agent** (Tier 2) will use multi-accreditor support

## Next Steps

1. Phase 37-01: Federal Regulations Library (build on this package system)
2. Add sources.py + parser.py for SACSCOC, HLC, ABHES when needed
3. Expand crosswalk seeds for non-ACCSC accreditors

## Self-Check: PASSED

**Created files exist:**
```
FOUND: src/db/migrations/0043_accreditor_packages.sql
FOUND: src/accreditors/accsc/mappings.py
FOUND: src/accreditors/sacscoc/manifest.json
FOUND: src/accreditors/hlc/manifest.json
FOUND: src/accreditors/abhes/manifest.json
FOUND: src/api/accreditors.py
FOUND: tests/test_accreditor_packages.py
```

**Commit exists:**
```
FOUND: 4955799
```

**Tests pass:**
```
8 passed in 0.15s
```

**Migration applied:**
```
✓ 0043_accreditor_packages.sql
```
