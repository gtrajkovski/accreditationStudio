"""Agent framework for AccreditAI.

Provides the multi-agent orchestration system for accreditation workflows.

Agent Layers:
- Orchestration: OrchestratorAgent
- Evidence/Standards: StandardsLibrarianAgent, EvidenceMapperAgent, CrosswalkBuilderAgent
- Document Intelligence: IngestionAgent, PolicyConsistencyAgent, TruthIndexCuratorAgent
- Compliance/Audit: ComplianceAuditAgent, RiskScorerAgent, SubstantiveChangeAgent
- Output Generation: RemediationAgent, NarrativeAgent, PacketAssemblerAgent
- Operational: CalendarDeadlineAgent, SiteVisitPrepAgent
"""

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.registry import AgentRegistry, register_agent

# Import all agents to trigger registration
from src.agents.orchestrator_agent import OrchestratorAgent
from src.agents.ingestion_agent import IngestionAgent
from src.agents.standards_librarian import StandardsLibrarianAgent
from src.agents.evidence_mapper import EvidenceMapperAgent
from src.agents.crosswalk_builder import CrosswalkBuilderAgent
from src.agents.policy_consistency import PolicyConsistencyAgent
from src.agents.truth_index_curator import TruthIndexCuratorAgent
from src.agents.compliance_audit import ComplianceAuditAgent
from src.agents.risk_scorer import RiskScorerAgent
from src.agents.substantive_change import SubstantiveChangeAgent
from src.agents.remediation_agent import RemediationAgent
from src.agents.narrative_agent import NarrativeAgent
from src.agents.packet_assembler import PacketAssemblerAgent
from src.agents.calendar_deadline import CalendarDeadlineAgent
from src.agents.site_visit_prep import SiteVisitPrepAgent

__all__ = [
    # Base
    "BaseAgent",
    "AgentType",
    "AgentRegistry",
    "register_agent",
    # Orchestration
    "OrchestratorAgent",
    # Evidence/Standards Layer
    "StandardsLibrarianAgent",
    "EvidenceMapperAgent",
    "CrosswalkBuilderAgent",
    # Document Intelligence Layer
    "IngestionAgent",
    "PolicyConsistencyAgent",
    "TruthIndexCuratorAgent",
    # Compliance/Audit Layer
    "ComplianceAuditAgent",
    "RiskScorerAgent",
    "SubstantiveChangeAgent",
    # Output Generation Layer
    "RemediationAgent",
    "NarrativeAgent",
    "PacketAssemblerAgent",
    # Operational Layer
    "CalendarDeadlineAgent",
    "SiteVisitPrepAgent",
]
