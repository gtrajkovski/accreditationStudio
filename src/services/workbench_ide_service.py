"""Workbench IDE Service.

Provides IDE-mode document workbench with inline findings overlay,
text positions, and remediation triggers.
"""

import difflib
import json
import os
import re
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional, Tuple

from src.db.connection import get_conn
from src.core.models import generate_id, now_iso


@dataclass
class FindingPosition:
    """Position of a finding within document text."""
    finding_id: str
    page: int
    start_char: int
    end_char: int
    text_snippet: str
    severity: str
    status: str = "non_compliant"
    summary: str = ""
    recommendation: str = ""
    standard_code: str = ""
    has_remediation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RemediationPreview:
    """Preview of a remediation for a finding."""
    finding_id: str
    document_id: str
    original_text: str
    remediated_text: str
    change_description: str
    impact_summary: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentDiff:
    """Diff between original and remediated document versions."""
    document_id: str
    title: str
    original_lines: List[str] = field(default_factory=list)
    remediated_lines: List[str] = field(default_factory=list)
    unified_diff: str = ""
    changes_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "original_lines": self.original_lines,
            "remediated_lines": self.remediated_lines,
            "unified_diff": self.unified_diff,
            "changes_count": self.changes_count,
        }


class WorkbenchIDEService:
    """Service for IDE-mode document workbench."""

    def __init__(self, institution_id: str, workspace_manager=None):
        """Initialize the service.

        Args:
            institution_id: Institution ID.
            workspace_manager: Optional workspace manager for file operations.
        """
        self.institution_id = institution_id
        self.workspace_manager = workspace_manager
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_conn()
        return self._conn

    def get_documents_with_findings(
        self,
        severity_filter: Optional[List[str]] = None,
        status_filter: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all documents with findings for the institution.

        Args:
            severity_filter: Optional list of severities to include.
            status_filter: Optional list of statuses to include.
            limit: Maximum documents to return.

        Returns:
            List of document dicts with finding counts.
        """
        query = """
            SELECT d.id, d.title, d.doc_type, d.page_count,
                   COUNT(af.id) as finding_count,
                   SUM(CASE WHEN af.severity = 'critical' THEN 1 ELSE 0 END) as critical_count,
                   SUM(CASE WHEN af.severity = 'significant' THEN 1 ELSE 0 END) as significant_count,
                   SUM(CASE WHEN af.severity = 'minor' THEN 1 ELSE 0 END) as minor_count,
                   MAX(ar.completed_at) as last_audit
            FROM documents d
            JOIN audit_findings af ON d.id = af.document_id
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE d.institution_id = ?
        """
        params: List[Any] = [self.institution_id]

        if severity_filter:
            placeholders = ",".join("?" * len(severity_filter))
            query += f" AND af.severity IN ({placeholders})"
            params.extend(severity_filter)

        if status_filter:
            placeholders = ",".join("?" * len(status_filter))
            query += f" AND af.status IN ({placeholders})"
            params.extend(status_filter)

        query += """
            GROUP BY d.id
            HAVING finding_count > 0
            ORDER BY critical_count DESC, significant_count DESC, finding_count DESC
            LIMIT ?
        """
        params.append(limit)

        cursor = self.conn.execute(query, params)
        documents = []

        for row in cursor.fetchall():
            documents.append({
                "id": row["id"],
                "title": row["title"],
                "doc_type": row["doc_type"],
                "page_count": row["page_count"] or 1,
                "finding_count": row["finding_count"],
                "critical_count": row["critical_count"] or 0,
                "significant_count": row["significant_count"] or 0,
                "minor_count": row["minor_count"] or 0,
                "last_audit": row["last_audit"],
            })

        return documents

    def get_document_with_findings(self, document_id: str) -> Dict[str, Any]:
        """Get document content with finding positions.

        Args:
            document_id: Document ID.

        Returns:
            Dict with document content, pages, and finding positions.
        """
        # Get document info
        cursor = self.conn.execute(
            """
            SELECT d.id, d.title, d.doc_type, d.page_count, d.extracted_text,
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
            return {"error": "Document not found"}

        doc = dict(row)
        pages = self._extract_pages(doc)
        findings = self.get_finding_positions(document_id)

        # Compute positions for findings without stored offsets
        for finding in findings:
            if finding.get("start_char", -1) < 0 and finding.get("text_snippet"):
                page_num = finding.get("page", 1)
                if 0 < page_num <= len(pages):
                    page_text = pages[page_num - 1].get("text", "")
                    pos = self._find_snippet_position(page_text, finding["text_snippet"])
                    if pos:
                        finding["start_char"] = pos[0]
                        finding["end_char"] = pos[1]

        return {
            "document_id": document_id,
            "title": doc["title"],
            "doc_type": doc["doc_type"],
            "total_pages": len(pages) or doc.get("page_count", 1),
            "pages": pages,
            "findings": findings,
        }

    def get_finding_positions(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all finding positions for a document.

        Args:
            document_id: Document ID.

        Returns:
            List of FindingPosition dicts.
        """
        cursor = self.conn.execute(
            """
            SELECT af.id, af.severity, af.status, af.summary, af.recommendation,
                   af.confidence, er.page, er.snippet_text, er.start_offset, er.end_offset,
                   er.locator, s.standard_code,
                   CASE WHEN rf.id IS NOT NULL THEN 1 ELSE 0 END as has_remediation
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            LEFT JOIN evidence_refs er ON af.id = er.finding_id AND er.document_id = ?
            LEFT JOIN finding_standard_refs fsr ON af.id = fsr.finding_id
            LEFT JOIN standards s ON fsr.standard_id = s.id
            LEFT JOIN remediation_fixes rf ON af.id = rf.finding_id
            WHERE af.document_id = ? AND ar.institution_id = ?
            ORDER BY er.page, af.severity DESC
            """,
            (document_id, document_id, self.institution_id),
        )

        findings: List[Dict[str, Any]] = []
        seen_ids = set()

        for row in cursor.fetchall():
            finding_id = row["id"]
            if finding_id in seen_ids:
                continue
            seen_ids.add(finding_id)

            # Parse locator for offsets if not stored directly
            start_char = row["start_offset"] or -1
            end_char = row["end_offset"] or -1
            if start_char < 0 and row["locator"]:
                try:
                    locator = json.loads(row["locator"])
                    start_char = locator.get("start_offset", -1)
                    end_char = locator.get("end_offset", -1)
                except (json.JSONDecodeError, TypeError):
                    pass

            finding = FindingPosition(
                finding_id=finding_id,
                page=row["page"] or 1,
                start_char=start_char,
                end_char=end_char,
                text_snippet=row["snippet_text"] or "",
                severity=row["severity"] or "minor",
                status=row["status"] or "non_compliant",
                summary=row["summary"] or "",
                recommendation=row["recommendation"] or "",
                standard_code=row["standard_code"] or "",
                has_remediation=bool(row["has_remediation"]),
            )
            findings.append(finding.to_dict())

        return findings

    def get_remediation_preview(self, finding_id: str) -> Dict[str, Any]:
        """Get preview of remediation for a finding.

        Args:
            finding_id: Finding ID.

        Returns:
            RemediationPreview dict or error.
        """
        # Get finding and any existing remediation
        cursor = self.conn.execute(
            """
            SELECT af.id, af.document_id, af.summary, af.recommendation,
                   rf.id as fix_id, rf.original_text, rf.new_text, rf.change_type,
                   rf.status as fix_status, rf.applied_at
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            LEFT JOIN remediation_fixes rf ON af.id = rf.finding_id
            WHERE af.id = ? AND ar.institution_id = ?
            """,
            (finding_id, self.institution_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "Finding not found"}

        # If remediation exists, return it
        if row["fix_id"]:
            return RemediationPreview(
                finding_id=finding_id,
                document_id=row["document_id"],
                original_text=row["original_text"] or "",
                remediated_text=row["new_text"] or "",
                change_description=f"Remediation ({row['change_type'] or 'edit'})",
                impact_summary=f"Status: {row['fix_status'] or 'pending'}",
                confidence=1.0 if row["applied_at"] else 0.8,
            ).to_dict()

        # No remediation yet - generate preview from recommendation
        return RemediationPreview(
            finding_id=finding_id,
            document_id=row["document_id"],
            original_text="[Original text not captured]",
            remediated_text=row["recommendation"] or "[No recommendation available]",
            change_description="Suggested fix based on audit recommendation",
            impact_summary=row["summary"] or "",
            confidence=0.5,
        ).to_dict()

    def apply_fix(self, finding_id: str, new_text: Optional[str] = None) -> Dict[str, Any]:
        """Apply remediation fix for a finding.

        Args:
            finding_id: Finding ID.
            new_text: Optional override for remediated text.

        Returns:
            Dict with success status and fix details.
        """
        # Get finding info
        cursor = self.conn.execute(
            """
            SELECT af.id, af.document_id, af.summary, af.recommendation,
                   rf.id as fix_id, rf.new_text
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            LEFT JOIN remediation_fixes rf ON af.id = rf.finding_id
            WHERE af.id = ? AND ar.institution_id = ?
            """,
            (finding_id, self.institution_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "Finding not found", "success": False}

        document_id = row["document_id"]
        fix_text = new_text or row["new_text"] or row["recommendation"]

        if not fix_text:
            return {"error": "No remediation text available", "success": False}

        # Create or update remediation fix record
        if row["fix_id"]:
            # Update existing
            self.conn.execute(
                """
                UPDATE remediation_fixes
                SET new_text = ?, status = 'applied', applied_at = ?
                WHERE id = ?
                """,
                (fix_text, now_iso(), row["fix_id"]),
            )
            fix_id = row["fix_id"]
        else:
            # Create new
            fix_id = generate_id("fix")
            self.conn.execute(
                """
                INSERT INTO remediation_fixes (id, finding_id, document_id, original_text, new_text, change_type, status, applied_at, created_at)
                VALUES (?, ?, ?, '', ?, 'edit', 'applied', ?, ?)
                """,
                (fix_id, finding_id, document_id, fix_text, now_iso(), now_iso()),
            )

        self.conn.commit()

        return {
            "success": True,
            "fix_id": fix_id,
            "finding_id": finding_id,
            "document_id": document_id,
            "applied_at": now_iso(),
        }

    def get_diff(self, document_id: str) -> Dict[str, Any]:
        """Get diff between original and remediated versions.

        Args:
            document_id: Document ID.

        Returns:
            DocumentDiff dict.
        """
        # Get document info
        cursor = self.conn.execute(
            """
            SELECT d.id, d.title, d.extracted_text,
                   dp.extracted_text_path
            FROM documents d
            LEFT JOIN document_parses dp ON d.id = dp.document_id
            WHERE d.id = ? AND d.institution_id = ?
            """,
            (document_id, self.institution_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "Document not found"}

        # Get original text
        original_text = row["extracted_text"] or ""
        if not original_text and row["extracted_text_path"]:
            try:
                if os.path.exists(row["extracted_text_path"]):
                    with open(row["extracted_text_path"], "r", encoding="utf-8") as f:
                        original_text = f.read()
            except IOError:
                pass

        # Get applied remediations
        cursor = self.conn.execute(
            """
            SELECT original_text, new_text
            FROM remediation_fixes
            WHERE document_id = ? AND status = 'applied'
            ORDER BY applied_at
            """,
            (document_id,),
        )

        # Apply remediations to generate remediated version
        remediated_text = original_text
        changes_count = 0
        for fix_row in cursor.fetchall():
            if fix_row["original_text"] and fix_row["new_text"]:
                old_text = remediated_text
                remediated_text = remediated_text.replace(
                    fix_row["original_text"], fix_row["new_text"], 1
                )
                if remediated_text != old_text:
                    changes_count += 1

        # Generate unified diff
        original_lines = original_text.splitlines(keepends=True)
        remediated_lines = remediated_text.splitlines(keepends=True)
        unified_diff = "".join(
            difflib.unified_diff(
                original_lines,
                remediated_lines,
                fromfile=f"original/{row['title']}",
                tofile=f"remediated/{row['title']}",
            )
        )

        return DocumentDiff(
            document_id=document_id,
            title=row["title"],
            original_lines=[line.rstrip("\n") for line in original_lines],
            remediated_lines=[line.rstrip("\n") for line in remediated_lines],
            unified_diff=unified_diff,
            changes_count=changes_count,
        ).to_dict()

    def _extract_pages(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract pages from document data.

        Args:
            doc: Document row dict.

        Returns:
            List of page dicts with page_number and text.
        """
        pages: List[Dict[str, Any]] = []

        # Try structured JSON first
        if doc.get("structured_json_path") and os.path.exists(doc["structured_json_path"]):
            try:
                with open(doc["structured_json_path"], "r", encoding="utf-8") as f:
                    structure = json.load(f)
                    if "pages" in structure:
                        for i, page_data in enumerate(structure["pages"], 1):
                            pages.append({
                                "page_number": i,
                                "text": page_data.get("text", ""),
                            })
                    elif "sections" in structure:
                        for i, section in enumerate(structure["sections"], 1):
                            pages.append({
                                "page_number": section.get("page", i),
                                "text": section.get("text", ""),
                            })
            except (json.JSONDecodeError, IOError):
                pass

        # Try extracted text file
        if not pages and doc.get("extracted_text_path") and os.path.exists(doc["extracted_text_path"]):
            try:
                with open(doc["extracted_text_path"], "r", encoding="utf-8") as f:
                    full_text = f.read()
                    page_pattern = r'\n?(?:---\s*Page\s*\d+\s*---|\f)\n?'
                    page_texts = re.split(page_pattern, full_text)
                    for i, text in enumerate(page_texts, 1):
                        if text.strip():
                            pages.append({"page_number": i, "text": text.strip()})
            except IOError:
                pass

        # Fall back to extracted_text field
        if not pages and doc.get("extracted_text"):
            pages.append({"page_number": 1, "text": doc["extracted_text"]})

        # Default empty page
        if not pages:
            pages.append({"page_number": 1, "text": "[Document text not available]"})

        return pages

    def _find_snippet_position(
        self,
        page_text: str,
        snippet: str,
        tolerance: float = 0.85,
    ) -> Optional[Tuple[int, int]]:
        """Find snippet position in page text using fuzzy matching.

        Args:
            page_text: Full page text.
            snippet: Snippet to find.
            tolerance: Minimum similarity ratio.

        Returns:
            Tuple of (start, end) or None.
        """
        if not snippet or not page_text:
            return None

        snippet = snippet.strip()

        # Exact match
        pos = page_text.find(snippet)
        if pos >= 0:
            return (pos, pos + len(snippet))

        # Normalize whitespace
        normalized_text = re.sub(r'\s+', ' ', page_text)
        normalized_snippet = re.sub(r'\s+', ' ', snippet)

        pos = normalized_text.find(normalized_snippet)
        if pos >= 0:
            # Map back to original positions
            return self._map_normalized_position(page_text, normalized_text, pos, len(normalized_snippet))

        # Fuzzy match using sliding window
        snippet_len = len(normalized_snippet)
        best_ratio = 0.0
        best_pos = -1

        for i in range(len(normalized_text) - snippet_len + 1):
            candidate = normalized_text[i:i + snippet_len]
            ratio = difflib.SequenceMatcher(None, normalized_snippet, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = i

        if best_ratio >= tolerance and best_pos >= 0:
            return self._map_normalized_position(page_text, normalized_text, best_pos, snippet_len)

        return None

    def _map_normalized_position(
        self,
        original: str,
        normalized: str,
        norm_start: int,
        norm_length: int,
    ) -> Tuple[int, int]:
        """Map normalized position back to original text.

        Args:
            original: Original text with whitespace.
            normalized: Normalized text.
            norm_start: Start position in normalized.
            norm_length: Length in normalized.

        Returns:
            Tuple of (start, end) in original text.
        """
        # Simple approximation - find corresponding char in original
        # by counting non-whitespace characters
        orig_pos = 0
        norm_pos = 0

        # Find start position
        while norm_pos < norm_start and orig_pos < len(original):
            if not original[orig_pos].isspace() or (norm_pos < len(normalized) and normalized[norm_pos] == ' '):
                norm_pos += 1
            orig_pos += 1

        start = orig_pos

        # Find end position
        chars_counted = 0
        while chars_counted < norm_length and orig_pos < len(original):
            if not original[orig_pos].isspace() or (norm_pos < len(normalized) and normalized[norm_pos] == ' '):
                chars_counted += 1
            orig_pos += 1

        return (start, orig_pos)
