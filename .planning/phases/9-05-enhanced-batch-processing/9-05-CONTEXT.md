---
phase: 9-05
name: Enhanced Batch Processing
status: planning
created: 2026-03-27
---

# Phase 9-05: Enhanced Batch Processing

## Goal

Enhance batch processing capabilities with real-time queue monitoring, batch scheduling, priority queuing, and reusable batch templates.

## Problem Statement

AccreditAI has solid batch processing infrastructure (BatchService, Anthropic Batch API integration, cost tracking), but lacks:
- Real-time queue visibility (no dashboard showing active/pending batches)
- Scheduling (must manually trigger each batch)
- Priority management (all batches treated equally)
- Reusable templates (must select documents each time)

## Success Criteria

1. **Queue Monitoring**: Real-time view of active/pending/completed batches with live progress
2. **Batch Templates**: Save and reuse batch configurations for common operations
3. **Scheduling**: Schedule batches for future execution with cron-like patterns
4. **Priority Queue**: Set priority levels for batches, critical batches jump queue

## Constraints

- Must integrate with existing BatchService (don't break current functionality)
- Must use APScheduler (already used for compliance calendar)
- Keep UI consistent with existing batch_history.html patterns

## Non-Goals

- Cross-institution batch operations (requires portfolio maturity)
- Full analytics dashboard (separate phase)
- Real-time WebSocket (use SSE for simplicity)

## Dependencies

- Existing BatchService and batch_operations table
- Existing APScheduler setup from compliance calendar
- Existing batch_history.html UI patterns
