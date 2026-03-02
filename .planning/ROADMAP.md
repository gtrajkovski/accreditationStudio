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
14. 🔶 Search API blueprint (implementation ready, needs registration)

### Phase 3: Audit Engine ← NEXT
15. ✅ Agent Architecture (15 agents + registry + AgentResult model)
16. Evidence Mapper Agent (Standard → Evidence crosswalk)
17. Compliance Audit Agent (multi-pass with citations)
18. Risk Scorer Agent (compliance health score)
19. Compliance Command Center UI
20. Evidence Explorer UI
21. Fix-It wizard with Remediation Agent

### Phase 4: Remediation
21. Remediation Agent (redlines, finals, section editing)
22. Document editor UI
23. Consistency Agent
24. Checklist auto-filling

### Phase 5: Findings + Packets
25. Findings Agent
26. Narrative Agent
27. Packet Agent
28. Submission Organizer
29. Action plan tracking

### Phase 6: Catalog + Exhibits + Faculty
30. Catalog Agent + Builder UI
31. Exhibit registry + Evidence Agent
32. Faculty Agent
33. Achievement Agent

### Phase 7: Visit Prep
34. Checklist Agent
35. Interview Prep Agent
36. Mock visit / readiness assessment
37. SER drafting

### Phase 8: Post-Visit + Ongoing
38. Team report response writer
39. Compliance calendar
40. Document review scheduler

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
