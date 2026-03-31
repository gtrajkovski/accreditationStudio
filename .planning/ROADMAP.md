# AccreditAI Master Roadmap

**Last updated:** 2026-03-29
**Current version:** v2.0.0 (shipped)
**Next:** v2.1 (Commercial Readiness) — planned

## Strategic Position

AccreditAI is the **only AI-native product** in the accreditation management market. Competitors (Watermark, SPOL, Weave, Anthology, Nuventive) provide workflow/data management but no:
- Document-level AI auditing
- Automated cross-document consistency checking
- AI-generated remediation with tracked changes
- Autonomous submission packet assembly

## Timeline Overview

```
v1.0-v1.7 ✅ Foundation through Performance
  │
v1.8 ✅ Operational Intelligence (retroactive)
  │
v1.9 ✅ Regulatory Intelligence (SHIPPED 2026-03-29)
  │     ├── Phase 36: Accreditor Package System ✅
  │     └── Phase 37: Federal Regulations Library ✅
  │
v2.0 ✅ Productivity Tools (SHIPPED 2026-03-29)
  │     ├── Phase 38: Bulk Remediation Wizard ✅
  │     ├── Phase 39: Packet Studio Wizard ✅
  │     └── Phase 40: Document Workbench IDE ✅
  │
v2.1 ⬜ Commercial Readiness (PLANNED)
  │     ├── Phase 41: Authentication System
  │     ├── Phase 42: Role-Based Access Control
  │     ├── Phase 43: Activity Audit Trail
  │     ├── Phase 44: Task Management
  │     ├── Phase 45: Executive Dashboard
  │     ├── Phase 46: Onboarding Wizard
  │     └── Phase 47: Consulting Mode
  │
v2.2 ⬜ Cloud & Collaboration (FUTURE)
  │     ├── Phase 48: PostgreSQL Migration
  │     ├── Phase 49: Docker + Cloud Deployment
  │     ├── Phase 50: Collaborative Writing
  │     ├── Phase 51: Standards Update Monitoring
  │     └── Phase 52: Regulatory Change Alerts
  │
v2.3 ⬜ Scale & Intelligence (FUTURE)
        ├── SIS/Data Integration
        ├── Public API v2
        ├── SSO/SAML Authentication
        ├── Benchmarking & Analytics
        └── White-Label for Consultants
```

## Current Metrics

| Metric | v2.0 | v2.1 target |
|--------|------|-------------|
| Lines of Code | ~129,000 | ~145,000 |
| Migrations | 45 | 51 |
| API Blueprints | 55 | 62 |
| Services | 37 | 43 |
| Agents | 34 | 34 |

## v2.1 — Commercial Readiness

**Goal:** Make AccreditAI sellable to first paying customers (ACCSC career schools and accreditation consultants).

**Blockers addressed:**
1. No multi-user support → Phase 41-42 (Auth + RBAC)
2. No onboarding experience → Phase 46 (Onboarding Wizard)
3. No accountability trail → Phase 43 (Activity Logging)

**Cloud deployment deferred to v2.2.**

| Phase | Name | Plans | Dependencies |
|-------|------|-------|--------------|
| 41 | Authentication System | Complete    | 2026-03-29 |
| 42 | 1/1 | Complete    | 2026-03-29 |
| 43 | 1/1 | Complete    | 2026-03-30 |
| 44 | 1/1 | Complete    | 2026-03-30 |
| 45 | 1/1 | Complete   | 2026-03-31 |
| 46 | Onboarding Wizard | 1 | 41, 42 |
| 47 | 1/1 | Complete   | 2026-03-31 |

**Total: 7 phases, 7 plans**

## v2.2 — Cloud & Collaboration (Future)

**Goal:** SaaS deployment option and collaborative features.

- PostgreSQL migration for multi-user concurrency
- Docker + cloud deployment (AWS/GCP/Azure)
- Real-time collaborative writing
- Standards update monitoring
- Regulatory change alerts

## v2.3 — Scale & Intelligence (Future)

**Goal:** Enterprise features and deeper AI capabilities.

- SIS/data integration
- Public API v2
- SSO/SAML authentication
- Benchmarking & analytics
- White-label for consulting firms

## Go-to-Market Strategy

### Target Segments (Priority Order)

1. **ACCSC career schools** (~650) — Underserved, document-heavy, consultant-dependent
2. **ABHES/COE health education** (~200+) — Similar requirements, overlapping regulations
3. **Small SACSCOC/HLC institutions** (~500) — Can't afford enterprise tools
4. **Accreditation consultants** — Power users managing multiple institutions

### Pricing Model (Proposed)

| Tier | Target | Price | Includes |
|------|--------|-------|----------|
| Starter | Single campus | $299/mo | 1 user, 1 institution |
| Professional | Multi-program | $599/mo | 5 users, 1 institution |
| Enterprise | Multi-campus | $999/mo | Unlimited users, 5 institutions |
| Consultant | Consultants | $1,499/mo | Unlimited users, 20 institutions |

### Competitive Differentiation

| vs Competitor | Their offering | AccreditAI advantage |
|---------------|----------------|---------------------|
| Watermark | Data organization | AI reads, audits, fixes documents |
| SPOL | Strategic planning | Autonomous compliance auditing |
| Weave | Evidence storage | Cross-document consistency checking |
| Consultants | $150-300/hr | 24/7 AI at fraction of cost |

## How to Execute

Each plan file is a self-contained prompt:

1. Start fresh Claude Code session
2. Feed the plan file (e.g., `.planning/phases/41-authentication/41-01-PLAN.md`)
3. Claude Code implements the plan
4. Run `pytest` to verify
5. Commit with format: `feat(phase-NN): description`
6. Move to next plan

**Execution order for v2.1:**
```
Phase 41 → Phase 42 → (43, 44, 46, 47 in parallel) → Phase 45
```

---

*Updated: 2026-03-29 after v2.1 planning session*
