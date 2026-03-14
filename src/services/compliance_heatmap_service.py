"""Compliance Heatmap Service.

Builds a document × standard matrix showing compliance status across
all documents and requirements for heatmap visualization.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.db.connection import get_conn


@dataclass
class HeatmapDocument:
    """A document row in the heatmap."""
    id: str
    title: str
    doc_type: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HeatmapStandard:
    """A standard column in the heatmap."""
    id: str
    code: str
    title: str
    parent_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class HeatmapCell:
    """A cell in the document-standard matrix."""
    document_id: str
    standard_id: str
    status: str  # compliant, partial, non_compliant, not_evaluated
    finding_count: int = 0
    evidence_count: int = 0
    avg_confidence: float = 0.0
    max_severity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "standard_id": self.standard_id,
            "status": self.status,
            "finding_count": self.finding_count,
            "evidence_count": self.evidence_count,
            "avg_confidence": round(self.avg_confidence, 2),
            "max_severity": self.max_severity,
        }


class ComplianceHeatmapService:
    """Builds document × standard compliance matrix."""

    def __init__(self, institution_id: str, accreditor_code: Optional[str] = None):
        """Initialize the service.

        Args:
            institution_id: Institution ID.
            accreditor_code: Optional accreditor filter.
        """
        self.institution_id = institution_id
        self.accreditor_code = accreditor_code
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_conn()
        return self._conn

    def get_heatmap_data(
        self,
        doc_type_filter: Optional[str] = None,
        standard_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get complete heatmap data.

        Args:
            doc_type_filter: Filter documents by type (e.g., 'catalog', 'policy').
            standard_level: Filter standards by level ('section', 'standard').

        Returns:
            Dict with documents, standards, matrix cells, and summary stats.
        """
        accreditor_id = self._get_accreditor_id()
        if not accreditor_id:
            return {
                "documents": [],
                "standards": [],
                "matrix": [],
                "summary": {
                    "total_documents": 0,
                    "total_standards": 0,
                    "compliant_pct": 0,
                    "partial_pct": 0,
                    "non_compliant_pct": 0,
                    "not_evaluated_pct": 100,
                },
            }

        documents = self._get_documents(doc_type_filter)
        standards = self._get_standards(accreditor_id, standard_level)
        matrix = self._compute_matrix(documents, standards, accreditor_id)
        summary = self._compute_summary(matrix, len(documents), len(standards))

        return {
            "documents": [d.to_dict() for d in documents],
            "standards": [s.to_dict() for s in standards],
            "matrix": [c.to_dict() for c in matrix],
            "summary": summary,
        }

    def get_cell_findings(
        self,
        document_id: str,
        standard_id: str,
    ) -> List[Dict[str, Any]]:
        """Get detailed findings for a document-standard cell.

        Args:
            document_id: Document ID.
            standard_id: Standard ID.

        Returns:
            List of findings with evidence.
        """
        cursor = self.conn.execute(
            """
            SELECT af.id, af.status, af.severity, af.summary, af.recommendation,
                   af.confidence, af.created_at,
                   ci.item_number, ci.text as checklist_text
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            LEFT JOIN checklist_items ci ON af.checklist_item_id = ci.id
            LEFT JOIN checklist_item_standard_refs cisr ON ci.id = cisr.checklist_item_id
            WHERE ar.institution_id = ?
              AND af.document_id = ?
              AND cisr.standard_id = ?
            ORDER BY af.severity DESC, af.created_at DESC
            """,
            (self.institution_id, document_id, standard_id),
        )

        findings = []
        for row in cursor.fetchall():
            finding = {
                "id": row["id"],
                "status": row["status"],
                "severity": row["severity"],
                "summary": row["summary"],
                "recommendation": row["recommendation"],
                "confidence": row["confidence"],
                "created_at": row["created_at"],
                "checklist_item": row["item_number"],
                "checklist_text": row["checklist_text"],
                "evidence": [],
            }

            # Get evidence refs for this finding
            ev_cursor = self.conn.execute(
                """
                SELECT er.id, er.page, er.snippet_text
                FROM evidence_refs er
                WHERE er.finding_id = ?
                ORDER BY er.page
                """,
                (row["id"],),
            )

            for ev_row in ev_cursor.fetchall():
                finding["evidence"].append({
                    "id": ev_row["id"],
                    "page": ev_row["page"],
                    "snippet": ev_row["snippet_text"][:200] if ev_row["snippet_text"] else None,
                })

            findings.append(finding)

        return findings

    def get_document_summary(self, document_id: str) -> Dict[str, Any]:
        """Get compliance summary for a single document.

        Args:
            document_id: Document ID.

        Returns:
            Summary dict with status counts.
        """
        cursor = self.conn.execute(
            """
            SELECT af.status, COUNT(*) as count
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE ar.institution_id = ? AND af.document_id = ?
            GROUP BY af.status
            """,
            (self.institution_id, document_id),
        )

        counts = {row["status"]: row["count"] for row in cursor.fetchall()}
        total = sum(counts.values())

        return {
            "document_id": document_id,
            "total_findings": total,
            "compliant": counts.get("compliant", 0),
            "partial": counts.get("partial", 0),
            "non_compliant": counts.get("non_compliant", 0),
            "compliance_rate": round(
                (counts.get("compliant", 0) / total * 100) if total > 0 else 0, 1
            ),
        }

    # =========================================================================
    # Private methods
    # =========================================================================

    def _get_accreditor_id(self) -> Optional[str]:
        """Get the accreditor ID to use."""
        if self.accreditor_code:
            cursor = self.conn.execute(
                "SELECT id FROM accreditors WHERE code = ?",
                (self.accreditor_code,),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT a.id
                FROM accreditors a
                JOIN institutions i ON i.accreditor_primary = a.code
                WHERE i.id = ?
                """,
                (self.institution_id,),
            )

        row = cursor.fetchone()
        return row["id"] if row else None

    def _get_documents(self, doc_type_filter: Optional[str] = None) -> List[HeatmapDocument]:
        """Get documents for the institution."""
        query = """
            SELECT id, title, doc_type
            FROM documents
            WHERE institution_id = ?
        """
        params = [self.institution_id]

        if doc_type_filter:
            query += " AND doc_type = ?"
            params.append(doc_type_filter)

        query += " ORDER BY doc_type, title"

        cursor = self.conn.execute(query, params)
        return [
            HeatmapDocument(
                id=row["id"],
                title=row["title"] or "Untitled",
                doc_type=row["doc_type"] or "other",
            )
            for row in cursor.fetchall()
        ]

    def _get_standards(
        self,
        accreditor_id: str,
        level: Optional[str] = None,
    ) -> List[HeatmapStandard]:
        """Get standards for the accreditor."""
        query = """
            SELECT s.id, s.standard_code, s.title, p.standard_code as parent_code
            FROM standards s
            LEFT JOIN standards p ON s.parent_id = p.id
            WHERE s.accreditor_id = ?
        """
        params = [accreditor_id]

        if level == "section":
            query += " AND s.parent_id IS NULL"
        elif level == "standard":
            query += " AND s.parent_id IS NOT NULL"

        query += " ORDER BY s.standard_code"

        cursor = self.conn.execute(query, params)
        return [
            HeatmapStandard(
                id=row["id"],
                code=row["standard_code"],
                title=row["title"] or "",
                parent_code=row["parent_code"],
            )
            for row in cursor.fetchall()
        ]

    def _compute_matrix(
        self,
        documents: List[HeatmapDocument],
        standards: List[HeatmapStandard],
        accreditor_id: str,
    ) -> List[HeatmapCell]:
        """Compute the compliance matrix."""
        # Get all findings with document-standard pairs
        cursor = self.conn.execute(
            """
            SELECT
                af.document_id,
                cisr.standard_id,
                af.status,
                af.severity,
                af.confidence,
                COUNT(DISTINCT af.id) as finding_count,
                COUNT(DISTINCT er.id) as evidence_count
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            JOIN checklist_items ci ON af.checklist_item_id = ci.id
            JOIN checklist_item_standard_refs cisr ON ci.id = cisr.checklist_item_id
            JOIN standards s ON cisr.standard_id = s.id
            LEFT JOIN evidence_refs er ON af.id = er.finding_id
            WHERE ar.institution_id = ? AND s.accreditor_id = ?
            GROUP BY af.document_id, cisr.standard_id, af.status, af.severity
            """,
            (self.institution_id, accreditor_id),
        )

        # Build aggregation map: (doc_id, std_id) -> aggregated data
        cell_data: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {
            "statuses": [],
            "finding_count": 0,
            "evidence_count": 0,
            "confidences": [],
            "severities": [],
        })

        for row in cursor.fetchall():
            key = (row["document_id"], row["standard_id"])
            cell_data[key]["statuses"].append(row["status"])
            cell_data[key]["finding_count"] += row["finding_count"]
            cell_data[key]["evidence_count"] += row["evidence_count"]
            if row["confidence"]:
                cell_data[key]["confidences"].append(row["confidence"])
            if row["severity"]:
                cell_data[key]["severities"].append(row["severity"])

        # Build document and standard ID sets for quick lookup
        doc_ids = {d.id for d in documents}
        std_ids = {s.id for s in standards}

        # Create cells for all doc-standard pairs
        severity_order = {"critical": 4, "significant": 3, "high": 2, "medium": 1, "low": 0, "advisory": 0}
        cells = []

        for doc in documents:
            for std in standards:
                key = (doc.id, std.id)
                data = cell_data.get(key)

                if data and data["statuses"]:
                    # Aggregate status: worst status wins
                    status = self._aggregate_status(data["statuses"])
                    avg_conf = (
                        sum(data["confidences"]) / len(data["confidences"])
                        if data["confidences"]
                        else 0.0
                    )
                    max_sev = max(
                        data["severities"],
                        key=lambda s: severity_order.get(s, 0),
                        default=None,
                    ) if data["severities"] else None

                    cells.append(HeatmapCell(
                        document_id=doc.id,
                        standard_id=std.id,
                        status=status,
                        finding_count=data["finding_count"],
                        evidence_count=data["evidence_count"],
                        avg_confidence=avg_conf,
                        max_severity=max_sev,
                    ))
                else:
                    # No findings for this pair
                    cells.append(HeatmapCell(
                        document_id=doc.id,
                        standard_id=std.id,
                        status="not_evaluated",
                    ))

        return cells

    def _aggregate_status(self, statuses: List[str]) -> str:
        """Aggregate multiple statuses into one (worst wins)."""
        if "non_compliant" in statuses:
            return "non_compliant"
        if "partial" in statuses:
            return "partial"
        if "compliant" in statuses:
            return "compliant"
        return "not_evaluated"

    def _compute_summary(
        self,
        matrix: List[HeatmapCell],
        doc_count: int,
        std_count: int,
    ) -> Dict[str, Any]:
        """Compute summary statistics."""
        status_counts = defaultdict(int)
        for cell in matrix:
            status_counts[cell.status] += 1

        total = len(matrix)
        if total == 0:
            return {
                "total_documents": doc_count,
                "total_standards": std_count,
                "total_cells": 0,
                "compliant_pct": 0,
                "partial_pct": 0,
                "non_compliant_pct": 0,
                "not_evaluated_pct": 100,
            }

        return {
            "total_documents": doc_count,
            "total_standards": std_count,
            "total_cells": total,
            "compliant_count": status_counts["compliant"],
            "partial_count": status_counts["partial"],
            "non_compliant_count": status_counts["non_compliant"],
            "not_evaluated_count": status_counts["not_evaluated"],
            "compliant_pct": round(status_counts["compliant"] / total * 100, 1),
            "partial_pct": round(status_counts["partial"] / total * 100, 1),
            "non_compliant_pct": round(status_counts["non_compliant"] / total * 100, 1),
            "not_evaluated_pct": round(status_counts["not_evaluated"] / total * 100, 1),
        }


# =============================================================================
# Factory
# =============================================================================

_services: Dict[str, ComplianceHeatmapService] = {}


def get_compliance_heatmap_service(
    institution_id: str,
    accreditor_code: Optional[str] = None,
) -> ComplianceHeatmapService:
    """Get or create a compliance heatmap service.

    Args:
        institution_id: Institution ID.
        accreditor_code: Optional accreditor filter.

    Returns:
        ComplianceHeatmapService instance.
    """
    key = f"{institution_id}:{accreditor_code or 'default'}"
    if key not in _services:
        _services[key] = ComplianceHeatmapService(institution_id, accreditor_code)
    return _services[key]
