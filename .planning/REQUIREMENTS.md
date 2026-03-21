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

- [ ] **AUD-01**: User can export agent session logs as JSON
- [ ] **AUD-02**: User can export activity history for date range
- [ ] **AUD-03**: User can package audit trail with compliance report
- [ ] **AUD-04**: Exported logs include tool calls, decisions, and timestamps
- [ ] **AUD-05**: User can filter export by agent type or operation

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
| AUD-01 | Phase 19 | Pending |
| AUD-02 | Phase 19 | Pending |
| AUD-03 | Phase 19 | Pending |
| AUD-04 | Phase 19 | Pending |
| AUD-05 | Phase 19 | Pending |

**Coverage:**
- v1.4 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after v1.4 milestone start*
