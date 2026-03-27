---
phase: 9-04
name: State Regulatory Modules
status: planning
created: 2026-03-27
---

# Phase 9-04: State Regulatory Modules

## Goal

Add state regulatory compliance tracking to AccreditAI, enabling institutions to manage state authorization, state-specific catalog requirements, and program-level licensing board approvals.

## Problem Statement

AccreditAI currently only audits against accreditor standards. The RegulatoryStack model has empty `state_regulations` and `federal_regulations` fields. Users cannot:
- Track state authorization status (SARA membership, individual state approvals)
- Manage state-specific catalog disclosure requirements
- Monitor program-level licensing board approvals and exam pass rates
- Get compliance scores for specific states

## Success Criteria

1. **State Authorization Tracking**: CRUD for state authorizations with SARA status, renewal dates
2. **Catalog Requirements**: State-specific required disclosures with evidence linking
3. **Program Licensing**: Board approvals, exam pass rates, expiration tracking
4. **Compliance Scoring**: Per-state readiness score (0-100)
5. **Calendar Integration**: State deadlines in existing compliance calendar
6. **UI Workflow**: State selector, authorization panel, checklist view, readiness ring

## Constraints

- Must integrate with existing Compliance Calendar system
- Must use existing readiness scoring pattern
- Initial support for 5 major states (CA, TX, NY, FL, IL)
- Must not break existing accreditor-based audit flow

## Non-Goals

- Complete coverage of all 50 states (start with 5)
- Federal regulation implementation (separate phase)
- Automatic fetching of state requirements from websites
- Real-time state regulation change detection

## Dependencies

- Existing Compliance Calendar Agent
- Existing Readiness Service
- Existing Standards Store pattern (for state requirements store)

## Risks

- State requirements vary significantly - need flexible schema
- Catalog requirement mapping is manual initially
- Program licensing data may be incomplete
