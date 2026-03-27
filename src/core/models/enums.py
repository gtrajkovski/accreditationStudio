"""Enum definitions for AccreditAI models."""

from enum import Enum


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


class CheckpointType(str, Enum):
    """Types of human checkpoints."""
    APPROVAL = "approval"
    REVIEW = "review"
    DECISION = "decision"
    FINALIZE_SUBMISSION = "finalize_submission"
    FORCED_EXPORT = "forced_export"


class SearchScope(str, Enum):
    """6 scope levels for contextual search."""
    GLOBAL = "global"
    INSTITUTION = "institution"
    PROGRAM = "program"
    DOCUMENT = "document"
    STANDARDS = "standards"
    COMPLIANCE = "compliance"


class RemediationStatus(str, Enum):
    """Status of a remediation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChecklistResponseStatus(str, Enum):
    """Status of a checklist response."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NEEDS_REVIEW = "needs_review"


class FilledChecklistStatus(str, Enum):
    """Status of a filled checklist."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    EXPORTED = "exported"


class SubmissionType(str, Enum):
    """Types of submission packets."""
    INITIAL_ACCREDITATION = "initial_accreditation"
    REACCREDITATION = "reaccreditation"
    SUBSTANTIVE_CHANGE = "substantive_change"
    COMPLIANCE_REPORT = "compliance_report"
    ANNUAL_REPORT = "annual_report"
    RESPONSE_TO_FINDINGS = "response_to_findings"


class PacketStatus(str, Enum):
    """Status of a submission packet."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    REJECTED = "rejected"


class PacketSectionType(str, Enum):
    """Types of sections in a submission packet."""
    NARRATIVE = "narrative"
    EXHIBIT = "exhibit"
    CROSSWALK = "crosswalk"
    SUPPORTING_DOCUMENT = "supporting_document"
    TABLE = "table"
    APPENDIX = "appendix"


class ActionItemPriority(str, Enum):
    """Priority levels for action items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EmploymentType(str, Enum):
    """Faculty employment types."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    ADJUNCT = "adjunct"


class CredentialType(str, Enum):
    """Types of academic credentials."""
    DEGREE = "degree"
    CERTIFICATE = "certificate"
    LICENSE = "license"
    CERTIFICATION = "certification"


class FacultyComplianceStatus(str, Enum):
    """Faculty compliance status."""
    COMPLIANT = "compliant"
    PENDING = "pending"
    NON_COMPLIANT = "non_compliant"
    EXPIRED = "expired"
