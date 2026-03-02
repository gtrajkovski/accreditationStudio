# AccreditAI

## Current State

**Version:** v0.1 (In Development)

Phase 1 Foundation infrastructure is partially complete:
- Flask app structure with blueprints
- Core domain models (Institution, Program, Document, Audit, Agent system)
- Workspace manager for file-based persistence
- AI client integration with Anthropic SDK
- Base agent framework with tool execution
- Chat API with SSE streaming
- Basic templates and dark theme UI

## What This Is

An AI-powered accreditation management platform that helps post-secondary educational institutions manage their entire accreditation lifecycle - from initial self-evaluation through document preparation, exhibit collection, on-site visit readiness, and post-visit response. Works with any accrediting body and audits against the full regulatory stack: accreditor standards + federal regulations + state/territory requirements + professional licensure body expectations.

Standalone Flask app, single-user localhost tool (same architecture as Course Builder Studio).

## Core Value

Reduce manual document auditing time by 80%+, ensure zero undiscovered compliance gaps at visit time, and enable rapid response to accreditor findings.

## Architecture Reference

Built from Course Builder Studio patterns in `_reference/`. See CLAUDE.md for full technical specification and SPEC.md for detailed agent descriptions.

## Key Components

- **Multi-Agent System:** Orchestrator, Audit, Ingestion, Standards, Evidence, Consistency, Remediation, Findings, Narrative, Packet, Checklist, Interview Prep, Catalog, Faculty, Achievement agents
- **Workspace Structure:** `workspace/{institution_slug}/` with originals, audits, redlines, finals, exhibits, and agent sessions
- **Truth Index:** Single source of truth for institution data consistency
- **RAG Pipeline:** Document chunking, embeddings, semantic search with PII redaction

## Next Steps

Complete Phase 1 Foundation:
- Orchestrator Agent implementation
- Background task queue
- Institution/Program CRUD UI
- Dashboard with compliance metrics
