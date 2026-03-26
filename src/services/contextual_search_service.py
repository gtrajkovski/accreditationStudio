"""Contextual Search Service - Scope-aware search across 8 data sources.

Provides context-sensitive search that automatically scopes queries based on
the user's current location in the application hierarchy.

Search sources (8 total per SRC-01):
1. documents - Semantic search via ChromaDB
2. document_text - FTS5 on document_text_fts
3. standards - FTS5 on standards_fts
4. findings - FTS5 on findings_fts
5. evidence - FTS5 on evidence_fts
6. knowledge_graph - SQL LIKE on kg_entities
7. truth_index - JSON traversal
8. agent_sessions - SQL LIKE on human_checkpoints
"""

import json
import time
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set

from src.db.connection import get_conn
from src.core.models import SearchContext, SearchScope, generate_id
from src.core.workspace import WorkspaceManager
from src.search.search_service import get_search_service
from src.services.site_visit_service import (
    SiteVisitResult,
    SearchResponse,
    Citation,
    SOURCE_WEIGHTS,
)


# All 8 sources for SRC-01
ALL_SOURCES = [
    "documents",
    "document_text",
    "standards",
    "findings",
    "evidence",
    "knowledge_graph",
    "truth_index",
    "agent_sessions",
]


class ContextualSearchService:
    """Orchestrates context-aware search across all 8 data sources."""

    def __init__(
        self,
        context: SearchContext,
        workspace_manager: Optional[WorkspaceManager] = None,
    ):
        """Initialize the service.

        Args:
            context: SearchContext with scope and IDs for filtering.
            workspace_manager: Optional workspace manager for truth index access.
        """
        self.context = context
        self.workspace_manager = workspace_manager
        self._search_service = None

        # Initialize search service if we have institution context
        if context.institution_id:
            self._search_service = get_search_service(context.institution_id)

    def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """Execute scoped search across all sources.

        Args:
            query: Search query text.
            sources: Optional list of sources to search (defaults to all 8).
            limit: Maximum results to return.
            offset: Offset for pagination.

        Returns:
            SearchResponse with ranked, deduplicated results.
        """
        start_time = time.time()
        sources = sources or ALL_SOURCES
        results: List[SiteVisitResult] = []

        # Search each source
        if "documents" in sources and self._search_service:
            results.extend(self._search_semantic(query))

        if "document_text" in sources:
            results.extend(self._search_document_text(query))

        if "standards" in sources:
            results.extend(self._search_standards(query))

        if "findings" in sources:
            results.extend(self._search_findings(query))

        if "evidence" in sources:
            results.extend(self._search_evidence(query))

        if "knowledge_graph" in sources:
            results.extend(self._search_knowledge_graph(query))

        if "truth_index" in sources and self.workspace_manager and self.context.institution_id:
            results.extend(self._search_truth_index(query))

        if "agent_sessions" in sources:
            results.extend(self._search_agent_sessions(query))

        # Calculate final scores
        for result in results:
            result.score = self._calculate_score(result, query)

        # Deduplicate by (source_type, source_id) - SRC-04
        results = self._deduplicate(results)

        # Sort by score descending
        results.sort(key=lambda r: -r.score)

        # Get total before pagination
        total = len(results)

        # Apply pagination
        results = results[offset:offset + limit]

        query_time_ms = int((time.time() - start_time) * 1000)

        return SearchResponse(
            results=results,
            total=total,
            query_time_ms=query_time_ms,
            sources_searched=sources,
        )

    def _search_semantic(self, query: str) -> List[SiteVisitResult]:
        """Semantic search on documents using ChromaDB with scope filtering (SRC-02)."""
        results = []
        if not self._search_service:
            return results

        try:
            # Get scope filter from context
            scope_where = self.context.to_chromadb_where()

            # Use the vector store's scoped search
            search_results = self._search_service.vector_store.search_with_scope(
                query_embedding=self._search_service.embedding_service.embed_text(query),
                n_results=30,
                scope_where=scope_where,
            )

            # Get document titles
            doc_ids = [r.chunk.document_id for r in search_results]
            doc_titles = self._get_document_titles(doc_ids)

            for sr in search_results:
                doc_id = sr.chunk.document_id
                title = doc_titles.get(doc_id, "Unknown Document")

                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="document",
                    source_id=doc_id,
                    title=title,
                    snippet=sr.chunk.text_anonymized or "",
                    citation=Citation(
                        document=title,
                        page=sr.chunk.page_number,
                        section=sr.chunk.section_header,
                    ),
                    score=sr.score,
                    metadata={
                        "chunk_index": sr.chunk.chunk_index,
                        "search_type": "semantic",
                    },
                ))
        except Exception:
            pass

        return results

    def _search_document_text(self, query: str) -> List[SiteVisitResult]:
        """FTS5 search on document_text_fts with scope filtering (SRC-03)."""
        results = []
        conn = get_conn()

        sql_where, params = self.context.to_sql_conditions()
        where_clause = f"AND {sql_where}" if sql_where else ""

        try:
            cursor = conn.execute(
                f"""
                SELECT fts.rowid, fts.content, fts.section_header, fts.document_id,
                       d.title, d.institution_id, d.program_id
                FROM document_text_fts fts
                JOIN documents d ON fts.document_id = d.id
                WHERE document_text_fts MATCH ?
                  {where_clause}
                ORDER BY rank
                LIMIT 20
                """,
                (query, *params),
            )

            for row in cursor.fetchall():
                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="document_text",
                    source_id=row["document_id"],
                    title=row["title"] or "Document",
                    snippet=row["content"][:300] if row["content"] else "",
                    citation=Citation(
                        document=row["title"] or "Document",
                        section=row["section_header"],
                    ),
                    score=0.7,
                    metadata={"search_type": "fts5"},
                ))
        except Exception:
            pass

        return results

    def _search_standards(self, query: str) -> List[SiteVisitResult]:
        """FTS5 search on standards_fts with optional accreditor scope."""
        results = []
        conn = get_conn()

        # Standards use accreditor_id scope
        where_clause = ""
        params = [query]
        if self.context.scope == SearchScope.STANDARDS and self.context.accreditor_id:
            where_clause = "AND s.accreditor_id = ?"
            params.append(self.context.accreditor_id)

        try:
            cursor = conn.execute(
                f"""
                SELECT s.id, s.standard_code, s.title, s.body_text, a.code as accreditor_code
                FROM standards s
                JOIN standards_fts fts ON s.rowid = fts.rowid
                LEFT JOIN accreditors a ON s.accreditor_id = a.id
                WHERE standards_fts MATCH ?
                  {where_clause}
                LIMIT 20
                """,
                params,
            )

            for row in cursor.fetchall():
                snippet = self._extract_snippet(row["body_text"] or "", query)
                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="standard",
                    source_id=row["id"],
                    title=f"{row['standard_code']} - {row['title']}",
                    snippet=snippet,
                    citation=Citation(
                        document="Accreditation Standards",
                        standard_code=row["standard_code"],
                    ),
                    score=0.75,
                    metadata={"accreditor": row["accreditor_code"] or ""},
                ))
        except Exception:
            pass

        return results

    def _search_findings(self, query: str) -> List[SiteVisitResult]:
        """FTS5 search on findings_fts with scope filtering."""
        results = []
        conn = get_conn()

        sql_where, params = self.context.to_sql_conditions()
        # Findings scope via audit_runs.institution_id
        where_clause = f"AND ar.{sql_where.replace('institution_id', 'institution_id')}" if sql_where and "institution_id" in sql_where else ""
        filter_params = [p for p in params if p == self.context.institution_id] if self.context.institution_id else []

        try:
            cursor = conn.execute(
                f"""
                SELECT f.id, f.summary, f.recommendation, f.status, f.severity,
                       d.title as doc_title
                FROM audit_findings f
                JOIN findings_fts fts ON f.rowid = fts.rowid
                JOIN audit_runs ar ON f.audit_run_id = ar.id
                LEFT JOIN documents d ON f.document_id = d.id
                WHERE findings_fts MATCH ?
                  {"AND ar.institution_id = ?" if self.context.institution_id else ""}
                LIMIT 20
                """,
                (query, *filter_params),
            )

            for row in cursor.fetchall():
                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="finding",
                    source_id=row["id"],
                    title=f"Finding: {row['doc_title'] or 'Document'}",
                    snippet=row["summary"][:300] if row["summary"] else "",
                    citation=Citation(
                        document=row["doc_title"] or "Audit Finding",
                    ),
                    score=0.8,
                    metadata={
                        "status": row["status"],
                        "severity": row["severity"],
                    },
                ))
        except Exception:
            pass

        return results

    def _search_evidence(self, query: str) -> List[SiteVisitResult]:
        """FTS5 search on evidence_fts with scope filtering."""
        results = []
        conn = get_conn()

        where_clause = ""
        params = [query]
        if self.context.institution_id:
            where_clause = "AND fts.institution_id = ?"
            params.append(self.context.institution_id)

        try:
            cursor = conn.execute(
                f"""
                SELECT fts.rowid, fts.snippet_text, fts.document_id, fts.finding_id,
                       d.title as doc_title
                FROM evidence_fts fts
                LEFT JOIN documents d ON fts.document_id = d.id
                WHERE evidence_fts MATCH ?
                  {where_clause}
                LIMIT 20
                """,
                params,
            )

            for row in cursor.fetchall():
                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="evidence",
                    source_id=f"ev_{row['rowid']}",
                    title=f"Evidence: {row['doc_title'] or 'Document'}",
                    snippet=row["snippet_text"][:300] if row["snippet_text"] else "",
                    citation=Citation(
                        document=row["doc_title"] or "Evidence",
                    ),
                    score=0.75,
                    metadata={"finding_id": row["finding_id"]},
                ))
        except Exception:
            pass

        return results

    def _search_knowledge_graph(self, query: str) -> List[SiteVisitResult]:
        """Search knowledge graph entities with scope filtering."""
        results = []
        conn = get_conn()

        where_clause = ""
        params = [f"%{query}%", f"%{query}%"]
        if self.context.institution_id:
            where_clause = "AND institution_id = ?"
            params.append(self.context.institution_id)

        try:
            cursor = conn.execute(
                f"""
                SELECT id, entity_type, entity_id, display_name, attributes
                FROM kg_entities
                WHERE (display_name LIKE ? OR attributes LIKE ?)
                  {where_clause}
                LIMIT 15
                """,
                params,
            )

            for row in cursor.fetchall():
                attrs = json.loads(row["attributes"]) if row["attributes"] else {}
                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="knowledge_graph",
                    source_id=row["id"],
                    title=row["display_name"],
                    snippet=f"Type: {row['entity_type']}. {json.dumps(attrs)[:200]}",
                    citation=Citation(
                        document="Knowledge Graph",
                        section=row["entity_type"],
                    ),
                    score=0.6,
                    metadata={
                        "entity_type": row["entity_type"],
                        "entity_id": row["entity_id"],
                    },
                ))
        except Exception:
            pass

        return results

    def _search_truth_index(self, query: str) -> List[SiteVisitResult]:
        """Search truth index JSON for matching facts."""
        results = []

        if not self.workspace_manager or not self.context.institution_id:
            return results

        truth_index = self.workspace_manager.get_truth_index(self.context.institution_id)
        if not truth_index:
            return results

        query_lower = query.lower()

        def search_dict(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if key in ("updated_at", "created_at", "version"):
                        continue
                    if query_lower in key.lower():
                        results.append(SiteVisitResult(
                            id=generate_id("csr"),
                            source_type="truth_index",
                            source_id=new_path,
                            title=key,
                            snippet=f"{new_path}: {json.dumps(value)[:200]}",
                            citation=Citation(
                                document="Truth Index",
                                section=path or "root",
                            ),
                            score=0.65,
                            metadata={"path": new_path},
                        ))
                    search_dict(value, new_path)
            elif isinstance(obj, str) and query_lower in obj.lower():
                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="truth_index",
                    source_id=path,
                    title=path.split(".")[-1] if path else "value",
                    snippet=obj[:300],
                    citation=Citation(
                        document="Truth Index",
                        section=path,
                    ),
                    score=0.7,
                    metadata={"path": path},
                ))

        search_dict(truth_index)
        return results[:10]

    def _search_agent_sessions(self, query: str) -> List[SiteVisitResult]:
        """Search agent session checkpoints for relevant decisions."""
        results = []
        conn = get_conn()

        where_clause = ""
        params = [f"%{query}%", f"%{query}%"]
        if self.context.institution_id:
            where_clause = "AND institution_id = ?"
            params.append(self.context.institution_id)

        try:
            cursor = conn.execute(
                f"""
                SELECT id, checkpoint_type, reason, notes, status, created_at
                FROM human_checkpoints
                WHERE (reason LIKE ? OR notes LIKE ?)
                  {where_clause}
                ORDER BY created_at DESC
                LIMIT 15
                """,
                params,
            )

            for row in cursor.fetchall():
                results.append(SiteVisitResult(
                    id=generate_id("csr"),
                    source_type="agent_session",
                    source_id=row["id"],
                    title=f"Checkpoint: {row['checkpoint_type']}",
                    snippet=row["reason"] or row["notes"] or "",
                    citation=Citation(
                        document="Agent Sessions",
                        section=row["checkpoint_type"],
                    ),
                    score=0.55,
                    metadata={
                        "status": row["status"],
                        "created_at": row["created_at"],
                    },
                ))
        except Exception:
            pass

        return results

    def _deduplicate(self, results: List[SiteVisitResult]) -> List[SiteVisitResult]:
        """Remove duplicates by (source_type, source_id), keeping highest score (SRC-04)."""
        # Sort by score descending so we keep highest
        results.sort(key=lambda r: -r.score)

        seen: Set[tuple] = set()
        unique: List[SiteVisitResult] = []

        for r in results:
            key = (r.source_type, r.source_id)
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique

    def _calculate_score(self, result: SiteVisitResult, query: str) -> float:
        """Calculate weighted score for ranking."""
        base_score = result.score
        source_weight = SOURCE_WEIGHTS.get(result.source_type, 0.5)
        title_boost = 0.1 if query.lower() in result.title.lower() else 0.0
        return min(1.0, base_score * source_weight + title_boost)

    def _extract_snippet(self, text: str, query: str, max_len: int = 200) -> str:
        """Extract snippet containing query."""
        if not text:
            return ""
        pos = text.lower().find(query.lower())
        if pos == -1:
            return text[:max_len] + ("..." if len(text) > max_len else "")
        start = max(0, pos - max_len // 2)
        end = min(len(text), pos + len(query) + max_len // 2)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

    def _get_document_titles(self, doc_ids: List[str]) -> Dict[str, str]:
        """Get document titles by IDs."""
        if not doc_ids:
            return {}
        conn = get_conn()
        placeholders = ",".join("?" * len(doc_ids))
        cursor = conn.execute(
            f"SELECT id, title FROM documents WHERE id IN ({placeholders})",
            doc_ids,
        )
        return {row["id"]: row["title"] for row in cursor.fetchall()}


# Factory
_services: Dict[str, ContextualSearchService] = {}


def get_contextual_search_service(
    context: SearchContext,
    workspace_manager: Optional[WorkspaceManager] = None,
) -> ContextualSearchService:
    """Get or create a contextual search service for a context.

    Args:
        context: SearchContext with scope and IDs.
        workspace_manager: Optional workspace manager.

    Returns:
        ContextualSearchService instance.
    """
    # Key by scope + institution for caching
    key = f"{context.scope.value}_{context.institution_id or 'global'}"
    if key not in _services:
        _services[key] = ContextualSearchService(context, workspace_manager)
    return _services[key]
