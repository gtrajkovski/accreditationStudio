"""Ingestion Agent for document processing pipeline.

Orchestrates:
- Document parsing (PDF, DOCX, text, images)
- Document type classification
- Metadata extraction (dates, costs, program names)
- Language detection (EN, ES, BILINGUAL)
- PII detection and redaction
- Chunking for vector storage
- Workspace persistence
"""

import re
from typing import Dict, Any, List, Optional, Callable, Generator
from pathlib import Path

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import register_agent
from src.core.models import (
    AgentSession,
    Document,
    DocumentType,
    Language,
    generate_id,
    now_iso,
)
from src.config import Config
from src.importers import (
    parse_document,
    ParsedDocument,
    detect_pii,
    redact_pii,
    PIIMatch,
    chunk_document,
    ChunkedDocument,
)


# Language detection word lists
SPANISH_INDICATORS = [
    "el", "la", "de", "que", "en", "los", "del", "las", "un", "por",
    "con", "para", "una", "su", "al", "es", "lo", "como", "más", "pero",
    "sus", "le", "ya", "o", "este", "si", "porque", "esta", "entre",
    "cuando", "muy", "sin", "sobre", "también", "me", "hasta", "hay",
    "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno",
    "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e",
    "esto", "mi", "antes", "algunos", "qué", "unos", "yo", "otro",
    "estudiante", "programa", "institución", "política", "matrícula",
]

ENGLISH_INDICATORS = [
    "the", "and", "of", "to", "in", "for", "is", "that", "it", "with",
    "as", "was", "on", "are", "be", "by", "at", "this", "have", "from",
    "or", "an", "they", "which", "one", "you", "were", "all", "her",
    "she", "there", "would", "their", "we", "him", "been", "has", "when",
    "who", "will", "no", "more", "if", "out", "so", "up", "said", "what",
    "its", "about", "than", "into", "them", "can", "only", "other", "new",
    "student", "program", "institution", "policy", "enrollment", "tuition",
]


SYSTEM_PROMPT = """You are the Ingestion Agent for AccreditAI, responsible for processing uploaded documents for accreditation compliance analysis.

Your role is to:
1. Parse documents to extract text and structure
2. Classify documents into the correct document type
3. Extract key metadata (effective dates, program names, costs, revision dates)
4. Detect the document language (English, Spanish, or Bilingual)
5. Identify and flag PII for redaction
6. Chunk documents for vector storage and semantic search

DOCUMENT TYPES (use exact values):
- enrollment_agreement: Student contracts with program costs, schedules, refund policies, signature blocks
- catalog: Institutional catalog with program descriptions, policies, faculty lists, academic calendars
- student_handbook: Student policies, conduct codes, grievance procedures, academic policies
- admissions_manual: Admissions criteria, enrollment processes, documentation requirements
- faculty_handbook: Faculty policies, evaluation procedures, professional development
- policy_manual: Institutional policies and procedures compilation
- self_evaluation_report: Accreditation self-study documents, compliance narratives
- canvas_manual: LMS usage guides, online learning procedures
- financial_aid_policy: Title IV policies, scholarships, payment plans, verification
- complaint_policy: Grievance and complaint procedures, resolution processes
- safety_plan: Emergency procedures, campus safety, evacuation plans
- drug_free_policy: Drug and alcohol policies (Drug-Free Schools Act compliance)
- title_ix_policy: Sexual harassment policies, Title IX compliance procedures
- ada_policy: Disability accommodations, ADA compliance, accessibility
- faculty_pd_protocol: Professional development requirements, in-service training
- advisory_committee_minutes: Industry advisory board meeting minutes
- organizational_chart: Institutional structure diagrams, reporting relationships
- financial_statements: Audited financials, budgets, financial reports
- other: Documents not matching above categories

CLASSIFICATION SIGNALS:
- Document titles, headers, and footers
- Regulatory citations (34 CFR, state education codes, accreditor standards)
- Form fields and signature blocks (enrollment agreements)
- Cost tables and fee schedules
- Policy section numbering and structure
- Accreditor names (ACCSC, SACSCOC, HLC, etc.)

METADATA TO EXTRACT:
- Effective dates: Look for "Effective [Date]", "Revised [Date]", catalog year ranges
- Program names: Degree/certificate titles, CIP codes, credential levels
- Costs: Tuition amounts, fees, total program costs, payment schedules
- Institution name: From headers, footers, letterhead, or body text
- Clock/credit hours: Program length specifications
- Accreditor references: Named accrediting bodies

LANGUAGE DETECTION:
- EN: Primarily English text (>80% English indicators)
- ES: Primarily Spanish text (>80% Spanish indicators)
- BILINGUAL: Significant content in both languages (20-80% each)

SAFETY RULES:
- NEVER fabricate document content or metadata not present in the source
- Report confidence levels honestly - flag uncertain classifications
- Preserve original documents - never modify files in originals/ folder
- Flag all detected PII for review before storage
- Cite page numbers and sections for extracted metadata

When processing a document:
1. First use parse_document to extract text
2. Use detect_language to determine language
3. Use classify_document to determine document type
4. Use extract_metadata to get structured data
5. Use detect_pii to identify sensitive information
6. Use chunk_document to prepare for vector storage
7. Use save_document to persist results
"""


@register_agent(AgentType.INGESTION)
class IngestionAgent(BaseAgent):
    """Agent for document ingestion, classification, and processing."""

    def __init__(
        self,
        session: AgentSession,
        workspace_manager=None,
        on_update: Optional[Callable[[AgentSession], None]] = None,
    ):
        """Initialize the Ingestion Agent.

        Args:
            session: AgentSession to track progress and state.
            workspace_manager: WorkspaceManager for file persistence.
            on_update: Callback for real-time UI updates.
        """
        super().__init__(session, workspace_manager, on_update)

        # Cache for parsed documents during processing
        self._parsed_cache: Dict[str, ParsedDocument] = {}
        self._chunks_cache: Dict[str, ChunkedDocument] = {}

    @property
    def agent_type(self) -> AgentType:
        return AgentType.INGESTION

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "parse_document",
                "description": "Parse a document file to extract text and structure. Supports PDF, DOCX, TXT, MD, and images with OCR.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the document file"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "classify_document",
                "description": "Classify document type based on text content. Analyzes headers, structure, and content to determine the document type.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text_sample": {
                            "type": "string",
                            "description": "First 5000 characters of document text for classification"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Original filename for additional hints"
                        }
                    },
                    "required": ["text_sample"]
                }
            },
            {
                "name": "extract_metadata",
                "description": "Extract structured metadata from document text including effective dates, program names, costs, and institution info.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Document text to extract metadata from"
                        },
                        "doc_type": {
                            "type": "string",
                            "description": "Classified document type for context-aware extraction"
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "detect_language",
                "description": "Detect primary language of document text (EN, ES, or BILINGUAL).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text_sample": {
                            "type": "string",
                            "description": "Sample of document text (first 2000 characters recommended)"
                        }
                    },
                    "required": ["text_sample"]
                }
            },
            {
                "name": "detect_pii",
                "description": "Scan document text for PII including SSN, phone numbers, email addresses, dates of birth, and credit card numbers.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Document text to scan for PII"
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "chunk_document",
                "description": "Split parsed document into overlapping chunks for vector storage. Preserves section boundaries and handles PII redaction.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the document (must be previously parsed)"
                        },
                        "document_id": {
                            "type": "string",
                            "description": "Document ID to associate chunks with"
                        }
                    },
                    "required": ["file_path", "document_id"]
                }
            },
            {
                "name": "save_document",
                "description": "Save processed document record to the institution workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "institution_id": {
                            "type": "string",
                            "description": "Institution ID for workspace location"
                        },
                        "document_id": {
                            "type": "string",
                            "description": "Document ID"
                        },
                        "doc_type": {
                            "type": "string",
                            "description": "Classified document type"
                        },
                        "language": {
                            "type": "string",
                            "description": "Detected language (en, es, bilingual)"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to original file"
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Extracted metadata"
                        }
                    },
                    "required": ["institution_id", "document_id", "doc_type", "file_path"]
                }
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Route tool calls to implementations."""
        if tool_name == "parse_document":
            return self._tool_parse_document(tool_input)
        elif tool_name == "classify_document":
            return self._tool_classify_document(tool_input)
        elif tool_name == "extract_metadata":
            return self._tool_extract_metadata(tool_input)
        elif tool_name == "detect_language":
            return self._tool_detect_language(tool_input)
        elif tool_name == "detect_pii":
            return self._tool_detect_pii(tool_input)
        elif tool_name == "chunk_document":
            return self._tool_chunk_document(tool_input)
        elif tool_name == "save_document":
            return self._tool_save_document(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _tool_parse_document(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a document file to extract text and structure."""
        file_path = input.get("file_path", "")

        if not file_path:
            return {"error": "file_path is required"}

        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            parsed = parse_document(file_path)

            # Cache for later use
            self._parsed_cache[file_path] = parsed

            return {
                "success": True,
                "file_path": parsed.file_path,
                "file_name": parsed.file_name,
                "file_type": parsed.file_type,
                "page_count": parsed.page_count,
                "word_count": parsed.word_count,
                "text_preview": parsed.text[:2000] if parsed.text else "",
                "text_length": len(parsed.text),
                "section_count": len(parsed.sections),
                "parse_errors": parsed.parse_errors,
            }
        except Exception as e:
            return {"error": f"Parse failed: {str(e)}"}

    def _tool_classify_document(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Classify document type based on text content.

        Uses heuristic rules based on content patterns.
        """
        text_sample = input.get("text_sample", "")
        filename = input.get("filename", "").lower()

        if not text_sample:
            return {"error": "text_sample is required"}

        text_lower = text_sample.lower()

        # Classification rules with confidence scores
        classifications = []

        # Enrollment Agreement signals
        if any(term in text_lower for term in [
            "enrollment agreement", "student agreement",
            "hereby enroll", "tuition and fees",
            "refund policy", "cancellation policy",
            "student signature", "total program cost"
        ]):
            score = sum(1 for term in [
                "enrollment agreement", "tuition", "refund",
                "signature", "total cost", "payment schedule"
            ] if term in text_lower)
            classifications.append(("enrollment_agreement", min(0.5 + score * 0.1, 0.95)))

        # Catalog signals
        if any(term in text_lower for term in [
            "academic catalog", "course catalog", "college catalog",
            "program offerings", "academic calendar",
            "degree requirements", "course descriptions"
        ]):
            score = sum(1 for term in [
                "catalog", "academic calendar", "course description",
                "faculty", "degree", "certificate"
            ] if term in text_lower)
            classifications.append(("catalog", min(0.5 + score * 0.1, 0.95)))

        # Student Handbook signals
        if any(term in text_lower for term in [
            "student handbook", "student code of conduct",
            "academic integrity", "student rights",
            "disciplinary procedures"
        ]):
            classifications.append(("student_handbook", 0.85))

        # Policy Manual signals
        if any(term in text_lower for term in [
            "policy manual", "policies and procedures",
            "institutional policies", "administrative procedures"
        ]):
            classifications.append(("policy_manual", 0.8))

        # Financial Aid Policy signals
        if any(term in text_lower for term in [
            "financial aid", "title iv", "fafsa",
            "satisfactory academic progress", "sap policy",
            "federal student aid"
        ]):
            classifications.append(("financial_aid_policy", 0.85))

        # Self-Evaluation Report signals
        if any(term in text_lower for term in [
            "self-evaluation", "self-study", "accreditation report",
            "compliance narrative", "standard i", "standard ii"
        ]):
            classifications.append(("self_evaluation_report", 0.85))

        # Title IX Policy signals
        if any(term in text_lower for term in [
            "title ix", "sexual harassment", "sexual misconduct",
            "title ix coordinator", "gender discrimination"
        ]):
            classifications.append(("title_ix_policy", 0.9))

        # ADA Policy signals
        if any(term in text_lower for term in [
            "americans with disabilities", "ada compliance",
            "disability accommodation", "accessibility",
            "reasonable accommodation"
        ]):
            classifications.append(("ada_policy", 0.85))

        # Drug-Free Policy signals
        if any(term in text_lower for term in [
            "drug-free", "drug free", "substance abuse",
            "alcohol policy", "drug-free schools act"
        ]):
            classifications.append(("drug_free_policy", 0.85))

        # Safety Plan signals
        if any(term in text_lower for term in [
            "safety plan", "emergency procedures", "evacuation",
            "campus security", "clery act", "emergency response"
        ]):
            classifications.append(("safety_plan", 0.85))

        # Complaint Policy signals
        if any(term in text_lower for term in [
            "complaint policy", "grievance procedure",
            "complaint resolution", "student complaints",
            "filing a complaint"
        ]):
            classifications.append(("complaint_policy", 0.85))

        # Faculty Handbook signals
        if any(term in text_lower for term in [
            "faculty handbook", "instructor handbook",
            "faculty policies", "teaching responsibilities",
            "faculty evaluation"
        ]):
            classifications.append(("faculty_handbook", 0.85))

        # Advisory Committee Minutes signals
        if any(term in text_lower for term in [
            "advisory committee", "advisory board minutes",
            "meeting minutes", "industry advisory",
            "committee members present"
        ]):
            classifications.append(("advisory_committee_minutes", 0.8))

        # Organizational Chart signals
        if any(term in text_lower for term in [
            "organizational chart", "org chart",
            "reporting structure", "chain of command"
        ]) or "organizational" in filename:
            classifications.append(("organizational_chart", 0.75))

        # Financial Statements signals
        if any(term in text_lower for term in [
            "financial statements", "balance sheet",
            "income statement", "audited financial",
            "statement of financial position"
        ]):
            classifications.append(("financial_statements", 0.85))

        # Filename-based hints
        if "enrollment" in filename or "agreement" in filename:
            classifications.append(("enrollment_agreement", 0.6))
        if "catalog" in filename:
            classifications.append(("catalog", 0.6))
        if "handbook" in filename:
            if "student" in filename:
                classifications.append(("student_handbook", 0.6))
            elif "faculty" in filename:
                classifications.append(("faculty_handbook", 0.6))

        # Select best classification
        if classifications:
            # Sort by confidence and take the best
            classifications.sort(key=lambda x: x[1], reverse=True)
            best_type, confidence = classifications[0]

            return {
                "doc_type": best_type,
                "confidence": confidence,
                "all_matches": [{"type": t, "confidence": c} for t, c in classifications[:3]],
            }

        # Default to "other" with low confidence
        return {
            "doc_type": "other",
            "confidence": 0.3,
            "all_matches": [],
            "note": "No strong classification signals found"
        }

    def _tool_extract_metadata(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured metadata from document text."""
        text = input.get("text", "")
        doc_type = input.get("doc_type", "")

        if not text:
            return {"error": "text is required"}

        metadata = {}

        # Extract effective dates
        date_patterns = [
            r'[Ee]ffective[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'[Ee]ffective\s+[Dd]ate[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'[Rr]evised[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'[Dd]ated[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{4}[-–]\d{4})\s*[Cc]atalog',  # Catalog year range
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                if "effective_date" not in metadata:
                    metadata["effective_date"] = match.group(1)
                elif "revision_date" not in metadata:
                    metadata["revision_date"] = match.group(1)

        # Extract costs/tuition
        cost_patterns = [
            r'[Tt]otal\s+[Pp]rogram\s+[Cc]ost[:\s]*\$?([\d,]+(?:\.\d{2})?)',
            r'[Tt]uition[:\s]*\$?([\d,]+(?:\.\d{2})?)',
            r'[Tt]otal\s+[Cc]ost[:\s]*\$?([\d,]+(?:\.\d{2})?)',
            r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:tuition|total)',
        ]

        costs = []
        for pattern in cost_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    cost_val = float(match.replace(",", ""))
                    if cost_val > 100:  # Filter out small numbers
                        costs.append(cost_val)
                except ValueError:
                    pass

        if costs:
            metadata["costs_found"] = sorted(set(costs), reverse=True)[:5]
            metadata["total_cost"] = max(costs)

        # Extract clock/credit hours
        hour_patterns = [
            r'(\d+)\s*[Cc]lock\s*[Hh]ours?',
            r'(\d+)\s*[Cc]redit\s*[Hh]ours?',
            r'(\d+)\s*[Ss]emester\s*[Hh]ours?',
            r'(\d+)\s*[Qq]uarter\s*[Hh]ours?',
        ]

        for pattern in hour_patterns:
            match = re.search(pattern, text)
            if match:
                hours = int(match.group(1))
                if hours > 10:  # Filter noise
                    if "clock" in pattern.lower():
                        metadata["clock_hours"] = hours
                    else:
                        metadata["credit_hours"] = hours

        # Extract program duration
        duration_patterns = [
            r'(\d+)\s*[Ww]eeks?',
            r'(\d+)\s*[Mm]onths?',
        ]

        for pattern in duration_patterns:
            match = re.search(pattern, text)
            if match:
                duration = int(match.group(1))
                if "week" in pattern.lower() and duration > 4:
                    metadata["duration_weeks"] = duration
                elif "month" in pattern.lower() and duration > 1:
                    metadata["duration_months"] = duration

        # Extract accreditor mentions
        accreditors = [
            "ACCSC", "SACSCOC", "HLC", "WASC", "ABHES", "COE", "DEAC",
            "Middle States", "New England", "Northwest", "Southern Association"
        ]

        found_accreditors = []
        for accreditor in accreditors:
            if accreditor.lower() in text.lower():
                found_accreditors.append(accreditor)

        if found_accreditors:
            metadata["accreditors_mentioned"] = found_accreditors

        return {
            "success": True,
            "metadata": metadata,
            "fields_extracted": len(metadata),
        }

    def _tool_detect_language(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Detect primary language of document text."""
        text_sample = input.get("text_sample", "")

        if not text_sample:
            return {"error": "text_sample is required"}

        # Tokenize and lowercase
        words = re.findall(r'\b[a-záéíóúñü]+\b', text_sample.lower())

        if len(words) < 10:
            return {
                "language": "en",
                "confidence": 0.5,
                "note": "Too few words to analyze reliably"
            }

        # Count indicator words
        english_count = sum(1 for w in words if w in ENGLISH_INDICATORS)
        spanish_count = sum(1 for w in words if w in SPANISH_INDICATORS)

        total_indicators = english_count + spanish_count
        if total_indicators == 0:
            return {
                "language": "en",
                "confidence": 0.5,
                "note": "No language indicators found, defaulting to English"
            }

        english_ratio = english_count / total_indicators
        spanish_ratio = spanish_count / total_indicators

        if english_ratio > 0.8:
            return {
                "language": "en",
                "confidence": min(0.5 + english_ratio * 0.5, 0.95),
                "english_ratio": round(english_ratio, 2),
                "spanish_ratio": round(spanish_ratio, 2),
            }
        elif spanish_ratio > 0.8:
            return {
                "language": "es",
                "confidence": min(0.5 + spanish_ratio * 0.5, 0.95),
                "english_ratio": round(english_ratio, 2),
                "spanish_ratio": round(spanish_ratio, 2),
            }
        else:
            return {
                "language": "bilingual",
                "confidence": 0.85,
                "english_ratio": round(english_ratio, 2),
                "spanish_ratio": round(spanish_ratio, 2),
            }

    def _tool_detect_pii(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Scan document text for PII."""
        text = input.get("text", "")

        if not text:
            return {"error": "text is required"}

        matches = detect_pii(text)

        # Summarize by type
        summary = {}
        for match in matches:
            pii_type = match.pii_type
            if pii_type not in summary:
                summary[pii_type] = {"count": 0, "confidence_avg": 0}
            summary[pii_type]["count"] += 1
            summary[pii_type]["confidence_avg"] += match.confidence

        for pii_type in summary:
            count = summary[pii_type]["count"]
            summary[pii_type]["confidence_avg"] = round(
                summary[pii_type]["confidence_avg"] / count, 2
            )

        return {
            "pii_found": len(matches) > 0,
            "pii_count": len(matches),
            "pii_summary": summary,
            "pii_types": list(summary.keys()),
            "redacted_preview": redact_pii(text[:1000]) if matches else text[:1000],
        }

    def _tool_chunk_document(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Chunk a parsed document for vector storage."""
        file_path = input.get("file_path", "")
        document_id = input.get("document_id", "")

        if not file_path:
            return {"error": "file_path is required"}
        if not document_id:
            return {"error": "document_id is required"}

        # Get from cache or parse
        if file_path in self._parsed_cache:
            parsed = self._parsed_cache[file_path]
        else:
            parsed = parse_document(file_path)
            self._parsed_cache[file_path] = parsed

        if not parsed.text:
            return {"error": "Document has no text content"}

        try:
            chunked = chunk_document(parsed, document_id)

            # Cache for potential later use
            self._chunks_cache[document_id] = chunked

            return {
                "success": True,
                "document_id": document_id,
                "total_chunks": chunked.total_chunks,
                "chunking_stats": chunked.chunking_stats,
                "first_chunk_preview": (
                    chunked.chunks[0].text_redacted[:500]
                    if chunked.chunks else ""
                ),
            }
        except Exception as e:
            return {"error": f"Chunking failed: {str(e)}"}

    def _tool_save_document(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Save processed document to workspace."""
        institution_id = input.get("institution_id", "")
        document_id = input.get("document_id", "")
        doc_type = input.get("doc_type", "other")
        language = input.get("language", "en")
        file_path = input.get("file_path", "")
        metadata = input.get("metadata", {})

        if not institution_id:
            return {"error": "institution_id is required"}
        if not document_id:
            return {"error": "document_id is required"}
        if not file_path:
            return {"error": "file_path is required"}

        if not self.workspace_manager:
            return {"error": "No workspace_manager available"}

        try:
            # Load institution
            institution = self.workspace_manager.load_institution(institution_id)
            if not institution:
                return {"error": f"Institution not found: {institution_id}"}

            # Get parsed data from cache
            parsed = self._parsed_cache.get(file_path)

            # Create document record
            try:
                doc_type_enum = DocumentType(doc_type)
            except ValueError:
                doc_type_enum = DocumentType.OTHER

            try:
                language_enum = Language(language)
            except ValueError:
                language_enum = Language.EN

            document = Document(
                id=document_id,
                institution_id=institution_id,
                doc_type=doc_type_enum,
                language=language_enum,
                original_filename=Path(file_path).name,
                file_path=file_path,
                extracted_text=parsed.text if parsed else "",
                page_count=parsed.page_count if parsed else 0,
                status="processed",
            )

            # Store extracted metadata
            document.extracted_structure = metadata

            # Add to institution documents
            # Check if document already exists
            existing_idx = None
            for i, doc in enumerate(institution.documents):
                if doc.id == document_id:
                    existing_idx = i
                    break

            if existing_idx is not None:
                institution.documents[existing_idx] = document
            else:
                institution.documents.append(document)

            institution.updated_at = now_iso()

            # Save institution
            self.workspace_manager.save_institution(institution)

            # Save chunks if available
            chunked = self._chunks_cache.get(document_id)
            chunks_saved = 0
            if chunked:
                # Save chunks as JSON in workspace
                chunks_data = chunked.to_dict()
                chunks_path = f"documents/{document_id}_chunks.json"

                import json
                self.workspace_manager.save_file(
                    institution_id,
                    chunks_path,
                    json.dumps(chunks_data, indent=2).encode("utf-8"),
                    create_version=False,
                )
                chunks_saved = chunked.total_chunks

            return {
                "success": True,
                "document_id": document_id,
                "institution_id": institution_id,
                "doc_type": doc_type,
                "language": language,
                "chunks_saved": chunks_saved,
                "status": "processed",
            }

        except Exception as e:
            return {"error": f"Save failed: {str(e)}"}

    def ingest_document(
        self,
        file_path: str,
        institution_id: str,
        document_id: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """High-level convenience method to run full ingestion pipeline.

        Args:
            file_path: Path to document file.
            institution_id: Institution ID for storage.
            document_id: Optional document ID (generated if not provided).

        Yields:
            Progress updates during processing.

        Returns:
            Final result with document details.
        """
        if not document_id:
            document_id = generate_id("doc")

        prompt = f"""Process the document for ingestion:

File: {file_path}
Institution: {institution_id}
Document ID: {document_id}

Please:
1. Parse the document to extract text
2. Detect the language
3. Classify the document type
4. Extract metadata (dates, costs, etc.)
5. Check for PII
6. Chunk for vector storage
7. Save the processed document

Report your findings and any issues encountered."""

        # Run the agent
        for update in self.run_turn(prompt):
            yield update

        # Return summary
        return {
            "document_id": document_id,
            "institution_id": institution_id,
            "file_path": file_path,
            "status": "completed",
        }
