# AccreditAI

## What This Is

AI-powered platform for managing the entire accreditation lifecycle of post-secondary educational institutions — from self-evaluation through document preparation, exhibit collection, on-site visit readiness, and post-visit response. Audits against the full regulatory stack: accreditor standards + federal regulations + state requirements + professional licensure expectations.

## Core Value

Institutions can achieve and maintain accreditation compliance with minimal manual effort through autonomous AI agents that audit, remediate, and prepare submission materials.

## Current State: v2.0.0 - Productivity Tools

**Released:** 2026-03-29

**Delivered:**
- **v1.8**: Operational intelligence (autopilot, work queue, change detection, evidence contracts, audit reproducibility)
- **v1.9**: Regulatory intelligence (accreditor packages, federal regulations library)
- **v2.0**: Productivity tools (bulk remediation wizard, packet studio wizard, document workbench IDE)

## Requirements

### Validated

- v1.0: Core platform (workspace, agents, standards, audit, remediation)
- v1.1: Analytics & visualization (heatmaps, knowledge graph, simulation)
- v1.2: Productivity (bulk operations, global search, UX polish)
- v1.3: AI & reporting (explainers, evidence assistant, PDF reports, scheduling)
- v1.4: Enterprise & polish (report enhancements, API docs, audit trails)
- v1.5: Operational intelligence (autopilot, evidence contracts, change detection, reproducibility, standards harvester)
- v1.6: Context-sensitive search (scoped search, 8 sources, scope badge UI)
- v1.7: Performance & efficiency (caching, gzip, multi-model routing, cost tracking, accessibility)
- v1.8: Operational intelligence extended (autopilot service, work queue, change detection, evidence contracts, audit reproducibility)
- v1.9: Regulatory intelligence (accreditor package system, federal regulations library)
- v2.0: Productivity tools (bulk remediation wizard, packet studio wizard, document workbench IDE)

### Active

Next milestone requirements to be defined via `/gsd:new-milestone`.

### Out of Scope

- Multi-user authentication — Single-user localhost tool for now
- Mobile app — Web-first, responsive design only
- Real-time collaboration — Single-user model

## Context

- Flask + Jinja2 + vanilla JS + Anthropic SDK
- 34-agent tiered architecture with registry pattern
- 55 API blueprints registered
- SQLite database with 45 migrations
- ChromaDB for semantic search + FTS5 for full-text
- Docker deployment with gunicorn
- ~129,000 lines of code
- 37 service modules
- Multi-model support: Claude Sonnet (reasoning) + Haiku (fast tasks)
- Anthropic Batch API integration for bulk operations

## Constraints

- **Tech stack**: Flask, vanilla JS (no React/Vue), SQLite
- **Deployment**: Single-user localhost, Docker optional
- **AI**: Anthropic Claude API only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| WeasyPrint for PDFs | GTK-based, high-quality PDF rendering | ✓ Good |
| APScheduler for scheduling | Lightweight, no broker required | ✓ Good |
| Flask-Mail for email | Simple SMTP integration | ✓ Good |
| ChromaDB for vectors | Easy setup, good performance | ✓ Good |
| Haiku for simple tasks | 73% cost savings on PII/language detection | ✓ Good |
| flask-compress for gzip | Simpler than manual middleware | ✓ Good |
| Batch API for bulk ops | 50% discount on bulk audits/remediation | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-29 after v2.0 milestone completion*
