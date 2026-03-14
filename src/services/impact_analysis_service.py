"""Impact Analysis Service.

Provides reverse-lookup from truth index facts to documents that reference them,
impact simulation before committing changes, and change propagation tracking.

Key capabilities:
- Scan documents to detect fact references
- Query all document references for a specific fact
- Simulate "what-if" change scenarios
- Apply changes with automatic remediation job creation
- Build fact-to-document dependency graphs
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from src.db.connection import get_conn


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class FactReference:
    """A reference to a fact within a document."""
    id: str
    institution_id: str
    fact_key: str
    document_id: str
    chunk_id: Optional[str] = None
    page_number: Optional[int] = None
    section_header: Optional[str] = None
    line_offset: Optional[int] = None
    reference_type: str = "literal"  # 'literal', 'placeholder', 'derived', 'inferred'
    context_snippet: Optional[str] = None
    matched_text: Optional[str] = None
    detection_method: str = "scan"  # 'scan', 'ai_analysis', 'manual', 'regex'
    confidence: float = 1.0
    verified: bool = False
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AffectedDocument:
    """A document affected by a fact change."""
    document_id: str
    title: str
    doc_type: str
    references_count: int
    pages_affected: List[int] = field(default_factory=list)
    sections_affected: List[str] = field(default_factory=list)
    preview_diffs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DependentFact:
    """A fact that depends on another fact (computed/derived)."""
    fact_key: str
    current_value: str
    computed_value: str
    dependency_type: str
    formula: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ImpactSimulation:
    """Result of a 'what-if' change simulation."""
    id: str
    institution_id: str
    fact_key: str
    current_value: Optional[str]
    proposed_value: str
    change_reason: Optional[str]
    documents_affected: int = 0
    chunks_affected: int = 0
    standards_affected: List[str] = field(default_factory=list)
    impact_severity: str = "low"  # 'low', 'medium', 'high', 'critical'
    auto_remediation_possible: bool = True
    affected_documents: List[AffectedDocument] = field(default_factory=list)
    dependent_facts: List[DependentFact] = field(default_factory=list)
    preview_diffs: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # 'pending', 'computing', 'completed', 'applied', 'cancelled'
    computed_at: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["affected_documents"] = [d.to_dict() if hasattr(d, "to_dict") else d
                                         for d in self.affected_documents]
        result["dependent_facts"] = [f.to_dict() if hasattr(f, "to_dict") else f
                                      for f in self.dependent_facts]
        return result


@dataclass
class ImpactGraphNode:
    """A node in the impact graph (fact or document)."""
    id: str
    node_type: str  # 'fact', 'document'
    label: str
    value: Optional[str] = None
    doc_type: Optional[str] = None
    ref_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ImpactGraphEdge:
    """An edge in the impact graph (fact references document)."""
    source: str
    target: str
    weight: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_id(prefix: str = "ref") -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}_{uuid4().hex[:12]}"


def _now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _flatten_truth_index(truth_index: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """Flatten nested truth index into dot-notation keys.

    Example:
        {"institution": {"name": "CEM"}} -> {"institution.name": "CEM"}
    """
    flattened = {}

    for key, value in truth_index.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if key in ("updated_at", "created_at"):
            continue  # Skip metadata keys

        if isinstance(value, dict):
            flattened.update(_flatten_truth_index(value, full_key))
        elif isinstance(value, (str, int, float, bool)):
            flattened[full_key] = str(value)
        elif isinstance(value, list):
            flattened[full_key] = json.dumps(value)

    return flattened


def _get_context_snippet(text: str, match_start: int, match_end: int,
                          context_chars: int = 50) -> str:
    """Extract context around a match."""
    start = max(0, match_start - context_chars)
    end = min(len(text), match_end + context_chars)

    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


def _calculate_impact_severity(
    documents_affected: int,
    chunks_affected: int,
    standards_affected: List[str],
    has_critical_findings: bool = False
) -> str:
    """Calculate impact severity level."""
    if has_critical_findings or documents_affected > 10 or len(standards_affected) > 5:
        return "critical"
    elif documents_affected > 5 or len(standards_affected) > 3:
        return "high"
    elif documents_affected > 2 or chunks_affected > 10:
        return "medium"
    return "low"


# =============================================================================
# Core Functions
# =============================================================================

def scan_document_for_facts(
    document_id: str,
    institution_id: str,
    truth_index: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> List[FactReference]:
    """Scan a document and detect all fact references.

    Detection methods:
    1. Template placeholders: [INSTITUTION_NAME], [PROGRAM_COST:id]
    2. Literal value matching: exact string search
    3. Currency/number formats: regex patterns

    Args:
        document_id: Document to scan
        institution_id: Institution ID
        truth_index: Truth index dictionary
        conn: Optional database connection

    Returns:
        List of detected fact references
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        references = []

        # Get document text and metadata
        cursor = conn.execute("""
            SELECT id, extracted_text, file_path, doc_type
            FROM documents
            WHERE id = ? AND institution_id = ?
        """, (document_id, institution_id))

        doc_row = cursor.fetchone()
        if not doc_row:
            return []

        doc_text = doc_row["extracted_text"] or ""
        if not doc_text:
            return []

        # Get document chunks for location tracking
        cursor = conn.execute("""
            SELECT id, chunk_index, page_number, section_header, text_original
            FROM document_chunks
            WHERE document_id = ?
            ORDER BY chunk_index
        """, (document_id,))

        chunks = cursor.fetchall()
        chunk_map = {row["id"]: dict(row) for row in chunks}

        # Flatten truth index for scanning
        flat_facts = _flatten_truth_index(truth_index)

        # Scan for each fact value
        for fact_key, fact_value in flat_facts.items():
            if not fact_value or len(fact_value) < 3:
                continue  # Skip empty or very short values

            # 1. Check for template placeholders
            placeholder_patterns = _get_placeholder_patterns(fact_key)
            for pattern in placeholder_patterns:
                for match in re.finditer(pattern, doc_text, re.IGNORECASE):
                    ref = FactReference(
                        id=_generate_id("ref"),
                        institution_id=institution_id,
                        fact_key=fact_key,
                        document_id=document_id,
                        reference_type="placeholder",
                        matched_text=match.group(),
                        context_snippet=_get_context_snippet(doc_text, match.start(), match.end()),
                        line_offset=match.start(),
                        detection_method="regex",
                        confidence=1.0,
                        created_at=_now_iso()
                    )
                    references.append(ref)

            # 2. Check for literal value matches
            escaped_value = re.escape(fact_value)
            for match in re.finditer(escaped_value, doc_text, re.IGNORECASE):
                # Find which chunk contains this match
                chunk_id = None
                page_number = None
                section_header = None

                for chunk in chunks:
                    chunk_text = chunk["text_original"] or ""
                    if fact_value.lower() in chunk_text.lower():
                        chunk_id = chunk["id"]
                        page_number = chunk["page_number"]
                        section_header = chunk["section_header"]
                        break

                ref = FactReference(
                    id=_generate_id("ref"),
                    institution_id=institution_id,
                    fact_key=fact_key,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    page_number=page_number,
                    section_header=section_header,
                    reference_type="literal",
                    matched_text=match.group(),
                    context_snippet=_get_context_snippet(doc_text, match.start(), match.end()),
                    line_offset=match.start(),
                    detection_method="scan",
                    confidence=0.9,
                    created_at=_now_iso()
                )
                references.append(ref)

            # 3. Check for currency formats (for numeric facts)
            if _is_currency_value(fact_value):
                currency_refs = _scan_for_currency(
                    doc_text, fact_key, fact_value, document_id, institution_id, chunks
                )
                references.extend(currency_refs)

        # Deduplicate references (same fact_key + similar location)
        references = _deduplicate_references(references)

        return references

    finally:
        if should_close:
            conn.close()


def _get_placeholder_patterns(fact_key: str) -> List[str]:
    """Get regex patterns for template placeholders based on fact key."""
    patterns = []

    # Standard placeholders
    if fact_key == "institution.name":
        patterns.append(r"\[INSTITUTION_NAME\]")
    elif fact_key.startswith("programs.") and fact_key.endswith(".name_en"):
        prog_id = fact_key.split(".")[1]
        patterns.append(rf"\[PROGRAM_NAME:{prog_id}\]")
        patterns.append(r"\[PROGRAM_NAME\]")
    elif fact_key.startswith("programs.") and fact_key.endswith(".total_cost"):
        prog_id = fact_key.split(".")[1]
        patterns.append(rf"\[PROGRAM_COST:{prog_id}\]")
        patterns.append(r"\[PROGRAM_COST\]")
    elif fact_key.startswith("programs.") and fact_key.endswith(".duration_months"):
        prog_id = fact_key.split(".")[1]
        patterns.append(rf"\[PROGRAM_DURATION:{prog_id}\]")

    return patterns


def _is_currency_value(value: str) -> bool:
    """Check if value looks like a currency amount."""
    try:
        # Remove currency symbols and commas
        cleaned = re.sub(r"[$,]", "", value)
        float(cleaned)
        return True
    except (ValueError, TypeError):
        return False


def _scan_for_currency(
    text: str,
    fact_key: str,
    fact_value: str,
    document_id: str,
    institution_id: str,
    chunks: List[Dict]
) -> List[FactReference]:
    """Scan for currency value in different formats."""
    references = []

    try:
        # Parse the numeric value
        cleaned = re.sub(r"[$,]", "", fact_value)
        numeric_value = float(cleaned)

        # Generate patterns for different currency formats
        patterns = [
            rf"\${numeric_value:,.2f}",  # $12,500.00
            rf"\${numeric_value:,.0f}",  # $12,500
            rf"\${int(numeric_value):,}",  # $12,500
            rf"{numeric_value:,.2f}",     # 12,500.00
        ]

        for pattern in patterns:
            escaped = re.escape(pattern)
            for match in re.finditer(escaped, text):
                ref = FactReference(
                    id=_generate_id("ref"),
                    institution_id=institution_id,
                    fact_key=fact_key,
                    document_id=document_id,
                    reference_type="derived",
                    matched_text=match.group(),
                    context_snippet=_get_context_snippet(text, match.start(), match.end()),
                    line_offset=match.start(),
                    detection_method="regex",
                    confidence=0.85,
                    created_at=_now_iso()
                )
                references.append(ref)

    except (ValueError, TypeError):
        pass

    return references


def _deduplicate_references(references: List[FactReference]) -> List[FactReference]:
    """Remove duplicate references (same fact at similar locations)."""
    seen = set()
    unique = []

    for ref in references:
        # Create a key based on fact_key and approximate location
        loc_bucket = (ref.line_offset or 0) // 100  # Group by 100-char windows
        key = (ref.fact_key, ref.document_id, loc_bucket, ref.reference_type)

        if key not in seen:
            seen.add(key)
            unique.append(ref)

    return unique


def save_fact_references(
    references: List[FactReference],
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Save fact references to database.

    Returns:
        Number of references saved
    """
    if not references:
        return 0

    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        saved = 0

        for ref in references:
            try:
                conn.execute("""
                    INSERT INTO fact_references (
                        id, institution_id, fact_key, document_id, chunk_id,
                        page_number, section_header, line_offset, reference_type,
                        context_snippet, matched_text, detection_method, confidence,
                        verified, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ref.id, ref.institution_id, ref.fact_key, ref.document_id,
                    ref.chunk_id, ref.page_number, ref.section_header, ref.line_offset,
                    ref.reference_type, ref.context_snippet, ref.matched_text,
                    ref.detection_method, ref.confidence, 1 if ref.verified else 0,
                    ref.created_at or _now_iso(), _now_iso()
                ))
                saved += 1
            except sqlite3.IntegrityError:
                pass  # Skip duplicates

        conn.commit()
        return saved

    finally:
        if should_close:
            conn.close()


def get_fact_references(
    institution_id: str,
    fact_key: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[FactReference]:
    """Get all document references for a specific fact.

    Args:
        institution_id: Institution ID
        fact_key: Fact key (e.g., "institution.name")
        conn: Optional database connection

    Returns:
        List of fact references
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT
                fr.*,
                d.file_path,
                d.doc_type
            FROM fact_references fr
            JOIN documents d ON fr.document_id = d.id
            WHERE fr.institution_id = ?
              AND fr.fact_key = ?
            ORDER BY fr.created_at DESC
        """, (institution_id, fact_key))

        references = []
        for row in cursor.fetchall():
            ref = FactReference(
                id=row["id"],
                institution_id=row["institution_id"],
                fact_key=row["fact_key"],
                document_id=row["document_id"],
                chunk_id=row["chunk_id"],
                page_number=row["page_number"],
                section_header=row["section_header"],
                line_offset=row["line_offset"],
                reference_type=row["reference_type"],
                context_snippet=row["context_snippet"],
                matched_text=row["matched_text"],
                detection_method=row["detection_method"],
                confidence=row["confidence"],
                verified=bool(row["verified"]),
                created_at=row["created_at"]
            )
            references.append(ref)

        return references

    finally:
        if should_close:
            conn.close()


def list_facts_with_counts(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """List all facts in truth index with their reference counts.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        List of facts with metadata and reference counts
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Get truth index from database
        cursor = conn.execute("""
            SELECT key, value, value_type, confidence, verified_at
            FROM truth_index
            WHERE institution_id = ?
            ORDER BY key
        """, (institution_id,))

        facts = []
        for row in cursor.fetchall():
            fact_key = row["key"]

            # Get reference count
            count_cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM fact_references
                WHERE institution_id = ? AND fact_key = ?
            """, (institution_id, fact_key))
            count_row = count_cursor.fetchone()
            ref_count = count_row["count"] if count_row else 0

            facts.append({
                "key": fact_key,
                "value": row["value"],
                "value_type": row["value_type"],
                "confidence": row["confidence"],
                "verified_at": row["verified_at"],
                "reference_count": ref_count,
                "category": fact_key.split(".")[0] if "." in fact_key else "other"
            })

        return facts

    finally:
        if should_close:
            conn.close()


def simulate_change(
    institution_id: str,
    fact_key: str,
    proposed_value: str,
    change_reason: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> ImpactSimulation:
    """Run 'what-if' analysis for a proposed fact change.

    Args:
        institution_id: Institution ID
        fact_key: Fact key to change
        proposed_value: New value
        change_reason: Optional reason for change
        conn: Optional database connection

    Returns:
        Impact simulation with affected documents and preview diffs
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        simulation_id = _generate_id("sim")

        # Get current value
        cursor = conn.execute("""
            SELECT value FROM truth_index
            WHERE institution_id = ? AND key = ?
        """, (institution_id, fact_key))
        current_row = cursor.fetchone()
        current_value = current_row["value"] if current_row else None

        # Get all references for this fact
        references = get_fact_references(institution_id, fact_key, conn)

        # Group references by document
        docs_map: Dict[str, List[FactReference]] = {}
        for ref in references:
            if ref.document_id not in docs_map:
                docs_map[ref.document_id] = []
            docs_map[ref.document_id].append(ref)

        # Build affected documents list
        affected_documents = []
        preview_diffs = {}
        chunks_affected = 0

        for doc_id, refs in docs_map.items():
            # Get document info
            cursor = conn.execute("""
                SELECT id, file_path, doc_type,
                       COALESCE(json_extract(metadata, '$.title'), file_path) as title
                FROM documents
                WHERE id = ?
            """, (doc_id,))
            doc_row = cursor.fetchone()

            if not doc_row:
                continue

            pages = list(set(r.page_number for r in refs if r.page_number))
            sections = list(set(r.section_header for r in refs if r.section_header))
            chunks_affected += len(set(r.chunk_id for r in refs if r.chunk_id))

            # Generate preview diffs
            doc_diffs = {}
            for ref in refs[:5]:  # Limit to 5 previews per doc
                if ref.context_snippet and current_value:
                    before = ref.context_snippet
                    after = before.replace(current_value, proposed_value)
                    if before != after:
                        key = f"line_{ref.line_offset or 0}"
                        doc_diffs[key] = {"before": before, "after": after}

            if doc_diffs:
                preview_diffs[doc_id] = doc_diffs

            affected_documents.append(AffectedDocument(
                document_id=doc_id,
                title=doc_row["title"] or doc_row["file_path"],
                doc_type=doc_row["doc_type"],
                references_count=len(refs),
                pages_affected=sorted(pages),
                sections_affected=sections,
                preview_diffs=doc_diffs
            ))

        # Get affected standards (from findings related to these documents)
        doc_ids = list(docs_map.keys())
        standards_affected = []
        if doc_ids:
            placeholders = ",".join("?" * len(doc_ids))
            cursor = conn.execute(f"""
                SELECT DISTINCT standard_ref
                FROM audit_findings
                WHERE document_id IN ({placeholders})
                  AND standard_ref IS NOT NULL
            """, doc_ids)
            standards_affected = [row["standard_ref"] for row in cursor.fetchall()]

        # Compute dependent facts
        dependent_facts = _compute_dependent_facts(institution_id, fact_key, proposed_value, conn)

        # Calculate severity
        impact_severity = _calculate_impact_severity(
            len(affected_documents),
            chunks_affected,
            standards_affected
        )

        # Create simulation record
        simulation = ImpactSimulation(
            id=simulation_id,
            institution_id=institution_id,
            fact_key=fact_key,
            current_value=current_value,
            proposed_value=proposed_value,
            change_reason=change_reason,
            documents_affected=len(affected_documents),
            chunks_affected=chunks_affected,
            standards_affected=standards_affected,
            impact_severity=impact_severity,
            auto_remediation_possible=True,
            affected_documents=affected_documents,
            dependent_facts=dependent_facts,
            preview_diffs=preview_diffs,
            status="completed",
            computed_at=_now_iso(),
            created_at=_now_iso()
        )

        # Save simulation to database
        _save_simulation(simulation, conn)

        return simulation

    finally:
        if should_close:
            conn.close()


def _compute_dependent_facts(
    institution_id: str,
    fact_key: str,
    new_value: str,
    conn: sqlite3.Connection
) -> List[DependentFact]:
    """Compute cascading changes to dependent facts."""
    dependent = []

    # Check for registered dependencies
    cursor = conn.execute("""
        SELECT dependent_fact, dependency_type, formula
        FROM fact_dependencies
        WHERE institution_id = ? AND source_fact = ?
    """, (institution_id, fact_key))

    for row in cursor.fetchall():
        dep_key = row["dependent_fact"]
        formula = row["formula"]
        dep_type = row["dependency_type"]

        # Get current value of dependent fact
        cursor2 = conn.execute("""
            SELECT value FROM truth_index
            WHERE institution_id = ? AND key = ?
        """, (institution_id, dep_key))
        current_row = cursor2.fetchone()
        current_dep_value = current_row["value"] if current_row else ""

        # Try to compute new value (simplified - for demo)
        computed_value = current_dep_value  # Would apply formula here

        dependent.append(DependentFact(
            fact_key=dep_key,
            current_value=current_dep_value,
            computed_value=computed_value,
            dependency_type=dep_type,
            formula=formula
        ))

    # Auto-detect common dependencies
    if fact_key.endswith(".total_cost"):
        # Check for cost_per_period
        parts = fact_key.rsplit(".", 1)
        if len(parts) == 2:
            period_key = parts[0] + ".cost_per_period"
            cursor = conn.execute("""
                SELECT value FROM truth_index
                WHERE institution_id = ? AND key = ?
            """, (institution_id, period_key))
            period_row = cursor.fetchone()

            if period_row:
                # Get periods count
                periods_key = parts[0] + ".academic_periods"
                cursor = conn.execute("""
                    SELECT value FROM truth_index
                    WHERE institution_id = ? AND key = ?
                """, (institution_id, periods_key))
                periods_row = cursor.fetchone()

                if periods_row:
                    try:
                        periods = int(periods_row["value"])
                        new_cost = float(new_value)
                        new_per_period = new_cost / periods if periods > 0 else 0

                        dependent.append(DependentFact(
                            fact_key=period_key,
                            current_value=period_row["value"],
                            computed_value=f"{new_per_period:.2f}",
                            dependency_type="computed",
                            formula="total_cost / academic_periods"
                        ))
                    except (ValueError, TypeError):
                        pass

    return dependent


def _save_simulation(
    simulation: ImpactSimulation,
    conn: sqlite3.Connection
) -> None:
    """Save impact simulation to database."""
    conn.execute("""
        INSERT INTO impact_simulations (
            id, institution_id, fact_key, current_value, proposed_value,
            change_reason, documents_affected, chunks_affected, standards_affected,
            impact_severity, auto_remediation_possible, affected_documents,
            affected_chunks, preview_diffs, dependent_facts, status, computed_at,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        simulation.id,
        simulation.institution_id,
        simulation.fact_key,
        simulation.current_value,
        simulation.proposed_value,
        simulation.change_reason,
        simulation.documents_affected,
        simulation.chunks_affected,
        json.dumps(simulation.standards_affected),
        simulation.impact_severity,
        1 if simulation.auto_remediation_possible else 0,
        json.dumps([d.to_dict() for d in simulation.affected_documents]),
        json.dumps([]),  # affected_chunks simplified
        json.dumps(simulation.preview_diffs),
        json.dumps([f.to_dict() for f in simulation.dependent_facts]),
        simulation.status,
        simulation.computed_at,
        simulation.created_at
    ))
    conn.commit()


def get_simulation(
    simulation_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[ImpactSimulation]:
    """Get a simulation by ID."""
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT * FROM impact_simulations WHERE id = ?
        """, (simulation_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return ImpactSimulation(
            id=row["id"],
            institution_id=row["institution_id"],
            fact_key=row["fact_key"],
            current_value=row["current_value"],
            proposed_value=row["proposed_value"],
            change_reason=row["change_reason"],
            documents_affected=row["documents_affected"],
            chunks_affected=row["chunks_affected"],
            standards_affected=json.loads(row["standards_affected"] or "[]"),
            impact_severity=row["impact_severity"],
            auto_remediation_possible=bool(row["auto_remediation_possible"]),
            affected_documents=[AffectedDocument(**d) for d in json.loads(row["affected_documents"] or "[]")],
            dependent_facts=[DependentFact(**f) for f in json.loads(row["dependent_facts"] or "[]")],
            preview_diffs=json.loads(row["preview_diffs"] or "{}"),
            status=row["status"],
            computed_at=row["computed_at"],
            created_at=row["created_at"]
        )

    finally:
        if should_close:
            conn.close()


def apply_simulation(
    simulation_id: str,
    user_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Apply a simulated change and trigger remediation.

    Args:
        simulation_id: ID of simulation to apply
        user_id: Optional user ID for audit trail
        conn: Optional database connection

    Returns:
        Result with updated truth index and created remediation jobs
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Get simulation
        simulation = get_simulation(simulation_id, conn)
        if not simulation:
            return {"success": False, "error": "Simulation not found"}

        if simulation.status == "applied":
            return {"success": False, "error": "Simulation already applied"}

        # Update truth index
        conn.execute("""
            UPDATE truth_index
            SET value = ?, updated_at = ?
            WHERE institution_id = ? AND key = ?
        """, (
            simulation.proposed_value,
            _now_iso(),
            simulation.institution_id,
            simulation.fact_key
        ))

        # Create remediation jobs for affected documents
        remediation_jobs = []
        for doc in simulation.affected_documents:
            job_id = _generate_id("rem")
            conn.execute("""
                INSERT INTO remediation_jobs (
                    id, document_id, status, changes_made, created_at
                ) VALUES (?, ?, 'queued', ?, ?)
            """, (
                job_id,
                doc.document_id,
                json.dumps([{
                    "type": "fact_update",
                    "fact_key": simulation.fact_key,
                    "old_value": simulation.current_value,
                    "new_value": simulation.proposed_value
                }]),
                _now_iso()
            ))
            remediation_jobs.append(job_id)

        # Update simulation status
        conn.execute("""
            UPDATE impact_simulations
            SET status = 'applied', applied_at = ?, applied_by = ?
            WHERE id = ?
        """, (_now_iso(), user_id, simulation_id))

        # Record in history
        history_id = _generate_id("hist")
        conn.execute("""
            INSERT INTO impact_change_history (
                id, simulation_id, institution_id, fact_key,
                old_value, new_value, documents_updated,
                remediation_jobs_created, applied_at, applied_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            history_id,
            simulation_id,
            simulation.institution_id,
            simulation.fact_key,
            simulation.current_value,
            simulation.proposed_value,
            len(simulation.affected_documents),
            json.dumps(remediation_jobs),
            _now_iso(),
            user_id
        ))

        conn.commit()

        return {
            "success": True,
            "simulation_id": simulation_id,
            "fact_key": simulation.fact_key,
            "new_value": simulation.proposed_value,
            "documents_updated": len(simulation.affected_documents),
            "remediation_jobs": remediation_jobs,
            "history_id": history_id
        }

    finally:
        if should_close:
            conn.close()


def build_impact_graph(
    institution_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Build the full fact-to-document dependency graph for visualization.

    Args:
        institution_id: Institution ID
        conn: Optional database connection

    Returns:
        Graph with nodes and edges for D3.js visualization
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        nodes = []
        edges = []

        # Get all facts from truth index
        cursor = conn.execute("""
            SELECT key, value FROM truth_index
            WHERE institution_id = ?
        """, (institution_id,))

        for row in cursor.fetchall():
            fact_key = row["key"]

            # Get reference count
            count_cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM fact_references
                WHERE institution_id = ? AND fact_key = ?
            """, (institution_id, fact_key))
            ref_count = count_cursor.fetchone()["count"]

            if ref_count > 0:  # Only include facts with references
                nodes.append(ImpactGraphNode(
                    id=fact_key,
                    node_type="fact",
                    label=fact_key.split(".")[-1],  # Short label
                    value=row["value"][:50] if row["value"] else None,
                    ref_count=ref_count
                ))

        # Get all documents with references
        cursor = conn.execute("""
            SELECT DISTINCT
                d.id, d.doc_type,
                COALESCE(json_extract(d.metadata, '$.title'), d.file_path) as title,
                COUNT(fr.id) as ref_count
            FROM documents d
            JOIN fact_references fr ON d.id = fr.document_id
            WHERE d.institution_id = ?
            GROUP BY d.id
        """, (institution_id,))

        for row in cursor.fetchall():
            nodes.append(ImpactGraphNode(
                id=row["id"],
                node_type="document",
                label=row["title"][:30] if row["title"] else row["id"][:12],
                doc_type=row["doc_type"],
                ref_count=row["ref_count"]
            ))

        # Build edges
        cursor = conn.execute("""
            SELECT fact_key, document_id, COUNT(*) as weight
            FROM fact_references
            WHERE institution_id = ?
            GROUP BY fact_key, document_id
        """, (institution_id,))

        for row in cursor.fetchall():
            edges.append(ImpactGraphEdge(
                source=row["fact_key"],
                target=row["document_id"],
                weight=row["weight"]
            ))

        # Identify high-impact facts (>5 references)
        high_impact_facts = [n.id for n in nodes
                            if n.node_type == "fact" and n.ref_count > 5]

        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "clusters": {
                "high_impact_facts": high_impact_facts
            },
            "stats": {
                "total_facts": len([n for n in nodes if n.node_type == "fact"]),
                "total_documents": len([n for n in nodes if n.node_type == "document"]),
                "total_edges": len(edges)
            }
        }

    finally:
        if should_close:
            conn.close()


def scan_all_documents(
    institution_id: str,
    truth_index: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Scan all documents for an institution and update fact references.

    Args:
        institution_id: Institution ID
        truth_index: Truth index dictionary
        conn: Optional database connection

    Returns:
        Summary of scan results
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        # Clear existing references
        conn.execute("""
            DELETE FROM fact_references WHERE institution_id = ?
        """, (institution_id,))

        # Get all documents
        cursor = conn.execute("""
            SELECT id FROM documents
            WHERE institution_id = ?
              AND extracted_text IS NOT NULL
              AND extracted_text != ''
        """, (institution_id,))

        documents = [row["id"] for row in cursor.fetchall()]

        total_refs = 0
        docs_scanned = 0

        for doc_id in documents:
            refs = scan_document_for_facts(doc_id, institution_id, truth_index, conn)
            saved = save_fact_references(refs, conn)
            total_refs += saved
            docs_scanned += 1

        return {
            "success": True,
            "documents_scanned": docs_scanned,
            "references_found": total_refs,
            "scanned_at": _now_iso()
        }

    finally:
        if should_close:
            conn.close()


def get_change_history(
    institution_id: str,
    limit: int = 50,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """Get history of applied fact changes.

    Args:
        institution_id: Institution ID
        limit: Maximum records to return
        conn: Optional database connection

    Returns:
        List of change history records
    """
    should_close = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cursor = conn.execute("""
            SELECT
                h.*,
                s.impact_severity,
                s.change_reason
            FROM impact_change_history h
            LEFT JOIN impact_simulations s ON h.simulation_id = s.id
            WHERE h.institution_id = ?
            ORDER BY h.applied_at DESC
            LIMIT ?
        """, (institution_id, limit))

        history = []
        for row in cursor.fetchall():
            history.append({
                "id": row["id"],
                "simulation_id": row["simulation_id"],
                "fact_key": row["fact_key"],
                "old_value": row["old_value"],
                "new_value": row["new_value"],
                "documents_updated": row["documents_updated"],
                "remediation_jobs_created": json.loads(row["remediation_jobs_created"] or "[]"),
                "impact_severity": row["impact_severity"],
                "change_reason": row["change_reason"],
                "applied_at": row["applied_at"],
                "applied_by": row["applied_by"]
            })

        return history

    finally:
        if should_close:
            conn.close()
