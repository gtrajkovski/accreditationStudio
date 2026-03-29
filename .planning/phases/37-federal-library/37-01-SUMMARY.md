---
phase: 37-federal-library
plan: 01
subsystem: regulatory
tags: [federal, regulations, title-iv, ferpa, clery, title-ix, ada, gainful-employment, coppa]

# Dependency graph
requires:
  - phase: 36-accreditor-packages
    provides: accreditor package system pattern for regulatory bundles
provides:
  - FederalBundleService with applicability rule evaluation
  - 7 federal regulation bundles with 34 requirements
  - Federal regulations API blueprint (7 endpoints)
  - Profile-based filtering for institution compliance
affects: [compliance-audit, readiness-service, regulatory-stack-agent]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - JSON-based regulation bundles with applicability rules
    - Safe eval for applicability expressions
    - Profile-based filtering pattern

key-files:
  created:
    - src/regulatory/federal/models.py
    - src/regulatory/federal/bundles.py
    - src/regulatory/federal/__init__.py
    - src/regulatory/federal/title_iv.json
    - src/regulatory/federal/ferpa.json
    - src/regulatory/federal/clery.json
    - src/regulatory/federal/title_ix.json
    - src/regulatory/federal/ada.json
    - src/regulatory/federal/gainful_employment.json
    - src/regulatory/federal/coppa.json
    - src/api/federal.py
    - tests/test_federal_bundles.py
  modified:
    - app.py

key-decisions:
  - "Safe eval with restricted builtins for applicability rules"
  - "Profile-based filtering with defaults for missing attributes"
  - "34 requirements across 7 federal bundles covering major regulations"

patterns-established:
  - "Federal bundle JSON structure: id, name, short_name, description, citations, applicability_rule, requirements[]"
  - "Applicability rule as Python expression evaluated against institution profile namespace"

requirements-completed: []

# Metrics
duration: 6min
completed: 2026-03-29
---

# Phase 37 Plan 01: Federal Regulations Library Summary

**Structured federal regulation bundles (Title IV, FERPA, Clery, Title IX, ADA, GE, COPPA) with applicability rules evaluated against institution profile**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-29T01:33:39Z
- **Completed:** 2026-03-29T01:39:45Z
- **Tasks:** 7
- **Files created:** 12
- **Files modified:** 1

## Accomplishments

- Created 7 federal regulation bundles with 34 total requirements
- FederalBundleService with profile-based applicability filtering
- Federal API blueprint with 7 endpoints for bundle queries
- Comprehensive test suite (22 tests) verifying all applicability rules

## Task Commits

Each task was committed atomically:

1. **Task 1: Directory structure** - `de8b0b8` (chore)
2. **Task 2: Federal models** - `2070c95` (feat)
3. **Task 3: JSON bundle files** - `18db04b` (feat)
4. **Task 4: Bundle service** - `c7c661e` (feat)
5. **Task 5: API blueprint** - `ca3c69b` (feat)
6. **Task 6: Tests** - `0f6a2da` (test)
7. **Task 7: App integration** - `bb4c9c9` (feat)

## Files Created/Modified

**Created:**
- `src/regulatory/federal/__init__.py` - Module exports
- `src/regulatory/federal/models.py` - FederalBundle, FederalRequirement dataclasses
- `src/regulatory/federal/bundles.py` - FederalBundleService for loading/querying
- `src/regulatory/federal/title_iv.json` - Title IV Student Financial Aid (5 requirements)
- `src/regulatory/federal/ferpa.json` - FERPA Student Privacy (5 requirements)
- `src/regulatory/federal/clery.json` - Clery Act Campus Security (4 requirements)
- `src/regulatory/federal/title_ix.json` - Title IX Sex Discrimination (5 requirements)
- `src/regulatory/federal/ada.json` - ADA/Section 504 Accessibility (5 requirements)
- `src/regulatory/federal/gainful_employment.json` - Gainful Employment (5 requirements)
- `src/regulatory/federal/coppa.json` - Children's Online Privacy (5 requirements)
- `src/api/federal.py` - Federal regulations API blueprint
- `tests/test_federal_bundles.py` - 22 tests for bundle service

**Modified:**
- `app.py` - Register federal_bp blueprint (33rd blueprint)

## API Endpoints Added

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/federal/bundles` | GET | List all federal bundles |
| `/api/federal/bundles/<id>` | GET | Get full bundle details |
| `/api/federal/bundles/<id>/requirements/<req_id>` | GET | Get specific requirement |
| `/api/federal/applicable/<inst_id>` | GET | Get applicable bundles for institution |
| `/api/federal/search` | GET | Search requirements (query param: q) |
| `/api/federal/profile-check` | POST | Check applicability without institution |
| `/api/federal/stats` | GET | Library statistics |

## Bundle Applicability Rules

| Bundle | Applicability Rule |
|--------|-------------------|
| Title IV | `institution.title_iv_eligible == True` |
| FERPA | `True` (all institutions) |
| Clery Act | `institution.title_iv_eligible == True` |
| Title IX | `True` (all institutions) |
| ADA/504 | `True` (all institutions) |
| Gainful Employment | `institution.offers_certificates == True or institution.for_profit == True` |
| COPPA | `institution.serves_minors == True` |

## Decisions Made

- **Safe eval pattern**: Applicability rules use restricted `__builtins__: {}` context with a simple namespace wrapper for profile attributes
- **Default attribute handling**: Missing profile attributes default to False (safe/conservative)
- **34 requirements**: Focus on actionable requirements with citation, evidence_types, common_violations, and penalty_range fields

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Federal regulations library complete and ready for use
- Integrates with existing workspace/institution model
- Ready for Compliance Audit Agent to query applicable federal requirements
- v1.9 milestone complete after this plan

## Self-Check: PASSED

- All 12 created files verified
- All 7 commits verified in git log
- All 22 tests passing

---
*Phase: 37-federal-library*
*Completed: 2026-03-29*
