# AccreditAI Replan — 2026-03-21 (Session 2)

## Session 2: Foundation Verification + v1.5 Planning

### Key Finding: Foundation Is Stronger Than Expected

The "hollow middle" analysis from earlier was **outdated**. Re-verification shows:
- **Orchestrator:** Already properly wired to registered agents (INGESTION, GAP_FINDER, EVIDENCE_MAPPER, COMPLIANCE_AUDIT, SER_DRAFTING)
- **Evidence Guardian:** Already implemented with real DB queries
- **Readiness Service:** Already uses real audit findings with critical cap

The earlier replan commits (482c0a0, 3564106, etc.) had already fixed these issues.

## Foundation Audit (Stage 1 Baseline)

| Metric | Before | After |
|--------|--------|-------|
| Stub/placeholder returns in agents | 57 | 57 (many are legitimate placeholders in SER drafts) |
| Silent exception handlers | 290 | 289 (sample fix applied) |
| Orchestrator phantom delegations | 0 | 0 (verified working) |
| Evidence guardian stub tools | 0 | 0 (verified working) |
| Duplicate migration numbers | 2 pairs (0026, 0027) | 0 |
| Tests passing | 224 | 232 |
| Tests failing | 7 | 6 |

## Stage 1 Results

| Item | Status | Notes |
|------|--------|-------|
| 1A: Stub audit | ✅ | Baseline recorded. Most "stubs" are legitimate (SER placeholders, graceful degradation) |
| 1B: Orchestrator fix | ⏭️ SKIP | Already correct - delegates to real registered agents |
| 1C: Evidence guardian | ⏭️ SKIP | Already implemented with real DB queries |
| 1D: Readiness wiring | ⏭️ SKIP | Already implemented with critical findings cap |
| 1E: Silent failure sweep | ⚠️ | Sample fix in accreditors/registry.py. 290 handlers total - most graceful degradation |
| 1F: Autopilot guard | ✅ | NotImplementedError raised when run_audit=True |
| 1G: Session round-trip test | ✅ | 7 comprehensive tests created and passing |

## Stage 2 Results

| Item | Status | Notes |
|------|--------|-------|
| 2A: v1.5 milestone files | ✅ | MILESTONE_V1.5.md created with 5 phases |
| 2B: Phase 20 plans | ✅ | 3 plans: 20-01 (service), 20-02 (API), 20-03 (UI) |
| 2C: Phase 21 plans | ✅ | 2 plans: 21-01 (validation), 21-02 (UI) |
| STATE.md update | ✅ | Updated for v1.5 milestone |
| REQUIREMENTS.md update | ✅ | 14 v1.5 requirements added with traceability |

## Files Created/Modified This Session

```
MODIFIED:
  src/services/autopilot_service.py  — NotImplementedError guard for run_audit=True
  src/accreditors/registry.py        — Logging added to exception handlers
  src/db/migrations/0030_reports.sql — Renamed from 0026
  src/db/migrations/0031_scheduled_reports.sql — Renamed from 0027
  .planning/STATE.md — Updated for v1.5 milestone
  .planning/REQUIREMENTS.md — Added v1.5 requirements

CREATED:
  tests/test_session_persistence.py  — 7 tests for AgentSession serialization
  .planning/phases/MILESTONE_V1.5.md
  .planning/phases/20-autopilot/20-01-PLAN.md
  .planning/phases/20-autopilot/20-02-PLAN.md
  .planning/phases/20-autopilot/20-03-PLAN.md
  .planning/phases/21-evidence-contract/21-01-PLAN.md
  .planning/phases/21-evidence-contract/21-02-PLAN.md
```

## v1.5 Status After This Session

```
v1.5: [░░░░░░░░░░░░░░░░░░░░] 0/12 plans
  Phase 20: [░░░░░░░░░░░░░░░░░░░░] 0/3 plans (READY - plans written)
  Phase 21: [░░░░░░░░░░░░░░░░░░░░] 0/2 plans (PLANNED)
  Phase 22: [░░░░░░░░░░░░░░░░░░░░] 0/3 plans (needs plan files)
  Phase 23: [░░░░░░░░░░░░░░░░░░░░] 0/2 plans (needs plan files)
  Phase 24: [░░░░░░░░░░░░░░░░░░░░] 0/2 plans (needs plan files)
```

## Next Session Priorities

1. **Execute Phase 20-01**: Wire autopilot audit, add change detection, generate morning brief
2. **Create Phase 22-24 plan files**: Detailed implementation plans
3. **Fix batch service tests**: Add proper FK setup in test fixtures
4. **Consider WeasyPrint alternative**: Skip PDF export on Windows or use wkhtmltopdf

## Deferred Backlog

### v1.6: Regulatory Intelligence
- Standards Web Harvester for SACSCOC, HLC, ABHES, COE
- Multi-state regulatory stack builder
- Federal regs library
- Standards change detector + diff

### v1.7: Scale & Experience
- Multi-tenancy / data isolation / auth
- PostgreSQL + pgvector migration
- CI pipeline (GitHub Actions)
- Offline mode / local LLM fallback

### Tech Debt
- `models.py` split into domain modules (2,584 lines)
- Silent exception handler sweep (289 remaining)
- AgentType enum cleanup
- Workspace file I/O caching

---
*Replan generated: 2026-03-21 Session 2*
*Test suite: 232 passed, 6 failed, 8 errors (pre-existing issues)*
