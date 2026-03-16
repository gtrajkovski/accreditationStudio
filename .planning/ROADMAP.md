# AccreditAI Roadmap

## Milestone: v1.0 - MVP

### Phase 1: Foundation Infrastructure ✅ COMPLETE
1. ✅ Project scaffolding (Flask + Jinja2 + vanilla JS)
2. ✅ Workspace manager
3. ✅ Core models + stores
4. ✅ Agent framework (BaseAgent, tool registry, session manager)
5. ✅ Orchestrator Agent + background task queue
6. ✅ Chat API + Chat Panel UI with SSE
7. ✅ Institution + Program CRUD
8. ✅ Dashboard with real metrics

### Phase 2: Ingestion + Standards ✅ COMPLETE
9. ✅ Ingestion Agent (upload, extraction, classification)
10. ✅ Chunking + embedding pipeline with PII redaction
11. ✅ Semantic search (sentence-transformers + ChromaDB)
12. ✅ Standards Library with ACCSC/SACSCOC/HLC/ABHES/COE presets
13. ✅ Standards API (`src/api/standards.py`)
14. ✅ Search API (semantic search via embeddings + ChromaDB)

### Phase 3: Audit Engine ✅ COMPLETE
15. ✅ Agent Architecture (24 agents + registry + AgentResult model)
16. ✅ Evidence Mapper Agent (Standard → Evidence crosswalk)
17. ✅ Compliance Audit Agent (multi-pass with citations)
18. ✅ Readiness Score Service
19. ✅ Work Queue + Autopilot
20. ✅ Document Audit Flow UI

### Phase 4: Remediation ✅ COMPLETE
21. ✅ Remediation Agent (7 tools, redlines, finals, truth index)
22. ✅ Document Workbench UI (remediation review, diff view, approvals)
23. ✅ Consistency Agent (8 policy categories, cross-doc checking)
24. ✅ Checklist Auto-Fill Agent (8 tools, evidence search, DOCX export)

### Phase 5: Findings + Packets ✅ COMPLETE
25. ✅ Findings Agent
26. ✅ Narrative Agent
27. ✅ Packet Agent
28. ✅ Submission Organizer UI
29. ✅ Action plan tracking

### Phase 6: Catalog + Exhibits + Faculty ✅ COMPLETE
30. ✅ Catalog Agent + Builder UI
31. ✅ Exhibit registry + Evidence Agent
32. ✅ Faculty Agent
33. ✅ Achievement Agent

### Phase 7: Visit Prep ✅ COMPLETE
34. ✅ Checklist Agent (enhanced with validation)
35. ✅ Interview Prep Agent
36. ✅ Mock visit / readiness assessment
37. ✅ SER Drafting Agent

### Phase 8: Post-Visit + Ongoing ✅ COMPLETE
38. ✅ Team Report Response Agent
39. ✅ Compliance Calendar Agent
40. ✅ Document Review Scheduler

---

## Milestone: v1.1 - Post-MVP Enhancements

### Phase 9: Analytics & Visualization ✅ COMPLETE
41. ✅ Compliance History (readiness over time graph)
42. ✅ Risk Alerts Banner (critical blockers on dashboard)
43. ✅ Quick Actions FAB (Upload/Audit/Packet)
44. ✅ Keyboard Shortcuts (G+D, G+C sequences)
45. ✅ Impact Analysis (fact-to-document dependencies)
46. ✅ Knowledge Graph (entity extraction, D3.js visualization)

### Phase 10: Planning & Search ✅ COMPLETE
47. ✅ Accreditation Timeline Planner (D3.js Gantt chart, 4 templates)
48. ✅ Site Visit Mode (unified search, F2 overlay, 6 data sources)
49. ✅ Global Search (FTS5 indexes, filter tabs, citations)
50. ✅ Evidence Coverage Map (D3.js treemap, drill-down, gaps view)

### Phase 11: Advanced Features ✅ COMPLETE
51. ✅ Accreditation Simulation (mock audit, pass/fail prediction, risk assessment)
52. ✅ Multi-Institution Mode (portfolios, aggregate readiness, comparison, Ctrl+K switcher)
53. ✅ Evidence Highlighting (document viewer, inline highlights, standards sidebar)
54. ✅ Compliance Heatmap (documents × standards matrix, drill-down, filters)

---

## Milestone: v1.2 - Productivity & Polish

### Phase 12: Bulk Operations ✅ COMPLETE
**Goal:** Multi-document batch processing for audit and remediation with cost estimation, progress tracking, and batch history
**Plans:** 4/4 plans complete

Plans:
- [x] 12-01-PLAN.md — Database schema + BatchService with cost estimation ✅ **COMPLETE** (b79fdf9, b1c3c3a, 0c335c0)
- [x] 12-02-PLAN.md — Batch API endpoints (audit, remediation, history) ✅ **COMPLETE** (275b18c, 8c26882, 2bb7218)
- [x] 12-03-PLAN.md — Frontend UI (selection, action bar, progress modal) ✅ **COMPLETE** (682c8dc, 9bb6f7b, 7a6010a)
- [x] 12-04-PLAN.md — Batch history page + workbench integration ✅ **COMPLETE** (c1c351c, 72cd187, 5a3df27)

55. ✅ Batch Remediation (multi-document correction workflow)
56. ✅ Bulk Audit Trigger (queue multiple documents for audit)
57. ✅ Progress Tracking Dashboard (batch operation status)

### Phase 13: Search Enhancement
**Goal:** Unified command palette with dual-mode search (Ctrl+K), live results, filter chips, result tabs with counts, and filter presets
**Plans:** 1/3 plans complete

Plans:
- [x] 13-01-PLAN.md — Database migration + global search API blueprint ✅ **COMPLETE** (57d45f0, 5ebd368, 81bc46b)
- [ ] 13-02-PLAN.md — Command palette dual-mode with live search
- [ ] 13-03-PLAN.md — Filter chips, result tabs, presets, F2 deprecation

58. ✅ Global Search API (filter presets, 6 endpoints, search grouping)
59. Search Autocomplete (recent searches, suggested queries)
60. Search Filters (date range, document type, compliance status)

### Phase 14: Polish & UX
61. Loading Skeletons (replace spinners with skeleton loaders)
62. Keyboard Shortcuts Modal (help overlay showing all shortcuts)
63. Onboarding Flow (first-run tutorial, setup wizard)

---

## Completed Infrastructure

### Core (`src/core/`)
- `models.py` - All domain models with `to_dict()`/`from_dict()` serialization
- `workspace_manager.py` - File locking, version tracking, JSON persistence
- `standards_store.py` - Standards library with preset seeding and CRUD

### Agents (`src/agents/`)
- `base_agent.py` - Tool execution, session management, confidence thresholds
- `orchestrator_agent.py` - Multi-agent coordination, checkpoints
- `ingestion_agent.py` - 7-tool document processing pipeline
- `session.py` - AgentSession, task tracking, audit trail

### Search (`src/search/`)
- `embeddings.py` - sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)
- `vector_store.py` - ChromaDB with cosine similarity, per-institution isolation
- `search_service.py` - High-level semantic search API

### Importers (`src/importers/`)
- `document_parser.py` - PDF/DOCX/TXT extraction with unstructured
- `pii_detector.py` - Regex + AI hybrid PII detection
- `chunker.py` - Semantic chunking with PII anonymization

### API (`src/api/`)
- `chat.py` - SSE streaming chat interface
- `agents.py` - Agent CRUD, streaming, checkpoint management
- `institutions.py` - Institution CRUD
- `documents.py` - Document upload and management
- `standards.py` - Standards library CRUD with 10 endpoints

### Frontend
- Dashboard with compliance metrics
- Institution management
- Program CRUD (modal-based)
- Chat panel with SSE streaming
