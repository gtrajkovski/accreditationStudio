"""Site Visit Mode - Unified Search Service.

Provides fast, unified search across all data sources for use during
accreditor site visits. When auditors ask questions, staff need instant
answers with document + page citations.

Search sources:
- Documents (semantic search via ChromaDB)
- Standards (SQL FTS)
- Findings (SQL FTS + evidence refs)
- Faculty (SQL LIKE)
- Truth Index (JSON traversal)
- Knowledge Graph (SQL)
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)
from hashlib import md5

from src.db.connection import get_conn
from src.search.search_service import get_search_service
from src.core.workspace import WorkspaceManager
from src.core.models import generate_id


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Citation:
    """Citation for a search result - tracks source location."""
    document: str
    page: Optional[int] = None
    section: Optional[str] = None
    standard_code: Optional[str] = None
    version: Optional[str] = None
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SiteVisitResult:
    """A single search result with citation."""
    id: str
    source_type: str  # document, standard, finding, faculty, truth_index, knowledge_graph
    source_id: str
    title: str
    snippet: str
    citation: Citation
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "snippet": self.snippet,
            "citation": self.citation.to_dict(),
            "score": round(self.score, 3),
            "metadata": self.metadata,
        }


@dataclass
class SearchResponse:
    """Complete search response."""
    results: List[SiteVisitResult]
    total: int
    query_time_ms: int
    sources_searched: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "total": self.total,
            "query_time_ms": self.query_time_ms,
            "sources_searched": self.sources_searched,
        }


# =============================================================================
# Source Weights for Ranking
# =============================================================================

SOURCE_WEIGHTS = {
    "document": 1.0,
    "finding": 0.95,
    "standard": 0.90,
    "truth_index": 0.85,
    "faculty": 0.80,
    "knowledge_graph": 0.75,
}

ALL_SOURCES = ["documents", "standards", "findings", "faculty", "truth_index", "knowledge_graph"]


# =============================================================================
# Site Visit Service
# =============================================================================

class SiteVisitService:
    """Orchestrates unified search across all data sources."""

    def __init__(
        self,
        institution_id: str,
        workspace_manager: Optional[WorkspaceManager] = None,
    ):
        """Initialize the service.

        Args:
            institution_id: Institution ID.
            workspace_manager: Optional workspace manager for truth index access.
        """
        self.institution_id = institution_id
        self.workspace_manager = workspace_manager
        self.search_service = get_search_service(institution_id)

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """Execute parallel search across all sources.

        Args:
            query: Search query text.
            filters: Optional filters (sources, doc_types, date_range, min_confidence).
            limit: Maximum results to return.
            offset: Offset for pagination.

        Returns:
            SearchResponse with ranked, deduplicated results.
        """
        start_time = time.time()
        filters = filters or {}
        sources = filters.get("sources", ALL_SOURCES)
        results: List[SiteVisitResult] = []

        # Search each source
        if "documents" in sources:
            results.extend(self._search_documents(query, filters))

        if "standards" in sources:
            results.extend(self._search_standards(query, filters))

        if "findings" in sources:
            results.extend(self._search_findings(query, filters))

        if "faculty" in sources:
            results.extend(self._search_faculty(query, filters))

        if "truth_index" in sources and self.workspace_manager:
            results.extend(self._search_truth_index(query))

        if "knowledge_graph" in sources:
            results.extend(self._search_knowledge_graph(query, filters))

        # Calculate final scores
        for result in results:
            result.score = self._calculate_final_score(result, query)

        # Deduplicate
        results = self._deduplicate_results(results)

        # Sort by score descending
        results.sort(key=lambda r: -r.score)

        # Get total before pagination
        total = len(results)

        # Apply pagination
        results = results[offset:offset + limit]

        # Calculate query time
        query_time_ms = int((time.time() - start_time) * 1000)

        # Save search to history
        self._save_search_history(query, filters, total, query_time_ms, sources)

        return SearchResponse(
            results=results,
            total=total,
            query_time_ms=query_time_ms,
            sources_searched=sources,
        )

    def get_fact(self, fact_path: str) -> Optional[Dict[str, Any]]:
        """Get a specific fact from the truth index.

        Args:
            fact_path: Dot-notation path to fact (e.g., programs.prog_001.total_cost).

        Returns:
            Fact data with value and citations if found.
        """
        if not self.workspace_manager:
            return None

        truth_index = self.workspace_manager.get_truth_index(self.institution_id)
        if not truth_index:
            return None

        # Navigate the path
        keys = fact_path.split(".")
        current = truth_index
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return {
            "path": fact_path,
            "value": current,
            "source": "truth_index",
            "institution_id": self.institution_id,
        }

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent search history.

        Args:
            limit: Maximum entries to return.

        Returns:
            List of recent searches.
        """
        conn = get_conn()
        cursor = conn.execute(
            """
            SELECT id, query, filters_json, result_count, query_time_ms, created_at
            FROM site_visit_searches
            WHERE institution_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (self.institution_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Source-specific search methods
    # =========================================================================

    def _search_documents(
        self,
        query: str,
        filters: Dict[str, Any],
    ) -> List[SiteVisitResult]:
        """Semantic search on documents using ChromaDB."""
        results = []
        doc_type = filters.get("doc_types", [None])[0] if filters.get("doc_types") else None

        try:
            search_results = self.search_service.search(
                query=query,
                n_results=30,
                doc_type=doc_type,
            )

            # Get document titles from database
            doc_titles = self._get_document_titles([r.chunk.document_id for r in search_results])

            for sr in search_results:
                doc_id = sr.chunk.document_id
                title = doc_titles.get(doc_id, "Unknown Document")

                results.append(SiteVisitResult(
                    id=generate_id("svr"),
                    source_type="document",
                    source_id=doc_id,
                    title=title,
                    snippet=sr.chunk.text_anonymized or sr.chunk.text_original or "",
                    citation=Citation(
                        document=title,
                        page=sr.chunk.page_number,
                        section=sr.chunk.section_header,
                    ),
                    score=sr.score,
                    metadata={
                        "doc_type": sr.chunk.metadata.get("doc_type", ""),
                        "chunk_index": sr.chunk.chunk_index,
                    },
                ))
        except Exception as e:
            logger.debug("ChromaDB search unavailable: %s", e)

        return results

    def _search_standards(
        self,
        query: str,
        filters: Dict[str, Any],
    ) -> List[SiteVisitResult]:
        """Full-text search on standards using FTS5."""
        results = []
        conn = get_conn()

        try:
            # Try FTS5 first
            cursor = conn.execute(
                """
                SELECT s.id, s.standard_code, s.title, s.body_text, a.code as accreditor_code
                FROM standards s
                JOIN standards_fts fts ON s.rowid = fts.rowid
                LEFT JOIN accreditors a ON s.accreditor_id = a.id
                WHERE standards_fts MATCH ?
                LIMIT 20
                """,
                (query,),
            )
        except Exception as e:
            logger.debug("FTS5 search failed, using LIKE fallback: %s", e)
            cursor = conn.execute(
                """
                SELECT s.id, s.standard_code, s.title, s.body_text, a.code as accreditor_code
                FROM standards s
                LEFT JOIN accreditors a ON s.accreditor_id = a.id
                WHERE s.title LIKE ? OR s.body_text LIKE ? OR s.standard_code LIKE ?
                LIMIT 20
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%"),
            )

        for row in cursor.fetchall():
            body_text = row["body_text"] or ""
            snippet = self._extract_snippet(body_text, query, 200)

            results.append(SiteVisitResult(
                id=generate_id("svr"),
                source_type="standard",
                source_id=row["id"],
                title=f"{row['standard_code']} - {row['title']}",
                snippet=snippet,
                citation=Citation(
                    document="Accreditation Standards",
                    standard_code=row["standard_code"],
                ),
                score=0.7,  # Base score for text matches
                metadata={
                    "accreditor": row["accreditor_code"] or "",
                },
            ))

        return results

    def _search_findings(
        self,
        query: str,
        filters: Dict[str, Any],
    ) -> List[SiteVisitResult]:
        """Search audit findings with evidence refs."""
        results = []
        conn = get_conn()

        try:
            # Try FTS5 first
            cursor = conn.execute(
                """
                SELECT f.id, f.summary, f.recommendation, f.status, f.severity,
                       d.title as doc_title, ci.text as checklist_text
                FROM audit_findings f
                JOIN findings_fts fts ON f.rowid = fts.rowid
                JOIN audit_runs ar ON f.audit_run_id = ar.id
                LEFT JOIN documents d ON f.document_id = d.id
                LEFT JOIN checklist_items ci ON f.checklist_item_id = ci.id
                WHERE ar.institution_id = ? AND findings_fts MATCH ?
                LIMIT 20
                """,
                (self.institution_id, query),
            )
        except Exception as e:
            logger.debug("Findings FTS search failed, using LIKE fallback: %s", e)
            cursor = conn.execute(
                """
                SELECT f.id, f.summary, f.recommendation, f.status, f.severity,
                       d.title as doc_title, ci.text as checklist_text
                FROM audit_findings f
                JOIN audit_runs ar ON f.audit_run_id = ar.id
                LEFT JOIN documents d ON f.document_id = d.id
                LEFT JOIN checklist_items ci ON f.checklist_item_id = ci.id
                WHERE ar.institution_id = ?
                  AND (f.summary LIKE ? OR f.recommendation LIKE ?)
                LIMIT 20
                """,
                (self.institution_id, f"%{query}%", f"%{query}%"),
            )

        for row in cursor.fetchall():
            snippet = row["summary"] or row["recommendation"] or ""

            results.append(SiteVisitResult(
                id=generate_id("svr"),
                source_type="finding",
                source_id=row["id"],
                title=f"Finding: {row['doc_title'] or 'Document'}",
                snippet=snippet[:300],
                citation=Citation(
                    document=row["doc_title"] or "Audit Finding",
                    section=row["checklist_text"][:50] if row["checklist_text"] else None,
                ),
                score=0.75,
                metadata={
                    "status": row["status"],
                    "severity": row["severity"],
                },
            ))

        return results

    def _search_faculty(
        self,
        query: str,
        filters: Dict[str, Any],
    ) -> List[SiteVisitResult]:
        """Search faculty members by name, credentials, or department."""
        results = []
        conn = get_conn()

        cursor = conn.execute(
            """
            SELECT fm.id, fm.first_name, fm.last_name, fm.title, fm.department,
                   fm.employment_type, fm.compliance_status,
                   GROUP_CONCAT(fc.title || ' in ' || fc.field_of_study, '; ') as credentials
            FROM faculty_members fm
            LEFT JOIN faculty_credentials fc ON fm.id = fc.faculty_id
            WHERE fm.institution_id = ?
              AND (fm.first_name LIKE ? OR fm.last_name LIKE ?
                   OR fm.title LIKE ? OR fm.department LIKE ?
                   OR fc.title LIKE ? OR fc.field_of_study LIKE ?)
            GROUP BY fm.id
            LIMIT 15
            """,
            (self.institution_id, f"%{query}%", f"%{query}%", f"%{query}%",
             f"%{query}%", f"%{query}%", f"%{query}%"),
        )

        for row in cursor.fetchall():
            full_name = f"{row['first_name']} {row['last_name']}"
            snippet = f"{row['title'] or ''} - {row['department'] or ''}"
            if row["credentials"]:
                snippet += f"\nCredentials: {row['credentials']}"

            results.append(SiteVisitResult(
                id=generate_id("svr"),
                source_type="faculty",
                source_id=row["id"],
                title=full_name,
                snippet=snippet[:300],
                citation=Citation(
                    document="Faculty Records",
                    section=row["department"],
                ),
                score=0.7,
                metadata={
                    "employment_type": row["employment_type"],
                    "compliance_status": row["compliance_status"],
                },
            ))

        return results

    def _search_truth_index(self, query: str) -> List[SiteVisitResult]:
        """Search the truth index JSON for matching facts."""
        results = []

        if not self.workspace_manager:
            return results

        truth_index = self.workspace_manager.get_truth_index(self.institution_id)
        if not truth_index:
            return results

        query_lower = query.lower()

        def search_dict(obj: Any, path: str = "") -> None:
            """Recursively search the truth index."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    # Skip metadata fields
                    if key in ("updated_at", "created_at", "version"):
                        continue

                    # Check if key matches
                    if query_lower in key.lower():
                        results.append(SiteVisitResult(
                            id=generate_id("svr"),
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
                    id=generate_id("svr"),
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
        return results[:10]  # Limit truth index results

    def _search_knowledge_graph(
        self,
        query: str,
        filters: Dict[str, Any],
    ) -> List[SiteVisitResult]:
        """Search knowledge graph entities."""
        results = []
        conn = get_conn()

        try:
            cursor = conn.execute(
                """
                SELECT id, entity_type, entity_id, display_name, attributes
                FROM kg_entities
                WHERE institution_id = ?
                  AND (display_name LIKE ? OR attributes LIKE ?)
                LIMIT 15
                """,
                (self.institution_id, f"%{query}%", f"%{query}%"),
            )

            for row in cursor.fetchall():
                attrs = json.loads(row["attributes"]) if row["attributes"] else {}

                results.append(SiteVisitResult(
                    id=generate_id("svr"),
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
        except Exception as e:
            logger.debug("Knowledge graph search unavailable: %s", e)

        return results

    # =========================================================================
    # Helper methods
    # =========================================================================

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

    def _extract_snippet(self, text: str, query: str, max_len: int = 200) -> str:
        """Extract a snippet containing the query."""
        if not text:
            return ""

        query_lower = query.lower()
        text_lower = text.lower()
        pos = text_lower.find(query_lower)

        if pos == -1:
            return text[:max_len] + ("..." if len(text) > max_len else "")

        # Center the snippet around the match
        start = max(0, pos - max_len // 2)
        end = min(len(text), pos + len(query) + max_len // 2)

        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    def _calculate_final_score(self, result: SiteVisitResult, query: str) -> float:
        """Calculate weighted final score for ranking."""
        base_score = result.score

        # Source weight
        source_weight = SOURCE_WEIGHTS.get(result.source_type, 0.5)

        # Title match boost
        title_boost = 0.15 if query.lower() in result.title.lower() else 0.0

        # Recency boost (if metadata has last_updated)
        recency_boost = 0.0
        if "last_updated" in result.metadata:
            try:
                updated = datetime.fromisoformat(result.metadata["last_updated"].rstrip("Z"))
                days_old = (datetime.now(timezone.utc) - updated).days
                recency_boost = max(0, 0.1 - (days_old / 365) * 0.1)
            except Exception as e:
                logger.debug("Could not parse recency date: %s", e)

        return min(1.0, base_score * source_weight + recency_boost + title_boost)

    def _deduplicate_results(
        self,
        results: List[SiteVisitResult],
    ) -> List[SiteVisitResult]:
        """Remove duplicate results, keeping highest-scored."""
        seen_hashes: Set[str] = set()
        seen_citations: Set[tuple] = set()
        unique: List[SiteVisitResult] = []

        # Sort by score first so we keep highest
        results.sort(key=lambda r: -r.score)

        for r in results:
            # Hash first 200 chars of snippet
            snippet_hash = md5(r.snippet[:200].encode()).hexdigest()

            # Create citation key
            citation_key = (
                r.citation.document,
                r.citation.page,
                r.citation.section,
            )

            if snippet_hash in seen_hashes:
                continue
            if citation_key in seen_citations and r.citation.page:
                continue

            seen_hashes.add(snippet_hash)
            if r.citation.page:
                seen_citations.add(citation_key)

            unique.append(r)

        return unique

    def _save_search_history(
        self,
        query: str,
        filters: Dict[str, Any],
        result_count: int,
        query_time_ms: int,
        sources: List[str],
    ) -> None:
        """Save search to history table."""
        try:
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO site_visit_searches
                (id, institution_id, query, filters_json, sources_searched, result_count, query_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("svs"),
                    self.institution_id,
                    query,
                    json.dumps(filters),
                    json.dumps(sources),
                    result_count,
                    query_time_ms,
                ),
            )
            conn.commit()
        except Exception as e:
            logger.debug("Failed to save search history: %s", e)


# =============================================================================
# Factory
# =============================================================================

_services: Dict[str, SiteVisitService] = {}


def get_site_visit_service(
    institution_id: str,
    workspace_manager: Optional[WorkspaceManager] = None,
) -> SiteVisitService:
    """Get or create a site visit service for an institution.

    Args:
        institution_id: Institution ID.
        workspace_manager: Optional workspace manager for truth index.

    Returns:
        SiteVisitService instance.
    """
    key = institution_id
    if key not in _services:
        _services[key] = SiteVisitService(institution_id, workspace_manager)
    return _services[key]
