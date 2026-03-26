# Requirements: AccreditAI

**Defined:** 2026-03-21
**Core Value:** Institutions can achieve and maintain accreditation compliance with minimal manual effort

## v1.4 Requirements

Requirements for v1.4 - Enterprise & Polish milestone.

### Report Enhancements

- [ ] **RPT-01**: User can create custom report templates with selected sections
- [ ] **RPT-02**: User can compare reports between two dates
- [x] **RPT-03**: User can view readiness trend chart over time
- [x] **RPT-04**: User can select which metrics appear in executive summary
- [ ] **RPT-05**: User can save template configurations for reuse

### API Documentation

- [x] **API-01**: System generates OpenAPI 3.0 spec from Flask blueprints
- [x] **API-02**: User can access Swagger UI at /api/docs endpoint
- [x] **API-03**: API documentation includes request/response examples
- [x] **API-04**: API documentation groups endpoints by blueprint

### Audit Trail Export

- [x] **AUD-01**: User can export agent session logs as JSON
- [x] **AUD-02**: User can export activity history for date range
- [x] **AUD-03**: User can package audit trail with compliance report
- [x] **AUD-04**: Exported logs include tool calls, decisions, and timestamps
- [x] **AUD-05**: User can filter export by agent type or operation

## v1.5 Requirements

Requirements for v1.5 - Operational Intelligence milestone.

### Autopilot & Operational

- [x] **AUTO-01**: System runs nightly autopilot for institutions with autopilot enabled
- [x] **AUTO-02**: Morning brief generated with readiness delta, blockers, and next actions
- [x] **AUTO-03**: User can trigger autopilot run manually via "Run Now"

### Evidence Contract

- [x] **EVID-01**: Packet export blocked unless all selected standards have evidence
- [x] **EVID-02**: Critical findings must be resolved or explicitly waived before export
- [x] **EVID-03**: Coverage step in Packet Studio shows gaps visually

### Change Detection

- [x] **CHG-01**: Document uploads compute sha256 diff against previous version
- [x] **CHG-02**: Changed documents trigger targeted re-audit recommendation
- [x] **CHG-03**: Targeted re-audit runs only impacted checklist items

### Reproducibility

- [x] **REPRO-01**: Each audit run stores a reproducibility bundle (standards, docs, model, timestamps)
- [x] **REPRO-02**: User can view "How this audit was produced" on audit detail page

### Standards Harvester

- [x] **HARV-01**: System can fetch and parse ACCSC standards PDF from official URL
- [x] **HARV-02**: Fetched standards stored with version date and hash
- [x] **HARV-03**: User can trigger fetch and view diff against previous version

## v1.6 Requirements

Requirements for v1.6 - Context-Sensitive Search milestone.

### Search Context & Scoping

- [x] **CTX-01**: User's search automatically scopes to their current page context (institution, program, document)
- [ ] **CTX-02**: User can manually widen/narrow search scope via UI controls
- [ ] **CTX-03**: Search scope is visually indicated with a badge showing current level

### Search Sources

- [x] **SRC-01**: User can search across 8 data sources (documents, document_text, standards, findings, evidence, knowledge_graph, truth_index, agent_sessions)
- [x] **SRC-02**: Semantic search (ChromaDB) respects scope via metadata filtering
- [x] **SRC-03**: Structured search (FTS5) respects scope via WHERE clause filtering
- [x] **SRC-04**: Results merge semantic + structured matches, deduplicated by item ID

### Search API

- [x] **SRCH-01**: POST /api/search/contextual returns scoped results with facets
- [x] **SRCH-02**: GET /api/search/contextual/sources returns available sources for a scope
- [x] **SRCH-03**: GET /api/search/contextual/suggest returns query suggestions

### Search Frontend

- [ ] **SRCHUI-01**: Command palette shows scope badge and allows scope cycling
- [x] **SRCHUI-02**: Inline search bar in page header shows scope as placeholder
- [ ] **SRCHUI-03**: Results panel has tabs for each source with counts
- [ ] **SRCHUI-04**: Keyboard shortcuts work (/, Ctrl+K, Tab, Shift+Up/Down)

### Integration

- [x] **INT-01**: Templates include data attributes for automatic context detection
- [x] **INT-02**: i18n strings for scope names, source names, and UI labels (en-US, es-PR)

## Future Requirements

Deferred to future milestones.

### Multi-User

- **USER-01**: Multiple users can access the same institution
- **USER-02**: Role-based access control (admin, auditor, viewer)
- **USER-03**: User authentication via OAuth

### Mobile

- **MOB-01**: Responsive design works on tablet
- **MOB-02**: PWA support for offline access

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user auth | Single-user localhost tool for v1.x |
| Mobile app | Web-first, responsive design sufficient |
| Real-time collaboration | Single-user model |
| Custom branding | Not needed for localhost tool |

## Traceability

### v1.4 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RPT-01 | Phase 17 | Pending |
| RPT-02 | Phase 17 | Pending |
| RPT-03 | Phase 17 | Complete |
| RPT-04 | Phase 17 | Complete |
| RPT-05 | Phase 17 | Pending |
| API-01 | Phase 18 | Complete |
| API-02 | Phase 18 | Complete |
| API-03 | Phase 18 | Complete |
| API-04 | Phase 18 | Complete |
| AUD-01 | Phase 19 | Complete (19-01) |
| AUD-02 | Phase 19 | Complete (19-01) |
| AUD-03 | Phase 19 | Complete (19-02) |
| AUD-04 | Phase 19 | Complete (19-01) |
| AUD-05 | Phase 19 | Complete (19-01) |

**v1.4 Coverage:**
- v1.4 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

### v1.5 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTO-01 | Phase 20 | Complete (20-01) |
| AUTO-02 | Phase 20 | Complete (20-01) |
| AUTO-03 | Phase 20 | Complete (20-02) |
| EVID-01 | Phase 21 | Complete (21-01) |
| EVID-02 | Phase 21 | Complete (21-01) |
| EVID-03 | Phase 21 | Complete (21-02) |
| CHG-01 | Phase 22 | Complete (22-01) |
| CHG-02 | Phase 22 | Complete (22-02) |
| CHG-03 | Phase 22 | Complete (22-03) |
| REPRO-01 | Phase 23 | Complete (23-01) |
| REPRO-02 | Phase 23 | Complete (23-02) |
| HARV-01 | Phase 24 | Complete (24-01) |
| HARV-02 | Phase 24 | Complete (24-01) |
| HARV-03 | Phase 24 | Complete (24-02) |

**v1.5 Coverage:**
- v1.5 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

### v1.6 Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTX-01 | Phase 25 | Complete |
| CTX-02 | Phase 27 | Pending |
| CTX-03 | Phase 27 | Pending |
| SRC-01 | Phase 25 | Complete |
| SRC-02 | Phase 25 | Complete |
| SRC-03 | Phase 25 | Complete |
| SRC-04 | Phase 25 | Complete |
| SRCH-01 | Phase 26 | Complete |
| SRCH-02 | Phase 26 | Complete |
| SRCH-03 | Phase 26 | Complete |
| SRCHUI-01 | Phase 27 | Pending |
| SRCHUI-02 | Phase 27 | Complete |
| SRCHUI-03 | Phase 27 | Pending |
| SRCHUI-04 | Phase 27 | Pending |
| INT-01 | Phase 26 | Complete |
| INT-02 | Phase 26 | Complete |

**v1.6 Coverage:**
- v1.6 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-26 after v1.6 roadmap creation*
