"""Advertising Scanner Agent.

Scans marketing materials (websites, brochures, catalogs) for compliance with
FTC advertising rules, accreditor standards, and accuracy against achievement data.
Detects misleading claims, unsubstantiated assertions, and missing disclosures.
"""

import hashlib
import json
import logging
import re
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urlparse

import requests

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import AgentSession, generate_id, now_iso
from src.config import Config
from src.db.connection import get_conn

logger = logging.getLogger(__name__)


# Claim extraction patterns (regex-based first pass)
CLAIM_PATTERNS = {
    "completion_rate": [
        r"(\d+(?:\.\d+)?)\s*%?\s*(?:completion|graduation|finish)\s*rate",
        r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s+)?(?:students?|graduates?)\s*(?:complete|graduate|finish)",
        r"(?:completion|graduation)\s*rate\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*%",
    ],
    "placement_rate": [
        r"(\d+(?:\.\d+)?)\s*%?\s*(?:placement|employment|job)\s*rate",
        r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s+)?(?:graduates?)\s*(?:find|get|secure|obtain)\s*(?:jobs?|employment)",
        r"(?:placement|employment)\s*rate\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*%",
    ],
    "licensure_rate": [
        r"(\d+(?:\.\d+)?)\s*%?\s*(?:licensure|pass|passing)\s*rate",
        r"(\d+(?:\.\d+)?)\s*%\s*pass\s*(?:the\s+)?(?:state\s+)?(?:board|exam|licensure)",
        r"(?:licensure|exam)\s*(?:pass\s+)?rate\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*%",
    ],
    "salary": [
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:k|K)?\s*(?:per\s+year|annually|salary|starting)?",
        r"earn(?:ing)?\s*(?:up\s+to\s+)?\$\s*(\d{1,3}(?:,\d{3})*)",
        r"(?:salary|income|wages?)\s*(?:of\s+)?\$\s*(\d{1,3}(?:,\d{3})*)",
    ],
    "program_length": [
        r"(?:complete|finish|graduate)\s*(?:in\s+)?(?:just\s+)?(\d+)\s*(weeks?|months?|years?)",
        r"(\d+)[\s-]*(week|month|year)\s*program",
        r"(?:as\s+(?:few|little)\s+as\s+)?(\d+)\s*(weeks?|months?)",
    ],
    "cost": [
        r"(?:tuition|cost|price)\s*(?:of\s+)?\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)",
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:total\s+)?(?:tuition|cost|program)",
        r"(?:only|just)\s*\$\s*(\d{1,3}(?:,\d{3})*)",
    ],
}

# Prohibited claim patterns (always violations)
PROHIBITED_PATTERNS = [
    (r"guarantee[ds]?\s+(?:a\s+)?(?:job|employment|placement)", "Employment guarantees are prohibited"),
    (r"100\s*%\s*(?:job\s+)?placement", "100% placement claims require extraordinary substantiation"),
    (r"(?:best|top|#1|number\s+one)\s+(?:school|program|institution)", "Superlative claims require substantiation"),
]

# Regulatory rules reference
ADVERTISING_RULES = {
    "FTC-5": {
        "title": "FTC Act Section 5 - Unfair or Deceptive Acts",
        "source": "federal_ftc",
        "description": "Claims must be truthful, substantiated, and not misleading",
    },
    "FTC-ENDORSEMENT": {
        "title": "FTC Endorsement Guides",
        "source": "federal_ftc",
        "description": "Testimonials must reflect typical experience; material connections disclosed",
    },
    "ACCSC-I.B.1": {
        "title": "ACCSC Section I.B.1 - Advertising and Promotion",
        "source": "accreditor",
        "description": "No guarantee of employment; rates must match annual report data",
    },
    "ABHES-VI.A": {
        "title": "ABHES Chapter VI.A - Advertising Standards",
        "source": "accreditor",
        "description": "Advertising must be accurate, not misleading, and substantiated",
    },
    "COE-ADVERTISING": {
        "title": "COE Advertising Requirements",
        "source": "accreditor",
        "description": "Outcomes must match reported data within reasonable tolerance",
    },
}

# Accreditor benchmarks for rate verification
ACCREDITOR_BENCHMARKS = {
    "ACCSC": {"completion": 67, "placement": 70, "licensure": 70},
    "ABHES": {"completion": 67, "placement": 70, "licensure": 70},
    "COE": {"completion": 60, "placement": 70, "licensure": 70},
}


SYSTEM_PROMPT = """You are the Advertising Compliance Scanner for AccreditAI.

Your role is to scan marketing materials (websites, brochures, catalogs) for advertising compliance violations.

SCAN PROCESS:
1. Extract all claims about student outcomes, costs, program length, credentials
2. Categorize each claim by type (rate, cost, credential, etc.)
3. Verify numeric claims against achievement data
4. Check for regulatory violations (FTC, accreditor rules)
5. Generate findings with specific remediation guidance

CLAIM TYPES TO IDENTIFY:
- Completion/graduation rates
- Placement/employment rates
- Licensure/exam pass rates
- Salary/earning claims
- Program length/duration
- Cost/tuition claims
- Credential/degree claims
- Accreditation status claims
- Testimonials/endorsements

REGULATORY REQUIREMENTS:
- FTC Act Section 5: No false or misleading claims
- FTC Endorsement Guides: Testimonials must be typical
- Accreditor standards: Rates must match reported data
- Gainful Employment: Required disclosures

VERIFICATION RULES:
- Rate claims must match achievement data within 2% tolerance
- Cost claims must match current catalog/enrollment agreement
- "100%" rate claims require extra scrutiny
- Guarantee language ("guaranteed job") is always a violation
- Superlatives ("best", "#1") require substantiation

SAFETY RULES:
- NEVER fabricate evidence or compliance claims
- Flag low confidence findings (<0.7) for human review
- Be conservative - prefer false positives over missed violations
- Always cite the specific text containing the claim
"""


@register_agent(AgentType.ADVERTISING_SCANNER)
class AdvertisingScannerAgent(BaseAgent):
    """Agent for scanning advertising materials for compliance violations."""

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update: Optional[Callable[[AgentSession], None]] = None,
    ):
        super().__init__(session, workspace_manager, on_update)
        self._achievement_cache: Dict[str, Any] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ADVERTISING_SCANNER

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "scan_url",
                "description": "Fetch and scan a web page for advertising compliance. Returns extracted text and initiates claim analysis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID to verify claims against",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL of the web page to scan",
                        },
                        "scan_id": {
                            "type": "string",
                            "description": "Existing scan ID to update, or omit to create new",
                        },
                    },
                    "required": ["institution_id", "url"],
                },
            },
            {
                "name": "scan_document",
                "description": "Scan an uploaded marketing document for advertising compliance.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID",
                        },
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to scan",
                        },
                        "scan_id": {
                            "type": "string",
                            "description": "Existing scan ID to update, or omit to create new",
                        },
                    },
                    "required": ["institution_id", "document_id"],
                },
            },
            {
                "name": "extract_claims",
                "description": "Extract advertising claims from text content using pattern matching and semantic analysis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text content to extract claims from",
                        },
                        "source_type": {
                            "type": "string",
                            "enum": ["url", "document"],
                            "description": "Source type for context",
                        },
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "verify_claim",
                "description": "Verify a specific claim against achievement data and regulatory requirements.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID",
                        },
                        "claim_type": {
                            "type": "string",
                            "enum": [
                                "completion_rate",
                                "placement_rate",
                                "licensure_rate",
                                "salary",
                                "program_length",
                                "cost",
                                "credential",
                                "accreditation",
                            ],
                            "description": "Type of claim being verified",
                        },
                        "claim_text": {
                            "type": "string",
                            "description": "Exact text of the claim",
                        },
                        "claimed_value": {
                            "type": "string",
                            "description": "The value being claimed (e.g., '95%', '$45,000')",
                        },
                        "program_id": {
                            "type": "string",
                            "description": "Program ID if claim is program-specific",
                        },
                    },
                    "required": ["institution_id", "claim_type", "claim_text"],
                },
            },
            {
                "name": "save_finding",
                "description": "Save an advertising finding to the scan results.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "string",
                            "description": "Scan ID to add finding to",
                        },
                        "claim_type": {
                            "type": "string",
                            "description": "Type of claim",
                        },
                        "claim_text": {
                            "type": "string",
                            "description": "Exact claim text",
                        },
                        "finding_type": {
                            "type": "string",
                            "enum": ["violation", "warning", "verified", "unverifiable"],
                            "description": "Finding classification",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "significant", "advisory", "informational"],
                            "description": "Severity level",
                        },
                        "regulation_code": {
                            "type": "string",
                            "description": "Regulatory code (e.g., 'FTC-5', 'ACCSC-I.B.1')",
                        },
                        "claimed_value": {
                            "type": "string",
                            "description": "Value stated in claim",
                        },
                        "verified_value": {
                            "type": "string",
                            "description": "Actual verified value",
                        },
                        "recommendation": {
                            "type": "string",
                            "description": "Remediation recommendation",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score (0-1)",
                        },
                    },
                    "required": ["scan_id", "claim_type", "claim_text", "finding_type"],
                },
            },
            {
                "name": "complete_scan",
                "description": "Finalize a scan, calculate compliance score, and generate summary.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "string",
                            "description": "Scan ID to complete",
                        },
                    },
                    "required": ["scan_id"],
                },
            },
            {
                "name": "get_achievement_data",
                "description": "Get achievement data for claim verification.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID",
                        },
                        "program_id": {
                            "type": "string",
                            "description": "Program ID (optional, for program-specific data)",
                        },
                    },
                    "required": ["institution_id"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool calls to implementations."""
        tool_map = {
            "scan_url": self._tool_scan_url,
            "scan_document": self._tool_scan_document,
            "extract_claims": self._tool_extract_claims,
            "verify_claim": self._tool_verify_claim,
            "save_finding": self._tool_save_finding,
            "complete_scan": self._tool_complete_scan,
            "get_achievement_data": self._tool_get_achievement_data,
        }
        handler = tool_map.get(tool_name)
        if handler:
            return handler(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_scan_url(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch and scan a web page."""
        institution_id = tool_input.get("institution_id")
        url = tool_input.get("url")
        scan_id = tool_input.get("scan_id")

        if not institution_id or not url:
            return {"error": "institution_id and url are required"}

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {"error": "Invalid URL format"}
        except Exception as e:
            return {"error": f"Invalid URL: {e}"}

        # Create or update scan record
        conn = get_conn()
        if not scan_id:
            scan_id = generate_id("adscan")
            conn.execute(
                """
                INSERT INTO advertising_scans
                (id, institution_id, scan_type, source_url, title, status, started_at, created_at)
                VALUES (?, ?, 'url', ?, ?, 'running', datetime('now'), datetime('now'))
                """,
                (scan_id, institution_id, url, f"Web Scan: {parsed.netloc}"),
            )
            conn.commit()
        else:
            conn.execute(
                "UPDATE advertising_scans SET status = 'running', started_at = datetime('now') WHERE id = ?",
                (scan_id,),
            )
            conn.commit()

        # Fetch URL content
        try:
            headers = {
                "User-Agent": "AccreditAI Advertising Scanner/1.0 (Compliance Verification)"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            content = response.text

            # Extract text from HTML (simple extraction)
            text = self._extract_text_from_html(content)
            content_hash = hashlib.sha256(text.encode()).hexdigest()

            # Store content
            conn.execute(
                "UPDATE advertising_scans SET raw_content = ?, content_hash = ? WHERE id = ?",
                (text, content_hash, scan_id),
            )
            conn.commit()

            return {
                "success": True,
                "scan_id": scan_id,
                "url": url,
                "content_length": len(text),
                "content_hash": content_hash,
                "text_preview": text[:1000] + "..." if len(text) > 1000 else text,
            }

        except requests.RequestException as e:
            conn.execute(
                "UPDATE advertising_scans SET status = 'failed', error_message = ? WHERE id = ?",
                (str(e), scan_id),
            )
            conn.commit()
            return {"error": f"Failed to fetch URL: {e}", "scan_id": scan_id}

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from HTML content."""
        # Remove script and style elements
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Decode HTML entities
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _tool_scan_document(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Scan an uploaded document."""
        institution_id = tool_input.get("institution_id")
        document_id = tool_input.get("document_id")
        scan_id = tool_input.get("scan_id")

        if not institution_id or not document_id:
            return {"error": "institution_id and document_id are required"}

        # Load document from workspace
        if not self.workspace_manager:
            return {"error": "Workspace manager not available"}

        # Try to load parsed document content
        doc_path = f"documents/{document_id}.json"
        doc_data = self.workspace_manager.load_file(institution_id, doc_path)
        if not doc_data:
            return {"error": f"Document {document_id} not found"}

        text = doc_data.get("text", "") or doc_data.get("content", "")
        if not text:
            return {"error": "Document has no extractable text"}

        # Create scan record
        conn = get_conn()
        if not scan_id:
            scan_id = generate_id("adscan")
            conn.execute(
                """
                INSERT INTO advertising_scans
                (id, institution_id, scan_type, document_id, title, status, started_at, created_at)
                VALUES (?, ?, 'document', ?, ?, 'running', datetime('now'), datetime('now'))
                """,
                (scan_id, institution_id, document_id, f"Document Scan: {doc_data.get('name', document_id)}"),
            )
        else:
            conn.execute(
                "UPDATE advertising_scans SET status = 'running', started_at = datetime('now') WHERE id = ?",
                (scan_id,),
            )

        content_hash = hashlib.sha256(text.encode()).hexdigest()
        conn.execute(
            "UPDATE advertising_scans SET raw_content = ?, content_hash = ? WHERE id = ?",
            (text, content_hash, scan_id),
        )
        conn.commit()

        return {
            "success": True,
            "scan_id": scan_id,
            "document_id": document_id,
            "content_length": len(text),
            "content_hash": content_hash,
            "text_preview": text[:1000] + "..." if len(text) > 1000 else text,
        }

    def _tool_extract_claims(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Extract claims from text using pattern matching."""
        text = tool_input.get("text", "")
        if not text:
            return {"error": "text is required"}

        claims = []
        text_lower = text.lower()

        # Extract claims using patterns
        for claim_type, patterns in CLAIM_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text_lower):
                    # Get surrounding context
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]

                    claims.append({
                        "claim_type": claim_type,
                        "claim_text": match.group(0),
                        "claimed_value": match.group(1) if match.groups() else None,
                        "context": context,
                        "position": match.start(),
                    })

        # Check for prohibited patterns
        prohibited_findings = []
        for pattern, reason in PROHIBITED_PATTERNS:
            for match in re.finditer(pattern, text_lower):
                prohibited_findings.append({
                    "claim_type": "prohibited",
                    "claim_text": match.group(0),
                    "reason": reason,
                    "position": match.start(),
                })

        return {
            "success": True,
            "claims_found": len(claims),
            "prohibited_found": len(prohibited_findings),
            "claims": claims,
            "prohibited": prohibited_findings,
        }

    def _tool_verify_claim(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a claim against achievement data."""
        institution_id = tool_input.get("institution_id")
        claim_type = tool_input.get("claim_type")
        claim_text = tool_input.get("claim_text")
        claimed_value = tool_input.get("claimed_value")
        program_id = tool_input.get("program_id")

        if not institution_id or not claim_type or not claim_text:
            return {"error": "institution_id, claim_type, and claim_text are required"}

        # Get achievement data
        achievement_data = self._load_achievement_data(institution_id)
        if not achievement_data:
            return {
                "verified": False,
                "finding_type": "unverifiable",
                "reason": "No achievement data available for verification",
                "confidence": 0.3,
            }

        # Rate claims verification
        if claim_type in ["completion_rate", "placement_rate", "licensure_rate"]:
            return self._verify_rate_claim(
                claim_type, claimed_value, achievement_data, program_id
            )

        # For other claim types, return unverifiable
        return {
            "verified": False,
            "finding_type": "unverifiable",
            "reason": f"Verification for {claim_type} claims requires manual review",
            "confidence": 0.5,
        }

    def _verify_rate_claim(
        self,
        claim_type: str,
        claimed_value: str,
        achievement_data: Dict[str, Any],
        program_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a rate claim against achievement data."""
        # Parse claimed value
        try:
            claimed_rate = float(re.sub(r"[^\d.]", "", claimed_value or "0"))
        except ValueError:
            return {
                "verified": False,
                "finding_type": "unverifiable",
                "reason": "Could not parse claimed rate value",
                "confidence": 0.3,
            }

        # Map claim type to achievement field
        field_map = {
            "completion_rate": "completion_rate",
            "placement_rate": "placement_rate",
            "licensure_rate": "licensure_rate",
        }
        field = field_map.get(claim_type)

        programs = achievement_data.get("programs", {})
        if program_id and program_id in programs:
            # Check specific program
            program_data = programs[program_id]
            years = program_data.get("years", {})
            if years:
                latest_year = max(years.keys())
                actual_rate = years[latest_year].get(field, 0)
                return self._compare_rates(claimed_rate, actual_rate, latest_year)
        else:
            # Check institution-wide (average across programs)
            all_rates = []
            for prog_id, prog_data in programs.items():
                years = prog_data.get("years", {})
                if years:
                    latest_year = max(years.keys())
                    rate = years[latest_year].get(field)
                    if rate is not None:
                        all_rates.append(rate)

            if all_rates:
                avg_rate = sum(all_rates) / len(all_rates)
                return self._compare_rates(claimed_rate, avg_rate, "institution average")

        return {
            "verified": False,
            "finding_type": "unverifiable",
            "reason": "No matching achievement data found",
            "confidence": 0.4,
        }

    def _compare_rates(
        self, claimed: float, actual: float, source: str
    ) -> Dict[str, Any]:
        """Compare claimed rate to actual rate."""
        variance = claimed - actual
        tolerance = 2.0  # 2% tolerance

        if abs(variance) <= tolerance:
            return {
                "verified": True,
                "finding_type": "verified",
                "claimed_value": f"{claimed}%",
                "verified_value": f"{actual:.1f}%",
                "variance": variance,
                "source": source,
                "confidence": 0.9,
            }
        elif variance > tolerance:
            # Overclaiming
            severity = "critical" if variance > 10 else "significant"
            return {
                "verified": False,
                "finding_type": "violation",
                "severity": severity,
                "claimed_value": f"{claimed}%",
                "verified_value": f"{actual:.1f}%",
                "variance": variance,
                "source": source,
                "reason": f"Claimed rate exceeds actual by {variance:.1f}%",
                "regulation_code": "FTC-5",
                "confidence": 0.85,
            }
        else:
            # Underclaiming (warning, not violation)
            return {
                "verified": True,
                "finding_type": "verified",
                "claimed_value": f"{claimed}%",
                "verified_value": f"{actual:.1f}%",
                "variance": variance,
                "source": source,
                "note": "Claimed rate is conservative (lower than actual)",
                "confidence": 0.9,
            }

    def _load_achievement_data(self, institution_id: str) -> Optional[Dict[str, Any]]:
        """Load achievement data from workspace."""
        if institution_id in self._achievement_cache:
            return self._achievement_cache[institution_id]

        if not self.workspace_manager:
            return None

        data = self.workspace_manager.load_file(
            institution_id, "achievements/achievement_data.json"
        )
        if data:
            self._achievement_cache[institution_id] = data
        return data

    def _tool_save_finding(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Save a finding to the database."""
        scan_id = tool_input.get("scan_id")
        if not scan_id:
            return {"error": "scan_id is required"}

        finding_id = generate_id("adfind")
        conn = get_conn()

        # Get regulation details
        regulation_code = tool_input.get("regulation_code", "")
        regulation_info = ADVERTISING_RULES.get(regulation_code, {})

        conn.execute(
            """
            INSERT INTO advertising_findings
            (id, scan_id, claim_type, claim_text, claim_context, finding_type, severity,
             regulation_code, regulation_title, regulatory_source,
             claimed_value, verified_value, variance, recommendation, confidence,
             requires_human_review, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                finding_id,
                scan_id,
                tool_input.get("claim_type", ""),
                tool_input.get("claim_text", ""),
                tool_input.get("claim_context", ""),
                tool_input.get("finding_type", "unverifiable"),
                tool_input.get("severity"),
                regulation_code,
                regulation_info.get("title", ""),
                regulation_info.get("source", ""),
                tool_input.get("claimed_value"),
                tool_input.get("verified_value"),
                tool_input.get("variance"),
                tool_input.get("recommendation", ""),
                tool_input.get("confidence", 0.5),
                1 if tool_input.get("confidence", 0.5) < 0.7 else 0,
            ),
        )
        conn.commit()

        return {"success": True, "finding_id": finding_id}

    def _tool_complete_scan(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Complete a scan and calculate scores."""
        scan_id = tool_input.get("scan_id")
        if not scan_id:
            return {"error": "scan_id is required"}

        conn = get_conn()

        # Get findings summary
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN finding_type = 'verified' THEN 1 ELSE 0 END) as verified,
                SUM(CASE WHEN finding_type = 'violation' THEN 1 ELSE 0 END) as violations,
                SUM(CASE WHEN finding_type = 'warning' THEN 1 ELSE 0 END) as warnings,
                SUM(CASE WHEN finding_type = 'unverifiable' THEN 1 ELSE 0 END) as unverifiable
            FROM advertising_findings WHERE scan_id = ?
            """,
            (scan_id,),
        )
        row = cursor.fetchone()

        total = row["total"] or 0
        verified = row["verified"] or 0
        violations = row["violations"] or 0
        warnings = row["warnings"] or 0
        unverifiable = row["unverifiable"] or 0

        # Calculate compliance score
        if total > 0:
            # Score: 100 - (violations * 20) - (warnings * 5) - (unverifiable * 2)
            score = max(0, min(100, 100 - (violations * 20) - (warnings * 5) - (unverifiable * 2)))
        else:
            score = 100  # No claims found = no violations

        # Determine risk level
        if violations > 3 or score < 50:
            risk_level = "critical"
        elif violations > 0 or score < 70:
            risk_level = "high"
        elif warnings > 2 or score < 85:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Update scan record
        conn.execute(
            """
            UPDATE advertising_scans SET
                status = 'completed',
                completed_at = datetime('now'),
                total_claims = ?,
                verified_claims = ?,
                unverified_claims = ?,
                violation_count = ?,
                warning_count = ?,
                compliance_score = ?,
                risk_level = ?
            WHERE id = ?
            """,
            (total, verified, unverifiable, violations, warnings, score, risk_level, scan_id),
        )
        conn.commit()

        return {
            "success": True,
            "scan_id": scan_id,
            "status": "completed",
            "summary": {
                "total_claims": total,
                "verified": verified,
                "violations": violations,
                "warnings": warnings,
                "unverifiable": unverifiable,
                "compliance_score": score,
                "risk_level": risk_level,
            },
        }

    def _tool_get_achievement_data(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Get achievement data for an institution."""
        institution_id = tool_input.get("institution_id")
        program_id = tool_input.get("program_id")

        if not institution_id:
            return {"error": "institution_id is required"}

        data = self._load_achievement_data(institution_id)
        if not data:
            return {
                "success": False,
                "error": "No achievement data found",
                "institution_id": institution_id,
            }

        if program_id:
            program_data = data.get("programs", {}).get(program_id)
            if program_data:
                return {
                    "success": True,
                    "institution_id": institution_id,
                    "program_id": program_id,
                    "data": program_data,
                }
            return {
                "success": False,
                "error": f"No data for program {program_id}",
            }

        return {
            "success": True,
            "institution_id": institution_id,
            "programs": list(data.get("programs", {}).keys()),
            "data": data,
        }
