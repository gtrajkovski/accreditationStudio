"""Core domain models for AccreditAI.

Contains all dataclasses and enums for the accreditation management system.
All models use to_dict() for serialization and from_dict() for deserialization
with unknown field filtering for schema evolution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid


# ===========================
# Enums
# ===========================

class AccreditingBody(str, Enum):
    """Supported accrediting bodies."""
    ACCSC = "ACCSC"
    SACSCOC = "SACSCOC"
    HLC = "HLC"
    WASC = "WASC"
    ABHES = "ABHES"
    COE = "COE"
    DEAC = "DEAC"
    CUSTOM = "CUSTOM"


class DocumentType(str, Enum):
    """Types of institutional documents."""
    ENROLLMENT_AGREEMENT = "enrollment_agreement"
    CATALOG = "catalog"
    STUDENT_HANDBOOK = "student_handbook"
    ADMISSIONS_MANUAL = "admissions_manual"
    FACULTY_HANDBOOK = "faculty_handbook"
    POLICY_MANUAL = "policy_manual"
    SELF_EVALUATION_REPORT = "self_evaluation_report"
    CANVAS_MANUAL = "canvas_manual"
    FINANCIAL_AID_POLICY = "financial_aid_policy"
    COMPLAINT_POLICY = "complaint_policy"
    SAFETY_PLAN = "safety_plan"
    DRUG_FREE_POLICY = "drug_free_policy"
    TITLE_IX_POLICY = "title_ix_policy"
    ADA_POLICY = "ada_policy"
    FACULTY_PD_PROTOCOL = "faculty_pd_protocol"
    ADVISORY_COMMITTEE_MINUTES = "advisory_committee_minutes"
    ORGANIZATIONAL_CHART = "organizational_chart"
    FINANCIAL_STATEMENTS = "financial_statements"
    OTHER = "other"


class Language(str, Enum):
    """Document language options."""
    EN = "en"
    ES = "es"
    BILINGUAL = "bilingual"


class ComplianceStatus(str, Enum):
    """Compliance status for audit findings."""
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NA = "na"


class FindingSeverity(str, Enum):
    """Severity levels for audit findings."""
    CRITICAL = "critical"
    SIGNIFICANT = "significant"
    ADVISORY = "advisory"
    INFORMATIONAL = "informational"


class RegulatorySource(str, Enum):
    """Sources of regulatory requirements."""
    ACCREDITOR = "accreditor"
    FEDERAL_TITLE_IV = "federal_title_iv"
    FEDERAL_FERPA = "federal_ferpa"
    FEDERAL_TITLE_IX = "federal_title_ix"
    FEDERAL_CLERY = "federal_clery"
    FEDERAL_ADA = "federal_ada"
    FEDERAL_VA = "federal_va"
    FEDERAL_FTC = "federal_ftc"
    FEDERAL_REG_Z = "federal_reg_z"
    FEDERAL_GAINFUL_EMPLOYMENT = "federal_gainful_employment"
    FEDERAL_DRUG_FREE = "federal_drug_free"
    STATE = "state"
    PROFESSIONAL = "professional"
    INSTITUTIONAL = "institutional"


class AuditStatus(str, Enum):
    """Status of an audit."""
    DRAFT = "draft"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class ExhibitStatus(str, Enum):
    """Status of an exhibit."""
    NOT_STARTED = "not_started"
    COLLECTING = "collecting"
    UPLOADED = "uploaded"
    AI_REVIEWED = "ai_reviewed"
    FLAGGED = "flagged"
    APPROVED = "approved"


class ActionItemStatus(str, Enum):
    """Status of an action item."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"


class CredentialLevel(str, Enum):
    """Academic credential levels."""
    DIPLOMA = "diploma"
    CERTIFICATE = "certificate"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORAL = "doctoral"


class Modality(str, Enum):
    """Program delivery modality."""
    ON_GROUND = "on_ground"
    HYBRID = "hybrid"
    ONLINE = "online"
    MIXED = "mixed"


class CalendarEventType(str, Enum):
    """Types of compliance calendar events."""
    ACCREDITOR_DEADLINE = "accreditor_deadline"
    FEDERAL_DEADLINE = "federal_deadline"
    STATE_DEADLINE = "state_deadline"
    VISIT_DATE = "visit_date"
    LICENSE_EXPIRATION = "license_expiration"
    DOCUMENT_REVIEW_DUE = "document_review_due"
    ANNUAL_REPORT_DUE = "annual_report_due"
    INTERNAL_DEADLINE = "internal_deadline"


class ReadinessLevel(str, Enum):
    """Readiness assessment levels."""
    READY = "ready"
    MOSTLY_READY = "mostly_ready"
    SIGNIFICANT_GAPS = "significant_gaps"
    NOT_READY = "not_ready"


class SessionStatus(str, Enum):
    """Agent session status."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Agent task priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ===========================
# Helper Functions
# ===========================

def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid


def now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


# ===========================
# Core Domain Models
# ===========================

@dataclass
class Program:
    """A program offered by an institution."""
    id: str = field(default_factory=lambda: generate_id("prog"))
    name_en: str = ""
    name_es: Optional[str] = None
    credential_level: CredentialLevel = CredentialLevel.CERTIFICATE
    total_credits: int = 0
    total_cost: float = 0.0
    duration_months: int = 0
    academic_periods: int = 0
    cost_per_period: float = 0.0
    book_cost: float = 0.0
    other_costs: Dict[str, float] = field(default_factory=dict)
    modality: Modality = Modality.ON_GROUND
    licensure_required: bool = False
    licensure_exam: Optional[str] = None
    professional_body: Optional[str] = None
    programmatic_accreditor: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name_en": self.name_en,
            "name_es": self.name_es,
            "credential_level": self.credential_level.value,
            "total_credits": self.total_credits,
            "total_cost": self.total_cost,
            "duration_months": self.duration_months,
            "academic_periods": self.academic_periods,
            "cost_per_period": self.cost_per_period,
            "book_cost": self.book_cost,
            "other_costs": self.other_costs,
            "modality": self.modality.value,
            "licensure_required": self.licensure_required,
            "licensure_exam": self.licensure_exam,
            "professional_body": self.professional_body,
            "programmatic_accreditor": self.programmatic_accreditor,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Program":
        """Deserialize from dictionary, filtering unknown fields."""
        return cls(
            id=data.get("id", generate_id("prog")),
            name_en=data.get("name_en", ""),
            name_es=data.get("name_es"),
            credential_level=CredentialLevel(data.get("credential_level", "certificate")),
            total_credits=data.get("total_credits", 0),
            total_cost=data.get("total_cost", 0.0),
            duration_months=data.get("duration_months", 0),
            academic_periods=data.get("academic_periods", 0),
            cost_per_period=data.get("cost_per_period", 0.0),
            book_cost=data.get("book_cost", 0.0),
            other_costs=data.get("other_costs", {}),
            modality=Modality(data.get("modality", "on_ground")),
            licensure_required=data.get("licensure_required", False),
            licensure_exam=data.get("licensure_exam"),
            professional_body=data.get("professional_body"),
            programmatic_accreditor=data.get("programmatic_accreditor"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class Institution:
    """An educational institution being managed."""
    id: str = field(default_factory=lambda: generate_id("inst"))
    name: str = ""
    accrediting_body: AccreditingBody = AccreditingBody.ACCSC
    opeid: str = ""
    website: str = ""
    school_ids: Dict[str, str] = field(default_factory=dict)
    campuses: List[Dict[str, Any]] = field(default_factory=list)
    state_authority: Dict[str, Any] = field(default_factory=dict)
    federal_characteristics: Dict[str, bool] = field(default_factory=dict)
    state_code: str = ""
    programs: List[Program] = field(default_factory=list)
    documents: List["Document"] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "accrediting_body": self.accrediting_body.value,
            "opeid": self.opeid,
            "website": self.website,
            "school_ids": self.school_ids,
            "campuses": self.campuses,
            "state_authority": self.state_authority,
            "federal_characteristics": self.federal_characteristics,
            "state_code": self.state_code,
            "programs": [p.to_dict() for p in self.programs],
            "documents": [d.to_dict() for d in self.documents],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Institution":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", generate_id("inst")),
            name=data.get("name", ""),
            accrediting_body=AccreditingBody(data.get("accrediting_body", "ACCSC")),
            opeid=data.get("opeid", ""),
            website=data.get("website", ""),
            school_ids=data.get("school_ids", {}),
            campuses=data.get("campuses", []),
            state_authority=data.get("state_authority", {}),
            federal_characteristics=data.get("federal_characteristics", {}),
            state_code=data.get("state_code", ""),
            programs=[Program.from_dict(p) for p in data.get("programs", [])],
            documents=[Document.from_dict(d) for d in data.get("documents", [])],
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class Document:
    """A document in the workspace."""
    id: str = field(default_factory=lambda: generate_id("doc"))
    institution_id: str = ""
    program_id: Optional[str] = None
    doc_type: DocumentType = DocumentType.OTHER
    language: Language = Language.EN
    original_filename: str = ""
    file_path: str = ""
    extracted_text: str = ""
    extracted_structure: Dict[str, Any] = field(default_factory=dict)
    page_count: int = 0
    version: int = 1
    status: str = "uploaded"
    last_reviewed_date: Optional[str] = None
    review_cycle_months: int = 12
    uploaded_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "program_id": self.program_id,
            "doc_type": self.doc_type.value,
            "language": self.language.value,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "extracted_text": self.extracted_text,
            "extracted_structure": self.extracted_structure,
            "page_count": self.page_count,
            "version": self.version,
            "status": self.status,
            "last_reviewed_date": self.last_reviewed_date,
            "review_cycle_months": self.review_cycle_months,
            "uploaded_at": self.uploaded_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", generate_id("doc")),
            institution_id=data.get("institution_id", ""),
            program_id=data.get("program_id"),
            doc_type=DocumentType(data.get("doc_type", "other")),
            language=Language(data.get("language", "en")),
            original_filename=data.get("original_filename", ""),
            file_path=data.get("file_path", ""),
            extracted_text=data.get("extracted_text", ""),
            extracted_structure=data.get("extracted_structure", {}),
            page_count=data.get("page_count", 0),
            version=data.get("version", 1),
            status=data.get("status", "uploaded"),
            last_reviewed_date=data.get("last_reviewed_date"),
            review_cycle_months=data.get("review_cycle_months", 12),
            uploaded_at=data.get("uploaded_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class AuditFinding:
    """A finding from a document audit."""
    id: str = field(default_factory=lambda: generate_id("find"))
    audit_id: str = ""
    item_number: str = ""
    item_description: str = ""
    status: ComplianceStatus = ComplianceStatus.NA
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL
    regulatory_source: RegulatorySource = RegulatorySource.ACCREDITOR
    regulatory_citation: str = ""
    evidence_in_document: str = ""
    finding_detail: str = ""
    recommendation: str = ""
    page_numbers: str = ""
    ai_confidence: float = 0.0
    human_override_status: Optional[str] = None
    human_notes: Optional[str] = None
    pass_discovered: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "audit_id": self.audit_id,
            "item_number": self.item_number,
            "item_description": self.item_description,
            "status": self.status.value,
            "severity": self.severity.value,
            "regulatory_source": self.regulatory_source.value,
            "regulatory_citation": self.regulatory_citation,
            "evidence_in_document": self.evidence_in_document,
            "finding_detail": self.finding_detail,
            "recommendation": self.recommendation,
            "page_numbers": self.page_numbers,
            "ai_confidence": self.ai_confidence,
            "human_override_status": self.human_override_status,
            "human_notes": self.human_notes,
            "pass_discovered": self.pass_discovered,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditFinding":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", generate_id("find")),
            audit_id=data.get("audit_id", ""),
            item_number=data.get("item_number", ""),
            item_description=data.get("item_description", ""),
            status=ComplianceStatus(data.get("status", "na")),
            severity=FindingSeverity(data.get("severity", "informational")),
            regulatory_source=RegulatorySource(data.get("regulatory_source", "accreditor")),
            regulatory_citation=data.get("regulatory_citation", ""),
            evidence_in_document=data.get("evidence_in_document", ""),
            finding_detail=data.get("finding_detail", ""),
            recommendation=data.get("recommendation", ""),
            page_numbers=data.get("page_numbers", ""),
            ai_confidence=data.get("ai_confidence", 0.0),
            human_override_status=data.get("human_override_status"),
            human_notes=data.get("human_notes"),
            pass_discovered=data.get("pass_discovered", 1),
        )


@dataclass
class Audit:
    """An audit of a document."""
    id: str = field(default_factory=lambda: generate_id("audit"))
    document_id: str = ""
    program_id: Optional[str] = None
    standards_library_id: str = ""
    regulatory_stack_id: str = ""
    audit_type: str = "full"
    status: AuditStatus = AuditStatus.DRAFT
    summary: Dict[str, int] = field(default_factory=dict)
    summary_by_source: Dict[str, Dict[str, int]] = field(default_factory=dict)
    findings: List[AuditFinding] = field(default_factory=list)
    passes_completed: int = 0
    ai_model_used: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "program_id": self.program_id,
            "standards_library_id": self.standards_library_id,
            "regulatory_stack_id": self.regulatory_stack_id,
            "audit_type": self.audit_type,
            "status": self.status.value,
            "summary": self.summary,
            "summary_by_source": self.summary_by_source,
            "findings": [f.to_dict() for f in self.findings],
            "passes_completed": self.passes_completed,
            "ai_model_used": self.ai_model_used,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Audit":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", generate_id("audit")),
            document_id=data.get("document_id", ""),
            program_id=data.get("program_id"),
            standards_library_id=data.get("standards_library_id", ""),
            regulatory_stack_id=data.get("regulatory_stack_id", ""),
            audit_type=data.get("audit_type", "full"),
            status=AuditStatus(data.get("status", "draft")),
            summary=data.get("summary", {}),
            summary_by_source=data.get("summary_by_source", {}),
            findings=[AuditFinding.from_dict(f) for f in data.get("findings", [])],
            passes_completed=data.get("passes_completed", 0),
            ai_model_used=data.get("ai_model_used", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


# ===========================
# Agent System Models
# ===========================

@dataclass
class ToolCall:
    """Record of a tool invocation by an agent."""
    id: str = field(default_factory=lambda: generate_id("tc"))
    tool_name: str = ""
    input_params: Dict[str, Any] = field(default_factory=dict)
    output_result: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "input_params": self.input_params,
            "output_result": self.output_result,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        return cls(
            id=data.get("id", generate_id("tc")),
            tool_name=data.get("tool_name", ""),
            input_params=data.get("input_params", {}),
            output_result=data.get("output_result", {}),
            duration_ms=data.get("duration_ms", 0),
            success=data.get("success", True),
            error=data.get("error"),
            timestamp=data.get("timestamp", now_iso()),
        )


@dataclass
class HumanCheckpoint:
    """A point where human input is required."""
    id: str = field(default_factory=lambda: generate_id("cp"))
    session_id: str = ""
    task_id: Optional[str] = None
    agent: str = ""
    checkpoint_type: str = "approval"
    question: str = ""
    context: str = ""
    options: List[str] = field(default_factory=list)
    user_response: Optional[str] = None
    status: str = "pending"
    created_at: str = field(default_factory=now_iso)
    answered_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "agent": self.agent,
            "checkpoint_type": self.checkpoint_type,
            "question": self.question,
            "context": self.context,
            "options": self.options,
            "user_response": self.user_response,
            "status": self.status,
            "created_at": self.created_at,
            "answered_at": self.answered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanCheckpoint":
        return cls(
            id=data.get("id", generate_id("cp")),
            session_id=data.get("session_id", ""),
            task_id=data.get("task_id"),
            agent=data.get("agent", ""),
            checkpoint_type=data.get("checkpoint_type", "approval"),
            question=data.get("question", ""),
            context=data.get("context", ""),
            options=data.get("options", []),
            user_response=data.get("user_response"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", now_iso()),
            answered_at=data.get("answered_at"),
        )


@dataclass
class AgentTask:
    """A task for an agent to execute."""
    id: str = field(default_factory=lambda: generate_id("task"))
    session_id: str = ""
    name: str = ""
    description: str = ""
    agent: str = ""
    action: str = ""
    status: str = "pending"
    priority: TaskPriority = TaskPriority.NORMAL
    input_data: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    citations: List[Dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
    ai_tokens_used: int = 0
    error: Optional[str] = None
    retries: int = 0
    requires_approval_before: bool = False
    requires_approval_after: bool = False
    depends_on: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "agent": self.agent,
            "action": self.action,
            "status": self.status,
            "priority": self.priority.value,
            "input_data": self.input_data,
            "result": self.result,
            "confidence": self.confidence,
            "citations": self.citations,
            "duration_ms": self.duration_ms,
            "ai_tokens_used": self.ai_tokens_used,
            "error": self.error,
            "retries": self.retries,
            "requires_approval_before": self.requires_approval_before,
            "requires_approval_after": self.requires_approval_after,
            "depends_on": self.depends_on,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTask":
        return cls(
            id=data.get("id", generate_id("task")),
            session_id=data.get("session_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            agent=data.get("agent", ""),
            action=data.get("action", ""),
            status=data.get("status", "pending"),
            priority=TaskPriority(data.get("priority", "normal")),
            input_data=data.get("input_data", {}),
            result=data.get("result", {}),
            confidence=data.get("confidence", 0.0),
            citations=data.get("citations", []),
            duration_ms=data.get("duration_ms", 0),
            ai_tokens_used=data.get("ai_tokens_used", 0),
            error=data.get("error"),
            retries=data.get("retries", 0),
            requires_approval_before=data.get("requires_approval_before", False),
            requires_approval_after=data.get("requires_approval_after", False),
            depends_on=data.get("depends_on", []),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class AgentSession:
    """A session tracking agent workflow execution."""
    id: str = field(default_factory=lambda: generate_id("sess"))
    agent_type: str = "orchestrator"
    institution_id: str = ""
    parent_session_id: Optional[str] = None
    orchestrator_request: str = ""
    status: SessionStatus = SessionStatus.PENDING
    agents_involved: List[str] = field(default_factory=list)
    tasks: List[AgentTask] = field(default_factory=list)
    checkpoints: List[HumanCheckpoint] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    current_task_id: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_api_calls: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    last_error: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "institution_id": self.institution_id,
            "parent_session_id": self.parent_session_id,
            "orchestrator_request": self.orchestrator_request,
            "status": self.status.value,
            "agents_involved": self.agents_involved,
            "tasks": [t.to_dict() for t in self.tasks],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "messages": self.messages,
            "artifacts_created": self.artifacts_created,
            "metadata": self.metadata,
            "current_task_id": self.current_task_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_api_calls": self.total_api_calls,
            "errors": self.errors,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSession":
        return cls(
            id=data.get("id", generate_id("sess")),
            agent_type=data.get("agent_type", "orchestrator"),
            institution_id=data.get("institution_id", ""),
            parent_session_id=data.get("parent_session_id"),
            orchestrator_request=data.get("orchestrator_request", ""),
            status=SessionStatus(data.get("status", "pending")),
            agents_involved=data.get("agents_involved", []),
            tasks=[AgentTask.from_dict(t) for t in data.get("tasks", [])],
            checkpoints=[HumanCheckpoint.from_dict(c) for c in data.get("checkpoints", [])],
            tool_calls=[ToolCall.from_dict(tc) for tc in data.get("tool_calls", [])],
            messages=data.get("messages", []),
            artifacts_created=data.get("artifacts_created", []),
            metadata=data.get("metadata", {}),
            current_task_id=data.get("current_task_id"),
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_api_calls=data.get("total_api_calls", 0),
            errors=data.get("errors", []),
            last_error=data.get("last_error"),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )

    def add_task(self, task: AgentTask) -> None:
        """Add a task to the session."""
        task.session_id = self.id
        self.tasks.append(task)

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call record to the session."""
        self.tool_calls.append(tool_call)

    def get_pending_tasks(self) -> List[AgentTask]:
        """Get tasks that are ready to execute."""
        completed_ids = {t.id for t in self.tasks if t.status == "completed"}
        pending = []
        for task in self.tasks:
            if task.status == "pending":
                # Check if all dependencies are complete
                if all(dep_id in completed_ids for dep_id in task.depends_on):
                    pending.append(task)
        return pending

    def request_approval(
        self,
        checkpoint_type: str,
        description: str,
        data: Dict[str, Any] = None
    ) -> HumanCheckpoint:
        """Create a human checkpoint for approval."""
        checkpoint = HumanCheckpoint(
            session_id=self.id,
            task_id=self.current_task_id,
            checkpoint_type=checkpoint_type,
            question=description,
            context=str(data) if data else "",
        )
        self.checkpoints.append(checkpoint)
        self.status = SessionStatus.WAITING_FOR_HUMAN
        return checkpoint


@dataclass
class ChatMessage:
    """A message in the chat interface."""
    id: str = field(default_factory=lambda: generate_id("msg"))
    session_id: Optional[str] = None
    institution_id: str = ""
    role: str = "user"
    message_type: str = "text"
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "institution_id": self.institution_id,
            "role": self.role,
            "message_type": self.message_type,
            "content": self.content,
            "metadata": self.metadata,
            "agent": self.agent,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            id=data.get("id", generate_id("msg")),
            session_id=data.get("session_id"),
            institution_id=data.get("institution_id", ""),
            role=data.get("role", "user"),
            message_type=data.get("message_type", "text"),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            agent=data.get("agent"),
            timestamp=data.get("timestamp", now_iso()),
        )


# ===========================
# Document Chunking Models
# ===========================

@dataclass
class DocumentChunk:
    """A single chunk from a parsed document for RAG/vector storage."""
    id: str = field(default_factory=lambda: generate_id("chunk"))
    document_id: str = ""
    chunk_index: int = 0
    page_number: int = 1
    section_header: str = ""
    text_original: str = ""
    text_redacted: str = ""
    text_anonymized: str = ""
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section_header": self.section_header,
            "text_original": self.text_original,
            "text_redacted": self.text_redacted,
            "text_anonymized": self.text_anonymized,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        return cls(
            id=data.get("id", generate_id("chunk")),
            document_id=data.get("document_id", ""),
            chunk_index=data.get("chunk_index", 0),
            page_number=data.get("page_number", 1),
            section_header=data.get("section_header", ""),
            text_original=data.get("text_original", ""),
            text_redacted=data.get("text_redacted", ""),
            text_anonymized=data.get("text_anonymized", ""),
            embedding=data.get("embedding", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", now_iso()),
        )


@dataclass
class ChunkedDocument:
    """Result of chunking a parsed document."""
    document_id: str = ""
    source_file: str = ""
    total_chunks: int = 0
    chunks: List[DocumentChunk] = field(default_factory=list)
    chunking_stats: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_file": self.source_file,
            "total_chunks": self.total_chunks,
            "chunks": [c.to_dict() for c in self.chunks],
            "chunking_stats": self.chunking_stats,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkedDocument":
        return cls(
            document_id=data.get("document_id", ""),
            source_file=data.get("source_file", ""),
            total_chunks=data.get("total_chunks", 0),
            chunks=[DocumentChunk.from_dict(c) for c in data.get("chunks", [])],
            chunking_stats=data.get("chunking_stats", {}),
            created_at=data.get("created_at", now_iso()),
        )


# ===========================
# Standards Library Models
# ===========================

@dataclass
class ChecklistItem:
    """A checklist item within a standards section.

    Represents a specific requirement or criterion that documents
    must satisfy for accreditation compliance.
    """
    number: str = ""                          # e.g., "1.a", "2.b.i"
    category: str = ""                        # e.g., "Institutional", "Program"
    description: str = ""
    section_reference: str = ""               # e.g., "Section I.A.1"
    applies_to: List[str] = field(default_factory=list)  # DocumentType values

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "category": self.category,
            "description": self.description,
            "section_reference": self.section_reference,
            "applies_to": self.applies_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChecklistItem":
        return cls(
            number=data.get("number", ""),
            category=data.get("category", ""),
            description=data.get("description", ""),
            section_reference=data.get("section_reference", ""),
            applies_to=data.get("applies_to", []),
        )


@dataclass
class StandardsSection:
    """A section within a standards library.

    Sections form a hierarchy (e.g., I -> I.A -> I.A.1) linked
    via parent_section references.
    """
    id: str = field(default_factory=lambda: generate_id("sec"))
    number: str = ""                          # e.g., "I", "I.A", "I.A.1"
    title: str = ""
    text: str = ""                            # Full section text
    parent_section: str = ""                  # ID of parent section (empty for top-level)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "text": self.text,
            "parent_section": self.parent_section,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardsSection":
        return cls(
            id=data.get("id", generate_id("sec")),
            number=data.get("number", ""),
            title=data.get("title", ""),
            text=data.get("text", ""),
            parent_section=data.get("parent_section", ""),
        )


@dataclass
class StandardsLibrary:
    """A set of accreditation standards for an accrediting body.

    Contains the hierarchical structure of standards sections and
    checklist items used for compliance auditing.
    """
    id: str = field(default_factory=lambda: generate_id("std"))
    accrediting_body: AccreditingBody = AccreditingBody.ACCSC
    name: str = ""                            # e.g., "ACCSC Substantive Standards"
    version: str = ""                         # e.g., "2023"
    effective_date: str = ""
    sections: List[StandardsSection] = field(default_factory=list)
    checklist_items: List[ChecklistItem] = field(default_factory=list)
    full_text: str = ""                       # Complete standards document text
    is_system_preset: bool = False
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "accrediting_body": self.accrediting_body.value if isinstance(self.accrediting_body, AccreditingBody) else self.accrediting_body,
            "name": self.name,
            "version": self.version,
            "effective_date": self.effective_date,
            "sections": [s.to_dict() for s in self.sections],
            "checklist_items": [c.to_dict() for c in self.checklist_items],
            "full_text": self.full_text,
            "is_system_preset": self.is_system_preset,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardsLibrary":
        accreditor = data.get("accrediting_body", "ACCSC")
        if isinstance(accreditor, str):
            try:
                accreditor = AccreditingBody(accreditor)
            except ValueError:
                accreditor = AccreditingBody.CUSTOM

        return cls(
            id=data.get("id", generate_id("std")),
            accrediting_body=accreditor,
            name=data.get("name", ""),
            version=data.get("version", ""),
            effective_date=data.get("effective_date", ""),
            sections=[StandardsSection.from_dict(s) for s in data.get("sections", [])],
            checklist_items=[ChecklistItem.from_dict(c) for c in data.get("checklist_items", [])],
            full_text=data.get("full_text", ""),
            is_system_preset=data.get("is_system_preset", False),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class AgentResult:
    """Standardized result from any agent execution.

    All agents return this structure for consistent handling by the
    orchestrator and workflow engine.
    """
    status: str = "success"  # success, error, pending_approval
    confidence: float = 0.0  # 0.0-1.0, triggers checkpoint if < threshold
    citations: List[Dict[str, Any]] = field(default_factory=list)  # Evidence pointers
    artifacts: List[str] = field(default_factory=list)  # Paths to created files
    data: Dict[str, Any] = field(default_factory=dict)  # Agent-specific output
    human_checkpoint_required: bool = False
    checkpoint_reason: str = ""
    next_actions: List[Dict[str, Any]] = field(default_factory=list)  # Suggested follow-ups
    error: Optional[str] = None
    duration_ms: int = 0
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "citations": self.citations,
            "artifacts": self.artifacts,
            "data": self.data,
            "human_checkpoint_required": self.human_checkpoint_required,
            "checkpoint_reason": self.checkpoint_reason,
            "next_actions": self.next_actions,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentResult":
        return cls(
            status=data.get("status", "success"),
            confidence=data.get("confidence", 0.0),
            citations=data.get("citations", []),
            artifacts=data.get("artifacts", []),
            data=data.get("data", {}),
            human_checkpoint_required=data.get("human_checkpoint_required", False),
            checkpoint_reason=data.get("checkpoint_reason", ""),
            next_actions=data.get("next_actions", []),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0),
            tokens_used=data.get("tokens_used", 0),
        )

    @classmethod
    def success(cls, data: Dict[str, Any], confidence: float = 1.0,
                citations: List[Dict[str, Any]] = None,
                artifacts: List[str] = None) -> "AgentResult":
        """Create a successful result."""
        return cls(
            status="success",
            confidence=confidence,
            citations=citations or [],
            artifacts=artifacts or [],
            data=data,
        )

    @classmethod
    def error(cls, message: str) -> "AgentResult":
        """Create an error result."""
        return cls(status="error", error=message)

    @classmethod
    def needs_approval(cls, reason: str, data: Dict[str, Any] = None) -> "AgentResult":
        """Create a result that requires human approval."""
        return cls(
            status="pending_approval",
            human_checkpoint_required=True,
            checkpoint_reason=reason,
            data=data or {},
        )


@dataclass
class RegulatoryStack:
    """Combined regulatory requirements for an institution.

    Aggregates accreditor standards with federal, state, and
    professional requirements for comprehensive compliance tracking.
    """
    id: str = field(default_factory=lambda: generate_id("stack"))
    institution_id: str = ""
    accreditor_standards_id: str = ""         # Reference to StandardsLibrary
    federal_regulations: List[Dict[str, Any]] = field(default_factory=list)
    state_regulations: List[Dict[str, Any]] = field(default_factory=list)
    professional_requirements: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "accreditor_standards_id": self.accreditor_standards_id,
            "federal_regulations": self.federal_regulations,
            "state_regulations": self.state_regulations,
            "professional_requirements": self.professional_requirements,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegulatoryStack":
        return cls(
            id=data.get("id", generate_id("stack")),
            institution_id=data.get("institution_id", ""),
            accreditor_standards_id=data.get("accreditor_standards_id", ""),
            federal_regulations=data.get("federal_regulations", []),
            state_regulations=data.get("state_regulations", []),
            professional_requirements=data.get("professional_requirements", []),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )
