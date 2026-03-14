"""Evidence Coverage Map Service.

Computes evidence coverage metrics for standards and builds a hierarchical
tree structure suitable for D3.js treemap visualization.

Coverage is computed based on:
- Linked checklist items per standard
- Audit findings status (compliant/partial/non-compliant)
- Evidence references from findings
- Document uploads linked to standards
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from collections import defaultdict

from src.db.connection import get_conn


@dataclass
class CoverageNode:
    """A node in the coverage tree (standard or accreditor)."""
    id: str
    name: str
    code: str
    level: str  # accreditor, section, standard, sub-standard
    coverage_pct: float = 0.0
    evidence_count: int = 0
    findings_compliant: int = 0
    findings_partial: int = 0
    findings_non_compliant: int = 0
    children: List["CoverageNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "level": self.level,
            "coverage_pct": round(self.coverage_pct, 1),
            "evidence_count": self.evidence_count,
            "findings_compliant": self.findings_compliant,
            "findings_partial": self.findings_partial,
            "findings_non_compliant": self.findings_non_compliant,
        }
        if self.children:
            result["children"] = [c.to_dict() for c in self.children]
        else:
            # Leaf nodes need a value for treemap sizing
            result["value"] = max(1, self.evidence_count or 1)
        return result


@dataclass
class EvidenceItem:
    """An evidence item linked to a standard."""
    id: str
    type: str  # document, finding, exhibit
    title: str
    status: str
    confidence: float
    snippet: Optional[str] = None
    page: Optional[int] = None
    document_id: Optional[str] = None
    finding_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class CoverageMapService:
    """Builds evidence coverage tree for visualization."""

    def __init__(self, institution_id: str, accreditor_code: Optional[str] = None):
        """Initialize the service.

        Args:
            institution_id: Institution ID.
            accreditor_code: Optional accreditor filter. If None, uses institution's primary.
        """
        self.institution_id = institution_id
        self.accreditor_code = accreditor_code
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_conn()
        return self._conn

    def get_coverage_tree(self) -> Dict[str, Any]:
        """Build the complete coverage tree.

        Returns:
            Tree structure with root containing accreditor -> section -> standard nodes.
        """
        # Get accreditor
        accreditor = self._get_accreditor()
        if not accreditor:
            return {"id": "root", "name": "No Standards", "children": [], "coverage_pct": 0}

        # Build standards hierarchy
        standards = self._get_standards_hierarchy(accreditor["id"])

        # Get coverage metrics for all standards
        coverage_data = self._compute_coverage_metrics(accreditor["id"])

        # Build tree nodes
        root = self._build_coverage_tree(accreditor, standards, coverage_data)

        return root.to_dict()

    def get_standard_evidence(self, standard_id: str) -> List[Dict[str, Any]]:
        """Get all evidence items linked to a specific standard.

        Args:
            standard_id: Standard ID to get evidence for.

        Returns:
            List of evidence items with details.
        """
        evidence = []

        # Get findings linked via checklist items
        cursor = self.conn.execute(
            """
            SELECT af.id, af.summary, af.status, af.severity, af.confidence,
                   d.id as doc_id, d.title as doc_title, d.doc_type,
                   ci.item_number, ci.text as checklist_text
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            LEFT JOIN documents d ON af.document_id = d.id
            LEFT JOIN checklist_items ci ON af.checklist_item_id = ci.id
            LEFT JOIN checklist_item_standard_refs cisr ON ci.id = cisr.checklist_item_id
            WHERE ar.institution_id = ? AND cisr.standard_id = ?
            ORDER BY af.status, af.severity DESC
            """,
            (self.institution_id, standard_id),
        )

        for row in cursor.fetchall():
            evidence.append(EvidenceItem(
                id=row["id"],
                type="finding",
                title=row["summary"] or f"Finding for {row['doc_title'] or 'document'}",
                status=row["status"],
                confidence=row["confidence"] or 0,
                document_id=row["doc_id"],
                finding_id=row["id"],
            ).to_dict())

        # Get evidence refs from findings
        cursor = self.conn.execute(
            """
            SELECT er.id, er.snippet_text, er.page, er.locator,
                   d.id as doc_id, d.title as doc_title, d.doc_type,
                   af.status, af.confidence
            FROM evidence_refs er
            JOIN audit_findings af ON er.finding_id = af.id
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            JOIN documents d ON er.document_id = d.id
            LEFT JOIN checklist_items ci ON af.checklist_item_id = ci.id
            LEFT JOIN checklist_item_standard_refs cisr ON ci.id = cisr.checklist_item_id
            WHERE ar.institution_id = ? AND cisr.standard_id = ?
            ORDER BY er.page
            """,
            (self.institution_id, standard_id),
        )

        for row in cursor.fetchall():
            evidence.append(EvidenceItem(
                id=row["id"],
                type="evidence_ref",
                title=row["doc_title"] or "Document",
                status=row["status"],
                confidence=row["confidence"] or 0,
                snippet=row["snippet_text"][:200] if row["snippet_text"] else None,
                page=row["page"],
                document_id=row["doc_id"],
            ).to_dict())

        # Deduplicate by ID
        seen = set()
        unique = []
        for item in evidence:
            if item["id"] not in seen:
                seen.add(item["id"])
                unique.append(item)

        return unique

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the coverage map.

        Returns:
            Dict with totals and breakdown.
        """
        accreditor = self._get_accreditor()
        if not accreditor:
            return {
                "total_standards": 0,
                "covered_standards": 0,
                "coverage_pct": 0,
                "findings_by_status": {},
            }

        # Count standards
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) as total
            FROM standards s
            WHERE s.accreditor_id = ?
            """,
            (accreditor["id"],),
        )
        total_standards = cursor.fetchone()["total"]

        # Count standards with evidence
        cursor = self.conn.execute(
            """
            SELECT COUNT(DISTINCT cisr.standard_id) as covered
            FROM checklist_item_standard_refs cisr
            JOIN checklist_items ci ON cisr.checklist_item_id = ci.id
            JOIN audit_findings af ON ci.id = af.checklist_item_id
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            JOIN standards s ON cisr.standard_id = s.id
            WHERE ar.institution_id = ? AND s.accreditor_id = ?
            """,
            (self.institution_id, accreditor["id"]),
        )
        covered_standards = cursor.fetchone()["covered"]

        # Findings by status
        cursor = self.conn.execute(
            """
            SELECT af.status, COUNT(*) as count
            FROM audit_findings af
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            WHERE ar.institution_id = ?
            GROUP BY af.status
            """,
            (self.institution_id,),
        )
        findings_by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

        coverage_pct = (covered_standards / total_standards * 100) if total_standards > 0 else 0

        return {
            "total_standards": total_standards,
            "covered_standards": covered_standards,
            "coverage_pct": round(coverage_pct, 1),
            "findings_by_status": findings_by_status,
            "accreditor_code": accreditor["code"],
            "accreditor_name": accreditor["name"],
        }

    # =========================================================================
    # Private methods
    # =========================================================================

    def _get_accreditor(self) -> Optional[Dict[str, Any]]:
        """Get the accreditor to use for the coverage map."""
        if self.accreditor_code:
            cursor = self.conn.execute(
                "SELECT id, code, name FROM accreditors WHERE code = ?",
                (self.accreditor_code,),
            )
        else:
            # Use institution's primary accreditor
            cursor = self.conn.execute(
                """
                SELECT a.id, a.code, a.name
                FROM accreditors a
                JOIN institutions i ON i.accreditor_primary = a.code
                WHERE i.id = ?
                """,
                (self.institution_id,),
            )

        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_standards_hierarchy(self, accreditor_id: str) -> List[Dict[str, Any]]:
        """Get all standards for the accreditor with parent relationships."""
        cursor = self.conn.execute(
            """
            SELECT id, standard_code, title, parent_id
            FROM standards
            WHERE accreditor_id = ?
            ORDER BY standard_code
            """,
            (accreditor_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def _compute_coverage_metrics(self, accreditor_id: str) -> Dict[str, Dict[str, Any]]:
        """Compute coverage metrics for each standard.

        Returns:
            Dict mapping standard_id to metrics dict.
        """
        metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "evidence_count": 0,
            "compliant": 0,
            "partial": 0,
            "non_compliant": 0,
        })

        # Count findings by status for each standard
        cursor = self.conn.execute(
            """
            SELECT cisr.standard_id, af.status, COUNT(*) as count
            FROM checklist_item_standard_refs cisr
            JOIN checklist_items ci ON cisr.checklist_item_id = ci.id
            JOIN audit_findings af ON ci.id = af.checklist_item_id
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            JOIN standards s ON cisr.standard_id = s.id
            WHERE ar.institution_id = ? AND s.accreditor_id = ?
            GROUP BY cisr.standard_id, af.status
            """,
            (self.institution_id, accreditor_id),
        )

        for row in cursor.fetchall():
            std_id = row["standard_id"]
            status = row["status"]
            count = row["count"]

            metrics[std_id]["evidence_count"] += count

            if status == "compliant":
                metrics[std_id]["compliant"] += count
            elif status == "partial":
                metrics[std_id]["partial"] += count
            elif status == "non_compliant":
                metrics[std_id]["non_compliant"] += count

        # Count evidence refs
        cursor = self.conn.execute(
            """
            SELECT cisr.standard_id, COUNT(DISTINCT er.id) as ref_count
            FROM checklist_item_standard_refs cisr
            JOIN checklist_items ci ON cisr.checklist_item_id = ci.id
            JOIN audit_findings af ON ci.id = af.checklist_item_id
            JOIN evidence_refs er ON af.id = er.finding_id
            JOIN audit_runs ar ON af.audit_run_id = ar.id
            JOIN standards s ON cisr.standard_id = s.id
            WHERE ar.institution_id = ? AND s.accreditor_id = ?
            GROUP BY cisr.standard_id
            """,
            (self.institution_id, accreditor_id),
        )

        for row in cursor.fetchall():
            metrics[row["standard_id"]]["evidence_count"] += row["ref_count"]

        return dict(metrics)

    def _build_coverage_tree(
        self,
        accreditor: Dict[str, Any],
        standards: List[Dict[str, Any]],
        coverage_data: Dict[str, Dict[str, Any]],
    ) -> CoverageNode:
        """Build the coverage tree from standards hierarchy."""
        # Build lookup maps
        by_id = {s["id"]: s for s in standards}
        by_parent: Dict[str, List[str]] = defaultdict(list)
        roots = []

        for s in standards:
            if s["parent_id"]:
                by_parent[s["parent_id"]].append(s["id"])
            else:
                roots.append(s["id"])

        def build_node(std_id: str, level: str) -> CoverageNode:
            s = by_id[std_id]
            metrics = coverage_data.get(std_id, {})

            # Build children first
            child_ids = by_parent.get(std_id, [])
            children = [build_node(cid, "sub-standard") for cid in child_ids]

            # Calculate coverage
            compliant = metrics.get("compliant", 0)
            partial = metrics.get("partial", 0)
            non_compliant = metrics.get("non_compliant", 0)
            total = compliant + partial + non_compliant

            # Aggregate from children if no direct metrics
            if not total and children:
                for child in children:
                    compliant += child.findings_compliant
                    partial += child.findings_partial
                    non_compliant += child.findings_non_compliant
                total = compliant + partial + non_compliant

            # Coverage: (compliant + 0.5*partial) / total
            if total > 0:
                coverage = ((compliant + 0.5 * partial) / total) * 100
            else:
                coverage = 0

            return CoverageNode(
                id=std_id,
                name=s["title"],
                code=s["standard_code"],
                level=level,
                coverage_pct=coverage,
                evidence_count=metrics.get("evidence_count", 0),
                findings_compliant=compliant,
                findings_partial=partial,
                findings_non_compliant=non_compliant,
                children=children,
            )

        # Build section nodes from top-level standards
        sections = [build_node(sid, "section") for sid in roots]

        # Calculate accreditor-level coverage
        total_compliant = sum(s.findings_compliant for s in sections)
        total_partial = sum(s.findings_partial for s in sections)
        total_non_compliant = sum(s.findings_non_compliant for s in sections)
        total = total_compliant + total_partial + total_non_compliant

        if total > 0:
            root_coverage = ((total_compliant + 0.5 * total_partial) / total) * 100
        else:
            root_coverage = 0

        return CoverageNode(
            id=accreditor["id"],
            name=accreditor["name"],
            code=accreditor["code"],
            level="accreditor",
            coverage_pct=root_coverage,
            evidence_count=sum(s.evidence_count for s in sections),
            findings_compliant=total_compliant,
            findings_partial=total_partial,
            findings_non_compliant=total_non_compliant,
            children=sections,
        )


# =============================================================================
# Factory
# =============================================================================

_services: Dict[str, CoverageMapService] = {}


def get_coverage_map_service(
    institution_id: str,
    accreditor_code: Optional[str] = None,
) -> CoverageMapService:
    """Get or create a coverage map service for an institution.

    Args:
        institution_id: Institution ID.
        accreditor_code: Optional accreditor filter.

    Returns:
        CoverageMapService instance.
    """
    key = f"{institution_id}:{accreditor_code or 'default'}"
    if key not in _services:
        _services[key] = CoverageMapService(institution_id, accreditor_code)
    return _services[key]
