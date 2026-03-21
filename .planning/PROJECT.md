# AccreditAI

## What This Is

AI-powered platform for managing the entire accreditation lifecycle of post-secondary educational institutions — from self-evaluation through document preparation, exhibit collection, on-site visit readiness, and post-visit response. Audits against the full regulatory stack: accreditor standards + federal regulations + state requirements + professional licensure expectations.

## Core Value

Institutions can achieve and maintain accreditation compliance with minimal manual effort through autonomous AI agents that audit, remediate, and prepare submission materials.

## Current Milestone: v1.4 - Enterprise & Polish

**Goal:** Improve report customization, API discoverability, and compliance audit trails for enterprise adoption.

**Target features:**
- Report templates and comparison views
- OpenAPI/Swagger documentation for all 35+ blueprints
- Audit trail export for compliance evidence

## Requirements

### Validated

- v1.0: Core platform (workspace, agents, standards, audit, remediation)
- v1.1: Analytics & visualization (heatmaps, knowledge graph, simulation)
- v1.2: Productivity (bulk operations, global search, UX polish)
- v1.3: AI & reporting (explainers, evidence assistant, PDF reports, scheduling)

### Active

See `.planning/REQUIREMENTS.md` for v1.4 requirements.

### Out of Scope

- Multi-user authentication — Single-user localhost tool for now
- Mobile app — Web-first, responsive design only
- Real-time collaboration — Single-user model

## Context

- Flask + Jinja2 + vanilla JS + Anthropic SDK
- 24-agent tiered architecture with registry pattern
- 35 API blueprints registered
- SQLite database with 28 migrations
- ChromaDB for semantic search
- Docker deployment with gunicorn

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
*Last updated: 2026-03-21 after v1.4 milestone start*
