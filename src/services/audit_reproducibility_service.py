"""Audit Reproducibility Service - Capture full context for defensible audits."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.config import Config
from src.db.connection import get_conn


def _hash_text(text: str) -> str:
    """Generate SHA-256 hash of text."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _hash_dict(data: Dict) -> str:
    """Generate hash of dictionary."""
    return _hash_text(json.dumps(data, sort_keys=True))


@dataclass
class AuditSnapshot:
    """Complete snapshot of audit execution context."""
    id: str = field(default_factory=lambda: f"snap_{uuid4().hex[:12]}")
    audit_run_id: str = ""
    institution_id: str = ""

    # Model info
    model_id: str = ""
    model_version: Optional[str] = None
    api_version: Optional[str] = None

    # Prompts
    system_prompt_hash: Optional[str] = None
    system_prompt: Optional[str] = None
    tool_definitions_hash: Optional[str] = None

    # Document state
    document_hashes: Dict[str, str] = field(default_factory=dict)
    truth_index_hash: Optional[str] = None

    # Standards
    accreditor_code: Optional[str] = None
    standards_version: Optional[str] = None
    standards_hash: Optional[str] = None

    # Config
    confidence_threshold: float = 0.7
    agent_config: Dict[str, Any] = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "audit_run_id": self.audit_run_id,
            "institution_id": self.institution_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "system_prompt_hash": self.system_prompt_hash,
            "document_hashes": self.document_hashes,
            "accreditor_code": self.accreditor_code,
            "confidence_threshold": self.confidence_threshold,
            "created_at": self.created_at,
        }


@dataclass
class FindingProvenance:
    """Provenance record for a single finding."""
    id: str = field(default_factory=lambda: f"prov_{uuid4().hex[:12]}")
    finding_id: str = ""
    audit_snapshot_id: str = ""
    prompt_hash: Optional[str] = None
    prompt_text: Optional[str] = None
    response_hash: Optional[str] = None
    response_text: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    evidence_chunk_hashes: List[str] = field(default_factory=list)
    reasoning_steps: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "audit_snapshot_id": self.audit_snapshot_id,
            "prompt_hash": self.prompt_hash,
            "response_hash": self.response_hash,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "evidence_chunk_hashes": self.evidence_chunk_hashes,
            "reasoning_steps": self.reasoning_steps,
        }


def capture_audit_snapshot(
    audit_run_id: str,
    institution_id: str,
    system_prompt: str,
    tool_definitions: List[Dict],
    accreditor_code: str,
    conn: Optional[sqlite3.Connection] = None
) -> AuditSnapshot:
    """
    Capture complete snapshot of audit context before execution.

    Args:
        audit_run_id: ID of the audit run
        institution_id: Institution being audited
        system_prompt: Agent system prompt
        tool_definitions: List of tool schemas
        accreditor_code: Accreditor code (e.g., "ACCSC")

    Returns:
        AuditSnapshot with all context captured
    """
    conn = conn or get_conn()

    snapshot = AuditSnapshot(
        audit_run_id=audit_run_id,
        institution_id=institution_id,
        model_id=Config.MODEL,
        model_version=getattr(Config, 'MODEL_VERSION', None),
        system_prompt=system_prompt,
        system_prompt_hash=_hash_text(system_prompt),
        tool_definitions_hash=_hash_dict({"tools": tool_definitions}),
        accreditor_code=accreditor_code,
        confidence_threshold=Config.AGENT_CONFIDENCE_THRESHOLD,
    )

    # Capture document hashes
    try:
        cursor = conn.execute("""
            SELECT id, file_sha256
            FROM documents
            WHERE institution_id = ?
              AND status = 'indexed'
        """, (institution_id,))
        snapshot.document_hashes = {
            row["id"]: row["file_sha256"]
            for row in cursor.fetchall()
        }
    except sqlite3.OperationalError:
        pass

    # Capture truth index hash
    try:
        cursor = conn.execute("""
            SELECT key, value
            FROM truth_index
            WHERE institution_id = ?
            ORDER BY key
        """, (institution_id,))
        truth_data = {row["key"]: row["value"] for row in cursor.fetchall()}
        snapshot.truth_index_hash = _hash_dict(truth_data)
    except sqlite3.OperationalError:
        pass

    return snapshot


def save_audit_snapshot(
    snapshot: AuditSnapshot,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Persist audit snapshot to database."""
    conn = conn or get_conn()

    conn.execute("""
        INSERT INTO audit_snapshots (
            id, audit_run_id, institution_id,
            model_id, model_version, api_version,
            system_prompt_hash, system_prompt, tool_definitions_hash,
            document_hashes, truth_index_hash,
            accreditor_code, standards_version, standards_hash,
            confidence_threshold, agent_config
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot.id, snapshot.audit_run_id, snapshot.institution_id,
        snapshot.model_id, snapshot.model_version, snapshot.api_version,
        snapshot.system_prompt_hash, snapshot.system_prompt, snapshot.tool_definitions_hash,
        json.dumps(snapshot.document_hashes), snapshot.truth_index_hash,
        snapshot.accreditor_code, snapshot.standards_version, snapshot.standards_hash,
        snapshot.confidence_threshold, json.dumps(snapshot.agent_config),
    ))
    conn.commit()

    return snapshot.id


def record_finding_provenance(
    finding_id: str,
    snapshot_id: str,
    prompt: str,
    response: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    evidence_hashes: Optional[List[str]] = None,
    reasoning: Optional[List[str]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """Record provenance for a single finding."""
    conn = conn or get_conn()

    prov = FindingProvenance(
        finding_id=finding_id,
        audit_snapshot_id=snapshot_id,
        prompt_hash=_hash_text(prompt),
        prompt_text=prompt,
        response_hash=_hash_text(response),
        response_text=response,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        evidence_chunk_hashes=evidence_hashes or [],
        reasoning_steps=reasoning or [],
    )

    conn.execute("""
        INSERT INTO finding_provenance (
            id, finding_id, audit_snapshot_id,
            prompt_hash, prompt_text, response_hash, response_text,
            input_tokens, output_tokens,
            evidence_chunk_hashes, reasoning_steps
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prov.id, prov.finding_id, prov.audit_snapshot_id,
        prov.prompt_hash, prov.prompt_text, prov.response_hash, prov.response_text,
        prov.input_tokens, prov.output_tokens,
        json.dumps(prov.evidence_chunk_hashes), json.dumps(prov.reasoning_steps),
    ))
    conn.commit()

    return prov.id


def get_audit_snapshot(
    audit_run_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[AuditSnapshot]:
    """Retrieve audit snapshot by run ID."""
    conn = conn or get_conn()

    try:
        cursor = conn.execute(
            "SELECT * FROM audit_snapshots WHERE audit_run_id = ?",
            (audit_run_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return AuditSnapshot(
            id=row["id"],
            audit_run_id=row["audit_run_id"],
            institution_id=row["institution_id"],
            model_id=row["model_id"],
            model_version=row["model_version"],
            system_prompt_hash=row["system_prompt_hash"],
            system_prompt=row["system_prompt"],
            document_hashes=json.loads(row["document_hashes"] or "{}"),
            truth_index_hash=row["truth_index_hash"],
            accreditor_code=row["accreditor_code"],
            confidence_threshold=row["confidence_threshold"],
            created_at=row["created_at"],
        )
    except sqlite3.OperationalError:
        return None


def verify_audit_reproducibility(
    audit_run_id: str,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Verify if an audit can be reproduced with current state.

    Returns dict with verification status and any discrepancies.
    """
    conn = conn or get_conn()
    snapshot = get_audit_snapshot(audit_run_id, conn)

    if not snapshot:
        return {"verified": False, "error": "Snapshot not found"}

    discrepancies = []

    # Check model
    if snapshot.model_id != Config.MODEL:
        discrepancies.append({
            "type": "model",
            "expected": snapshot.model_id,
            "current": Config.MODEL,
        })

    # Check document hashes
    try:
        cursor = conn.execute("""
            SELECT id, file_sha256
            FROM documents
            WHERE institution_id = ?
              AND status = 'indexed'
        """, (snapshot.institution_id,))

        current_hashes = {row["id"]: row["file_sha256"] for row in cursor.fetchall()}

        for doc_id, expected_hash in snapshot.document_hashes.items():
            current = current_hashes.get(doc_id)
            if current != expected_hash:
                discrepancies.append({
                    "type": "document",
                    "document_id": doc_id,
                    "expected": expected_hash[:12],
                    "current": current[:12] if current else None,
                })
    except sqlite3.OperationalError:
        pass

    return {
        "verified": len(discrepancies) == 0,
        "snapshot_id": snapshot.id,
        "created_at": snapshot.created_at,
        "discrepancies": discrepancies,
    }
