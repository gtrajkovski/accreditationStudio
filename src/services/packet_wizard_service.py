"""Packet Studio wizard service.

Provides 5-step wizard state machine for submission packet creation:
1. Submission Type - Choose packet type (self-study, response, etc.)
2. Standards - Select applicable standards
3. Evidence - Map evidence to standards
4. Narrative - Generate/edit narratives
5. Preview - Review and finalize
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import IntEnum

from src.db.connection import get_conn
from src.core.models import generate_id, now_iso


class WizardStep(IntEnum):
    """Wizard steps (1-indexed for UI clarity)."""
    SUBMISSION_TYPE = 1
    STANDARDS = 2
    EVIDENCE = 3
    NARRATIVE = 4
    PREVIEW = 5


@dataclass
class WizardSession:
    """A packet wizard session."""
    id: str = field(default_factory=lambda: generate_id("wiz"))
    institution_id: str = ""
    packet_id: Optional[str] = None
    current_step: int = 1
    step_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "draft"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None
    created_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "packet_id": self.packet_id,
            "current_step": self.current_step,
            "step_data": self.step_data,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "created_by": self.created_by,
            "can_proceed": self._can_proceed(),
            "step_validation": self._get_step_validation(),
        }

    def _can_proceed(self) -> bool:
        """Check if current step is complete enough to proceed."""
        if self.current_step == WizardStep.SUBMISSION_TYPE:
            return bool(self.step_data.get("submission_type"))
        elif self.current_step == WizardStep.STANDARDS:
            return len(self.step_data.get("selected_standards", [])) > 0
        elif self.current_step == WizardStep.EVIDENCE:
            return self._evidence_coverage() >= 0.8
        elif self.current_step == WizardStep.NARRATIVE:
            # Narratives are optional but at least one should be present
            return len(self.step_data.get("narratives", {})) > 0
        elif self.current_step == WizardStep.PREVIEW:
            # Preview step is always complete (final review)
            return True
        return False

    def _evidence_coverage(self) -> float:
        """Calculate evidence coverage percentage."""
        standards = self.step_data.get("selected_standards", [])
        mappings = self.step_data.get("evidence_mappings", {})
        if not standards:
            return 0
        covered = sum(1 for s in standards if mappings.get(s))
        return covered / len(standards)

    def _get_step_validation(self) -> Dict[str, Any]:
        """Get detailed validation info for current step."""
        if self.current_step == WizardStep.SUBMISSION_TYPE:
            return {
                "has_type": bool(self.step_data.get("submission_type")),
                "has_accreditor": bool(self.step_data.get("accreditor_code")),
            }
        elif self.current_step == WizardStep.STANDARDS:
            return {
                "selected_count": len(self.step_data.get("selected_standards", [])),
                "minimum_required": 1,
            }
        elif self.current_step == WizardStep.EVIDENCE:
            coverage = self._evidence_coverage()
            return {
                "coverage_percent": round(coverage * 100, 1),
                "minimum_required": 80,
                "standards_covered": sum(
                    1 for s in self.step_data.get("selected_standards", [])
                    if self.step_data.get("evidence_mappings", {}).get(s)
                ),
                "standards_total": len(self.step_data.get("selected_standards", [])),
            }
        elif self.current_step == WizardStep.NARRATIVE:
            return {
                "narratives_count": len(self.step_data.get("narratives", {})),
                "sections_available": len(self.step_data.get("selected_standards", [])),
            }
        elif self.current_step == WizardStep.PREVIEW:
            return {
                "ready_to_complete": self._can_proceed(),
            }
        return {}


class PacketWizardService:
    """Service for managing packet wizard sessions."""

    def __init__(self, workspace_manager=None, standards_store=None):
        """Initialize with optional dependencies."""
        self._workspace_manager = workspace_manager
        self._standards_store = standards_store

    def create_session(self, institution_id: str, created_by: str = None) -> WizardSession:
        """Create a new wizard session."""
        session = WizardSession(
            institution_id=institution_id,
            created_by=created_by
        )

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO packet_wizard_sessions
            (id, institution_id, current_step, step_data, status, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session.id, session.institution_id, session.current_step,
              json.dumps(session.step_data), session.status, session.created_at, session.created_by))
        conn.commit()

        return session

    def get_session(self, session_id: str) -> Optional[WizardSession]:
        """Get wizard session by ID."""
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packet_wizard_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None

        return WizardSession(
            id=row["id"],
            institution_id=row["institution_id"],
            packet_id=row["packet_id"],
            current_step=row["current_step"],
            step_data=json.loads(row["step_data"]) if row["step_data"] else {},
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            created_by=row["created_by"]
        )

    def list_sessions(self, institution_id: str, status: str = None) -> List[WizardSession]:
        """List wizard sessions for an institution."""
        conn = get_conn()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                "SELECT * FROM packet_wizard_sessions WHERE institution_id = ? AND status = ? ORDER BY updated_at DESC",
                (institution_id, status)
            )
        else:
            cursor.execute(
                "SELECT * FROM packet_wizard_sessions WHERE institution_id = ? ORDER BY updated_at DESC",
                (institution_id,)
            )

        sessions = []
        for row in cursor.fetchall():
            sessions.append(WizardSession(
                id=row["id"],
                institution_id=row["institution_id"],
                packet_id=row["packet_id"],
                current_step=row["current_step"],
                step_data=json.loads(row["step_data"]) if row["step_data"] else {},
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_at=row["completed_at"],
                created_by=row["created_by"]
            ))
        return sessions

    def update_step(self, session_id: str, step: int, data: Dict[str, Any]) -> WizardSession:
        """Update step data and optionally advance."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        # Merge step data (preserve existing data)
        session.step_data.update(data)
        session.current_step = step
        session.updated_at = now_iso()

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE packet_wizard_sessions
            SET current_step = ?, step_data = ?, updated_at = ?
            WHERE id = ?
        """, (session.current_step, json.dumps(session.step_data), session.updated_at, session_id))
        conn.commit()

        return session

    def abandon_session(self, session_id: str) -> WizardSession:
        """Mark a session as abandoned."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        session.status = "abandoned"
        session.updated_at = now_iso()

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE packet_wizard_sessions
            SET status = 'abandoned', updated_at = ?
            WHERE id = ?
        """, (session.updated_at, session_id))
        conn.commit()

        return session

    def get_submission_types(self) -> List[Dict[str, str]]:
        """Get available submission types."""
        return [
            {
                "id": "self_study",
                "name": "Self-Study Report",
                "description": "Comprehensive self-evaluation for initial/renewal accreditation"
            },
            {
                "id": "response",
                "name": "Team Report Response",
                "description": "Response to visiting team findings"
            },
            {
                "id": "teach_out",
                "name": "Teach-Out Plan",
                "description": "Plan for program closure"
            },
            {
                "id": "annual",
                "name": "Annual Report",
                "description": "Annual compliance update"
            },
            {
                "id": "substantive_change",
                "name": "Substantive Change",
                "description": "Notification of significant changes"
            }
        ]

    def get_standards_tree(self, institution_id: str, accreditor_code: str = None) -> List[Dict]:
        """Get standards tree for selection.

        Returns hierarchical standards structure with selection state.
        """
        conn = get_conn()
        cursor = conn.cursor()

        # Get accreditor
        if not accreditor_code:
            # Default to institution's primary accreditor
            cursor.execute("""
                SELECT accrediting_body FROM institutions WHERE id = ?
            """, (institution_id,))
            row = cursor.fetchone()
            accreditor_code = row["accrediting_body"] if row else "ACCSC"

        # Get standards for accreditor
        cursor.execute("""
            SELECT s.id, s.ref_code, s.title, s.parent_id, s.section_number
            FROM standards s
            JOIN accreditors a ON s.accreditor_id = a.id
            WHERE a.code = ?
            ORDER BY s.section_number, s.ref_code
        """, (accreditor_code,))

        standards = []
        for row in cursor.fetchall():
            standards.append({
                "id": row["id"],
                "ref_code": row["ref_code"],
                "title": row["title"],
                "parent_id": row["parent_id"],
                "section_number": row["section_number"],
            })

        return standards

    def get_evidence_for_standard(self, institution_id: str, standard_id: str) -> List[Dict]:
        """Get available evidence documents for a standard."""
        conn = get_conn()
        cursor = conn.cursor()

        # Get documents with evidence linked to this standard
        cursor.execute("""
            SELECT DISTINCT d.id, d.title, d.doc_type, d.file_path,
                   er.id as evidence_id, er.excerpt, er.page_number
            FROM documents d
            LEFT JOIN evidence_refs er ON er.document_id = d.id
            LEFT JOIN finding_standard_refs fsr ON fsr.finding_id = er.finding_id
            WHERE d.institution_id = ?
              AND (fsr.standard_id = ? OR fsr.standard_id IS NULL)
            ORDER BY d.title
        """, (institution_id, standard_id))

        evidence = []
        for row in cursor.fetchall():
            evidence.append({
                "document_id": row["id"],
                "title": row["title"],
                "doc_type": row["doc_type"],
                "evidence_id": row["evidence_id"],
                "excerpt": row["excerpt"],
                "page_number": row["page_number"],
            })

        return evidence

    def suggest_evidence(self, institution_id: str, standard_id: str) -> List[Dict]:
        """AI-suggest evidence for a standard using semantic search.

        Uses existing document chunks and embeddings to find relevant evidence.
        """
        # This would integrate with semantic search if available
        # For now, return documents that match standard keywords
        conn = get_conn()
        cursor = conn.cursor()

        # Get standard details for keyword matching
        cursor.execute("SELECT ref_code, title FROM standards WHERE id = ?", (standard_id,))
        standard = cursor.fetchone()
        if not standard:
            return []

        # Simple keyword search in document text
        keywords = standard["title"].lower().split()[:5]  # First 5 words
        suggestions = []

        for keyword in keywords:
            cursor.execute("""
                SELECT DISTINCT d.id, d.title, d.doc_type
                FROM documents d
                JOIN document_chunks dc ON dc.document_id = d.id
                WHERE d.institution_id = ?
                  AND LOWER(dc.text) LIKE ?
                LIMIT 5
            """, (institution_id, f"%{keyword}%"))

            for row in cursor.fetchall():
                if row["id"] not in [s["document_id"] for s in suggestions]:
                    suggestions.append({
                        "document_id": row["id"],
                        "title": row["title"],
                        "doc_type": row["doc_type"],
                        "match_keyword": keyword,
                        "suggested": True,
                    })

        return suggestions[:10]  # Limit suggestions

    def generate_narrative(self, session_id: str, section_id: str) -> str:
        """Generate narrative for a section using AI.

        This is a placeholder for AI integration. In production,
        this would call the Narrative Agent.
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        # Get context from session
        submission_type = session.step_data.get("submission_type", "self_study")
        selected_standards = session.step_data.get("selected_standards", [])
        evidence_mappings = session.step_data.get("evidence_mappings", {})

        # Build context for narrative generation
        evidence_for_section = evidence_mappings.get(section_id, [])

        # Placeholder - would call AI in production
        return f"""[Generated narrative for {section_id}]

This section addresses the requirements of {section_id} as part of the {submission_type} submission.

Evidence supporting compliance:
- {len(evidence_for_section)} document(s) mapped to this standard

[AI-generated content would appear here based on mapped evidence and institutional context.]
"""

    def render_preview(self, session_id: str) -> str:
        """Render HTML preview of packet."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        submission_type = session.step_data.get("submission_type", "Submission")
        submission_types = {t["id"]: t["name"] for t in self.get_submission_types()}
        type_name = submission_types.get(submission_type, submission_type)

        # Build preview HTML
        sections_html = self._render_sections(session)
        evidence_count = sum(
            len(v) for v in session.step_data.get("evidence_mappings", {}).values()
        )

        html = f"""
        <div class="packet-preview">
            <div class="preview-header">
                <h1>{type_name}</h1>
                <div class="preview-meta">
                    <span class="meta-item">Standards: {len(session.step_data.get('selected_standards', []))}</span>
                    <span class="meta-item">Evidence Items: {evidence_count}</span>
                    <span class="meta-item">Narratives: {len(session.step_data.get('narratives', {}))}</span>
                </div>
            </div>
            <div class="preview-sections">
                {sections_html}
            </div>
        </div>
        """
        return html

    def _render_sections(self, session: WizardSession) -> str:
        """Render sections HTML for preview."""
        sections = []
        narratives = session.step_data.get("narratives", {})
        evidence_mappings = session.step_data.get("evidence_mappings", {})

        for standard_id in session.step_data.get("selected_standards", []):
            narrative = narratives.get(standard_id, "[No narrative yet]")
            evidence = evidence_mappings.get(standard_id, [])

            evidence_list = ""
            if evidence:
                items = "".join(
                    f'<li>{e.get("title", e.get("document_id", "Document"))}</li>'
                    for e in evidence
                )
                evidence_list = f'<ul class="evidence-list">{items}</ul>'

            sections.append(f"""
            <div class="preview-section">
                <h2>{standard_id}</h2>
                <div class="narrative">{narrative}</div>
                <div class="evidence">
                    <h3>Supporting Evidence</h3>
                    {evidence_list or '<p class="no-evidence">No evidence mapped</p>'}
                </div>
            </div>
            """)

        return "\n".join(sections) if sections else "<p>No sections selected</p>"

    def complete_wizard(self, session_id: str) -> Dict[str, Any]:
        """Complete wizard and create packet."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        # Validate coverage
        coverage = session._evidence_coverage()
        if coverage < 0.8:
            raise ValueError(f"Evidence coverage too low: {coverage:.0%} (80% required)")

        # Create packet record in database
        packet_id = generate_id("pkt")
        conn = get_conn()
        cursor = conn.cursor()

        # Insert packet
        cursor.execute("""
            INSERT INTO submission_packets (id, institution_id, packet_type, title, status, created_at)
            VALUES (?, ?, ?, ?, 'draft', ?)
        """, (
            packet_id,
            session.institution_id,
            session.step_data.get("submission_type", "self_study"),
            session.step_data.get("packet_name", "Submission Packet"),
            now_iso()
        ))

        # Update session
        cursor.execute("""
            UPDATE packet_wizard_sessions
            SET status = 'complete', packet_id = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
        """, (packet_id, now_iso(), now_iso(), session_id))
        conn.commit()

        return {
            "session_id": session_id,
            "packet_id": packet_id,
            "status": "complete",
            "message": "Packet created successfully"
        }


# Module-level singleton for convenience
_service_instance: Optional[PacketWizardService] = None


def get_packet_wizard_service(workspace_manager=None, standards_store=None) -> PacketWizardService:
    """Get or create the packet wizard service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PacketWizardService(workspace_manager, standards_store)
    return _service_instance
