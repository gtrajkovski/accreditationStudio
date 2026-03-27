"""Core domain models for AccreditAI.

This package contains all dataclasses and enums for the accreditation management system.
All models use to_dict() for serialization and from_dict() for deserialization
with unknown field filtering for schema evolution.

Re-exports all models from submodules for backward compatibility with:
    from src.core.models import Institution, Document, etc.
"""

# Helper functions
from src.core.models.helpers import generate_id, now_iso

# All enums
from src.core.models.enums import (
    AccreditingBody,
    DocumentType,
    Language,
    ComplianceStatus,
    FindingSeverity,
    RegulatorySource,
    AuditStatus,
    ExhibitStatus,
    ActionItemStatus,
    BatchStatus,
    CredentialLevel,
    Modality,
    CalendarEventType,
    ReadinessLevel,
    SessionStatus,
    TaskPriority,
    CheckpointType,
    SearchScope,
    RemediationStatus,
    ChecklistResponseStatus,
    FilledChecklistStatus,
    SubmissionType,
    PacketStatus,
    PacketSectionType,
    ActionItemPriority,
    EmploymentType,
    CredentialType,
    FacultyComplianceStatus,
)

# Institution and Program models
from src.core.models.institution import Program, Institution

# Document models
from src.core.models.document import Document, DocumentChunk, ChunkedDocument

# Audit models
from src.core.models.audit import AuditFinding, Audit

# Agent system models
from src.core.models.agent import (
    ToolCall,
    HumanCheckpoint,
    AgentTask,
    AgentSession,
    ChatMessage,
    AgentResult,
)

# Standards and regulatory models
from src.core.models.standards import (
    ChecklistItem,
    StandardsSection,
    StandardsLibrary,
    CrosswalkEntry,
    EvidenceMapping,
    EvidenceMap,
    EvidenceGap,
    RegulatoryStack,
)

# Remediation models
from src.core.models.remediation import (
    RemediationStatus as RemediationStatusEnum,  # Alias to avoid conflict with enums.py
    RemediationChange,
    RemediationResult,
)

# Checklist models
from src.core.models.checklist import (
    ChecklistResponseStatus as ChecklistResponseStatusEnum,  # Alias to avoid conflict
    FilledChecklistStatus as FilledChecklistStatusEnum,  # Alias to avoid conflict
    ChecklistResponse,
    FilledChecklist,
)

# Packet models
from src.core.models.packet import (
    SubmissionType as SubmissionTypeEnum,  # Alias to avoid conflict
    PacketStatus as PacketStatusEnum,  # Alias to avoid conflict
    PacketSectionType as PacketSectionTypeEnum,  # Alias to avoid conflict
    PacketSection,
    ExhibitEntry,
    ValidationIssue,
    SubmissionPacket,
)

# Action plan models
from src.core.models.action_plan import (
    ActionItemPriority as ActionItemPriorityEnum,  # Alias to avoid conflict
    ActionItemStatus as ActionItemStatusEnum,  # Alias to avoid conflict
    ActionItem,
    ActionPlan,
)

# Faculty models
from src.core.models.faculty import (
    EmploymentType as EmploymentTypeEnum,  # Alias to avoid conflict
    CredentialType as CredentialTypeEnum,  # Alias to avoid conflict
    FacultyComplianceStatus as FacultyComplianceStatusEnum,  # Alias to avoid conflict
    AcademicCredential,
    ProfessionalLicense,
    TeachingAssignment,
    FacultyMember,
)

# Batch operation models
from src.core.models.batch import BatchItem, BatchOperation

# Search models
from src.core.models.search import SearchContext

# Export all names for backward compatibility
__all__ = [
    # Helpers
    "generate_id",
    "now_iso",
    # Enums from enums.py
    "AccreditingBody",
    "DocumentType",
    "Language",
    "ComplianceStatus",
    "FindingSeverity",
    "RegulatorySource",
    "AuditStatus",
    "ExhibitStatus",
    "ActionItemStatus",
    "BatchStatus",
    "CredentialLevel",
    "Modality",
    "CalendarEventType",
    "ReadinessLevel",
    "SessionStatus",
    "TaskPriority",
    "CheckpointType",
    "SearchScope",
    "RemediationStatus",
    "ChecklistResponseStatus",
    "FilledChecklistStatus",
    "SubmissionType",
    "PacketStatus",
    "PacketSectionType",
    "ActionItemPriority",
    "EmploymentType",
    "CredentialType",
    "FacultyComplianceStatus",
    # Institution models
    "Program",
    "Institution",
    # Document models
    "Document",
    "DocumentChunk",
    "ChunkedDocument",
    # Audit models
    "AuditFinding",
    "Audit",
    # Agent models
    "ToolCall",
    "HumanCheckpoint",
    "AgentTask",
    "AgentSession",
    "ChatMessage",
    "AgentResult",
    # Standards models
    "ChecklistItem",
    "StandardsSection",
    "StandardsLibrary",
    "CrosswalkEntry",
    "EvidenceMapping",
    "EvidenceMap",
    "EvidenceGap",
    "RegulatoryStack",
    # Remediation models
    "RemediationChange",
    "RemediationResult",
    # Checklist models
    "ChecklistResponse",
    "FilledChecklist",
    # Packet models
    "PacketSection",
    "ExhibitEntry",
    "ValidationIssue",
    "SubmissionPacket",
    # Action plan models
    "ActionItem",
    "ActionPlan",
    # Faculty models
    "AcademicCredential",
    "ProfessionalLicense",
    "TeachingAssignment",
    "FacultyMember",
    # Batch models
    "BatchItem",
    "BatchOperation",
    # Search models
    "SearchContext",
]
