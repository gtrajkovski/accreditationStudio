"""Agent Registry for dynamic agent dispatch.

Provides a central registry for all agent types, enabling the orchestrator
to dispatch tasks to specialist agents by name.
"""

from typing import Dict, Type, Optional, TYPE_CHECKING
from src.agents.base_agent import BaseAgent, AgentType

if TYPE_CHECKING:
    from src.core.models import AgentSession


class AgentRegistry:
    """Central registry for agent types.

    Enables dynamic agent instantiation and dispatch by the orchestrator.
    """

    _agents: Dict[AgentType, Type[BaseAgent]] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, agent_type: AgentType, agent_class: Type[BaseAgent]) -> None:
        """Register an agent class for a given type.

        Args:
            agent_type: The type identifier for the agent.
            agent_class: The agent class to register.
        """
        cls._agents[agent_type] = agent_class

    @classmethod
    def get(cls, agent_type: AgentType) -> Optional[Type[BaseAgent]]:
        """Get an agent class by type.

        Args:
            agent_type: The type of agent to retrieve.

        Returns:
            The agent class or None if not registered.
        """
        cls._ensure_initialized()
        return cls._agents.get(agent_type)

    @classmethod
    def create(
        cls,
        agent_type: AgentType,
        session: "AgentSession",
        workspace_manager=None,
        on_update=None,
        **kwargs
    ) -> Optional[BaseAgent]:
        """Create an agent instance by type.

        Args:
            agent_type: The type of agent to create.
            session: The agent session.
            workspace_manager: WorkspaceManager instance.
            on_update: Callback for session updates.
            **kwargs: Additional agent-specific arguments.

        Returns:
            Agent instance or None if type not registered.
        """
        agent_class = cls.get(agent_type)
        if agent_class is None:
            return None
        return agent_class(
            session=session,
            workspace_manager=workspace_manager,
            on_update=on_update,
            **kwargs
        )

    @classmethod
    def list_agents(cls) -> Dict[AgentType, str]:
        """List all registered agents with their descriptions.

        Returns:
            Dict mapping agent types to their docstrings.
        """
        cls._ensure_initialized()
        return {
            agent_type: (agent_class.__doc__ or "No description").split('\n')[0]
            for agent_type, agent_class in cls._agents.items()
        }

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure all agents are registered."""
        if cls._initialized:
            return

        # Import all agents to trigger registration
        try:
            from src.agents import (
                # Tier 0 - Runtime & Governance
                orchestrator_agent,
                evidence_guardian,
                # Tier 1 - Document Intake
                ingestion_agent,
                # Tier 2 - Standards Management
                standards_librarian,
                # Tier 3 - Compliance Analysis
                compliance_audit,
                policy_consistency,
                risk_scorer,
                findings_agent,  # GAP_FINDER
                advertising_scanner_agent,
                # Tier 4 - Remediation & Authoring
                remediation_agent,
                truth_index_curator,
                substantive_change,
                # Tier 5 - Submission Preparation
                narrative_agent,
                crosswalk_builder,
                packet_agent,  # PACKET
                packet_assembler,
                site_visit_prep,
                # Tier 6 - Product Experience
                checklist_agent,  # WORKFLOW_COACH
                calendar_deadline,
                evidence_mapper,
                # Domain Agents
                faculty_agent,
                catalog_agent,
                evidence_agent,
                achievement_agent,
                # Visit Preparation
                interview_prep_agent,
                ser_drafting_agent,
                # Post-Visit & Ongoing
                team_report_agent,
                compliance_calendar_agent,
                document_review_agent,
                # Analytics
                knowledge_graph_agent,
            )
        except ImportError:
            # Agents may not all exist yet
            pass

        cls._initialized = True


def register_agent(agent_type: AgentType):
    """Decorator to register an agent class.

    Usage:
        @register_agent(AgentType.INGESTION)
        class IngestionAgent(BaseAgent):
            ...
    """
    def decorator(agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
        AgentRegistry.register(agent_type, agent_class)
        return agent_class
    return decorator
