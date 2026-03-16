"""Core domain models for AccreditAI.

Contains all dataclasses and enums for the accreditation management system.
All models use to_dict() for serialization and from_dict() for deserialization
with unknown field filtering for schema evolution.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
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


class BatchStatus(str, Enum):
    """Status of a batch operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


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
    PAUSED = "paused"
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
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


# =============================================================================
# Evidence Mapping Models
# =============================================================================


@dataclass
class CrosswalkEntry:
    """Single row in a crosswalk table.

    Maps a standard requirement to its supporting evidence from documents.
    """
    standard_ref: str = ""
    section_reference: str = ""
    category: str = ""
    requirement: str = ""
    evidence_found: bool = False
    quality: str = "missing"  # strong, adequate, weak, missing
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    page: Optional[int] = None
    snippet: Optional[str] = None
    confidence: float = 0.0
    exhibit_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_ref": self.standard_ref,
            "section_reference": self.section_reference,
            "category": self.category,
            "requirement": self.requirement,
            "evidence_found": self.evidence_found,
            "quality": self.quality,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page": self.page,
            "snippet": self.snippet,
            "confidence": self.confidence,
            "exhibit_label": self.exhibit_label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrosswalkEntry":
        return cls(
            standard_ref=data.get("standard_ref", ""),
            section_reference=data.get("section_reference", ""),
            category=data.get("category", ""),
            requirement=data.get("requirement", ""),
            evidence_found=data.get("evidence_found", False),
            quality=data.get("quality", "missing"),
            document_id=data.get("document_id"),
            document_name=data.get("document_name"),
            page=data.get("page"),
            snippet=data.get("snippet"),
            confidence=data.get("confidence", 0.0),
            exhibit_label=data.get("exhibit_label"),
        )


@dataclass
class EvidenceMapping:
    """Maps a single standard to its supporting evidence.

    Contains all evidence found for a requirement with quality assessment.
    """
    standard_id: str = ""
    standard_number: str = ""
    standard_text: str = ""
    status: str = "missing"  # satisfied, partial, weak, missing
    confidence: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    suggested_exhibit: Optional[str] = None
    gap_notes: Optional[str] = None
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_id": self.standard_id,
            "standard_number": self.standard_number,
            "standard_text": self.standard_text,
            "status": self.status,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "suggested_exhibit": self.suggested_exhibit,
            "gap_notes": self.gap_notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceMapping":
        return cls(
            standard_id=data.get("standard_id", ""),
            standard_number=data.get("standard_number", ""),
            standard_text=data.get("standard_text", ""),
            status=data.get("status", "missing"),
            confidence=data.get("confidence", 0.0),
            evidence=data.get("evidence", []),
            suggested_exhibit=data.get("suggested_exhibit"),
            gap_notes=data.get("gap_notes"),
            created_at=data.get("created_at", now_iso()),
        )


@dataclass
class EvidenceMap:
    """Complete evidence map for an institution against a standards library.

    Contains all standard-to-evidence mappings with coverage statistics.
    """
    id: str = field(default_factory=lambda: generate_id("evmap"))
    institution_id: str = ""
    standards_library_id: str = ""
    mappings: List[EvidenceMapping] = field(default_factory=list)
    coverage_stats: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "standards_library_id": self.standards_library_id,
            "mappings": [m.to_dict() if hasattr(m, 'to_dict') else m for m in self.mappings],
            "coverage_stats": self.coverage_stats,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceMap":
        mappings_data = data.get("mappings", [])
        mappings = [
            EvidenceMapping.from_dict(m) if isinstance(m, dict) else m
            for m in mappings_data
        ]
        return cls(
            id=data.get("id", generate_id("evmap")),
            institution_id=data.get("institution_id", ""),
            standards_library_id=data.get("standards_library_id", ""),
            mappings=mappings,
            coverage_stats=data.get("coverage_stats", {}),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class EvidenceGap:
    """An identified gap in evidence coverage.

    Represents a standard that lacks sufficient evidence, with
    severity classification and remediation suggestions.
    """
    standard_id: str = ""
    standard_number: str = ""
    standard_text: str = ""
    severity: str = "advisory"  # critical, high, advisory
    current_coverage: str = "missing"  # weak, missing
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    related_doc_types: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_id": self.standard_id,
            "standard_number": self.standard_number,
            "standard_text": self.standard_text,
            "severity": self.severity,
            "current_coverage": self.current_coverage,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
            "related_doc_types": self.related_doc_types,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceGap":
        return cls(
            standard_id=data.get("standard_id", ""),
            standard_number=data.get("standard_number", ""),
            standard_text=data.get("standard_text", ""),
            severity=data.get("severity", "advisory"),
            current_coverage=data.get("current_coverage", "missing"),
            confidence=data.get("confidence", 0.0),
            suggestions=data.get("suggestions", []),
            related_doc_types=data.get("related_doc_types", []),
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


# ===========================
# Remediation Models
# ===========================

class RemediationStatus(str, Enum):
    """Status of a remediation task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    GENERATED = "generated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    APPLIED = "applied"


@dataclass
class RemediationChange:
    """A single change to be applied to a document."""
    id: str = field(default_factory=lambda: generate_id("chg"))
    finding_id: str = ""
    item_number: str = ""
    change_type: str = "insert"  # insert, replace, delete
    location: str = ""  # section/page reference
    original_text: str = ""
    corrected_text: str = ""
    standard_citation: str = ""
    rationale: str = ""
    ai_confidence: float = 0.0
    human_approved: bool = False
    human_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "item_number": self.item_number,
            "change_type": self.change_type,
            "location": self.location,
            "original_text": self.original_text,
            "corrected_text": self.corrected_text,
            "standard_citation": self.standard_citation,
            "rationale": self.rationale,
            "ai_confidence": self.ai_confidence,
            "human_approved": self.human_approved,
            "human_notes": self.human_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RemediationChange":
        return cls(
            id=data.get("id", generate_id("chg")),
            finding_id=data.get("finding_id", ""),
            item_number=data.get("item_number", ""),
            change_type=data.get("change_type", "insert"),
            location=data.get("location", ""),
            original_text=data.get("original_text", ""),
            corrected_text=data.get("corrected_text", ""),
            standard_citation=data.get("standard_citation", ""),
            rationale=data.get("rationale", ""),
            ai_confidence=data.get("ai_confidence", 0.0),
            human_approved=data.get("human_approved", False),
            human_notes=data.get("human_notes"),
        )


@dataclass
class RemediationResult:
    """Result of remediating a document based on audit findings."""
    id: str = field(default_factory=lambda: generate_id("remed"))
    audit_id: str = ""
    document_id: str = ""
    institution_id: str = ""
    status: RemediationStatus = RemediationStatus.PENDING
    changes: List[RemediationChange] = field(default_factory=list)
    findings_addressed: int = 0
    findings_skipped: int = 0
    redline_path: str = ""
    final_path: str = ""
    crossref_path: str = ""
    truth_index_applied: bool = False
    truth_index_changes: List[Dict[str, Any]] = field(default_factory=list)
    ai_model_used: str = ""
    created_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "audit_id": self.audit_id,
            "document_id": self.document_id,
            "institution_id": self.institution_id,
            "status": self.status.value,
            "changes": [c.to_dict() for c in self.changes],
            "findings_addressed": self.findings_addressed,
            "findings_skipped": self.findings_skipped,
            "redline_path": self.redline_path,
            "final_path": self.final_path,
            "crossref_path": self.crossref_path,
            "truth_index_applied": self.truth_index_applied,
            "truth_index_changes": self.truth_index_changes,
            "ai_model_used": self.ai_model_used,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RemediationResult":
        return cls(
            id=data.get("id", generate_id("remed")),
            audit_id=data.get("audit_id", ""),
            document_id=data.get("document_id", ""),
            institution_id=data.get("institution_id", ""),
            status=RemediationStatus(data.get("status", "pending")),
            changes=[RemediationChange.from_dict(c) for c in data.get("changes", [])],
            findings_addressed=data.get("findings_addressed", 0),
            findings_skipped=data.get("findings_skipped", 0),
            redline_path=data.get("redline_path", ""),
            final_path=data.get("final_path", ""),
            crossref_path=data.get("crossref_path", ""),
            truth_index_applied=data.get("truth_index_applied", False),
            truth_index_changes=data.get("truth_index_changes", []),
            ai_model_used=data.get("ai_model_used", ""),
            created_at=data.get("created_at", now_iso()),
            completed_at=data.get("completed_at"),
        )


# ===========================
# Checklist Auto-Fill Models
# ===========================

class ChecklistResponseStatus(str, Enum):
    """Status of a checklist item response."""
    NOT_STARTED = "not_started"
    AUTO_FILLED = "auto_filled"
    NEEDS_REVIEW = "needs_review"
    HUMAN_EDITED = "human_edited"
    APPROVED = "approved"


@dataclass
class ChecklistResponse:
    """A filled response to a single checklist item.

    Contains the compliance status, evidence gathered, and narrative
    response for a specific checklist requirement.
    """
    id: str = field(default_factory=lambda: generate_id("resp"))
    item_number: str = ""                     # e.g., "I.A.1"
    item_description: str = ""                # Description from ChecklistItem
    category: str = ""                        # Category from ChecklistItem
    section_reference: str = ""               # Standard section reference
    compliance_status: ComplianceStatus = ComplianceStatus.NA
    response_status: ChecklistResponseStatus = ChecklistResponseStatus.NOT_STARTED
    narrative_response: str = ""              # AI-generated or human-written response
    evidence_summary: str = ""                # Summary of supporting evidence
    evidence_sources: List[Dict[str, Any]] = field(default_factory=list)  # [{doc_id, page, excerpt}]
    audit_finding_ids: List[str] = field(default_factory=list)  # Related finding IDs
    remediation_ids: List[str] = field(default_factory=list)    # Related remediation IDs
    ai_confidence: float = 0.0
    human_notes: str = ""
    last_updated: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "item_number": self.item_number,
            "item_description": self.item_description,
            "category": self.category,
            "section_reference": self.section_reference,
            "compliance_status": self.compliance_status.value,
            "response_status": self.response_status.value,
            "narrative_response": self.narrative_response,
            "evidence_summary": self.evidence_summary,
            "evidence_sources": self.evidence_sources,
            "audit_finding_ids": self.audit_finding_ids,
            "remediation_ids": self.remediation_ids,
            "ai_confidence": self.ai_confidence,
            "human_notes": self.human_notes,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChecklistResponse":
        return cls(
            id=data.get("id", generate_id("resp")),
            item_number=data.get("item_number", ""),
            item_description=data.get("item_description", ""),
            category=data.get("category", ""),
            section_reference=data.get("section_reference", ""),
            compliance_status=ComplianceStatus(data.get("compliance_status", "na")),
            response_status=ChecklistResponseStatus(data.get("response_status", "not_started")),
            narrative_response=data.get("narrative_response", ""),
            evidence_summary=data.get("evidence_summary", ""),
            evidence_sources=data.get("evidence_sources", []),
            audit_finding_ids=data.get("audit_finding_ids", []),
            remediation_ids=data.get("remediation_ids", []),
            ai_confidence=data.get("ai_confidence", 0.0),
            human_notes=data.get("human_notes", ""),
            last_updated=data.get("last_updated", now_iso()),
        )


class FilledChecklistStatus(str, Enum):
    """Status of the overall filled checklist."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AUTO_FILL_COMPLETE = "auto_fill_complete"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    EXPORTED = "exported"


@dataclass
class FilledChecklist:
    """A complete filled checklist for an institution.

    Links to a standards library and contains filled responses
    for each checklist item.
    """
    id: str = field(default_factory=lambda: generate_id("fcl"))
    institution_id: str = ""
    program_id: str = ""                      # Optional: program-specific checklist
    standards_library_id: str = ""            # Source standards library
    accrediting_body: str = ""                # e.g., "ACCSC"
    name: str = ""                            # e.g., "ACCSC Self-Evaluation 2024"
    status: FilledChecklistStatus = FilledChecklistStatus.NOT_STARTED
    responses: List[ChecklistResponse] = field(default_factory=list)
    total_items: int = 0
    items_completed: int = 0
    items_compliant: int = 0
    items_partial: int = 0
    items_non_compliant: int = 0
    items_needs_review: int = 0
    auto_fill_sources: Dict[str, Any] = field(default_factory=dict)  # {audit_ids, doc_ids}
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    completed_at: Optional[str] = None
    exported_path: str = ""                   # Path to exported DOCX/PDF

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "program_id": self.program_id,
            "standards_library_id": self.standards_library_id,
            "accrediting_body": self.accrediting_body,
            "name": self.name,
            "status": self.status.value,
            "responses": [r.to_dict() for r in self.responses],
            "total_items": self.total_items,
            "items_completed": self.items_completed,
            "items_compliant": self.items_compliant,
            "items_partial": self.items_partial,
            "items_non_compliant": self.items_non_compliant,
            "items_needs_review": self.items_needs_review,
            "auto_fill_sources": self.auto_fill_sources,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "exported_path": self.exported_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilledChecklist":
        return cls(
            id=data.get("id", generate_id("fcl")),
            institution_id=data.get("institution_id", ""),
            program_id=data.get("program_id", ""),
            standards_library_id=data.get("standards_library_id", ""),
            accrediting_body=data.get("accrediting_body", ""),
            name=data.get("name", ""),
            status=FilledChecklistStatus(data.get("status", "not_started")),
            responses=[ChecklistResponse.from_dict(r) for r in data.get("responses", [])],
            total_items=data.get("total_items", 0),
            items_completed=data.get("items_completed", 0),
            items_compliant=data.get("items_compliant", 0),
            items_partial=data.get("items_partial", 0),
            items_non_compliant=data.get("items_non_compliant", 0),
            items_needs_review=data.get("items_needs_review", 0),
            auto_fill_sources=data.get("auto_fill_sources", {}),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
            completed_at=data.get("completed_at"),
            exported_path=data.get("exported_path", ""),
        )

    def update_stats(self) -> None:
        """Recalculate statistics from responses."""
        self.total_items = len(self.responses)
        self.items_completed = sum(
            1 for r in self.responses
            if r.response_status in (ChecklistResponseStatus.AUTO_FILLED,
                                     ChecklistResponseStatus.HUMAN_EDITED,
                                     ChecklistResponseStatus.APPROVED)
        )
        self.items_compliant = sum(
            1 for r in self.responses if r.compliance_status == ComplianceStatus.COMPLIANT
        )
        self.items_partial = sum(
            1 for r in self.responses if r.compliance_status == ComplianceStatus.PARTIAL
        )
        self.items_non_compliant = sum(
            1 for r in self.responses if r.compliance_status == ComplianceStatus.NON_COMPLIANT
        )
        self.items_needs_review = sum(
            1 for r in self.responses if r.response_status == ChecklistResponseStatus.NEEDS_REVIEW
        )
        self.updated_at = now_iso()


# ===========================
# Submission Packet Models
# ===========================

class SubmissionType(str, Enum):
    """Types of accreditation submissions."""
    INITIAL_ACCREDITATION = "initial_accreditation"
    RENEWAL = "renewal"
    SUBSTANTIVE_CHANGE = "substantive_change"
    COMPLIANCE_REPORT = "compliance_report"
    RESPONSE_TO_FINDINGS = "response_to_findings"
    ANNUAL_REPORT = "annual_report"
    TEACH_OUT_PLAN = "teach_out_plan"
    OTHER = "other"


class PacketStatus(str, Enum):
    """Status of submission packet assembly."""
    DRAFT = "draft"
    ASSEMBLING = "assembling"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    READY = "ready"
    APPROVED = "approved"
    EXPORTED = "exported"
    SUBMITTED = "submitted"


class PacketSectionType(str, Enum):
    """Types of sections in a submission packet."""
    COVER_PAGE = "cover_page"
    TABLE_OF_CONTENTS = "table_of_contents"
    EXECUTIVE_SUMMARY = "executive_summary"
    NARRATIVE_RESPONSE = "narrative_response"
    CORRECTIVE_ACTION_PLAN = "corrective_action_plan"
    EVIDENCE_INDEX = "evidence_index"
    EXHIBIT_LIST = "exhibit_list"
    CROSSWALK = "crosswalk"
    SIGNATURE_PAGE = "signature_page"
    APPENDIX = "appendix"


@dataclass
class PacketSection:
    """A section within a submission packet."""
    id: str = field(default_factory=lambda: generate_id("psec"))
    section_type: PacketSectionType = PacketSectionType.NARRATIVE_RESPONSE
    title: str = ""
    order: int = 0
    content: str = ""
    finding_id: str = ""           # Link to finding being addressed
    standard_refs: List[str] = field(default_factory=list)  # Standards referenced
    evidence_refs: List[str] = field(default_factory=list)  # Evidence document IDs
    word_count: int = 0
    page_count: int = 0
    ai_generated: bool = False
    human_reviewed: bool = False
    approved: bool = False
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "section_type": self.section_type.value,
            "title": self.title,
            "order": self.order,
            "content": self.content,
            "finding_id": self.finding_id,
            "standard_refs": self.standard_refs,
            "evidence_refs": self.evidence_refs,
            "word_count": self.word_count,
            "page_count": self.page_count,
            "ai_generated": self.ai_generated,
            "human_reviewed": self.human_reviewed,
            "approved": self.approved,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PacketSection":
        return cls(
            id=data.get("id", generate_id("psec")),
            section_type=PacketSectionType(data.get("section_type", "narrative_response")),
            title=data.get("title", ""),
            order=data.get("order", 0),
            content=data.get("content", ""),
            finding_id=data.get("finding_id", ""),
            standard_refs=data.get("standard_refs", []),
            evidence_refs=data.get("evidence_refs", []),
            word_count=data.get("word_count", 0),
            page_count=data.get("page_count", 0),
            ai_generated=data.get("ai_generated", False),
            human_reviewed=data.get("human_reviewed", False),
            approved=data.get("approved", False),
            created_at=data.get("created_at", now_iso()),
        )


@dataclass
class ExhibitEntry:
    """An exhibit in the submission packet."""
    id: str = field(default_factory=lambda: generate_id("exh"))
    exhibit_number: str = ""       # e.g., "A-1", "B-3"
    title: str = ""
    description: str = ""
    document_id: str = ""          # Link to source document
    file_path: str = ""            # Path in workspace
    standard_refs: List[str] = field(default_factory=list)
    finding_refs: List[str] = field(default_factory=list)
    page_range: str = ""           # e.g., "1-5" or "all"
    file_type: str = ""            # pdf, docx, xlsx, etc.
    included: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "exhibit_number": self.exhibit_number,
            "title": self.title,
            "description": self.description,
            "document_id": self.document_id,
            "file_path": self.file_path,
            "standard_refs": self.standard_refs,
            "finding_refs": self.finding_refs,
            "page_range": self.page_range,
            "file_type": self.file_type,
            "included": self.included,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExhibitEntry":
        return cls(
            id=data.get("id", generate_id("exh")),
            exhibit_number=data.get("exhibit_number", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            document_id=data.get("document_id", ""),
            file_path=data.get("file_path", ""),
            standard_refs=data.get("standard_refs", []),
            finding_refs=data.get("finding_refs", []),
            page_range=data.get("page_range", ""),
            file_type=data.get("file_type", ""),
            included=data.get("included", True),
        )


@dataclass
class ValidationIssue:
    """An issue found during packet validation."""
    issue_type: str = ""           # missing_evidence, missing_standard, low_confidence, etc.
    severity: str = "warning"      # error, warning, info
    message: str = ""
    standard_ref: str = ""
    section_id: str = ""
    finding_id: str = ""
    can_override: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "standard_ref": self.standard_ref,
            "section_id": self.section_id,
            "finding_id": self.finding_id,
            "can_override": self.can_override,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationIssue":
        return cls(
            issue_type=data.get("issue_type", ""),
            severity=data.get("severity", "warning"),
            message=data.get("message", ""),
            standard_ref=data.get("standard_ref", ""),
            section_id=data.get("section_id", ""),
            finding_id=data.get("finding_id", ""),
            can_override=data.get("can_override", True),
        )


@dataclass
class SubmissionPacket:
    """A complete submission packet for accreditation.

    Contains all sections, exhibits, and metadata needed for
    a formal accreditation submission.
    """
    id: str = field(default_factory=lambda: generate_id("pkt"))
    institution_id: str = ""
    submission_type: SubmissionType = SubmissionType.RESPONSE_TO_FINDINGS
    accrediting_body: str = ""
    name: str = ""
    description: str = ""
    status: PacketStatus = PacketStatus.DRAFT
    version: int = 1

    # Sections and exhibits
    sections: List[PacketSection] = field(default_factory=list)
    exhibits: List[ExhibitEntry] = field(default_factory=list)

    # Source data links
    findings_report_id: str = ""
    audit_ids: List[str] = field(default_factory=list)
    checklist_id: str = ""

    # Validation
    validation_issues: List[ValidationIssue] = field(default_factory=list)
    is_valid: bool = False
    validated_at: Optional[str] = None

    # Statistics
    total_sections: int = 0
    sections_approved: int = 0
    total_exhibits: int = 0
    standards_covered: List[str] = field(default_factory=list)
    findings_addressed: int = 0

    # Export paths
    docx_path: str = ""
    pdf_path: str = ""
    zip_path: str = ""

    # Timestamps
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    approved_at: Optional[str] = None
    submitted_at: Optional[str] = None
    approved_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "submission_type": self.submission_type.value,
            "accrediting_body": self.accrediting_body,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "version": self.version,
            "sections": [s.to_dict() for s in self.sections],
            "exhibits": [e.to_dict() for e in self.exhibits],
            "findings_report_id": self.findings_report_id,
            "audit_ids": self.audit_ids,
            "checklist_id": self.checklist_id,
            "validation_issues": [v.to_dict() for v in self.validation_issues],
            "is_valid": self.is_valid,
            "validated_at": self.validated_at,
            "total_sections": self.total_sections,
            "sections_approved": self.sections_approved,
            "total_exhibits": self.total_exhibits,
            "standards_covered": self.standards_covered,
            "findings_addressed": self.findings_addressed,
            "docx_path": self.docx_path,
            "pdf_path": self.pdf_path,
            "zip_path": self.zip_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approved_at": self.approved_at,
            "submitted_at": self.submitted_at,
            "approved_by": self.approved_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubmissionPacket":
        return cls(
            id=data.get("id", generate_id("pkt")),
            institution_id=data.get("institution_id", ""),
            submission_type=SubmissionType(data.get("submission_type", "response_to_findings")),
            accrediting_body=data.get("accrediting_body", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=PacketStatus(data.get("status", "draft")),
            version=data.get("version", 1),
            sections=[PacketSection.from_dict(s) for s in data.get("sections", [])],
            exhibits=[ExhibitEntry.from_dict(e) for e in data.get("exhibits", [])],
            findings_report_id=data.get("findings_report_id", ""),
            audit_ids=data.get("audit_ids", []),
            checklist_id=data.get("checklist_id", ""),
            validation_issues=[ValidationIssue.from_dict(v) for v in data.get("validation_issues", [])],
            is_valid=data.get("is_valid", False),
            validated_at=data.get("validated_at"),
            total_sections=data.get("total_sections", 0),
            sections_approved=data.get("sections_approved", 0),
            total_exhibits=data.get("total_exhibits", 0),
            standards_covered=data.get("standards_covered", []),
            findings_addressed=data.get("findings_addressed", 0),
            docx_path=data.get("docx_path", ""),
            pdf_path=data.get("pdf_path", ""),
            zip_path=data.get("zip_path", ""),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
            approved_at=data.get("approved_at"),
            submitted_at=data.get("submitted_at"),
            approved_by=data.get("approved_by", ""),
        )

    def update_stats(self) -> None:
        """Recalculate packet statistics."""
        self.total_sections = len(self.sections)
        self.sections_approved = sum(1 for s in self.sections if s.approved)
        self.total_exhibits = len([e for e in self.exhibits if e.included])

        # Collect unique standards covered
        all_refs = set()
        for section in self.sections:
            all_refs.update(section.standard_refs)
        for exhibit in self.exhibits:
            all_refs.update(exhibit.standard_refs)
        self.standards_covered = list(all_refs)

        # Count addressed findings
        finding_ids = set()
        for section in self.sections:
            if section.finding_id:
                finding_ids.add(section.finding_id)
        self.findings_addressed = len(finding_ids)

        self.updated_at = now_iso()


# ===========================
# Action Plan Models
# ===========================

class ActionItemPriority(str, Enum):
    """Priority levels for action items."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionItemStatus(str, Enum):
    """Status of an action item."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ActionItem:
    """A single action item in a remediation plan."""
    id: str = field(default_factory=lambda: generate_id("act"))
    title: str = ""
    description: str = ""
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    status: ActionItemStatus = ActionItemStatus.NOT_STARTED

    # Links
    finding_id: str = ""
    standard_ref: str = ""
    document_id: str = ""

    # Assignment
    assigned_to: str = ""
    assigned_by: str = ""

    # Dates
    due_date: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Progress
    progress_notes: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "finding_id": self.finding_id,
            "standard_ref": self.standard_ref,
            "document_id": self.document_id,
            "assigned_to": self.assigned_to,
            "assigned_by": self.assigned_by,
            "due_date": self.due_date,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress_notes": self.progress_notes,
            "blockers": self.blockers,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionItem":
        return cls(
            id=data.get("id", generate_id("act")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=ActionItemPriority(data.get("priority", "medium")),
            status=ActionItemStatus(data.get("status", "not_started")),
            finding_id=data.get("finding_id", ""),
            standard_ref=data.get("standard_ref", ""),
            document_id=data.get("document_id", ""),
            assigned_to=data.get("assigned_to", ""),
            assigned_by=data.get("assigned_by", ""),
            due_date=data.get("due_date"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            progress_notes=data.get("progress_notes", []),
            blockers=data.get("blockers", []),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


@dataclass
class ActionPlan:
    """A complete action plan for remediation tracking."""
    id: str = field(default_factory=lambda: generate_id("plan"))
    institution_id: str = ""
    name: str = ""
    description: str = ""

    # Links
    findings_report_id: str = ""
    packet_id: str = ""

    # Items
    items: List[ActionItem] = field(default_factory=list)

    # Statistics
    total_items: int = 0
    items_completed: int = 0
    items_in_progress: int = 0
    items_blocked: int = 0
    items_overdue: int = 0

    # Dates
    target_completion_date: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "name": self.name,
            "description": self.description,
            "findings_report_id": self.findings_report_id,
            "packet_id": self.packet_id,
            "items": [i.to_dict() for i in self.items],
            "total_items": self.total_items,
            "items_completed": self.items_completed,
            "items_in_progress": self.items_in_progress,
            "items_blocked": self.items_blocked,
            "items_overdue": self.items_overdue,
            "target_completion_date": self.target_completion_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionPlan":
        return cls(
            id=data.get("id", generate_id("plan")),
            institution_id=data.get("institution_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            findings_report_id=data.get("findings_report_id", ""),
            packet_id=data.get("packet_id", ""),
            items=[ActionItem.from_dict(i) for i in data.get("items", [])],
            total_items=data.get("total_items", 0),
            items_completed=data.get("items_completed", 0),
            items_in_progress=data.get("items_in_progress", 0),
            items_blocked=data.get("items_blocked", 0),
            items_overdue=data.get("items_overdue", 0),
            target_completion_date=data.get("target_completion_date"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )

    def update_stats(self) -> None:
        """Recalculate statistics."""
        from datetime import datetime

        self.total_items = len(self.items)
        self.items_completed = sum(1 for i in self.items if i.status == ActionItemStatus.COMPLETED)
        self.items_in_progress = sum(1 for i in self.items if i.status == ActionItemStatus.IN_PROGRESS)
        self.items_blocked = sum(1 for i in self.items if i.status == ActionItemStatus.BLOCKED)

        # Count overdue items
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.items_overdue = sum(
            1 for i in self.items
            if i.due_date and i.due_date < today and i.status not in [ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED]
        )

        self.updated_at = now_iso()


# ===========================
# Phase 6: Faculty Domain Models
# ===========================

class EmploymentType(str, Enum):
    """Faculty employment types."""
    FULLTIME = "fulltime"
    PARTTIME = "parttime"
    ADJUNCT = "adjunct"


class CredentialType(str, Enum):
    """Types of academic/professional credentials."""
    DEGREE = "degree"
    LICENSE = "license"
    CERTIFICATION = "certification"
    INDUSTRY_EXPERIENCE = "industry_experience"


class FacultyComplianceStatus(str, Enum):
    """Faculty credential compliance status."""
    COMPLIANT = "compliant"
    PENDING_VERIFICATION = "pending_verification"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    NEEDS_REVIEW = "needs_review"
    NON_COMPLIANT = "non_compliant"


@dataclass
class AcademicCredential:
    """An academic degree or credential."""
    id: str = field(default_factory=lambda: generate_id("cred"))
    credential_type: CredentialType = CredentialType.DEGREE
    title: str = ""  # e.g., "Master of Science in Nursing"
    field_of_study: str = ""  # e.g., "Nursing"
    institution_name: str = ""
    year_awarded: Optional[int] = None
    transcript_on_file: bool = False
    transcript_path: Optional[str] = None
    verified: bool = False
    verified_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "credential_type": self.credential_type.value,
            "title": self.title,
            "field_of_study": self.field_of_study,
            "institution_name": self.institution_name,
            "year_awarded": self.year_awarded,
            "transcript_on_file": self.transcript_on_file,
            "transcript_path": self.transcript_path,
            "verified": self.verified,
            "verified_at": self.verified_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcademicCredential":
        return cls(
            id=data.get("id", generate_id("cred")),
            credential_type=CredentialType(data.get("credential_type", "degree")),
            title=data.get("title", ""),
            field_of_study=data.get("field_of_study", ""),
            institution_name=data.get("institution_name", ""),
            year_awarded=data.get("year_awarded"),
            transcript_on_file=data.get("transcript_on_file", False),
            transcript_path=data.get("transcript_path"),
            verified=data.get("verified", False),
            verified_at=data.get("verified_at"),
            notes=data.get("notes", ""),
        )


@dataclass
class ProfessionalLicense:
    """A professional license or certification."""
    id: str = field(default_factory=lambda: generate_id("lic"))
    license_type: str = ""  # e.g., "RN", "CPA", "PE"
    license_number: str = ""
    issuing_authority: str = ""  # e.g., "Puerto Rico Board of Nursing"
    state_code: str = ""  # e.g., "PR", "FL"
    issued_date: Optional[str] = None
    expiration_date: Optional[str] = None
    status: str = "active"  # active, expired, suspended, pending_renewal
    verification_url: Optional[str] = None
    last_verified_at: Optional[str] = None
    verification_method: str = ""  # "manual", "web_api", "web_scrape"
    document_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "license_type": self.license_type,
            "license_number": self.license_number,
            "issuing_authority": self.issuing_authority,
            "state_code": self.state_code,
            "issued_date": self.issued_date,
            "expiration_date": self.expiration_date,
            "status": self.status,
            "verification_url": self.verification_url,
            "last_verified_at": self.last_verified_at,
            "verification_method": self.verification_method,
            "document_path": self.document_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfessionalLicense":
        return cls(
            id=data.get("id", generate_id("lic")),
            license_type=data.get("license_type", ""),
            license_number=data.get("license_number", ""),
            issuing_authority=data.get("issuing_authority", ""),
            state_code=data.get("state_code", ""),
            issued_date=data.get("issued_date"),
            expiration_date=data.get("expiration_date"),
            status=data.get("status", "active"),
            verification_url=data.get("verification_url"),
            last_verified_at=data.get("last_verified_at"),
            verification_method=data.get("verification_method", ""),
            document_path=data.get("document_path"),
        )


@dataclass
class TeachingAssignment:
    """A teaching assignment for a faculty member."""
    id: str = field(default_factory=lambda: generate_id("assign"))
    program_id: str = ""
    course_code: str = ""
    course_name: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    required_credentials: List[str] = field(default_factory=list)
    qualification_basis: str = ""  # "degree", "license", "experience", "combination"
    is_qualified: bool = True
    qualification_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "program_id": self.program_id,
            "course_code": self.course_code,
            "course_name": self.course_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "required_credentials": self.required_credentials,
            "qualification_basis": self.qualification_basis,
            "is_qualified": self.is_qualified,
            "qualification_notes": self.qualification_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeachingAssignment":
        return cls(
            id=data.get("id", generate_id("assign")),
            program_id=data.get("program_id", ""),
            course_code=data.get("course_code", ""),
            course_name=data.get("course_name", ""),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            required_credentials=data.get("required_credentials", []),
            qualification_basis=data.get("qualification_basis", ""),
            is_qualified=data.get("is_qualified", True),
            qualification_notes=data.get("qualification_notes", ""),
        )


@dataclass
class FacultyMember:
    """A faculty or staff member with credentials."""
    id: str = field(default_factory=lambda: generate_id("fac"))
    institution_id: str = ""
    # Basic info
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    title: str = ""  # e.g., "Program Director", "Instructor"
    department: str = ""
    # Employment
    employment_type: EmploymentType = EmploymentType.FULLTIME
    employment_start_date: Optional[str] = None
    employment_end_date: Optional[str] = None
    is_active: bool = True
    # Credentials
    academic_credentials: List[AcademicCredential] = field(default_factory=list)
    professional_licenses: List[ProfessionalLicense] = field(default_factory=list)
    work_experience_years: int = 0
    work_experience_summary: str = ""
    foreign_credential_evaluation: Optional[Dict[str, Any]] = None
    # Teaching
    teaching_assignments: List[TeachingAssignment] = field(default_factory=list)
    # Professional development
    professional_development: List[Dict[str, Any]] = field(default_factory=list)
    # Compliance
    compliance_status: FacultyComplianceStatus = FacultyComplianceStatus.PENDING_VERIFICATION
    compliance_issues: List[str] = field(default_factory=list)
    last_compliance_check: Optional[str] = None
    # Metadata
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @property
    def full_name(self) -> str:
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "title": self.title,
            "department": self.department,
            "employment_type": self.employment_type.value,
            "employment_start_date": self.employment_start_date,
            "employment_end_date": self.employment_end_date,
            "is_active": self.is_active,
            "academic_credentials": [c.to_dict() for c in self.academic_credentials],
            "professional_licenses": [lic.to_dict() for lic in self.professional_licenses],
            "work_experience_years": self.work_experience_years,
            "work_experience_summary": self.work_experience_summary,
            "foreign_credential_evaluation": self.foreign_credential_evaluation,
            "teaching_assignments": [t.to_dict() for t in self.teaching_assignments],
            "professional_development": self.professional_development,
            "compliance_status": self.compliance_status.value,
            "compliance_issues": self.compliance_issues,
            "last_compliance_check": self.last_compliance_check,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FacultyMember":
        return cls(
            id=data.get("id", generate_id("fac")),
            institution_id=data.get("institution_id", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            title=data.get("title", ""),
            department=data.get("department", ""),
            employment_type=EmploymentType(data.get("employment_type", "fulltime")),
            employment_start_date=data.get("employment_start_date"),
            employment_end_date=data.get("employment_end_date"),
            is_active=data.get("is_active", True),
            academic_credentials=[
                AcademicCredential.from_dict(c)
                for c in data.get("academic_credentials", [])
            ],
            professional_licenses=[
                ProfessionalLicense.from_dict(lic)
                for lic in data.get("professional_licenses", [])
            ],
            work_experience_years=data.get("work_experience_years", 0),
            work_experience_summary=data.get("work_experience_summary", ""),
            foreign_credential_evaluation=data.get("foreign_credential_evaluation"),
            teaching_assignments=[
                TeachingAssignment.from_dict(t)
                for t in data.get("teaching_assignments", [])
            ],
            professional_development=data.get("professional_development", []),
            compliance_status=FacultyComplianceStatus(
                data.get("compliance_status", "pending_verification")
            ),
            compliance_issues=data.get("compliance_issues", []),
            last_compliance_check=data.get("last_compliance_check"),
            created_at=data.get("created_at", now_iso()),
            updated_at=data.get("updated_at", now_iso()),
        )


# ===========================
# Batch Operations
# ===========================

@dataclass
class BatchItem:
    """Individual item in a batch operation."""
    id: str = field(default_factory=lambda: generate_id("bitem"))
    batch_id: str = ""
    document_id: str = ""
    document_name: str = ""
    status: str = "pending"  # pending, running, completed, failed
    task_id: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    findings_count: int = 0
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "status": self.status,
            "task_id": self.task_id,
            "result_path": self.result_path,
            "error": self.error,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "duration_ms": self.duration_ms,
            "findings_count": self.findings_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchItem":
        return cls(
            id=data.get("id", generate_id("bitem")),
            batch_id=data.get("batch_id", ""),
            document_id=data.get("document_id", ""),
            document_name=data.get("document_name", ""),
            status=data.get("status", "pending"),
            task_id=data.get("task_id"),
            result_path=data.get("result_path"),
            error=data.get("error"),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            duration_ms=data.get("duration_ms", 0),
            findings_count=data.get("findings_count", 0),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class BatchOperation:
    """Batch operation for processing multiple documents."""
    id: str = field(default_factory=lambda: generate_id("batch"))
    institution_id: str = ""
    operation_type: str = ""  # audit or remediation
    document_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    concurrency: int = 3
    status: str = "pending"  # pending, running, completed, cancelled, failed
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    parent_batch_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    items: List[BatchItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "institution_id": self.institution_id,
            "operation_type": self.operation_type,
            "document_count": self.document_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "estimated_cost": self.estimated_cost,
            "actual_cost": self.actual_cost,
            "concurrency": self.concurrency,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "parent_batch_id": self.parent_batch_id,
            "metadata": self.metadata,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchOperation":
        return cls(
            id=data.get("id", generate_id("batch")),
            institution_id=data.get("institution_id", ""),
            operation_type=data.get("operation_type", ""),
            document_count=data.get("document_count", 0),
            completed_count=data.get("completed_count", 0),
            failed_count=data.get("failed_count", 0),
            estimated_cost=data.get("estimated_cost"),
            actual_cost=data.get("actual_cost"),
            concurrency=data.get("concurrency", 3),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", now_iso()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            parent_batch_id=data.get("parent_batch_id"),
            metadata=data.get("metadata", {}),
            items=[BatchItem.from_dict(item) for item in data.get("items", [])],
        )
