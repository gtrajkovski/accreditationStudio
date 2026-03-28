---
phase: 9-06
name: Full Observability Dashboard
status: planning
created: 2026-03-28
---

# Phase 9-06: Full Observability Dashboard

## Goal

Create a unified observability dashboard showing system health, AI costs, agent activity, and performance metrics across all AccreditAI operations.

## Success Criteria

1. **System Health Panel**: Database size, cache hit rates, uptime
2. **AI Costs Panel**: Total spend, per-model breakdown, daily trend
3. **Agent Activity Panel**: Active sessions, recent completions, failures
4. **Performance Panel**: Response times, queue depth, batch throughput

## Scope (Focused for Context Budget)

Single plan with:
- ObservabilityService aggregating existing metrics
- API blueprint with dashboard endpoints
- Dashboard UI page with 4 panels

## Dependencies

- Existing ai_cost_log table for cost data
- Existing agent_sessions table for agent data
- Existing batch_operations for batch data
