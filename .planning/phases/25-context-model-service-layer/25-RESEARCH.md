# Phase 25: Context Model & Service Layer - Research

**Researched:** 2026-03-26
**Domain:** Context-sensitive search with scope filtering (SQLite FTS5 + ChromaDB)
**Confidence:** HIGH

## Summary

Phase 25 establishes the foundation for context-sensitive search by creating a SearchContext model that detects the user's current location in the application hierarchy and automatically scopes search queries. The implementation builds on existing infrastructure: `SiteVisitService` for unified search, `SearchService` for semantic search via ChromaDB, and FTS5 indexes for structured search.

The core deliverables are: (1) SearchContext dataclass with 6 scope levels (GLOBAL, INSTITUTION, PROGRAM, DOCUMENT, STANDARDS, COMPLIANCE), (2) FTS5 migrations adding scope columns to existing indexes, (3) ContextualSearchService that wraps existing search infrastructure with scope-aware filtering, and (4) merging/deduplication of semantic and structured results.

**Primary recommendation:** Extend existing `SiteVisitService` pattern with a new `ContextualSearchService` that accepts a `SearchContext` object and applies scope filtering to both ChromaDB metadata queries and FTS5 WHERE clauses. Do not replace existing global search - wrap and extend it.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTX-01 | User's search automatically scopes to their current page context | SearchContext.from_page() factory method parses page type and IDs from existing `#page-context` JSON; scope levels map to URL patterns |
| SRC-01 | Search across 8 data sources | Extend SiteVisitService sources from 6 to 8: add document_text (FTS5 on document chunks) and agent_sessions (FTS5 on session logs) |
| SRC-02 | Semantic search (ChromaDB) respects scope via metadata filtering | ChromaDB `where` clause already supports metadata filters; add institution_id, program_id, document_id to chunk metadata |
| SRC-03 | Structured search (FTS5) respects scope via WHERE clause filtering | FTS5 content tables have scope columns via foreign keys; join to parent tables for institution_id/program_id filtering |
| SRC-04 | Results merge semantic + structured, deduplicated by item ID | Extend existing `_deduplicate_results()` in SiteVisitService; use source_type + source_id as dedup key |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLite FTS5 | built-in | Full-text search with ranking | Already used for standards_fts, findings_fts; proven pattern |
| ChromaDB | 0.4.x | Vector store with metadata filtering | Already in use via `src/search/vector_store.py` |
| dataclasses | stdlib | SearchContext model | Project standard per CLAUDE.md |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| enum | stdlib | SearchScope enumeration | Define 6 scope levels |
| typing | stdlib | Type hints | All new code |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extending SiteVisitService | New standalone service | More duplication, but cleaner separation - RECOMMEND separate ContextualSearchService for clarity |
| FTS5 scope columns | JOIN filtering only | JOINs work but scope columns enable faster queries - ADD columns to FTS5 tables |
| ChromaDB where clause | Post-filter Python | Much slower for large collections - USE ChromaDB native filtering |

**Installation:**
No new dependencies required - all libraries already in use.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── core/
│   └── models.py          # Add SearchScope enum, SearchContext dataclass
├── services/
│   └── contextual_search_service.py  # NEW: ContextualSearchService
├── search/
│   ├── search_service.py  # Existing - add scope_metadata parameter
│   └── vector_store.py    # Existing - add scope-aware search method
└── db/
    └── migrations/
        └── 0033_contextual_search.sql  # FTS5 scope indexes
```

### Pattern 1: SearchContext Model
**What:** Dataclass that captures current user context for search scoping
**When to use:** Every contextual search request
**Example:**
```python
# Source: Project pattern from CLAUDE.md
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any

class SearchScope(str, Enum):
    """6 scope levels for contextual search."""
    GLOBAL = "global"           # All institutions
    INSTITUTION = "institution" # Single institution, all content
    PROGRAM = "program"         # Single program within institution
    DOCUMENT = "document"       # Single document context
    STANDARDS = "standards"     # Standards library (accreditor-scoped)
    COMPLIANCE = "compliance"   # Compliance findings/audits

@dataclass
class SearchContext:
    """Captures user's current location for search scoping."""
    scope: SearchScope
    institution_id: Optional[str] = None
    program_id: Optional[str] = None
    document_id: Optional[str] = None
    accreditor_id: Optional[str] = None

    @classmethod
    def from_page(cls, page_type: str, context: Dict[str, Any]) -> "SearchContext":
        """Factory method to create context from page type and context dict."""
        # Map page endpoints to scope levels
        if page_type in ("dashboard", "portfolios_list"):
            return cls(scope=SearchScope.GLOBAL)
        elif page_type.startswith("institution_"):
            inst_id = context.get("institution_id")
            if "program" in page_type:
                return cls(
                    scope=SearchScope.PROGRAM,
                    institution_id=inst_id,
                    program_id=context.get("program_id")
                )
            elif "compliance" in page_type or "audit" in page_type:
                return cls(
                    scope=SearchScope.COMPLIANCE,
                    institution_id=inst_id
                )
            elif "document" in page_type:
                return cls(
                    scope=SearchScope.DOCUMENT,
                    institution_id=inst_id,
                    document_id=context.get("document_id")
                )
            else:
                return cls(scope=SearchScope.INSTITUTION, institution_id=inst_id)
        elif page_type == "standards":
            return cls(
                scope=SearchScope.STANDARDS,
                accreditor_id=context.get("accreditor_id")
            )
        else:
            return cls(scope=SearchScope.GLOBAL)

    def to_chromadb_where(self) -> Optional[Dict[str, Any]]:
        """Convert context to ChromaDB where clause."""
        if self.scope == SearchScope.GLOBAL:
            return None

        where = {}
        if self.institution_id:
            where["institution_id"] = self.institution_id
        if self.program_id:
            where["program_id"] = self.program_id
        if self.document_id:
            where["document_id"] = self.document_id

        return where if where else None

    def to_sql_conditions(self) -> tuple[str, list]:
        """Convert context to SQL WHERE clause and params."""
        conditions = []
        params = []

        if self.scope == SearchScope.GLOBAL:
            return "", []

        if self.institution_id:
            conditions.append("institution_id = ?")
            params.append(self.institution_id)
        if self.program_id:
            conditions.append("program_id = ?")
            params.append(self.program_id)
        if self.document_id:
            conditions.append("document_id = ?")
            params.append(self.document_id)
        if self.accreditor_id:
            conditions.append("accreditor_id = ?")
            params.append(self.accreditor_id)

        sql = " AND ".join(conditions)
        return sql, params
```

### Pattern 2: ContextualSearchService
**What:** Service that wraps existing search infrastructure with context awareness
**When to use:** All contextual search requests from API
**Example:**
```python
# Source: Project pattern extending SiteVisitService
from src.services.site_visit_service import SiteVisitService, SearchResponse, SiteVisitResult
from src.search.search_service import get_search_service

class ContextualSearchService:
    """Orchestrates context-aware search across all sources."""

    def __init__(self, context: SearchContext, workspace_manager=None):
        self.context = context
        self.workspace_manager = workspace_manager

        # Use existing services where scope permits
        if context.institution_id:
            self.search_service = get_search_service(context.institution_id)
            self.site_visit_service = SiteVisitService(
                context.institution_id, workspace_manager
            )

    def search(self, query: str, filters=None, limit=20) -> SearchResponse:
        """Execute scoped search across all sources."""
        results = []

        # Semantic search (ChromaDB) with scope
        if self.context.institution_id:
            semantic_results = self._search_semantic(query)
            results.extend(semantic_results)

        # Structured search (FTS5) with scope
        structured_results = self._search_structured(query)
        results.extend(structured_results)

        # Merge and deduplicate
        results = self._deduplicate(results)

        # Sort by score
        results.sort(key=lambda r: -r.score)

        return SearchResponse(
            results=results[:limit],
            total=len(results),
            query_time_ms=0,  # Calculate actual
            sources_searched=self._get_sources_for_scope()
        )

    def _search_semantic(self, query: str) -> list[SiteVisitResult]:
        """Search ChromaDB with scope filtering."""
        where = self.context.to_chromadb_where()
        # Use existing search_service with where clause
        ...

    def _search_structured(self, query: str) -> list[SiteVisitResult]:
        """Search FTS5 indexes with scope filtering."""
        sql_where, params = self.context.to_sql_conditions()
        # Execute FTS5 queries with scope conditions
        ...

    def _deduplicate(self, results: list) -> list:
        """Remove duplicates by source_type + source_id."""
        seen = set()
        unique = []
        for r in results:
            key = (r.source_type, r.source_id)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
```

### Pattern 3: FTS5 Scope Indexing
**What:** Add institution_id and program_id columns to FTS5 indexes
**When to use:** Migration 0033
**Example:**
```sql
-- Add scope-aware document text FTS5
CREATE VIRTUAL TABLE IF NOT EXISTS document_text_fts USING fts5(
    content,
    document_id UNINDEXED,
    institution_id UNINDEXED,
    program_id UNINDEXED,
    content='document_chunks',
    content_rowid='rowid'
);

-- Query with scope filtering
SELECT d.id, d.title, dt.content
FROM documents d
JOIN document_text_fts dt ON d.id = dt.document_id
WHERE document_text_fts MATCH ?
  AND dt.institution_id = ?
LIMIT 20;
```

### Anti-Patterns to Avoid
- **Post-filtering in Python:** Don't fetch all results then filter by scope - use database-level filtering
- **Separate search services per scope:** Don't create 6 different services - use one service with context parameter
- **Modifying existing SiteVisitService:** Don't change working code - extend with new ContextualSearchService
- **Ignoring existing FTS5 indexes:** Don't rebuild from scratch - add scope columns to existing tables

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Full-text search | Custom tokenizer | SQLite FTS5 | Built-in, proven, fast |
| Vector similarity | Manual cosine calc | ChromaDB query | Optimized C++ backend |
| Result deduplication | Complex hash logic | Simple set with (type, id) key | Already proven in SiteVisitService |
| Scope detection | Manual URL parsing | from_page() factory with page_type | Centralizes logic |

**Key insight:** The project already has working search infrastructure. Phase 25 adds a thin coordination layer, not a replacement.

## Common Pitfalls

### Pitfall 1: ChromaDB Metadata Not Populated
**What goes wrong:** Semantic search returns results outside scope because chunks lack metadata
**Why it happens:** Existing chunks in ChromaDB may not have institution_id/program_id metadata
**How to avoid:** Migration must backfill metadata on existing chunks OR accept that only new chunks are scope-aware
**Warning signs:** Scoped searches return unexpected results

### Pitfall 2: FTS5 Content Table Mismatch
**What goes wrong:** FTS5 triggers fail because content table structure changed
**Why it happens:** FTS5 content= tables must match exactly
**How to avoid:** Create new FTS5 tables with scope columns rather than altering existing; OR use external content tables
**Warning signs:** INSERT/UPDATE triggers error on content sync

### Pitfall 3: JOIN Performance on Large Tables
**What goes wrong:** Scoped FTS5 queries become slow
**Why it happens:** FTS5 MATCH + JOIN + WHERE can be expensive without indexes
**How to avoid:** Add indexes on scope columns; use UNINDEXED columns in FTS5 for filtering
**Warning signs:** Query times > 100ms

### Pitfall 4: Deduplication Key Collisions
**What goes wrong:** Different results get deduplicated as same item
**Why it happens:** Using only source_id without source_type
**How to avoid:** Always use (source_type, source_id) tuple as dedup key
**Warning signs:** Missing expected results

## Code Examples

### SearchContext Factory Usage
```python
# Source: Pattern from base.html #page-context JSON
# In API endpoint:
@contextual_search_bp.route("/api/search/contextual", methods=["POST"])
def contextual_search():
    data = request.get_json()

    # Create context from request
    context = SearchContext.from_page(
        page_type=data.get("page_type", "dashboard"),
        context={
            "institution_id": data.get("institution_id"),
            "program_id": data.get("program_id"),
            "document_id": data.get("document_id"),
            "accreditor_id": data.get("accreditor_id")
        }
    )

    service = ContextualSearchService(context, _workspace_manager)
    response = service.search(data["query"], data.get("filters"), data.get("limit", 20))

    return jsonify(response.to_dict())
```

### ChromaDB Scoped Query
```python
# Source: Extend existing vector_store.py pattern
def search_with_scope(
    self,
    query_embedding: List[float],
    n_results: int = 10,
    scope_where: Optional[Dict] = None,
    filter_doc_type: Optional[str] = None,
) -> List[SearchResult]:
    """Search with scope filtering."""
    where = {}

    # Add scope filters
    if scope_where:
        where.update(scope_where)

    # Add type filter
    if filter_doc_type:
        where["doc_type"] = filter_doc_type

    results = self.collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where if where else None,
        include=["documents", "metadatas", "distances"],
    )

    # ... process results
```

### FTS5 Scoped Query Pattern
```python
# Source: Extend existing SiteVisitService pattern
def _search_documents_scoped(
    self,
    query: str,
    context: SearchContext,
) -> List[SiteVisitResult]:
    """Search documents with scope filtering."""
    conn = get_conn()

    sql_where, params = context.to_sql_conditions()
    where_clause = f"AND {sql_where}" if sql_where else ""

    cursor = conn.execute(
        f"""
        SELECT d.id, d.title, dc.content, dc.page_start
        FROM documents d
        JOIN document_chunks dc ON d.id = dc.document_id
        JOIN document_text_fts fts ON dc.rowid = fts.rowid
        WHERE document_text_fts MATCH ?
          {where_clause}
        ORDER BY rank
        LIMIT 30
        """,
        (query, *params),
    )

    # ... process results
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global search only | Context-aware search | Phase 25 | Users get relevant results faster |
| Post-filter results | Database-level filtering | Phase 25 | Better performance at scale |
| Single search service | Layered services | Phase 25 | Cleaner separation of concerns |

**Deprecated/outdated:**
- Site Visit Mode (F2) remains for dedicated site visit use case, not deprecated
- Global search (Ctrl+K) becomes context-aware, not replaced

## Open Questions

1. **Backfill ChromaDB metadata?**
   - What we know: Existing chunks may lack institution_id/program_id in metadata
   - What's unclear: How many chunks exist? Cost to re-embed vs re-upsert metadata?
   - Recommendation: Add metadata on new chunks only; document that scoped semantic search works best with Phase 25+ uploads

2. **Agent sessions as searchable source?**
   - What we know: SRC-01 requires 8 sources including agent_sessions
   - What's unclear: What table stores agent session logs? Need to verify schema
   - Recommendation: Check for agent_sessions table in migrations; may need to add FTS5 index

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SQLite FTS5 | Structured search | Yes | Built-in | - |
| ChromaDB | Semantic search | Yes | In use | - |
| Python dataclasses | SearchContext | Yes | stdlib | - |

**Missing dependencies with no fallback:** None

**Missing dependencies with fallback:** None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini (if exists) or pyproject.toml |
| Quick run command | `pytest tests/test_contextual_search.py -x` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTX-01 | SearchContext.from_page() returns correct scope | unit | `pytest tests/test_search_context.py::test_from_page -x` | Wave 0 |
| SRC-01 | ContextualSearchService searches 8 sources | integration | `pytest tests/test_contextual_search.py::test_all_sources -x` | Wave 0 |
| SRC-02 | ChromaDB respects scope metadata | unit | `pytest tests/test_contextual_search.py::test_chromadb_scope -x` | Wave 0 |
| SRC-03 | FTS5 respects scope WHERE clause | unit | `pytest tests/test_contextual_search.py::test_fts5_scope -x` | Wave 0 |
| SRC-04 | Results deduplicated by item ID | unit | `pytest tests/test_contextual_search.py::test_deduplication -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_contextual_search.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_search_context.py` - covers CTX-01
- [ ] `tests/test_contextual_search.py` - covers SRC-01, SRC-02, SRC-03, SRC-04

## Sources

### Primary (HIGH confidence)
- `src/services/site_visit_service.py` - existing unified search implementation
- `src/search/search_service.py` - existing semantic search service
- `src/search/vector_store.py` - ChromaDB integration with where clause filtering
- `src/db/migrations/0021_site_visit.sql` - existing FTS5 patterns for standards_fts, findings_fts
- `src/db/migrations/0002_docs.sql` - documents table schema with institution_id, program_id
- `templates/base.html` - existing `#page-context` JSON pattern for page type detection

### Secondary (MEDIUM confidence)
- SQLite FTS5 documentation - external content tables pattern
- ChromaDB documentation - metadata filtering with where clause

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use in project
- Architecture: HIGH - extends proven patterns from SiteVisitService
- Pitfalls: HIGH - based on direct code analysis of existing implementation

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (30 days - stable infrastructure)
