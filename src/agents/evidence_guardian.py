"""Evidence Guardian Agent.

Tier 0 governance agent that validates every compliance claim has:
1. A citation to a specific standard
2. A document snippet pointer (evidence reference)

Blocks compliance determinations without strong evidence.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent


@dataclass
class EvidenceCheck:
    """Result of evidence validation for a claim."""
    claim_id: str
    claim_text: str
    has_standard_citation: bool
    has_document_evidence: bool
    standard_refs: List[str]
    document_refs: List[Dict[str, Any]]
    confidence: float
    is_valid: bool
    issues: List[str]


@register_agent(AgentType.EVIDENCE_GUARDIAN)
class EvidenceGuardianAgent(BaseAgent):
    """Evidence Guardian Agent - Tier 0 Governance.

    Validates every compliance claim has proper evidence grounding.
    Critical for maintaining trust and preventing fabrication.

    Responsibilities:
    - Validate claims have standard citations
    - Validate claims have document snippet pointers
    - Compute evidence completeness scores
    - Block compliance claims without evidence
    - Flag low-confidence determinations for human review
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.EVIDENCE_GUARDIAN

    @property
    def system_prompt(self) -> str:
        return """You are the Evidence Guardian Agent for AccreditAI.

You are a CRITICAL governance agent that protects the integrity of compliance determinations.

YOUR CORE RULE: No compliance claim may be presented to users without:
1. A citation to a specific standard (e.g., "ACCSC Standard 5.2.1")
2. A document snippet pointer showing WHERE the evidence exists

VALIDATION CHECKS:
- Standard citation exists and is valid
- Document reference points to actual indexed content
- Evidence actually supports the claim (not just keyword match)
- Confidence level meets threshold (0.7 minimum)

EVIDENCE SCORING:
- Full evidence: standard + document + high confidence = 1.0
- Partial: standard + document but low confidence = 0.7
- Missing document: standard only = 0.4
- No evidence: 0.0 (BLOCK THIS)

OUTPUT:
- evidence_completeness_score (0.0-1.0)
- blocked_claims (list of claims without evidence)
- flagged_claims (claims needing human review)
- approved_claims (claims with full evidence)

NEVER approve claims without proper evidence grounding."""

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "validate_claim",
                "description": "Validate a single compliance claim has proper evidence",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string"},
                        "claim_text": {"type": "string"},
                        "standard_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Standard citations (e.g., 'ACCSC 5.2.1')"
                        },
                        "document_refs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "document_id": {"type": "string"},
                                    "chunk_id": {"type": "string"},
                                    "snippet": {"type": "string"},
                                    "page": {"type": "integer"}
                                }
                            },
                            "description": "Document evidence references"
                        },
                        "confidence": {"type": "number"}
                    },
                    "required": ["claim_id", "claim_text"]
                }
            },
            {
                "name": "validate_audit_findings",
                "description": "Validate all findings from an audit have proper evidence",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "audit_id": {"type": "string"}
                    },
                    "required": ["institution_id", "audit_id"]
                }
            },
            {
                "name": "get_evidence_score",
                "description": "Calculate evidence completeness score for an institution",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {"type": "string"},
                        "scope": {
                            "type": "string",
                            "enum": ["all", "recent_audit", "program"],
                            "default": "all"
                        },
                        "program_id": {"type": "string"}
                    },
                    "required": ["institution_id"]
                }
            },
            {
                "name": "block_ungrounded_claims",
                "description": "Identify and block claims without evidence grounding",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "claim_id": {"type": "string"},
                                    "claim_text": {"type": "string"},
                                    "standard_refs": {"type": "array"},
                                    "document_refs": {"type": "array"},
                                    "confidence": {"type": "number"}
                                }
                            }
                        }
                    },
                    "required": ["claims"]
                }
            }
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an evidence guardian tool."""
        if tool_name == "validate_claim":
            return self._tool_validate_claim(tool_input)
        elif tool_name == "validate_audit_findings":
            return self._tool_validate_audit(tool_input)
        elif tool_name == "get_evidence_score":
            return self._tool_evidence_score(tool_input)
        elif tool_name == "block_ungrounded_claims":
            return self._tool_block_ungrounded(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_validate_claim(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single claim has proper evidence."""
        claim_id = tool_input.get("claim_id", "")
        claim_text = tool_input.get("claim_text", "")
        standard_refs = tool_input.get("standard_refs", [])
        document_refs = tool_input.get("document_refs", [])
        confidence = tool_input.get("confidence", 0.0)

        issues = []
        has_standard = len(standard_refs) > 0
        has_document = len(document_refs) > 0

        if not has_standard:
            issues.append("Missing standard citation")
        if not has_document:
            issues.append("Missing document evidence reference")
        if confidence < 0.7:
            issues.append(f"Low confidence ({confidence:.2f} < 0.70)")

        # Calculate evidence score
        score = 0.0
        if has_standard and has_document:
            score = min(confidence, 1.0)
        elif has_standard:
            score = 0.4
        elif has_document:
            score = 0.3

        is_valid = has_standard and has_document and confidence >= 0.7

        return {
            "success": True,
            "claim_id": claim_id,
            "is_valid": is_valid,
            "evidence_score": round(score, 2),
            "has_standard_citation": has_standard,
            "has_document_evidence": has_document,
            "confidence": confidence,
            "issues": issues,
            "action": "approved" if is_valid else ("flag_review" if score >= 0.4 else "blocked")
        }

    def _tool_validate_audit(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all findings from an audit."""
        institution_id = tool_input.get("institution_id")
        audit_id = tool_input.get("audit_id")

        # TODO: Load audit findings from workspace and validate each
        return {
            "success": True,
            "institution_id": institution_id,
            "audit_id": audit_id,
            "total_findings": 0,
            "valid_findings": 0,
            "blocked_findings": 0,
            "flagged_findings": 0,
            "evidence_completeness_score": 0.0,
            "message": "Audit validation requires findings data",
            "status": "stub"
        }

    def _tool_evidence_score(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate evidence completeness score."""
        institution_id = tool_input.get("institution_id")
        scope = tool_input.get("scope", "all")

        # TODO: Calculate actual evidence coverage from indexed documents
        return {
            "success": True,
            "institution_id": institution_id,
            "scope": scope,
            "evidence_completeness_score": 0.0,
            "standards_covered": 0,
            "standards_total": 0,
            "documents_indexed": 0,
            "evidence_gaps": [],
            "message": "Evidence scoring requires indexed documents",
            "status": "stub"
        }

    def _tool_block_ungrounded(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Identify and block ungrounded claims."""
        claims = tool_input.get("claims", [])

        approved = []
        flagged = []
        blocked = []

        for claim in claims:
            result = self._tool_validate_claim(claim)
            action = result.get("action")

            if action == "approved":
                approved.append(result)
            elif action == "flag_review":
                flagged.append(result)
            else:
                blocked.append(result)

        return {
            "success": True,
            "total_claims": len(claims),
            "approved_count": len(approved),
            "flagged_count": len(flagged),
            "blocked_count": len(blocked),
            "approved_claims": approved,
            "flagged_claims": flagged,
            "blocked_claims": blocked,
            "can_proceed": len(blocked) == 0
        }


def validate_evidence(
    claim_text: str,
    standard_refs: List[str],
    document_refs: List[Dict[str, Any]],
    confidence: float = 0.0
) -> Dict[str, Any]:
    """Utility function to validate evidence without agent context.

    Use this in other agents to quickly check evidence grounding.

    Args:
        claim_text: The compliance claim being made
        standard_refs: List of standard citations
        document_refs: List of document evidence references
        confidence: Confidence level (0.0-1.0)

    Returns:
        Validation result dict with is_valid, score, and issues
    """
    has_standard = len(standard_refs) > 0
    has_document = len(document_refs) > 0
    issues = []

    if not has_standard:
        issues.append("Missing standard citation")
    if not has_document:
        issues.append("Missing document evidence")
    if confidence < 0.7:
        issues.append(f"Low confidence: {confidence:.2f}")

    score = 0.0
    if has_standard and has_document:
        score = min(confidence, 1.0)
    elif has_standard:
        score = 0.4

    return {
        "is_valid": has_standard and has_document and confidence >= 0.7,
        "evidence_score": round(score, 2),
        "issues": issues
    }
