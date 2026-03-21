---
phase: 15-ai-explainers
plan: 02
subsystem: evidence-assistant
tags: [ai, search, evidence, standards, weighting, context-aware]
dependency_graph:
  requires:
    - standard-explainer-service
    - search-service
    - ai-client
  provides:
    - evidence-assistant-service
    - evidence-assistant-api
    - evidence-finder-ui
  affects:
    - ai-assistant-nav
tech_stack:
  added:
    - EvidenceAssistantService
    - evidence_assistant_bp
  patterns:
    - Context-aware search with weighting
    - Required evidence type boosting (1.5x)
    - AI-generated follow-up suggestions
key_files:
  created:
    - src/services/evidence_assistant_service.py
    - src/api/evidence_assistant.py
    - templates/evidence_assistant.html
    - static/js/evidence_assistant.js
    - static/css/evidence_assistant.css
    - tests/test_evidence_assistant_service.py
  modified:
    - app.py
    - templates/base.html
    - src/i18n/en-US.json
    - src/i18n/es-PR.json
decisions:
  - decision: "Use 1.5x score boost for required evidence types"
    rationale: "Strong signal without overwhelming non-required but highly relevant results"
    alternatives: ["2x boost (too aggressive)", "1.25x boost (too subtle)"]
  - decision: "Generate suggestions based on conversation + context"
    rationale: "More relevant follow-ups by combining history with active standard and page"
    alternatives: ["Static suggestions", "Random suggestions"]
  - decision: "Relevance labels: Required/Relevant/Related"
    rationale: "Clear visual hierarchy matching user mental model"
    alternatives: ["Numeric scores only", "Color coding only"]
metrics:
  duration_minutes: 11.5
  tasks_completed: 2
  tests_added: 7
  tests_passing: 7
  files_created: 6
  files_modified: 4
  lines_added: 1681
  completed_at: "2026-03-21T03:24:56Z"
---

# Phase 15 Plan 02: Evidence Assistant Summary

**One-liner:** Context-aware evidence finder with 1.5x weighting for required document types and AI-generated follow-up suggestions

## What Was Built

### EvidenceAssistantService (268 lines)
- `find_evidence_for_standard()`: Searches for evidence with standard-aware weighting
- `generate_suggested_prompts()`: AI-generated context-aware follow-up questions
- `EvidenceResult` dataclass with relevance indicators
- Required evidence type detection with partial matching
- 1.5x score boost for documents matching required types
- Graceful error handling for AI parse failures

### Evidence Assistant API (138 lines)
- `POST /api/evidence/search`: Find evidence for a standard
  - Parameters: standard_id, institution_id, query (optional), context
  - Returns: results, standard info, query used
- `POST /api/evidence/suggestions`: Generate follow-up prompts
  - Parameters: conversation_history, context
  - Returns: list of 3-5 suggested questions
- Error handling: 400 (missing params), 404 (unknown standard), 500 (internal)
- Blueprint registered in app.py

### Evidence Finder UI
- **HTML Template (127 lines)**: Two-column layout
  - Left panel: Standard selector, custom query input, search button
  - Right panel: Results cards with relevance badges
  - Empty state, no results state, loading skeletons
  - Suggested prompts section (collapsible)

- **JavaScript Module (352 lines)**:
  - Standards loading from API
  - Evidence search with POST /api/evidence/search
  - Suggestion fetching with POST /api/evidence/suggestions
  - Evidence card rendering with badges and confidence bars
  - Enter key support, click handlers

- **CSS Styles (359 lines)**:
  - Dark theme matching existing design
  - Relevance badge colors: Required (green), Relevant (red/accent), Related (gray)
  - Confidence bar with gradient fill
  - Responsive layout (stacks on mobile)
  - Card hover effects

### Navigation Integration
- Added "Evidence Finder" link to AI Assistant section in sidebar
- Page route `/evidence-assistant` in app.py
- Search icon (magnifying glass) SVG

### i18n Support
- 16 strings added to en-US.json
- 16 strings added to es-PR.json
- Full bilingual support (English/Spanish)

## Deviations from Plan

None - plan executed exactly as written.

## Tests

**7 tests added, 100% pass rate:**

1. `test_evidence_result_to_dict`: Serialization correctness
2. `test_find_evidence_for_standard_returns_results`: End-to-end search with weighting
3. `test_find_evidence_applies_weighting`: 1.5x boost verification
4. `test_find_evidence_sorts_by_score`: Descending sort by weighted score
5. `test_generate_suggested_prompts_returns_list`: AI suggestion generation
6. `test_generate_suggested_prompts_handles_parse_error`: Graceful failure on invalid JSON
7. `test_is_required_evidence_type_matches`: Partial matching logic

All tests use mocks for SearchService, StandardExplainerService, and AIClient.

## Key Decisions

### 1. Weighting Factor: 1.5x for Required Types
**Why:** Balances strong prioritization with flexibility. Required documents rise to top but highly relevant non-required docs still rank well.

**Example:**
- Required doc with score 0.7 → weighted 1.05
- Non-required doc with score 0.9 → weighted 0.9
- Required doc ranks first ✓

### 2. Relevance Labels
**Labels:**
- "Required": Document type matches required evidence (green badge)
- "Relevant": Score > 0.7 (red/accent badge)
- "Related": Score ≤ 0.7 (gray badge)

**Why:** Clear visual hierarchy. Users immediately identify critical evidence.

### 3. Context-Aware Suggestions
**Context fields used:**
- `current_page`: Where user is in the app
- `active_standard_id`: Currently selected standard
- `recent_findings`: Last 3 compliance findings
- `conversation_history`: Last 3 messages

**AI Prompt:** Generates 3-5 specific, actionable follow-up questions under 80 characters each.

**Graceful failure:** Returns empty list on parse error (no crash).

## Usage Example

```python
# Service usage
from src.services.evidence_assistant_service import EvidenceAssistantService

service = EvidenceAssistantService(search_service, explainer_service, ai_client)

results = service.find_evidence_for_standard(
    institution_id="inst_001",
    standard_id="std_ACCSC_1.1",
    query=None,  # Auto-generated from standard
    context={"current_page": "compliance"}
)

for result in results:
    print(f"{result.relevance_label}: {result.doc_type} (confidence: {result.confidence})")
    # Output: Required: Admissions Policy (confidence: 0.85)
```

```bash
# API usage
curl -X POST http://localhost:5003/api/evidence/search \
  -H "Content-Type: application/json" \
  -d '{
    "standard_id": "std_ACCSC_1.1",
    "institution_id": "inst_001"
  }'

# Response:
{
  "results": [
    {
      "document_id": "doc_001",
      "doc_type": "Admissions Policy",
      "snippet": "Students are admitted based on...",
      "page": 5,
      "score": 1.05,
      "is_required_type": true,
      "relevance_label": "Required",
      "confidence": 0.7
    }
  ],
  "standard": {
    "id": "std_ACCSC_1.1",
    "title": "Admissions Policies",
    "code": "1.1"
  },
  "query": "Auto-generated from standard"
}
```

## Integration Points

**Consumes:**
- `StandardExplainerService.explain_standard()` for required evidence types
- `SearchService.search()` for semantic search
- `AIClient.generate()` for suggestion prompts

**Provides:**
- REST API endpoints for UI and external integrations
- Dedicated UI page accessible from sidebar
- Context-aware evidence prioritization

**Affects:**
- AI Assistant navigation section (new link added)

## Performance Notes

- Search limited to top 20 results before weighting
- Returns top 10 after weighting and sorting
- Suggestions limited to 5 prompts max
- All AI calls have graceful error handling (no crashes)

## Next Steps

No additional work required. Plan complete and verified.

## Self-Check: PASSED

**Files created verification:**
- ✓ src/services/evidence_assistant_service.py exists
- ✓ src/api/evidence_assistant.py exists
- ✓ templates/evidence_assistant.html exists (127 lines)
- ✓ static/js/evidence_assistant.js exists (352 lines)
- ✓ static/css/evidence_assistant.css exists (359 lines)
- ✓ tests/test_evidence_assistant_service.py exists

**Commits verification:**
- ✓ d41fe8c: EvidenceAssistantService with context-aware search
- ✓ 6d26e4c: Evidence Assistant API blueprint and UI

**Tests verification:**
- ✓ 7 tests added
- ✓ 7 tests passing
- ✓ 0 tests failing

All claims verified. Plan complete.
