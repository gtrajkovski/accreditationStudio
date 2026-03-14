"""Evidence Highlighting Service.

Provides document text retrieval and evidence data for the document viewer
with text highlighting capabilities.
"""

import json
import os
import re
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Tuple

from src.db.connection import get_conn


@dataclass
class PageContent:
    """Content for a single page."""
    page_number: int
    text: str
    section_header: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class EvidenceHighlight:
    """An evidence highlight with position and standard info."""
    id: str
    finding_id: str
    page: int
    snippet_text: str
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    status: str = "compliant"
    confidence: float = 1.0
    finding_summary: Optional[str] = None
    standards: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.standards is None:
            self.standards = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "page": self.page,
            "snippet_text": self.snippet_text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "status": self.status,
            "confidence": self.confidence,
            "finding_summary": self.finding_summary,
            "standards": self.standards,
        }


class EvidenceHighlightingService:
    """Service for document viewer with evidence highlighting."""

    def __init__(self, institution_id: str):
        """Initialize the service.

        Args:
            institution_id: Institution ID.
        """
        self.institution_id = institution_id
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_conn()
        return self._conn

    def get_document_text(self, document_id: str) -> Dict[str, Any]:
        """Get document text content organized by pages.

        Args:
            document_id: Document ID.

        Returns:
            Dict with pages array and metadata.
        """
        # Get document info
        cursor = self.conn.execute(
            """
            SELECT d.id, d.title, d.page_count, d.doc_type,
                   dp.extracted_text_path, dp.structured_json_path
            FROM documents d
            LEFT JOIN document_parses dp ON d.id = dp.document_id
            WHERE d.id = ? AND d.institution_id = ?
            ORDER BY dp.created_at DESC
            LIMIT 1
            """,
            (document_id, self.institution_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "Document not found", "pages": [], "total_pages": 0}

        doc = dict(row)
        pages: List[PageContent] = []

        # Try to load structured content first (has page breaks)
        if doc.get("structured_json_path") and os.path.exists(doc["structured_json_path"]):
            try:
                with open(doc["structured_json_path"], "r", encoding="utf-8") as f:
                    structure = json.load(f)
                    # Structure may have pages or sections
                    if "pages" in structure:
                        for i, page_data in enumerate(structure["pages"], 1):
                            pages.append(PageContent(
                                page_number=i,
                                text=page_data.get("text", ""),
                                section_header=page_data.get("section"),
                            ))
                    elif "sections" in structure:
                        # Sections-based structure
                        for i, section in enumerate(structure["sections"], 1):
                            pages.append(PageContent(
                                page_number=section.get("page", i),
                                text=section.get("text", ""),
                                section_header=section.get("header"),
                            ))
            except (json.JSONDecodeError, IOError):
                pass

        # Fall back to extracted text (single blob)
        if not pages and doc.get("extracted_text_path") and os.path.exists(doc["extracted_text_path"]):
            try:
                with open(doc["extracted_text_path"], "r", encoding="utf-8") as f:
                    full_text = f.read()
                    # Split by page markers if present
                    page_pattern = r'\n?(?:---\s*Page\s*\d+\s*---|\f)\n?'
                    page_texts = re.split(page_pattern, full_text)
                    for i, text in enumerate(page_texts, 1):
                        if text.strip():
                            pages.append(PageContent(page_number=i, text=text.strip()))
            except IOError:
                pass

        # If still no pages, create single page from whatever we have
        if not pages:
            # Try to get text from document record directly
            cursor = self.conn.execute(
                "SELECT extracted_text FROM documents WHERE id = ?",
                (document_id,),
            )
            text_row = cursor.fetchone()
            if text_row and text_row["extracted_text"]:
                pages.append(PageContent(page_number=1, text=text_row["extracted_text"]))
            else:
                pages.append(PageContent(page_number=1, text="[Document text not available]"))

        return {
            "document_id": document_id,
            "title": doc["title"],
            "doc_type": doc["doc_type"],
            "total_pages": len(pages) or doc.get("page_count", 1),
            "pages": [p.to_dict() for p in pages],
        }

    def get_document_evidence(
        self,
        document_id: str,
        page: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get all evidence highlights for a document.

        Args:
            document_id: Document ID.
            page: Optional page number filter.

        Returns:
            List of evidence highlight dicts.
        """
        # Build query with optional page filter
        query = """
            SELECT er.id, er.finding_id, er.page, er.snippet_text,
                   er.start_offset, er.end_offset, er.locator,
                   af.status, af.confidence, af.summary as finding_summary
            FROM evidence_refs er
            JOIN audit_findings af ON er.finding_id = af.id
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE er.document_id = ? AND ar.institution_id = ?
        """
        params = [document_id, self.institution_id]

        if page is not None:
            query += " AND er.page = ?"
            params.append(page)

        query += " ORDER BY er.page, er.id"

        cursor = self.conn.execute(query, params)
        evidence_items = []

        for row in cursor.fetchall():
            evidence = EvidenceHighlight(
                id=row["id"],
                finding_id=row["finding_id"],
                page=row["page"] or 1,
                snippet_text=row["snippet_text"] or "",
                start_offset=row["start_offset"],
                end_offset=row["end_offset"],
                status=row["status"],
                confidence=row["confidence"] or 1.0,
                finding_summary=row["finding_summary"],
            )

            # Try to extract offsets from locator JSON if not stored directly
            if evidence.start_offset is None and row["locator"]:
                try:
                    locator = json.loads(row["locator"])
                    evidence.start_offset = locator.get("start_offset")
                    evidence.end_offset = locator.get("end_offset")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Get linked standards
            evidence.standards = self._get_evidence_standards(row["finding_id"])
            evidence_items.append(evidence.to_dict())

        return evidence_items

    def get_document_standards(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all standards linked to evidence in this document.

        Args:
            document_id: Document ID.

        Returns:
            List of standard dicts with evidence counts.
        """
        cursor = self.conn.execute(
            """
            SELECT DISTINCT s.id, s.standard_code, s.title,
                   a.code as accreditor_code, a.name as accreditor_name,
                   COUNT(er.id) as evidence_count
            FROM standards s
            JOIN finding_standard_refs fsr ON s.id = fsr.standard_id
            JOIN audit_findings af ON fsr.finding_id = af.id
            JOIN evidence_refs er ON af.id = er.finding_id
            JOIN accreditors a ON s.accreditor_id = a.id
            WHERE er.document_id = ?
            GROUP BY s.id
            ORDER BY s.standard_code
            """,
            (document_id,),
        )

        standards = []
        for row in cursor.fetchall():
            standards.append({
                "id": row["id"],
                "code": row["standard_code"],
                "title": row["title"],
                "accreditor_code": row["accreditor_code"],
                "accreditor_name": row["accreditor_name"],
                "evidence_count": row["evidence_count"],
                "source": self._get_source_type(row["accreditor_code"]),
            })

        return standards

    def find_snippet_position(
        self,
        page_text: str,
        snippet: str,
        tolerance: float = 0.85,
    ) -> Optional[Tuple[int, int]]:
        """Find snippet position in page text using fuzzy matching.

        Args:
            page_text: Full page text.
            snippet: Snippet to find.
            tolerance: Minimum similarity ratio (0.0-1.0).

        Returns:
            Tuple of (start_offset, end_offset) or None if not found.
        """
        if not snippet or not page_text:
            return None

        snippet = snippet.strip()

        # Try exact match first
        pos = page_text.find(snippet)
        if pos >= 0:
            return (pos, pos + len(snippet))

        # Normalize whitespace and try again
        normalized_text = self._normalize_whitespace(page_text)
        normalized_snippet = self._normalize_whitespace(snippet)
        pos = normalized_text.find(normalized_snippet)
        if pos >= 0:
            # Map back to original positions
            return self._map_to_original_positions(page_text, normalized_text, pos, len(normalized_snippet))

        # Fuzzy sliding window search
        snippet_len = len(snippet)
        if snippet_len > len(page_text):
            return None

        best_score = 0.0
        best_pos = None

        # Use a step to speed up search for long texts
        step = max(1, snippet_len // 10)

        for i in range(0, len(page_text) - snippet_len + 1, step):
            window = page_text[i:i + snippet_len]
            score = SequenceMatcher(None, window.lower(), snippet.lower()).ratio()

            if score > best_score:
                best_score = score
                best_pos = i

        # Fine-tune around best position
        if best_pos is not None and best_score >= tolerance * 0.9:
            start = max(0, best_pos - step)
            end = min(len(page_text) - snippet_len + 1, best_pos + step + 1)

            for i in range(start, end):
                window = page_text[i:i + snippet_len]
                score = SequenceMatcher(None, window.lower(), snippet.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_pos = i

        if best_score >= tolerance and best_pos is not None:
            return (best_pos, best_pos + snippet_len)

        return None

    # =========================================================================
    # Private methods
    # =========================================================================

    def _get_evidence_standards(self, finding_id: str) -> List[Dict[str, Any]]:
        """Get standards linked to a finding."""
        cursor = self.conn.execute(
            """
            SELECT s.id, s.standard_code, s.title,
                   a.code as accreditor_code
            FROM standards s
            JOIN finding_standard_refs fsr ON s.id = fsr.standard_id
            JOIN accreditors a ON s.accreditor_id = a.id
            WHERE fsr.finding_id = ?
            ORDER BY s.standard_code
            """,
            (finding_id,),
        )

        return [
            {
                "id": row["id"],
                "code": row["standard_code"],
                "title": row["title"],
                "source": self._get_source_type(row["accreditor_code"]),
            }
            for row in cursor.fetchall()
        ]

    def _get_source_type(self, accreditor_code: str) -> str:
        """Determine source type from accreditor code."""
        code_upper = (accreditor_code or "").upper()
        if code_upper in ("USDOE", "FEDERAL", "TITLE_IV"):
            return "federal"
        elif code_upper.startswith("STATE_") or code_upper in ("BPPE", "SCHEV"):
            return "state"
        elif code_upper in ("NURSING", "DENTAL", "MEDICAL"):
            return "professional"
        else:
            return "accreditor"

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        return " ".join(text.split())

    def _map_to_original_positions(
        self,
        original: str,
        normalized: str,
        norm_start: int,
        norm_length: int,
    ) -> Tuple[int, int]:
        """Map normalized positions back to original text positions."""
        # Build mapping from normalized to original positions
        orig_pos = 0
        norm_pos = 0
        mapping = []

        in_whitespace = False
        for char in original:
            if char.isspace():
                if not in_whitespace:
                    mapping.append(orig_pos)
                    norm_pos += 1
                    in_whitespace = True
            else:
                mapping.append(orig_pos)
                norm_pos += 1
                in_whitespace = False
            orig_pos += 1

        # Map start and end
        if norm_start < len(mapping):
            start = mapping[norm_start]
        else:
            start = len(original)

        norm_end = norm_start + norm_length
        if norm_end < len(mapping):
            end = mapping[norm_end]
        else:
            end = len(original)

        return (start, end)


# =============================================================================
# Factory
# =============================================================================

_services: Dict[str, EvidenceHighlightingService] = {}


def get_evidence_highlighting_service(institution_id: str) -> EvidenceHighlightingService:
    """Get or create an evidence highlighting service for an institution.

    Args:
        institution_id: Institution ID.

    Returns:
        EvidenceHighlightingService instance.
    """
    if institution_id not in _services:
        _services[institution_id] = EvidenceHighlightingService(institution_id)
    return _services[institution_id]
