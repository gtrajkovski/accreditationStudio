# v1.5 — Operational Intelligence

## Theme
Transform AccreditAI from "audit-and-fix tool" into an always-current operational system.

## Success Criteria
1. Institution stays audit-ready without manual re-runs (Autopilot functional)
2. Evidence coverage gaps are visible before packet export (Evidence Contract)
3. Document changes trigger targeted re-audits, not full re-runs (Change Detection)
4. Every audit can be explained and reproduced later (Reproducibility)
5. Standards updates from accreditor sites are detected and surfaced (Harvester MVP)

## Phases

| Phase | Name | Goal | Plans Est. |
|-------|------|------|------------|
| 20 | Autopilot & Morning Brief | Nightly run + morning brief | 3 |
| 21 | Evidence Coverage Contract | Packet export gating | 2 |
| 22 | Change Detection + Targeted Re-Audit | Incremental efficiency | 3 |
| 23 | Audit Reproducibility | Trust + compliance | 2 |
| 24 | Standards Harvester MVP | Regulatory intelligence foundation | 2 |

## Dependencies
- Phase 20 requires: Foundation fixes (autopilot guard removed, orchestrator verified)
- Phase 21 requires: Evidence Guardian functional (verified in v1.4)
- Phase 22 requires: Document parser (exists), audit agent (exists)
- Phase 23 requires: audit_runs table (exists)
- Phase 24 requires: requests library (exists), standards_store (exists)

## Foundation Fixes (Pre-v1.5)

Before starting v1.5 execution, these foundation issues must be resolved:

1. **Migration Numbering** — Fixed: Renamed duplicate 0026/0027 to 0030/0031
2. **Autopilot Stub Guard** — Fixed: NotImplementedError when run_audit=True
3. **Session Round-Trip** — Verified: New test suite validates serialization
4. **Silent Handlers** — Sample fix applied; 290 remain for future sweep

## v1.6 Candidates (Deferred)
- Standards Web Harvester for SACSCOC, HLC, ABHES, COE
- Multi-state regulatory stack builder
- Federal regs library
- Standards change detector + diff
- Accreditor package system

## v1.7 Candidates (Deferred)
- Multi-tenancy / data isolation / auth
- PostgreSQL + pgvector migration
- CI pipeline (GitHub Actions)
- Offline mode / local LLM fallback
