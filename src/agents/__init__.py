"""Agent framework for AccreditAI.

Provides the multi-agent orchestration system for accreditation workflows.
"""

from src.agents.base_agent import BaseAgent, AgentType
from src.agents.orchestrator_agent import OrchestratorAgent

__all__ = [
    "BaseAgent",
    "AgentType",
    "OrchestratorAgent",
]
